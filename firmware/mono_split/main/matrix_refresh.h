#pragma once

#include <stdint.h>

#include "esp_err.h"
#include "matrix_panel.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Hardware scan engine (v13): the whole 32-row x 8-bit-plane BCM scan is a DMA sample stream
 * clocked out by the ESP32-S3 LCD_CAM i80 peripheral at 20 MHz. PCLK (WR) = LED_CLK, and the
 * 16-bit data bus carries SDI, LE, OE_N, ROW_A0..A3, DEC_A_EN_N, DEC_B_EN_N (all via the GPIO
 * matrix). One DMA transaction = one full frame; the CPU only rebuilds the SDI bits when the
 * content changes. See SIM_REPORT.md "v13" for the timing math.
 */
#define MATRIX_PCLK_HZ        (20 * 1000 * 1000)   /* MBI5124 max 25 MHz; LV125A tpd <= 11.5 ns */
#define MATRIX_SAMPLE_NS      50
#define MATRIX_PLANES         8
#define MATRIX_ROWS           32

/* bus bit assignment */
#define MBUS_SDI   (1u << 0)
#define MBUS_LE    (1u << 1)
#define MBUS_OE_N  (1u << 2)
#define MBUS_A0    (1u << 3)
#define MBUS_DECA_N (1u << 7)
#define MBUS_DECB_N (1u << 8)

esp_err_t matrix_refresh_start(matrix_panel_t *panel);
void matrix_refresh_stop(void);
uint32_t matrix_refresh_frame_count(void);
void matrix_refresh_set_brightness(uint8_t level_0_255);
uint8_t matrix_refresh_get_brightness(void);
void matrix_refresh_set_gamma(float gamma);
float matrix_refresh_get_gamma(void);
void matrix_refresh_lock_panel(void);
void matrix_refresh_unlock_panel(void);

/* layout / stats (for the console and the sim tap) */
uint32_t matrix_refresh_row_samples(void);
uint32_t matrix_refresh_frame_samples(void);
float matrix_refresh_nominal_hz(void);
uint32_t matrix_refresh_build_cycles(void);     /* CPU cycles of the last frame build */
const uint16_t *matrix_refresh_front_buffer(uint32_t *gen);

#ifdef __cplusplus
}
#endif
