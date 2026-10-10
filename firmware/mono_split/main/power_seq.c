#include "power_seq.h"

#include "board_pins.h"
#include "driver/gpio.h"
#include "soc/gpio_reg.h"
#include "soc/soc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "power_seq";

static void drive_safe_matrix_idle(void)
{
    gpio_set_level(BOARD_PIN_GPIO_LED_OE_N, 1);
    gpio_set_level(BOARD_PIN_GPIO_LED_CLK, 0);
    gpio_set_level(BOARD_PIN_GPIO_LED_SDI, 0);
    gpio_set_level(BOARD_PIN_GPIO_LED_LE, 0);

    gpio_set_level(BOARD_PIN_GPIO_ROW_A0, 0);
    gpio_set_level(BOARD_PIN_GPIO_ROW_A1, 0);
    gpio_set_level(BOARD_PIN_GPIO_ROW_A2, 0);
    gpio_set_level(BOARD_PIN_GPIO_ROW_A3, 0);
    gpio_set_level(BOARD_PIN_GPIO_DEC_A_EN_N, 1);
    gpio_set_level(BOARD_PIN_GPIO_DEC_B_EN_N, 1);
}

esp_err_t power_seq_init(void)
{
    /* Safe idle level per output. The level is written BEFORE the driver is enabled and no
     * internal pull is used: gpio_reset_pin() would enable the ~45 k internal pull-up, which
     * against the 100 k external pull-downs lifts LED_EN / LED_LOGIC_EN / AUDIO_EN to ~2.3 V
     * for a few microseconds. */
    const struct { gpio_num_t pin; int level; } outputs[] = {
        {BOARD_PIN_GPIO_LED_EN, 0},
        {BOARD_PIN_GPIO_LED_LOGIC_EN, 0},
        {BOARD_PIN_GPIO_ROW_XLAT_OE_N, 1},
        {BOARD_PIN_GPIO_LED_CLK, 0},
        {BOARD_PIN_GPIO_LED_SDI, 0},
        {BOARD_PIN_GPIO_LED_LE, 0},
        {BOARD_PIN_GPIO_LED_OE_N, 1},
        {BOARD_PIN_GPIO_ROW_A0, 0},
        {BOARD_PIN_GPIO_ROW_A1, 0},
        {BOARD_PIN_GPIO_ROW_A2, 0},
        {BOARD_PIN_GPIO_ROW_A3, 0},
        {BOARD_PIN_GPIO_DEC_A_EN_N, 1},
        {BOARD_PIN_GPIO_DEC_B_EN_N, 1},
        {BOARD_PIN_GPIO_AUDIO_EN, 0},
    };

    for (size_t index = 0; index < sizeof(outputs) / sizeof(outputs[0]); index++) {
#if CONFIG_ESP_CONSOLE_UART
        if (outputs[index].pin == BOARD_PIN_GPIO_ROW_XLAT_OE_N) {
            ESP_LOGW(TAG, "UART console build: GPIO44 (ROW_XLAT_OE_N) left as U0RXD - sim/bench only");
            continue;
        }
#endif
        gpio_set_level(outputs[index].pin, outputs[index].level);
        const gpio_config_t config = {
            .pin_bit_mask = 1ULL << outputs[index].pin,
            .mode = GPIO_MODE_INPUT_OUTPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&config);
    }

    gpio_set_level(BOARD_PIN_GPIO_LED_EN, 0);
    gpio_set_level(BOARD_PIN_GPIO_LED_LOGIC_EN, 0);
    gpio_set_level(BOARD_PIN_GPIO_ROW_XLAT_OE_N, 1);

    /* Stacking ports: everything an input with internal pull-down while the
     * RS-485 transceiver (on LED_LOGIC_3V3) is unpowered, so D is never back-powered. */
    const gpio_num_t port_inputs[] = {
        BOARD_PIN_GPIO_RS485_TX, BOARD_PIN_GPIO_RS485_RX, BOARD_PIN_GPIO_FRAME_SYNC,
        BOARD_PIN_GPIO_PRES_N, BOARD_PIN_GPIO_PRES_E, BOARD_PIN_GPIO_PRES_S, BOARD_PIN_GPIO_PRES_W,
    };
    for (size_t index = 0; index < sizeof(port_inputs) / sizeof(port_inputs[0]); index++) {
        const gpio_config_t config = {
            .pin_bit_mask = 1ULL << port_inputs[index],
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_ENABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&config);
    }
    ESP_LOGI(TAG, "step 1: LED_EN=0 LED_LOGIC_EN=0 XLAT_OE_N=1 AUDIO_EN=0 OE_N=1 DEC_EN_N=1; ports input+PD");
    gpio_set_level(BOARD_PIN_GPIO_AUDIO_EN, 0);
    drive_safe_matrix_idle();

    ESP_LOGI(TAG, "AON assumed up (TPS7A2033); rails off, matrix blanked");
    return ESP_OK;
}

