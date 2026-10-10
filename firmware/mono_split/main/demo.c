#include "demo.h"

#include <stdlib.h>
#include <string.h>

#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "matrix_refresh.h"

static const char *TAG = "demo";
static const char *const NAMES[DEMO_COUNT] = {"none", "smiley", "logo", "scroll", "ball", "life", "ring", "plasma", "tilt"};

static matrix_panel_t *s_panel;
static volatile demo_mode_t s_mode;
static volatile bool s_cycle;
static volatile bool s_run;
static TaskHandle_t s_task;
static uint8_t s_fb[32][32]; /* 0..3 grey, composed here then copied under the panel lock */

/* 5x7 font: only the glyphs the demos use. Each byte = one column, bit0 = top row. */
typedef struct { char c; uint8_t col[5]; } glyph_t;
static const glyph_t FONT[] = {
    {'I', {0x00, 0x41, 0x7F, 0x41, 0x00}},
    {'L', {0x7F, 0x40, 0x40, 0x40, 0x40}},
    {'A', {0x7E, 0x11, 0x11, 0x11, 0x7E}},
    {'E', {0x7F, 0x49, 0x49, 0x49, 0x41}},
    {'D', {0x7F, 0x41, 0x41, 0x22, 0x1C}},
    {' ', {0x00, 0x00, 0x00, 0x00, 0x00}},
};

static const uint8_t *glyph(char c)
{
    for (size_t i = 0; i < sizeof(FONT) / sizeof(FONT[0]); i++) {
        if (FONT[i].c == c) {
            return FONT[i].col;
        }
    }
    return FONT[5].col;
}

static void px(int r, int c, uint8_t v)
{
    if (r >= 0 && r < 32 && c >= 0 && c < 32 && v > s_fb[r][c]) {
        s_fb[r][c] = v > 3 ? 3 : v;
    }
}

static int text_width(const char *s) { return (int)strlen(s) * 6; }

static void draw_text(const char *s, int x, int y, uint8_t v)
{
    for (int i = 0; s[i]; i++) {
        const uint8_t *g = glyph(s[i]);
        for (int cx = 0; cx < 5; cx++) {
            for (int cy = 0; cy < 7; cy++) {
                if (g[cx] & (1 << cy)) {
                    px(y + cy, x + i * 6 + cx, v);
                }
            }
        }
    }
}

/* integer sine, 0..255 phase -> -127..127 */
static int isin(int phase)
{
    static const int8_t q[65] = {0, 3, 6, 9, 12, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 49, 51, 54, 57, 60, 63,
        65, 68, 71, 73, 76, 78, 81, 83, 85, 88, 90, 92, 94, 96, 98, 100, 102, 104, 106, 107, 109, 111, 112, 113, 115,
        116, 117, 118, 120, 121, 122, 122, 123, 124, 125, 125, 126, 126, 126, 127, 127, 127, 127};
    phase &= 255;
    if (phase < 64) return q[phase];
    if (phase < 128) return q[128 - phase];
    if (phase < 192) return -q[phase - 128];
    return -q[256 - phase];
}

static void draw_smiley(void)
{
    for (int r = 0; r < 32; r++) {
        for (int c = 0; c < 32; c++) {
            int dx = 2 * c - 31, dy = 2 * r - 31, d2 = dx * dx + dy * dy;
            if (d2 <= 30 * 30 && d2 >= 26 * 26) px(r, c, 3);        /* outline */
            else if (d2 < 26 * 26) px(r, c, 1);                     /* dim face */
        }
    }
    for (int r = 9; r <= 13; r++) for (int c = 10; c <= 12; c++) px(r, c, 3), px(r, 31 - c, 3);
    for (int c = 8; c <= 23; c++) {                                  /* mouth: parabola */
        int x = c - 15;
        int r = 19 + (64 - (2 * x + 1) * (2 * x + 1) / 4) / 16 * 0 + (x * x) / -12 + 4;
        px(r, c, 3);
        px(r - 1, c, 2);
    }
}

