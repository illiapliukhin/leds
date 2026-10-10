#pragma once

#include <stdint.h>

#include "esp_err.h"
#include "matrix_panel.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Full-frame target (Hz). Row scan runs at REFRESH_HZ * 32. */
#define MATRIX_TARGET_REFRESH_HZ 400

esp_err_t matrix_refresh_start(matrix_panel_t *panel);
void matrix_refresh_stop(void);
void matrix_refresh_set_brightness(uint8_t level_0_255);
uint8_t matrix_refresh_get_brightness(void);
void matrix_refresh_lock_panel(void);
void matrix_refresh_unlock_panel(void);

#ifdef __cplusplus
}
#endif