void power_seq_log_gpio_states(const char *when)
{
    const int pins[] = {0, 3, 45, 46, BOARD_PIN_GPIO_LED_EN, BOARD_PIN_GPIO_LED_LOGIC_EN, BOARD_PIN_GPIO_ROW_XLAT_OE_N,
        BOARD_PIN_GPIO_LED_OE_N, BOARD_PIN_GPIO_DEC_A_EN_N, BOARD_PIN_GPIO_DEC_B_EN_N, BOARD_PIN_GPIO_AUDIO_EN,
        BOARD_PIN_GPIO_RS485_TX, BOARD_PIN_GPIO_FRAME_SYNC};
    const char *names[] = {"GPIO0_BOOT", "PRES_N(strap3)", "GPIO45(strap)", "GPIO46(strap)", "LED_EN", "LED_LOGIC_EN",
        "ROW_XLAT_OE_N", "LED_OE_N", "DEC_A_EN_N", "DEC_B_EN_N", "AUDIO_EN", "RS485_TX", "FRAME_SYNC"};
    for (size_t i = 0; i < sizeof(pins) / sizeof(pins[0]); i++) {
        uint32_t out_en, out;
        if (pins[i] < 32) {
            out_en = (REG_READ(GPIO_ENABLE_REG) >> pins[i]) & 1;
            out = (REG_READ(GPIO_OUT_REG) >> pins[i]) & 1;
        } else {
            out_en = (REG_READ(GPIO_ENABLE1_REG) >> (pins[i] - 32)) & 1;
            out = (REG_READ(GPIO_OUT1_REG) >> (pins[i] - 32)) & 1;
        }
        ESP_LOGI(TAG, "[%s] GPIO%-2d %-15s %s%s  pad=%d", when, pins[i], names[i], out_en ? "OUT=" : "input/hi-Z",
            out_en ? (out ? "1" : "0") : "", gpio_get_level(pins[i]));
    }
}

esp_err_t power_seq_matrix_enable(void)
{
    drive_safe_matrix_idle();

    int64_t t0 = esp_timer_get_time();
    gpio_set_level(BOARD_PIN_GPIO_LED_LOGIC_EN, BOARD_ACTIVE_LED_LOGIC_EN);
    ESP_LOGI(TAG, "seq t=+%lld us: LED_LOGIC_EN(GPIO%d)=1", (long long)(esp_timer_get_time() - t0), BOARD_PIN_GPIO_LED_LOGIC_EN);
    vTaskDelay(pdMS_TO_TICKS(5));

    gpio_set_level(BOARD_PIN_GPIO_LED_EN, BOARD_ACTIVE_LED_EN);
    ESP_LOGI(TAG, "seq t=+%lld us: LED_EN(GPIO%d)=1", (long long)(esp_timer_get_time() - t0), BOARD_PIN_GPIO_LED_EN);
    vTaskDelay(pdMS_TO_TICKS(10));

    gpio_set_level(BOARD_PIN_GPIO_ROW_XLAT_OE_N, BOARD_ACTIVE_ROW_XLAT_OE_N);
    ESP_LOGI(TAG, "seq t=+%lld us: ROW_XLAT_OE_N(GPIO%d)=0", (long long)(esp_timer_get_time() - t0), BOARD_PIN_GPIO_ROW_XLAT_OE_N);
    vTaskDelay(pdMS_TO_TICKS(1));

    ESP_LOGI(TAG, "LED_LOGIC_3V3 and LED_4V1 enabled, row translator active");
    return ESP_OK;
}

esp_err_t power_seq_matrix_disable(void)
{
    drive_safe_matrix_idle();
    gpio_set_level(BOARD_PIN_GPIO_ROW_XLAT_OE_N, 1);
    gpio_set_level(BOARD_PIN_GPIO_LED_EN, 0);
    vTaskDelay(pdMS_TO_TICKS(2));
    gpio_set_level(BOARD_PIN_GPIO_LED_LOGIC_EN, 0);
    ESP_LOGI(TAG, "Matrix powered down");
    return ESP_OK;
}
