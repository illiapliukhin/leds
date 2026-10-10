#include "power_seq.h"

#include "board_pins.h"
#include "driver/gpio.h"
#include "esp_log.h"
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
    gpio_set_level(BOARD_PIN_GPIO_AUDIO_EN, 0);
    drive_safe_matrix_idle();

    ESP_LOGI(TAG, "AON assumed up (TPS7A2033); rails off, matrix blanked");
    return ESP_OK;
}

esp_err_t power_seq_matrix_enable(void)
{
    drive_safe_matrix_idle();

    gpio_set_level(BOARD_PIN_GPIO_LED_LOGIC_EN, BOARD_ACTIVE_LED_LOGIC_EN);
    vTaskDelay(pdMS_TO_TICKS(5));

    gpio_set_level(BOARD_PIN_GPIO_LED_EN, BOARD_ACTIVE_LED_EN);
    vTaskDelay(pdMS_TO_TICKS(10));

    gpio_set_level(BOARD_PIN_GPIO_ROW_XLAT_OE_N, BOARD_ACTIVE_ROW_XLAT_OE_N);
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
