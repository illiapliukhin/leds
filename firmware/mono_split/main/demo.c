#include "demo.h"
#include "patterns.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "matrix_refresh.h"

static const char *TAG = "demo";
static const char *const NAMES[DEMO_COUNT] = {"none", "smiley", "logo", "scroll", "ball", "life", "ring", "plasma", "tilt", "vyshyvanka", "aurora", "kinetic"};

static matrix_panel_t *s_panel;
static volatile demo_mode_t s_mode;
static volatile bool s_cycle;
static volatile bool s_run;
static TaskHandle_t s_task;
static uint8_t s_fb[32][32]; /* 8-bit levels composed here, then copied under the panel lock */
static volatile uint32_t s_frames_rendered;

/* 5x7 font: only the glyphs the demos use. Each byte = one column, bit0 = top row. */
typedef struct { char c; uint8_t col[5]; } glyph_t;
static const glyph_t FONT[] = {
    {'I', {0x00, 0x41, 0x7F, 0x41, 0x00}},
    {'L', {0x7F, 0x40, 0x40, 0x40, 0x40}},
    {'A', {0x7E, 0x11, 0x11, 0x11, 0x7E}},
    {'E', {0x7F, 0x49, 0x49, 0x49, 0x41}},
    {'D', {0x7F, 0x41, 0x41, 0x22, 0x1C}},
    {'P', {0x7F, 0x09, 0x09, 0x09, 0x06}},
    {'U', {0x3F, 0x40, 0x40, 0x40, 0x3F}},
    {'K', {0x7F, 0x08, 0x14, 0x22, 0x41}},
    {'H', {0x7F, 0x08, 0x08, 0x08, 0x7F}},
    {'N', {0x7F, 0x04, 0x08, 0x10, 0x7F}},
    {' ', {0x00, 0x00, 0x00, 0x00, 0x00}},
};

static const uint8_t *glyph(char c)
{
    for (size_t i = 0; i < sizeof(FONT) / sizeof(FONT[0]); i++) {
        if (FONT[i].c == c) {
            return FONT[i].col;
        }
    }
    return FONT[sizeof(FONT) / sizeof(FONT[0]) - 1].col;
}

static float s_ff[32][32]; /* float intensity 0..1 composed per frame */
static uint8_t s_prev[32][32]; /* last shown frame (for cross-fades) */

static void pxf(int r, int c, float v)
{
    if (r >= 0 && r < 32 && c >= 0 && c < 32 && v > s_ff[r][c]) s_ff[r][c] = v > 1 ? 1 : v;
}
static int text_width(const char *s) { return (int)strlen(s) * 6; }

/* text at a fractional x: each glyph column is spread over two LED columns (box filter) */
static void draw_text_sub(const char *s, float x, int y, float v)
{
    int xi = (int)floorf(x);
    float fr = x - xi;
    for (int i = 0; s[i]; i++) {
        const uint8_t *g = glyph(s[i]);
        for (int cx = 0; cx < 5; cx++) for (int cy = 0; cy < 7; cy++) {
            if (!(g[cx] & (1 << cy))) continue;
            int c = xi + i * 6 + cx;
            pxf(y + cy, c, v * (1 - fr));
            pxf(y + cy, c + 1, v * fr);
        }
    }
}

/* antialiased filled disc: coverage from the distance to the edge */
static void disc_aa(float cx, float cy, float rad, float v)
{
    for (int r = (int)(cy - rad - 2); r <= (int)(cy + rad + 2); r++)
        for (int c = (int)(cx - rad - 2); c <= (int)(cx + rad + 2); c++) {
            float d = sqrtf((c - cx) * (c - cx) + (r - cy) * (r - cy));
            float cov = rad + 0.5f - d;
            if (cov > 0) pxf(r, c, v * (cov > 1 ? 1 : cov));
        }
}

