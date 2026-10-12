#include "test_patterns.h"

#include <string.h>

static const char SCROLL_TEXT[] = "MONO SPLIT BRING-UP 20x20 / 32x32  ";

static void fill_all(matrix_panel_t *panel, bool on)
{
    for (uint8_t row = 0; row < panel->active_rows; row++) {
        for (uint8_t col = 0; col < panel->active_cols; col++) {
            matrix_panel_set_pixel(panel, row, col, on);
        }
    }
}

void test_patterns_apply(matrix_panel_t *panel, test_pattern_t pattern, uint32_t phase)
{
    matrix_panel_clear(panel);
    switch (pattern) {
    case TEST_PATTERN_OFF:
        break;
    case TEST_PATTERN_ALL_ON:
        fill_all(panel, true);
        break;
    case TEST_PATTERN_ROW_WALK: {
        uint8_t row = (uint8_t)(phase % panel->active_rows);
        for (uint8_t col = 0; col < panel->active_cols; col++) {
            matrix_panel_set_pixel(panel, row, col, true);
        }
        break;
    }
    case TEST_PATTERN_COL_WALK: {
        uint8_t col = (uint8_t)(phase % panel->active_cols);
        for (uint8_t row = 0; row < panel->active_rows; row++) {
            matrix_panel_set_pixel(panel, row, col, true);
        }
        break;
    }
    case TEST_PATTERN_CHECKERBOARD:
        for (uint8_t row = 0; row < panel->active_rows; row++) {
            for (uint8_t col = 0; col < panel->active_cols; col++) {
                bool on = ((row + col + (phase & 1U)) & 1U) == 0U;
                matrix_panel_set_pixel(panel, row, col, on);
            }
        }
        break;
    case TEST_PATTERN_TEXT_SCROLL: {
        size_t text_len = strlen(SCROLL_TEXT);
        int offset = (int)(phase % (text_len * 6));
        for (uint8_t row = 0; row < panel->active_rows; row++) {
            for (uint8_t col = 0; col < panel->active_cols; col++) {
                int glyph_index = (col + offset) / 6;
                char ch = SCROLL_TEXT[glyph_index % text_len];
                bool on = (ch != ' ') && (((col + offset) % 6) < 4) && ((row % 5) < 4);
                matrix_panel_set_pixel(panel, row, col, on);
            }
        }
        break;
    }
    default:
        break;
    }
}

const char *test_pattern_name(test_pattern_t pattern)
{
    switch (pattern) {
    case TEST_PATTERN_OFF:
        return "off";
    case TEST_PATTERN_ALL_ON:
        return "all_on";
    case TEST_PATTERN_ROW_WALK:
        return "row_walk";
    case TEST_PATTERN_COL_WALK:
        return "col_walk";
    case TEST_PATTERN_CHECKERBOARD:
        return "checkerboard";
    case TEST_PATTERN_TEXT_SCROLL:
        return "text_scroll";
    default:
        return "unknown";
    }
}
