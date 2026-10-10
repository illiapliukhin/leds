#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BMI270_I2C_ADDR_PRIMARY 0x68
#define BMI270_I2C_ADDR_SECONDARY 0x69
#define BMI270_REG_CHIP_ID 0x00
#define BMI270_CHIP_ID_VALUE 0x24

esp_err_t bmi270_probe_init(void);
esp_err_t bmi270_read_chip_id(uint8_t *chip_id);
esp_err_t bmi270_i2c_bus_scan(void);

#ifdef __cplusplus
}
#endif
