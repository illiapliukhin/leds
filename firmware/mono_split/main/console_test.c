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
#include "demo.h"
#include "bmi270_probe.h"
#include "sim_scan.h"
#include "stack.h"
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
static esp_err_t display_ensure_on(void);

/* LED rails are powered only on demand (first test/display/bright-set command), not at boot. */
esp_err_t console_display_on(void) { return display_ensure_on(); }
static esp_err_t display_ensure_on(void)
{
    sim_scan_start(); /* MONO_SIM only: stream complete scans for the virtual board */
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

static int cmd_gamma(int argc, char **argv)
{
    if (argc >= 2) {
        float g = strtof(argv[1], NULL);
        if (g < 0.5f || g > 4.0f) {
            printf("gamma 0.5..4.0\n");
            return 1;
        }
        matrix_refresh_set_gamma(g);
    }
    printf("Gamma: %.2f\n", matrix_refresh_get_gamma());
    return 0;
}

static int cmd_scan(int argc, char **argv)
{
    (void)argc; (void)argv;
    printf("scan: LCD_CAM i80 %d MHz, %lu samples/row, %lu/frame, nominal %.1f Hz, 8-bit BCM, bright %u, gamma %.2f, last build %lu cycles, frames %lu, demo frames %lu\n",
           MATRIX_PCLK_HZ / 1000000, (unsigned long)matrix_refresh_row_samples(), (unsigned long)matrix_refresh_frame_samples(),
           matrix_refresh_nominal_hz(), matrix_refresh_get_brightness(), matrix_refresh_get_gamma(),
           (unsigned long)matrix_refresh_build_cycles(), (unsigned long)matrix_refresh_frame_count(), (unsigned long)demo_frames_rendered());
    return 0;
}

static int cmd_stack(int argc, char **argv)
{
    if (argc < 2 || strcmp(argv[1], "status") == 0) { stack_print_status(); return 0; }
    if (strcmp(argv[1], "start") == 0) {
        esp_err_t e = stack_start(s_panel);
        printf("stack start: %s\n", esp_err_to_name(e));
        return e == ESP_OK ? 0 : 1;
    }
    if (strcmp(argv[1], "mode") == 0 && argc >= 3) { stack_set_mode(strcmp(argv[2], "stream") == 0 ? STACK_MODE_STREAM : STACK_MODE_GEN); return 0; }
    if (strcmp(argv[1], "fps") == 0 && argc >= 3) { stack_set_fps(atoi(argv[2])); return 0; }
    if (strcmp(argv[1], "demo") == 0 && argc >= 3) {
        static const char *n[] = {"scroll", "ball", "plasma", "wipe"};
        int d = -1;
        for (int i = 0; i < 4; i++) if (strcmp(argv[2], n[i]) == 0) d = i;
        stack_set_demo(d);
        return 0;
    }
    printf("stack start|status|mode gen|stream|demo scroll|ball|plasma|wipe|cycle|fps N\n");
    return 1;
}

static int cmd_i2cscan(int argc, char **argv)
{
    (void)argc; (void)argv;
    uint8_t id = 0, v[2] = {0};
    bmi270_i2c_bus_scan();
    if (bmi270_read_chip_id(&id) == ESP_OK) printf("BMI270 CHIP_ID=0x%02X %s\n", id, id == 0x24 ? "OK" : "BAD");
    if (bmi270_read_reg16(0x36, 0x08, v) == ESP_OK) printf("MAX17048 VERSION=0x%02X%02X OK\n", v[0], v[1]);
    return 0;
}

static int cmd_demo(int argc, char **argv)
{
    if (argc < 2) {
        printf("Usage: demo smiley|logo|scroll|ball|life|ring|plasma|tilt|cycle|stop\n");
        return 1;
    }
    if (strcmp(argv[1], "stop") == 0) {
        demo_stop();
        printf("Demo stopped\n");
        return 0;
    }
    bool cycle = strcmp(argv[1], "cycle") == 0;
    demo_mode_t mode = cycle ? DEMO_SMILEY : demo_from_name(argv[1]);
    if (mode == DEMO_NONE) {
        printf("Unknown demo\n");
        return 1;
    }
    if (display_ensure_on() != ESP_OK) {
        return 1;
    }
    s_animator_running = false;
    sim_scan_start();
    demo_start(s_panel, mode, cycle);
    printf("Demo: %s%s\n", demo_name(mode), cycle ? " (cycle, 5 s each)" : "");
    return 0;
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
            demo_stop();
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
    if (demo_running()) {
        demo_stop();
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

    const esp_console_cmd_t stack_cmd = {.command = "stack", .help = "Stacking: stack start|status|mode gen|stream|demo <name>|cycle|fps N", .func = &cmd_stack};
    ESP_ERROR_CHECK(esp_console_cmd_register(&stack_cmd));
    const esp_console_cmd_t gamma_cmd = {.command = "gamma", .help = "Gamma LUT exponent: gamma [0.5..4.0] (default 2.2)", .func = &cmd_gamma};
    ESP_ERROR_CHECK(esp_console_cmd_register(&gamma_cmd));
    const esp_console_cmd_t scan_cmd = {.command = "scan", .help = "Scan engine timing and stats", .func = &cmd_scan};
    ESP_ERROR_CHECK(esp_console_cmd_register(&scan_cmd));

    const esp_console_cmd_t i2c_cmd = {
        .command = "i2cscan",
        .help = "Scan the IMU/gauge I2C bus and read BMI270/MAX17048 IDs",
        .func = &cmd_i2cscan,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&i2c_cmd));

    const esp_console_cmd_t demo_cmd = {
        .command = "demo",
        .help = "32x32 demos: demo smiley|logo|scroll|ball|life|ring|plasma|tilt|cycle|stop",
        .func = &cmd_demo,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&demo_cmd));

    ESP_LOGI(TAG, "Console commands: panel, test, bright, display, demo (LED rails off until first use)");
    return ESP_OK;
}