static void draw_smiley(void)
{
    for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) {
        float d = sqrtf((c - 15.5f) * (c - 15.5f) + (r - 15.5f) * (r - 15.5f));
        float rim = 1.0f - fabsf(d - 14.0f) / 1.6f;                 /* AA rim */
        if (d < 13.2f) s_ff[r][c] = 0.38f;                           /* dim face */
        if (rim > 0) pxf(r, c, rim);
    }
    for (int e = 0; e < 2; e++) {                                    /* dark eyes with glints */
        float ex = e ? 20.5f : 10.5f;
        for (int r = 7; r < 15; r++) for (int c = (int)ex - 3; c <= (int)ex + 3; c++) {
            float d = sqrtf((c - ex) * (c - ex) + (r - 10.5f) * (r - 10.5f) * 0.6f);
            if (d < 2.6f) s_ff[r][c] = 0;
        }
        s_ff[9][(int)ex] = 1.0f;
    }
    for (int c = 7; c <= 24; c++) {                                  /* dark AA smile */
        float x = c - 15.5f, y = 24.0f - x * x / 18.0f;
        for (int r = (int)y - 2; r <= (int)y + 2; r++) {
            float k = fabsf(r - y);
            if (r >= 0 && r < 32 && k < 1.3f) s_ff[r][c] *= k / 1.3f;
        }
    }
}

static void draw_logo(void)
{
    /* static artwork: the 4x4-supersampled star is rasterised once (was ~10 ms/frame on the S3), 528 B cache */
    static uint8_t cache[22][24]; static bool done;
    if (done) { for (int r = 0; r < 22; r++) for (int c = 4; c < 28; c++) pxf(r, c, cache[r][c - 4] / 255.0f); draw_text_sub("LED", (32 - text_width("LED") + 1) / 2.0f, 24, 1.0f); return; }
    done = true;
    static const int8_t sx[10] = {0, 23, 95, 37, 59, 0, -59, -37, -95, -23};
    static const int8_t sy[10] = {-100, -32, -31, 12, 81, 40, 81, 12, -31, -32};
    for (int r = 0; r < 22; r++) for (int c = 4; c < 28; c++) {
        int hits = 0;                                                /* 4x4 supersampling */
        for (int sy_ = 0; sy_ < 4; sy_++) for (int sx_ = 0; sx_ < 4; sx_++) {
            int x = (c - 15) * 10 + sx_ * 25 / 10 - 4, y = (r - 11) * 10 + sy_ * 25 / 10 - 4;
            bool in = false;
            for (int i = 0, j = 9; i < 10; j = i++)
                if (((sy[i] > y) != (sy[j] > y)) && (x < (sx[j] - sx[i]) * (y - sy[i]) / (sy[j] - sy[i]) + sx[i])) in = !in;
            hits += in;
        }
        cache[r][c - 4] = (uint8_t)(hits * 255 / 16); pxf(r, c, hits / 16.0f);
    }
    draw_text_sub("LED", (32 - text_width("LED") + 1) / 2.0f, 24, 1.0f);
}

static uint8_t s_life[32][32];
static float s_lifef[32][32];
static void life_seed(void)
{
    for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) s_life[r][c] = (esp_random() % 100) < 30;
}
static void life_step(void)
{
    static uint8_t n[32][32];
    int alive = 0;
    for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) {
        int k = 0;
        for (int dr = -1; dr <= 1; dr++) for (int dc = -1; dc <= 1; dc++)
            if (dr || dc) k += s_life[(r + dr + 32) & 31][(c + dc + 32) & 31];
        n[r][c] = (k == 3) || (s_life[r][c] && k == 2);
        alive += n[r][c];
    }
    memcpy(s_life, n, sizeof(n));
    if (alive < 20) life_seed();
}


/* ---------------------------------------------------------------- gamma-aware dither tables (3 KB) */
#define DITH_N 1024
static uint8_t s_dlo[DITH_N], s_dhi[DITH_N], s_dfr[DITH_N];       /* low/high level, fraction (0..255) toward high */
static float s_dgamma = -1;
static const uint8_t BAYER4[4][4] = {{0, 8, 2, 10}, {12, 4, 14, 6}, {3, 11, 1, 9}, {15, 7, 13, 5}};
static void dither_build(void)
{
    float g = matrix_refresh_get_gamma();
    if (g == s_dgamma) return;
    s_dgamma = g;
    uint8_t G[256];
    for (int i = 0; i < 256; i++) { float v = powf(i / 255.0f, g) * 255.0f + 0.5f; G[i] = (uint8_t)(v > 255 ? 255 : v); }
    int lo = 0;
    for (int k = 0; k < DITH_N; k++) {
        float D = powf(k / (float)(DITH_N - 1), g) * 255.0f;            /* exact wanted duty */
        while (lo < 255 && G[lo + 1] <= D) lo++;
        int L = lo; while (L > 0 && G[L - 1] == G[L]) L--;               /* lowest level giving that duty */
        int hi = lo; while (hi < 255 && G[hi] == G[lo]) hi++;
        float fr = G[hi] > G[lo] ? (D - G[lo]) / (float)(G[hi] - G[lo]) : 0;
        s_dlo[k] = (uint8_t)(G[lo] == 0 ? 0 : L); s_dhi[k] = (uint8_t)hi; s_dfr[k] = (uint8_t)(fr * 255 + 0.5f);
    }
}

