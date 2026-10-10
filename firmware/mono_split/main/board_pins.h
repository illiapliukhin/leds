#pragma once

/**
 * Single source of GPIO assignments for mono_electronics (ESP32-S3FN8).
 * Keep in sync with hardware/common/MONO_SPLIT_ARCHITECTURE.md § ESP32-S3FN8 GPIO map (EVT).
 * Run: python3 firmware/mono_split/tools/check_pins.py
 */

#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int gpio;
    int qfn_pad;
    const char *net;
    const char *role;
} board_pin_entry_t;

#define BOARD_PIN_TABLE(X) \
    X(0, 5, "GPIO0_BOOT", "Boot strap + SW1") \
    X(8, 13, "IMU_SDA", "BMI270 I2C data") \
    X(9, 14, "IMU_SCL", "BMI270 I2C clock") \
    X(10, 15, "IMU_INT1", "BMI270 interrupt") \
    X(13, 18, "LED_CLK", "MBI5124 shift clock") \
    X(14, 19, "LED_SDI", "MBI5124 serial data in") \
    X(15, 21, "LED_LE", "MBI5124 latch enable") \
    X(16, 22, "LED_OE_N", "MBI5124 output enable (active low)") \
    X(6, 11, "AUDIO_EN", "Audio domain switch enable") \
    X(33, 38, "ROW_A3", "Row address bit 3") \
    X(38, 43, "ROW_A2", "Row address bit 2") \
    X(39, 44, "ROW_A0", "Row address bit 0") \
    X(40, 45, "ROW_A1", "Row address bit 1") \
    X(41, 47, "DEC_A_EN_N", "74HC154 A enable (active low)") \
    X(42, 48, "DEC_B_EN_N", "74HC154 B enable (active low)") \
    X(18, 24, "LED_EN", "TPS63802 enable") \
    X(21, 27, "LED_LOGIC_EN", "LED logic rail switch") \
    X(19, 25, "USB_D_N_MCU", "Native USB D-") \
    X(20, 26, "USB_D_P_MCU", "Native USB D+") \
    X(47, 37, "ROW_XLAT_OE_N", "SN74LVC8T245 /OE (active low)")

#define BOARD_PIN_GPIO_IMU_SDA 8
#define BOARD_PIN_GPIO_IMU_SCL 9
#define BOARD_PIN_GPIO_IMU_INT1 10

#define BOARD_PIN_GPIO_LED_CLK 13
#define BOARD_PIN_GPIO_LED_SDI 14
#define BOARD_PIN_GPIO_LED_LE 15
#define BOARD_PIN_GPIO_LED_OE_N 16

#define BOARD_PIN_GPIO_AUDIO_EN 6

#define BOARD_PIN_GPIO_ROW_A0 39
#define BOARD_PIN_GPIO_ROW_A1 40
#define BOARD_PIN_GPIO_ROW_A2 38
#define BOARD_PIN_GPIO_ROW_A3 33

#define BOARD_PIN_GPIO_DEC_A_EN_N 41
#define BOARD_PIN_GPIO_DEC_B_EN_N 42

#define BOARD_PIN_GPIO_LED_EN 18
#define BOARD_PIN_GPIO_LED_LOGIC_EN 21
#define BOARD_PIN_GPIO_ROW_XLAT_OE_N 47

/** Active levels (see README / PCB_ARCHITECTURE safe sequencing). */
#define BOARD_ACTIVE_LED_EN 1
#define BOARD_ACTIVE_LED_LOGIC_EN 1
#define BOARD_ACTIVE_ROW_XLAT_OE_N 0
#define BOARD_ACTIVE_LED_OE_N 0
#define BOARD_ACTIVE_DEC_EN_N 0

#define BOARD_MATRIX_COLS 32
#define BOARD_MATRIX_ROWS 32

extern const board_pin_entry_t board_pin_table[];
extern const size_t board_pin_table_count;

#ifdef __cplusplus
}
#endif
