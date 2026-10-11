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
    memset(panel->plane_hi, 0, sizeof(panel->plane_hi));
    memset(panel->level, 0, sizeof(panel->level));
}

void matrix_panel_set_pixel(matrix_panel_t *panel, uint8_t row, uint8_t col, bool on)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return;
    }
    matrix_panel_set_grey(panel, row, col, on ? 3 : 0);
}

bool matrix_panel_get_pixel(const matrix_panel_t *panel, uint8_t row, uint8_t col)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return false;
    }
    return ((panel->framebuffer[row] | panel->plane_hi[row]) & (1U << col)) != 0;
}

uint32_t matrix_panel_row_bits(const matrix_panel_t *panel, uint8_t row)
{
    if (row >= panel->active_rows) {
        return 0;
    }
    uint32_t mask = (panel->active_cols >= 32) ? 0xFFFFFFFFU : ((1U << panel->active_cols) - 1U);
    return panel->framebuffer[row] & mask;
}

void matrix_panel_set_grey(matrix_panel_t *panel, uint8_t row, uint8_t col, uint8_t level)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return;
    }
    uint32_t bit = 1U << col;
    if (level & 1) {
        panel->framebuffer[row] |= bit;
    } else {
        panel->framebuffer[row] &= ~bit;
    }
    if (level & 2) {
        panel->plane_hi[row] |= bit;
    } else {
        panel->plane_hi[row] &= ~bit;
    }
    static const uint8_t map[4] = {0, 85, 170, 255};
    panel->level[row][col] = map[level & 3];
}

void matrix_panel_set_level(matrix_panel_t *panel, uint8_t row, uint8_t col, uint8_t level)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return;
    }
    panel->level[row][col] = level;
    uint32_t bit = 1U << col;
    if (level >= 128) panel->plane_hi[row] |= bit; else panel->plane_hi[row] &= ~bit;
    if (level & 64) panel->framebuffer[row] |= bit; else panel->framebuffer[row] &= ~bit;
}

uint8_t matrix_panel_get_level(const matrix_panel_t *panel, uint8_t row, uint8_t col)
{
    if (row >= panel->active_rows || col >= panel->active_cols) {
        return 0;
    }
    return panel->level[row][col];
}

uint32_t matrix_panel_row_plane(const matrix_panel_t *panel, uint8_t row, uint8_t plane)
{
    if (row >= panel->active_rows) {
        return 0;
    }
    uint32_t mask = (panel->active_cols >= 32) ? 0xFFFFFFFFU : ((1U << panel->active_cols) - 1U);
    return (plane ? panel->plane_hi[row] : panel->framebuffer[row]) & mask;
}
