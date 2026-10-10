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
    const gpio_num_t outputs[] = {
        BOARD_PIN_GPIO_LED_EN,
        BOARD_PIN_GPIO_LED_LOGIC_EN,
        BOARD_PIN_GPIO_ROW_XLAT_OE_N,
        BOARD_PIN_GPIO_LED_CLK,
        BOARD_PIN_GPIO_LED_SDI,
        BOARD_PIN_GPIO_LED_LE,
        BOARD_PIN_GPIO_LED_OE_N,
        BOARD_PIN_GPIO_ROW_A0,
        BOARD_PIN_GPIO_ROW_A1,
        BOARD_PIN_GPIO_ROW_A2,
        BOARD_PIN_GPIO_ROW_A3,
        BOARD_PIN_GPIO_DEC_A_EN_N,
        BOARD_PIN_GPIO_DEC_B_EN_N,
        BOARD_PIN_GPIO_AUDIO_EN,
    };

    for (size_t index = 0; index < sizeof(outputs) / sizeof(outputs[0]); index++) {
        gpio_reset_pin(outputs[index]);
        gpio_set_direction(outputs[index], GPIO_MODE_OUTPUT);
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
        gpio_reset_pin(port_inputs[index]);
        gpio_set_direction(port_inputs[index], GPIO_MODE_INPUT);
        gpio_set_pull_mode(port_inputs[index], GPIO_PULLDOWN_ONLY);
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
        ESP_LOGI(TAG, "[%s] GPIO%-2d %-15s %s%s", when, pins[i], names[i], out_en ? "OUT=" : "input/hi-Z",
            out_en ? (out ? "1" : "0") : "");
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