static void render(demo_mode_t mode, uint32_t t)
{
    float ts = t / 60.0f;                                             /* seconds at 60 fps */
    memset(s_fb, 0, sizeof(s_fb));
    memset(s_ff, 0, sizeof(s_ff));
    switch (mode) {
    case DEMO_SMILEY: draw_smiley(); break;
    case DEMO_LOGO: draw_logo(); break;
    case DEMO_SCROLL: {
        const char *msg = "ILLIA  ";
        float w = (float)text_width(msg);
        float x = 32 - fmodf(ts * 14.0f, w + 32);                     /* 14 px/s, sub-pixel */
        draw_text_sub(msg, x, 4, 1.0f);
        draw_text_sub(msg, x + w, 4, 1.0f);
        draw_text_sub("LED", 32 - fmodf(ts * 7.0f, 50.0f), 20, 0.35f);
        break;
    }
    case DEMO_BALL: {
        static float bx = 6, by = 5, vx = 11.3f, vy = 7.9f;           /* px/s */
        static float tr[12][2];
        bx += vx / 60; by += vy / 60;
        if (bx < 3 || bx > 28) vx = -vx;
        if (by < 3 || by > 28) vy = -vy;
        memmove(tr[1], tr[0], sizeof(tr) - sizeof(tr[0]));
        tr[0][0] = bx; tr[0][1] = by;
        for (int i = 11; i >= 1; i--) disc_aa(tr[i][0], tr[i][1], 1.2f, 0.35f * (12 - i) / 12.0f);
        disc_aa(bx, by, 2.6f, 1.0f);
        for (int i = 0; i < 32; i++) pxf(0, i, 0.08f), pxf(31, i, 0.08f), pxf(i, 0, 0.08f), pxf(i, 31, 0.08f);
        break;
    }
    case DEMO_LIFE:
        if (t % 9 == 0) life_step();
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) {     /* cells fade in/out smoothly */
            float target = s_life[r][c] ? 1.0f : 0.0f;
            s_lifef[r][c] += (target - s_lifef[r][c]) * 0.18f;
            pxf(r, c, s_lifef[r][c]);
        }
        break;
    case DEMO_RING:
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) {
            float d = sqrtf((c - 15.5f) * (c - 15.5f) + (r - 15.5f) * (r - 15.5f));
            float ph = d - ts * 9.0f;                                 /* rings expand at 9 px/s */
            float v = 0.5f + 0.5f * cosf(ph * 0.7f);
            pxf(r, c, v * v * v * (1.0f - d / 30.0f));
        }
        break;
    case DEMO_VYSH: case DEMO_AURORA: case DEMO_KINETIC: {
        int pat = s_mode == DEMO_VYSH ? PAT_VYSH : s_mode == DEMO_AURORA ? PAT_AURORA : PAT_KINETIC;
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) pxf(r, c, pattern_px(pat, c, r, 32, 32, ts));
        break;
    }
    case DEMO_PLASMA:
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) {
            float v = sinf(c * 0.22f + ts * 1.3f) + sinf(r * 0.17f - ts * 0.9f) + sinf((r + c) * 0.13f + ts * 1.7f) +
                      sinf(sqrtf((c - 16 + 8 * sinf(ts * 0.5f)) * (c - 16 + 8 * sinf(ts * 0.5f)) + (r - 16) * (r - 16)) * 0.3f);
            pxf(r, c, (v + 4.0f) / 8.0f);
        }
        break;
    case DEMO_TILT: {
        /* Mocked BMI270 accel (no IMU in QEMU): slow figure-eight tilt. */
        static float x = 16, y = 16, vx, vy;
        float ax = 0.5f * sinf(ts * 0.9f), ay = 0.5f * sinf(ts * 1.3f + 1.0f);  /* g */
        vx += ax * 40 / 60; vy += ay * 40 / 60; vx *= 0.985f; vy *= 0.985f;
        x += vx / 60 * 8; y += vy / 60 * 8;
        if (x < 3) { x = 3; vx = -vx * 0.5f; }
        if (x > 28) { x = 28; vx = -vx * 0.5f; }
        if (y < 3) { y = 3; vy = -vy * 0.5f; }
        if (y > 28) { y = 28; vy = -vy * 0.5f; }
        for (int k = 0; k < 28; k++) {                                /* AA guide line (bilinear splat) */
            float py = 15.5f + ay * k * 0.5f, px = 15.5f + ax * k * 0.5f; int iy = (int)floorf(py), ix = (int)floorf(px); float fy = py - iy, fx = px - ix;
            pxf(iy, ix, 0.14f * (1 - fx) * (1 - fy)); pxf(iy, ix + 1, 0.14f * fx * (1 - fy)); pxf(iy + 1, ix, 0.14f * (1 - fx) * fy); pxf(iy + 1, ix + 1, 0.14f * fx * fy);
        }
        disc_aa(x, y, 2.6f, 1.0f);
        break;
    }
    default: break;
    }
    /* gamma-aware spatio-temporal dithering: the scan engine shows duty G[level] = round((level/255)^g * 255), which
     * collapses levels 1..~20 into a few duty steps. Pick between the two neighbouring distinct duties so the average
     * over 4 frames x 4x4 pixels equals the exact (v^g * 255): smooth dark gradients and sub-step fades, same mean. */
    dither_build();
    for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) {
        float f = s_ff[r][c];
        int k = (int)(f * (DITH_N - 1) + 0.5f);
        if (k <= 0) continue;
        if (k >= DITH_N) k = DITH_N - 1;
        int thr = (BAYER4[r & 3][c & 3] + (int)(t & 3) * 4 + ((t >> 2) & 1) * 2) & 15;   /* 16-step ordered threshold */
        uint8_t v = (s_dfr[k] > thr * 16 + 8) ? s_dhi[k] : s_dlo[k];
        if (v > s_fb[r][c]) s_fb[r][c] = v;
    }
}

