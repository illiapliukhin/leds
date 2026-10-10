#include "mbi5124_driver.h"

#include "board_pins.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"

static const char *TAG = "mbi5124";
static spi_device_handle_t s_spi_device;

esp_err_t mbi5124_driver_init(void)
{
    spi_bus_config_t bus_config = {
        .mosi_io_num = BOARD_PIN_GPIO_LED_SDI,
        .miso_io_num = -1,
        .sclk_io_num = BOARD_PIN_GPIO_LED_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4,
    };

    esp_err_t err = spi_bus_initialize(SPI2_HOST, &bus_config, SPI_DMA_DISABLED);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }

    spi_device_interface_config_t device_config = {
        .clock_speed_hz = MBI5124_SHIFT_CLOCK_HZ,
        .mode = 0,
        .spics_io_num = -1,
        .queue_size = 1,
        .flags = SPI_DEVICE_NO_DUMMY,
    };

    err = spi_bus_add_device(SPI2_HOST, &device_config, &s_spi_device);
    if (err != ESP_OK) {
        return err;
    }

    gpio_set_direction(BOARD_PIN_GPIO_LED_LE, GPIO_MODE_OUTPUT);
    gpio_set_direction(BOARD_PIN_GPIO_LED_OE_N, GPIO_MODE_OUTPUT);
    gpio_set_level(BOARD_PIN_GPIO_LED_LE, 0);
    mbi5124_set_blank(true);

    ESP_LOGI(TAG, "SPI shift @ %d Hz, LE/OE on GPIO", MBI5124_SHIFT_CLOCK_HZ);
    return ESP_OK;
}

void mbi5124_shift_columns(const uint32_t column_bits)
{
    uint8_t bytes[4] = {
        (uint8_t)((column_bits >> 24) & 0xFF),
        (uint8_t)((column_bits >> 16) & 0xFF),
        (uint8_t)((column_bits >> 8) & 0xFF),
        (uint8_t)(column_bits & 0xFF),
    };

    spi_transaction_t transaction = {
        .length = 32,
        .tx_buffer = bytes,
    };
    spi_device_polling_transmit(s_spi_device, &transaction);
}

void mbi5124_latch(void)
{
    gpio_set_level(BOARD_PIN_GPIO_LED_LE, 1);
    esp_rom_delay_us(1);
    gpio_set_level(BOARD_PIN_GPIO_LED_LE, 0);
}

void mbi5124_set_blank(bool blanked)
{
    gpio_set_level(BOARD_PIN_GPIO_LED_OE_N, blanked ? 1 : 0);
}
