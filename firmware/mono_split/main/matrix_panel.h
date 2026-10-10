#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MATRIX_PANEL_20X20 = 0,
    MATRIX_PANEL_32X32 = 1,
} matrix_panel_geometry_t;

typedef struct {
    matrix_panel_geometry_t geometry;
    uint8_t active_rows;
    uint8_t active_cols;
    uint32_t framebuffer[32]; /* bit plane 0 (LSB, weight 1) */
    uint32_t plane_hi[32];    /* bit plane 1 (MSB, weight 2) -> 4 grey levels via BCM */
} matrix_panel_t;

void matrix_panel_init(matrix_panel_t *panel, matrix_panel_geometry_t geometry);
void matrix_panel_clear(matrix_panel_t *panel);
void matrix_panel_set_pixel(matrix_panel_t *panel, uint8_t row, uint8_t col, bool on);
bool matrix_panel_get_pixel(const matrix_panel_t *panel, uint8_t row, uint8_t col);
uint32_t matrix_panel_row_bits(const matrix_panel_t *panel, uint8_t row);
/** level 0..3 */
void matrix_panel_set_grey(matrix_panel_t *panel, uint8_t row, uint8_t col, uint8_t level);
uint32_t matrix_panel_row_plane(const matrix_panel_t *panel, uint8_t row, uint8_t plane);

#ifdef __cplusplus
}
#endif
