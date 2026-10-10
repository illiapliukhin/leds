#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** MBI5124 shift clock: 20 MHz EVT baseline (25 MHz max per datasheet). */
#define MBI5124_SHIFT_CLOCK_HZ (20 * 1000 * 1000)

esp_err_t mbi5124_driver_init(void);
void mbi5124_shift_columns(const uint32_t column_bits);
void mbi5124_latch(void);
void mbi5124_set_blank(bool blanked);

#ifdef __cplusplus
}
#endif
