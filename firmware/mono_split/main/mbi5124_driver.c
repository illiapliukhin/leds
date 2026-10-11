#include "mbi5124_driver.h"

#include "board_pins.h"
#include "driver/gpio.h"
#include "esp_log.h"

/* v13: the shift/latch/OE stream is produced by the LCD_CAM scan engine (matrix_refresh.c).
 * This driver only parks the pins in a safe GPIO state while the engine is not running. */
static const char *TAG = "mbi5124";

esp_err_t mbi5124_driver_init(void)
{
    const gpio_num_t outs[] = {BOARD_PIN_GPIO_LED_CLK, BOARD_PIN_GPIO_LED_SDI, BOARD_PIN_GPIO_LED_LE, BOARD_PIN_GPIO_LED_OE_N};
    const int lvl[] = {0, 0, 0, 1};
    for (int i = 0; i < 4; i++) {
        gpio_set_level(outs[i], lvl[i]);
        gpio_config_t c = {.pin_bit_mask = 1ULL << outs[i], .mode = GPIO_MODE_OUTPUT};
        gpio_config(&c);
        gpio_set_level(outs[i], lvl[i]);
    }
    ESP_LOGI(TAG, "pins parked: CLK/SDI/LE low, OE_N high (scan engine owns them while running)");
    return ESP_OK;
}

void mbi5124_set_blank(bool blanked)
{
    gpio_set_level(BOARD_PIN_GPIO_LED_OE_N, blanked ? 1 : 0);
}
