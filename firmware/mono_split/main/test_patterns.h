#pragma once

#include "matrix_panel.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TEST_PATTERN_OFF = 0,
    TEST_PATTERN_ALL_ON,
    TEST_PATTERN_ROW_WALK,
    TEST_PATTERN_COL_WALK,
    TEST_PATTERN_CHECKERBOARD,
    TEST_PATTERN_TEXT_SCROLL,
} test_pattern_t;

void test_patterns_apply(matrix_panel_t *panel, test_pattern_t pattern, uint32_t phase);
const char *test_pattern_name(test_pattern_t pattern);

#ifdef __cplusplus
}
#endif
