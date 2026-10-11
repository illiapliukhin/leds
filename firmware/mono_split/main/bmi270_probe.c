#include "bmi270_probe.h"

#include "board_pins.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

static const char *TAG = "bmi270";
static i2c_master_bus_handle_t s_i2c_bus;

esp_err_t bmi270_probe_init(void)
{
    i2c_master_bus_config_t bus_config = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = BOARD_PIN_GPIO_IMU_SDA,
        .scl_io_num = BOARD_PIN_GPIO_IMU_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };

    esp_err_t err = i2c_new_master_bus(&bus_config, &s_i2c_bus);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2C bus init failed: %s", esp_err_to_name(err));
    }
    return err;
}


#ifdef MONO_SIM
/* Sim-only I2C mock (QEMU has no BMI270/MAX17048): answers like a populated board.
 * BMI270 @0x68 CHIP_ID(0x00)=0x24, MAX17048 @0x36 VERSION(0x08)=0x0012, VCELL(0x02)=3.80 V, SOC(0x04)=76 %. */
static bool sim_present(uint8_t a) { return a == 0x68 || a == 0x36; }
static esp_err_t sim_read(uint8_t a, uint8_t reg, uint8_t *v, int n)
{
    if (!sim_present(a)) return ESP_ERR_TIMEOUT;
    uint16_t w = 0;
    if (a == 0x68) w = reg == 0x00 ? 0x24 : 0;
    if (a == 0x36) w = reg == 0x08 ? 0x0012 : reg == 0x02 ? (uint16_t)(3800000 / 78) : reg == 0x04 ? 0x4C00 : 0;
    if (n == 1) v[0] = (uint8_t)w; else { v[0] = w >> 8; v[1] = w & 0xFF; }
    return ESP_OK;
}
#endif

static esp_err_t read_reg(uint8_t device_addr, uint8_t reg, uint8_t *value)
{
#ifdef MONO_SIM
    return sim_read(device_addr, reg, value, 1);
#endif
    i2c_device_config_t device_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = device_addr,
        .scl_speed_hz = 400000,
    };

    i2c_master_dev_handle_t device;
    esp_err_t err = i2c_master_bus_add_device(s_i2c_bus, &device_config, &device);
    if (err != ESP_OK) {
        return err;
    }

    err = i2c_master_transmit_receive(device, &reg, 1, value, 1, 100);
    i2c_master_bus_rm_device(device);
    return err;
}

esp_err_t bmi270_read_chip_id(uint8_t *chip_id)
{
    if (chip_id == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t err = read_reg(BMI270_I2C_ADDR_PRIMARY, BMI270_REG_CHIP_ID, chip_id);
    if (err != ESP_OK) {
        err = read_reg(BMI270_I2C_ADDR_SECONDARY, BMI270_REG_CHIP_ID, chip_id);
    }
    return err;
}

esp_err_t bmi270_i2c_bus_scan(void)
{
    ESP_LOGI(TAG, "I2C scan (SDA=%d SCL=%d):", BOARD_PIN_GPIO_IMU_SDA, BOARD_PIN_GPIO_IMU_SCL);
    int found = 0;
    for (uint8_t address = 0x08; address < 0x78; address++) {
#ifdef MONO_SIM
        if (sim_present(address)) {
#else
        if (i2c_master_probe(s_i2c_bus, address, 50) == ESP_OK) {
#endif
            ESP_LOGI(TAG, "  0x%02X", address);
            found++;
        }
    }
    ESP_LOGI(TAG, "Scan complete: %d device(s)%s", found,
#ifdef MONO_SIM
             " [sim-mock: BMI270+MAX17048 present]"
#else
             ""
#endif
    );
    return ESP_OK;
}

esp_err_t bmi270_read_reg16(uint8_t device_addr, uint8_t reg, uint8_t value[2])
{
#ifdef MONO_SIM
    return sim_read(device_addr, reg, value, 2);
#endif
    i2c_device_config_t device_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = device_addr,
        .scl_speed_hz = 400000,
    };
    i2c_master_dev_handle_t device;
    esp_err_t err = i2c_master_bus_add_device(s_i2c_bus, &device_config, &device);
    if (err != ESP_OK) {
        return err;
    }
    err = i2c_master_transmit_receive(device, &reg, 1, value, 2, 100);
    i2c_master_bus_rm_device(device);
    return err;
}