static void draw_logo(void)
{
    /* five-point star, centre (11, 15.5), outer 10 / inner 4 px, filled by point-in-polygon */
    static const int8_t sx[10] = {0, 23, 95, 37, 59, 0, -59, -37, -95, -23}; /* x*10 */
    static const int8_t sy[10] = {-100, -32, -31, 12, 81, 40, 81, 12, -31, -32};
    for (int r = 0; r < 22; r++) {
        for (int c = 4; c < 28; c++) {
            int x = (c - 15) * 10 * 10 / 10, y = (r - 11) * 10;
            x = x * 10 / 10; /* scale: 1 px = 10 units, star radius 100 = 10 px */
            bool in = false;
            for (int i = 0, j = 9; i < 10; j = i++) {
                if (((sy[i] > y) != (sy[j] > y)) && (x < (sx[j] - sx[i]) * (y - sy[i]) / (sy[j] - sy[i]) + sx[i])) in = !in;
            }
            if (in) px(r, c, 3);
        }
    }
    draw_text("LED", (32 - text_width("LED") + 1) / 2, 24, 3);
}

static uint8_t s_life[32][32];
static void life_seed(void)
{
    for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) s_life[r][c] = (esp_random() % 100) < 30;
}
static void life_step(void)
{
    static uint8_t n[32][32];
    int alive = 0;
    for (int r = 0; r < 32; r++) {
        for (int c = 0; c < 32; c++) {
            int k = 0;
            for (int dr = -1; dr <= 1; dr++) for (int dc = -1; dc <= 1; dc++)
                if (dr || dc) k += s_life[(r + dr + 32) & 31][(c + dc + 32) & 31] & 1;
            uint8_t was = s_life[r][c] & 1;
            uint8_t now = (k == 3) || (was && k == 2);
            n[r][c] = now | (was << 1);
            alive += now;
        }
    }
    memcpy(s_life, n, sizeof(n));
    if (alive < 20) life_seed();
}

static void render(demo_mode_t mode, uint32_t t)
{
    memset(s_fb, 0, sizeof(s_fb));
    switch (mode) {
    case DEMO_SMILEY: draw_smiley(); break;
    case DEMO_LOGO: draw_logo(); break;
    case DEMO_SCROLL: {
        const char *msg = "ILLIA  ";
        int w = text_width(msg);
        int x = 32 - (int)(t / 2 % (uint32_t)(w + 32));
        draw_text(msg, x, 4, 3);
        draw_text(msg, x + w, 4, 3);
        draw_text("LED", x / 2 + 8, 20, 1);
        break;
    }
    case DEMO_BALL: {
        static int bx = 5 * 16, by = 3 * 16, vx = 13, vy = 9;
        static int trail[6][2];
        bx += vx; by += vy;
        if (bx < 2 * 16 || bx > 29 * 16) vx = -vx;
        if (by < 2 * 16 || by > 29 * 16) vy = -vy;
        memmove(trail[1], trail[0], sizeof(trail) - sizeof(trail[0]));
        trail[0][0] = bx / 16; trail[0][1] = by / 16;
        for (int i = 5; i >= 1; i--) px(trail[i][1], trail[i][0], i < 3 ? 2 : 1);
        for (int dr = -2; dr <= 2; dr++) for (int dc = -2; dc <= 2; dc++)
            if (dr * dr + dc * dc <= 5) px(by / 16 + dr, bx / 16 + dc, 3);
        for (int i = 0; i < 32; i++) px(0, i, 1), px(31, i, 1), px(i, 0, 1), px(i, 31, 1);
        break;
    }
    case DEMO_LIFE:
        if (t % 3 == 0) life_step();
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++)
            px(r, c, (s_life[r][c] & 1) ? 3 : ((s_life[r][c] & 2) ? 1 : 0));
        break;
    case DEMO_RING:
        for (int r = 0; r < 32; r++) {
            for (int c = 0; c < 32; c++) {
                int dx = 2 * c - 31, dy = 2 * r - 31;
                int d = 0;
                while ((d + 1) * (d + 1) <= dx * dx + dy * dy) d++; /* isqrt */
                int ph = (d - (int)t * 2) & 31;
                px(r, c, ph < 4 ? 3 : (ph < 8 ? 2 : (ph < 11 ? 1 : 0)));
            }
        }
        break;
    case DEMO_PLASMA:
        for (int r = 0; r < 32; r++) {
            for (int c = 0; c < 32; c++) {
                int v = isin(c * 8 + t * 3) + isin(r * 6 - t * 2) + isin((r + c) * 4 + t * 5) + isin(r * c / 4 + t);
                px(r, c, (uint8_t)((v + 508) * 4 / 1017));
            }
        }
        break;
    case DEMO_TILT: {
        /* Mocked BMI270 accel (IMU absent in QEMU): slow figure-eight tilt in milli-g. */
        static int x = 16 * 16, y = 16 * 16, vx, vy;
        int ax = isin(t * 2) * 4, ay = isin(t * 3 + 64) * 4; /* about ±0.5 g */
        vx += ax / 64; vy += ay / 64;
        vx = vx * 15 / 16; vy = vy * 15 / 16;
        x += vx; y += vy;
        if (x < 2 * 16) { x = 2 * 16; vx = -vx / 2; }
        if (x > 29 * 16) { x = 29 * 16; vx = -vx / 2; }
        if (y < 2 * 16) { y = 2 * 16; vy = -vy / 2; }
        if (y > 29 * 16) { y = 29 * 16; vy = -vy / 2; }
        for (int dr = -2; dr <= 2; dr++) for (int dc = -2; dc <= 2; dc++)
            if (dr * dr + dc * dc <= 5) px(y / 16 + dr, x / 16 + dc, 3);
        /* tilt indicator: line from centre in the accel direction */
        for (int k = 0; k < 8; k++) px(15 + ay * k / 512, 15 + ax * k / 512, 1);
        break;
    }
    default: break;
    }
}

