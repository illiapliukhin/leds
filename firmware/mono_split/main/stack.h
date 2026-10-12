#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "matrix_panel.h"

typedef enum { STACK_OFF = 0, STACK_ELECT, STACK_WAIT, STACK_DISCOVER, STACK_LEAD, STACK_FOLLOW } stack_state_t;
typedef enum { STACK_MODE_GEN = 0, STACK_MODE_STREAM = 1 } stack_mode_t;

esp_err_t stack_start(matrix_panel_t *panel);
void stack_set_mode(stack_mode_t m);
void stack_set_demo(int demo);        /* -1 = cycle */
void stack_set_fps(int fps);
void stack_print_status(void);
