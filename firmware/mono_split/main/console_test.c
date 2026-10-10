#include "console_test.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_console.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "matrix_refresh.h"
#include "power_seq.h"
#include "test_patterns.h"

static const char *TAG = "console";

static matrix_panel_t *s_panel;
static test_pattern_t s_pattern = TEST_PATTERN_OFF;
static volatile bool s_animator_running;
static TaskHandle_t s_animator_task;

static void animator_task(void *argument)
{
    (void)argument;
    uint32_t phase = 0;
    while (s_animator_running) {
        matrix_refresh_lock_panel();
        test_patterns_apply(s_panel, s_pattern, phase);
        matrix_refresh_unlock_panel();
        phase++;
        vTaskDelay(pdMS_TO_TICKS(120));
    }
    vTaskDelete(NULL);
}

static void start_animator_if_needed(void)
{
    if (s_animator_running) {
        return;
    }
    s_animator_running = true;
    xTaskCreate(animator_task, "test_anim", 3072, NULL, 5, &s_animator_task);
}

static int cmd_panel(int argc, char **argv)
{
    if (argc < 2) {
        printf("Usage: panel 20|32\n");
        return 1;
    }
    matrix_panel_geometry_t geometry = MATRIX_PANEL_32X32;
    if (strcmp(argv[1], "20") == 0) {
        geometry = MATRIX_PANEL_20X20;
    }
    matrix_refresh_lock_panel();
    matrix_panel_init(s_panel, geometry);
    matrix_refresh_unlock_panel();
    printf("Panel geometry: %s\n", geometry == MATRIX_PANEL_20X20 ? "20x20" : "32x32");
    return 0;
}

static bool s_display_on;

/* LED rails are powered only on demand (first test/display/bright-set command), not at boot. */
static esp_err_t display_ensure_on(void)
{
    if (s_display_on) {
        return ESP_OK;
    }
    ESP_LOGI(TAG, "display on demand: powering LED rails");
    esp_err_t err = power_seq_matrix_enable();
    if (err == ESP_OK) {
        err = matrix_refresh_start(s_panel);
    }
    if (err == ESP_OK || err == ESP_ERR_INVALID_STATE) {
        s_display_on = true;
        return ESP_OK;
    }
    return err;
}

static int cmd_display(int argc, char **argv)
{
    if (argc < 2) {
        printf("Display: %s\n", s_display_on ? "on" : "off");
        return 0;
    }
    if (strcmp(argv[1], "on") == 0) {
        return display_ensure_on() == ESP_OK ? 0 : 1;
    }
    if (strcmp(argv[1], "off") == 0) {
        if (s_display_on) {
            s_animator_running = false;
            matrix_refresh_stop();
            power_seq_matrix_disable();
            s_display_on = false;
        }
        printf("Display: off (LED rails down)\n");
        return 0;
    }
    printf("Usage: display [on|off]\n");
    return 1;
}

static int cmd_test(int argc, char **argv)
{
    if (argc < 2) {
        printf(
            "Usage: test off|all|row|col|checker|scroll|pixel <row> <col> <0|1>\n");
        return 1;
    }
    if (strcmp(argv[1], "off") == 0 && !s_display_on) {
        printf("Test pattern: off (display already off)\n");
        return 0;
    }
    static const char *const modes[] = {"off", "all", "row", "col", "checker", "scroll", "pixel"};
    bool known = false;
    for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); i++) {
        known |= strcmp(argv[1], modes[i]) == 0;
    }
    if (!known || (strcmp(argv[1], "pixel") == 0 && argc < 5)) {
        printf("Unknown test mode\n");
        return 1;
    }
    if (display_ensure_on() != ESP_OK) {
        printf("Display power-up failed\n");
        return 1;
    }
    if (strcmp(argv[1], "pixel") == 0 && argc >= 5) {
        uint8_t row = (uint8_t)atoi(argv[2]);
        uint8_t col = (uint8_t)atoi(argv[3]);
        bool on = atoi(argv[4]) != 0;
        matrix_refresh_lock_panel();
        matrix_panel_set_pixel(s_panel, row, col, on);
        matrix_refresh_unlock_panel();
        s_pattern = TEST_PATTERN_OFF;
        return 0;
    }

    if (strcmp(argv[1], "off") == 0) {
        s_pattern = TEST_PATTERN_OFF;
    } else if (strcmp(argv[1], "all") == 0) {
        s_pattern = TEST_PATTERN_ALL_ON;
    } else if (strcmp(argv[1], "row") == 0) {
        s_pattern = TEST_PATTERN_ROW_WALK;
    } else if (strcmp(argv[1], "col") == 0) {
        s_pattern = TEST_PATTERN_COL_WALK;
    } else if (strcmp(argv[1], "checker") == 0) {
        s_pattern = TEST_PATTERN_CHECKERBOARD;
    } else if (strcmp(argv[1], "scroll") == 0) {
        s_pattern = TEST_PATTERN_TEXT_SCROLL;
    } else {
        printf("Unknown test mode\n");
        return 1;
    }

    matrix_refresh_lock_panel();
    test_patterns_apply(s_panel, s_pattern, 0);
    matrix_refresh_unlock_panel();
    if (s_pattern != TEST_PATTERN_OFF && s_pattern != TEST_PATTERN_ALL_ON) {
        start_animator_if_needed();
    }
    printf("Test pattern: %s\n", test_pattern_name(s_pattern));
    return 0;
}

static int cmd_bright(int argc, char **argv)
{
    if (argc < 2) {
        printf("Brightness: %u\n", matrix_refresh_get_brightness());
        return 0;
    }
    int level = atoi(argv[1]);
    if (level < 0) {
        level = 0;
    }
    if (level > 255) {
        level = 255;
    }
    if (display_ensure_on() != ESP_OK) {
        return 1;
    }
    matrix_refresh_set_brightness((uint8_t)level);
    printf("Brightness set to %d\n", level);
    return 0;
}

esp_err_t console_test_register(matrix_panel_t *panel)
{
    s_panel = panel;

    const esp_console_cmd_t panel_cmd = {
        .command = "panel",
        .help = "Select panel geometry: panel 20|32",
        .func = &cmd_panel,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&panel_cmd));

    const esp_console_cmd_t test_cmd = {
        .command = "test",
        .help = "LED test patterns and single-pixel set",
        .func = &cmd_test,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&test_cmd));

    const esp_console_cmd_t bright_cmd = {
        .command = "bright",
        .help = "Get/set brightness 0-255",
        .func = &cmd_bright,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&bright_cmd));

    const esp_console_cmd_t display_cmd = {
        .command = "display",
        .help = "LED rails on demand: display [on|off]",
        .func = &cmd_display,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&display_cmd));

    ESP_LOGI(TAG, "Console commands: panel, test, bright, display (LED rails off until first use)");
    return ESP_OK;
}