static void demo_task(void *arg)
{
    (void)arg;
    uint32_t t = 0;
    int64_t switched = esp_timer_get_time();
    demo_mode_t last = DEMO_NONE;
    while (s_run) {
        demo_mode_t mode = s_mode;
        if (s_cycle && esp_timer_get_time() - switched > 5000000) {
            mode = (demo_mode_t)(mode % (DEMO_COUNT - 1) + 1);
            s_mode = mode;
            switched = esp_timer_get_time();
        }
        if (mode != last) {
            ESP_LOGI(TAG, "demo: %s", NAMES[mode]);
            if (mode == DEMO_LIFE) life_seed();
            last = mode;
            t = 0;
        }
        render(mode, t++);
        matrix_refresh_lock_panel();
        matrix_panel_init(s_panel, MATRIX_PANEL_32X32);
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) matrix_panel_set_grey(s_panel, r, c, s_fb[r][c]);
        matrix_refresh_unlock_panel();
        vTaskDelay(pdMS_TO_TICKS(40)); /* 25 fps content */
    }
    s_task = NULL;
    vTaskDelete(NULL);
}

demo_mode_t demo_from_name(const char *name)
{
    for (int i = 1; i < DEMO_COUNT; i++) if (strcmp(name, NAMES[i]) == 0) return (demo_mode_t)i;
    return DEMO_NONE;
}

const char *demo_name(demo_mode_t mode) { return mode < DEMO_COUNT ? NAMES[mode] : "?"; }

esp_err_t demo_start(matrix_panel_t *panel, demo_mode_t mode, bool cycle)
{
    s_panel = panel;
    s_mode = mode == DEMO_NONE ? DEMO_SMILEY : mode;
    s_cycle = cycle;
    if (!s_task) {
        s_run = true;
        if (xTaskCreatePinnedToCore(demo_task, "demo", 4096, NULL, 4, &s_task, 0) != pdPASS) return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void demo_stop(void)
{
    s_run = false;
    vTaskDelay(pdMS_TO_TICKS(60));
}

bool demo_running(void) { return s_task != NULL; }
