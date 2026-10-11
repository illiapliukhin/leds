#pragma once
#include <stdbool.h>
#include "esp_err.h"
#include "matrix_panel.h"

typedef enum {
    DEMO_NONE = 0,
    DEMO_SMILEY,   /* static, 4 grey levels */
    DEMO_LOGO,     /* static star + "LED" */
    DEMO_SCROLL,   /* scrolling "ILLIA" */
    DEMO_BALL,     /* bouncing ball with a fading trail */
    DEMO_LIFE,     /* Conway's Game of Life on a torus */
    DEMO_RING,     /* expanding rings */
    DEMO_PLASMA,   /* grey plasma */
    DEMO_TILT,     /* ball rolled by BMI270 tilt (mocked when the IMU is absent) */
    DEMO_COUNT,
} demo_mode_t;

demo_mode_t demo_from_name(const char *name);
const char *demo_name(demo_mode_t mode);
/** cycle=true walks all modes, 5 s each. */
esp_err_t demo_start(matrix_panel_t *panel, demo_mode_t mode, bool cycle);
void demo_stop(void);
bool demo_running(void);
uint32_t demo_frames_rendered(void);
const uint8_t *demo_glyph(char ch); /* 5x7 font, 5 column bytes, bit0 = top */