static void demo_task(void *arg)
{
    (void)arg;
    uint32_t t = 0;
    int64_t switched = esp_timer_get_time();
    demo_mode_t last = DEMO_NONE;
    int fade = 0;                                                     /* frames left in the cross-fade */
    static uint8_t from[32][32];
    TickType_t wake = xTaskGetTickCount();
    while (s_run) {
        demo_mode_t mode = s_mode;
        if (s_cycle && esp_timer_get_time() - switched > 5000000) {
            mode = (demo_mode_t)(mode % (DEMO_COUNT - 1) + 1);
            s_mode = mode;
            switched = esp_timer_get_time();
        }
        if (mode != last) {
            ESP_LOGI(TAG, "demo: %s", NAMES[mode]);
            if (mode == DEMO_LIFE) { life_seed(); memset(s_lifef, 0, sizeof(s_lifef)); }
            memcpy(from, s_prev, sizeof(from));
            fade = last == DEMO_NONE ? 0 : 36;                        /* 0.6 s smooth cross-fade */
            last = mode;
            t = 0;
        }
        render(mode, t++);
        if (fade > 0) {
            float a = fade / 36.0f; a = a * a * (3 - 2 * a);           /* smoothstep */
            for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) s_fb[r][c] = (uint8_t)(from[r][c] * a + s_fb[r][c] * (1 - a) + 0.5f);
            fade--;
        }
        memcpy(s_prev, s_fb, sizeof(s_prev));
        matrix_refresh_lock_panel();
        if (s_panel->geometry != MATRIX_PANEL_32X32) matrix_panel_init(s_panel, MATRIX_PANEL_32X32);
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) matrix_panel_set_level(s_panel, r, c, s_fb[r][c]);
        matrix_refresh_unlock_panel();                                /* publishes to the scan engine (swap at frame end) */
        s_frames_rendered++;
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(16) + ((t % 3) == 0 ? 1 : 0)); /* 60 fps on a 1 ms tick (16,17,17) */
    }
    s_task = NULL;
    vTaskDelete(NULL);
}

uint32_t demo_frames_rendered(void) { return s_frames_rendered; }
const uint8_t *demo_glyph(char ch) { return glyph(ch); }

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
