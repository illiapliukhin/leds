#include "matrix_panel.h"

#include <string.h>

#include "board_pins.h"

void matrix_panel_init(matrix_panel_t *panel, matrix_panel_geometry_t geometry)
{
    panel->geometry = geometry;
    if (geometry == MATRIX_PANEL_20X20) {
        panel->active_rows = 20;
        panel->active_cols = 20;
    } else {
        panel->active_rows = BOARD_MATRIX_ROWS;
        panel->active_cols = BOARD_MATRIX_COLS;
    }
    matrix_panel_clear(panel);
}

void matrix_panel_clear(matrix_panel_t *panel)
{
    memset(panel->framebuffer, 0, sizeof(panel->framebuffer));
}

void matrix_panel_set_pixel(matrix_panel_t *panel, uint8_t row, uint8_t col, bool on)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return;
    }
    if (on) {
        panel->framebuffer[row] |= (1U << col);
    } else {
        panel->framebuffer[row] &= ~(1U << col);
    }
}

bool matrix_panel_get_pixel(const matrix_panel_t *panel, uint8_t row, uint8_t col)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return false;
    }
    return (panel->framebuffer[row] & (1U << col)) != 0;
}

uint32_t matrix_panel_row_bits(const matrix_panel_t *panel, uint8_t row)
{
    if (row >= panel->active_rows) {
        return 0;
    }
    uint32_t mask = (panel->active_cols >= 32) ? 0xFFFFFFFFU : ((1U << panel->active_cols) - 1U);
    return panel->framebuffer[row] & mask;
}
