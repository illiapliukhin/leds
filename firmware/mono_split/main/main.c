#include <stdio.h>

#include "bmi270_probe.h"
#include "console_test.h"
#include "esp_console.h"
#include "esp_log.h"
#include "matrix_panel.h"
#include "matrix_refresh.h"
#include "mbi5124_driver.h"
#include "nvs_flash.h"
#include "power_seq.h"
#include "board_pins.h"

static const char *TAG = "mono_split";

static matrix_panel_t s_panel;

static void register_builtin_console(matrix_panel_t *panel)
{
    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t repl_config = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    repl_config.prompt = "mono> ";

#if CONFIG_ESP_CONSOLE_UART
    /* QEMU / bench build only (sdkconfig.qemu): UART0 console. On the real board GPIO44 is ROW_XLAT_OE_N. */
    esp_console_dev_uart_config_t hw_config = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_console_new_repl_uart(&hw_config, &repl_config, &repl));
#else
    esp_console_dev_usb_serial_jtag_config_t hw_config =
        ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_console_new_repl_usb_serial_jtag(&hw_config, &repl_config, &repl));
#endif
    ESP_ERROR_CHECK(esp_console_register_help_command());
    ESP_ERROR_CHECK(console_test_register(panel));
    ESP_ERROR_CHECK(esp_console_start_repl(repl));
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    ESP_LOGI(TAG, "Mono split LED bring-up (ESP32-S3FN8)");
    power_seq_log_gpio_states("reset");
    ESP_ERROR_CHECK(power_seq_init());
    power_seq_log_gpio_states("after init");
    ESP_ERROR_CHECK(mbi5124_driver_init());
    ESP_ERROR_CHECK(bmi270_probe_init());

    uint8_t chip_id = 0;
    err = bmi270_read_chip_id(&chip_id);
    if (err == ESP_OK) {
        ESP_LOGI(
            TAG,
            "BMI270 chip_id=0x%02X (expected 0x%02X)",
            chip_id,
            BMI270_CHIP_ID_VALUE);
    } else {
        ESP_LOGW(TAG, "BMI270 not detected: %s", esp_err_to_name(err));
    }
    uint8_t gauge_version[2] = {0};
    err = bmi270_read_reg16(BOARD_I2C_ADDR_MAX17048, 0x08, gauge_version);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "MAX17048 VERSION=0x%02X%02X", gauge_version[0], gauge_version[1]);
    } else {
        ESP_LOGW(TAG, "MAX17048 not detected at 0x%02X: %s", BOARD_I2C_ADDR_MAX17048, esp_err_to_name(err));
    }
    bmi270_i2c_bus_scan();

    matrix_panel_init(&s_panel, MATRIX_PANEL_20X20);
    ESP_ERROR_CHECK(power_seq_matrix_enable());
    ESP_ERROR_CHECK(matrix_refresh_start(&s_panel));

    /* esp_console_new_repl_*() calls esp_console_init() itself; calling it first made the
     * REPL creation fail with ESP_ERR_INVALID_STATE -> abort -> boot loop (found in QEMU). */
    register_builtin_console(&s_panel);

    ESP_LOGI(
        TAG,
        "Ready. Target refresh %d Hz, row rate %d Hz",
        MATRIX_TARGET_REFRESH_HZ,
        MATRIX_TARGET_REFRESH_HZ * 32);
}
