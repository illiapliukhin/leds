/* Host (Windows/Linux) build of the real mono_split firmware sources for the LED simulator.
 * The firmware .c files are #included verbatim (unchanged) so their static functions -
 * demo.c render(), stack.c render_tile()/canvas_px()/compute_grid()/crc8() and patterns.c -
 * are exported through a small C API that Python calls via ctypes. FreeRTOS/ESP-IDF are stubbed
 * (stubs/), the hardware is replaced by the sim HAL below. matrix_refresh.c's gamma LUT and BCM
 * plane/brightness slot formula are reproduced bit-exactly in sim_duty_lut(). */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "esp_err.h"
#include "esp_timer.h"
#include "matrix_panel.h"
#include "stack_hal.h"

#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif

/* ---------------- sim HAL / stubs */
static int64_t g_now_us;
static uint32_t g_rng = 0x12345678u;
uint32_t esp_random(void) { g_rng ^= g_rng << 13; g_rng ^= g_rng >> 17; g_rng ^= g_rng << 5; return g_rng; }
int64_t esp_timer_get_time(void) { return g_now_us; }
void matrix_panel_init(matrix_panel_t *p, matrix_panel_geometry_t g) { memset(p, 0, sizeof(*p)); p->geometry = g; p->active_rows = p->active_cols = 32; }
void matrix_panel_set_level(matrix_panel_t *p, uint8_t r, uint8_t c, uint8_t v) { if (r < 32 && c < 32) p->level[r][c] = v; }
static float g_gamma = 2.2f;
float matrix_refresh_get_gamma(void) { return g_gamma; }
void matrix_refresh_lock_panel(void) {}
void matrix_refresh_unlock_panel(void) {}
void matrix_refresh_set_sync(bool on, int burst) { (void)on; (void)burst; }
void matrix_refresh_sync_swap(void) {}
esp_err_t console_display_on(void) { return ESP_OK; }
void shal_init(shal_sync_cb_t cb) { (void)cb; }
void shal_bus_write(const uint8_t *d, size_t n) { (void)d; (void)n; }
int shal_bus_read(uint8_t *b, size_t m, TickType_t t) { (void)b; (void)m; (void)t; return 0; }
void shal_pres_drive(int s, bool h) { (void)s; (void)h; }
bool shal_pres_read(int s) { (void)s; return false; }
void shal_sync_role(bool l) { (void)l; }
void shal_sync_pulse(void) {}
uint64_t shal_mac(void) { return 0; }
void shal_report(const char *fmt, ...) { (void)fmt; }

/* ---------------- the firmware, verbatim */
#define TAG demo_TAG
#define s_mode demo_s_mode
#define s_panel demo_s_panel
#include "demo.c"
#undef s_mode
#undef s_panel
#undef TAG
#define TAG stack_TAG
#include "stack.c"
#undef TAG
#include "patterns.c"
#include "panel_id.c"                 /* firmware/panel_id: EEPROM record CRC + logical->physical mapping */

/* ---------------- exported API */
API int sim_api_version(void) { return 2; }
API int sim_maxb(void) { return MAXB; }
#ifndef FW_SHA
#define FW_SHA "unknown"
#endif
API const char *sim_fw_sha(void) { return FW_SHA; }      /* git SHA of firmware/mono_split + panel_id this library was compiled from */
API unsigned sim_panel_id_crc16(const uint8_t *p, unsigned n) { return panel_id_crc16(p, (uint16_t)n); }
API int sim_panel_map(const uint8_t *rec64, int x, int y, int *row, int *col)
{
    uint8_t r = 0, c = 0; bool ok = panel_map((const panel_id_t *)rec64, (uint8_t)x, (uint8_t)y, &r, &c);
    *row = r; *col = c; return ok;
}
API void sim_panel_id_default(uint8_t *rec64) { panel_id_default((panel_id_t *)rec64); }
API int sim_demo_count(void) { return DEMO_COUNT; }
API const char *sim_demo_name(int i) { return demo_name((demo_mode_t)i); }
API int sim_canvas_count(void) { return D_N; }
API const char *sim_canvas_name(int i) { return (i >= 0 && i < D_N) ? DNAMES[i] : "?"; }
API int sim_canvas_secs(int i) { return (i >= 0 && i < D_N) ? DSECS[i] : 0; }
API void sim_seed(uint32_t s) { g_rng = s ? s : 1; }

/* demo.c: one 60 fps frame t of a single-panel demo (stateful demos keep their statics, as on HW) */
API void sim_demo_render(int mode, uint32_t t, uint8_t *out)
{
    if (mode != (int)demo_s_mode && mode == DEMO_LIFE) { life_seed(); memset(s_lifef, 0, sizeof(s_lifef)); }
    demo_s_mode = (demo_mode_t)mode;
    render((demo_mode_t)mode, t);
    memcpy(out, s_fb, 1024);
}

/* stack.c: the 32x32 tile of a board at grid (x,y) rot on a W x H-tile canvas for content frame f */
API void sim_render_tile(int x, int y, int rot, int W, int H, int demo, int fps, uint32_t f, uint8_t *out)
{
    tile_t t = {0, (int8_t)x, (int8_t)y, (int8_t)rot, true};
    s_W = W; s_H = H; s_demo = demo; s_fps = fps;
    render_tile(&t, f, out);
}
API int sim_demo_for_frame(int demo, uint32_t f, int fps) { s_demo = demo; return demo_for_frame(f, fps); }

/* stack.c compute_grid(): members (sorted ids), my id = leader, edges (a,as,b,bs) -> tiles */
API int sim_compute_grid(uint32_t leader, int n, const uint32_t *ids, int ne, const uint32_t *edges, int *out /* n x {placed,x,y,rot} */, int *WH)
{
    s_id = leader; s_nmem = 0;
    for (int i = 0; i < n && i < MAXB; i++) add_member(ids[i]);
    s_nedges = 0;
    for (int e = 0; e < ne; e++) add_edge(edges[4 * e], (int)edges[4 * e + 1], edges[4 * e + 2], (int)edges[4 * e + 3]);
    if (member_idx(leader) < 0) return -1;
    compute_grid();
    for (int i = 0; i < s_ntiles; i++) {
        int k = -1;
        for (int j = 0; j < n; j++) if (ids[j] == s_tiles[i].id) k = j;
        if (k < 0) continue;
        out[4 * k] = s_tiles[i].placed; out[4 * k + 1] = s_tiles[i].x; out[4 * k + 2] = s_tiles[i].y; out[4 * k + 3] = s_tiles[i].rot;
    }
    WH[0] = s_W; WH[1] = s_H;
    return s_ntiles;
}

API int sim_crc8(const uint8_t *d, int n) { return crc8(d, n); }

/* matrix_refresh.c: gamma LUT (build_gamma) + BCM: plane k is on for ((2<<k)*br+127)/255 slots of
 * a 2<<k full-scale window -> time-averaged duty relative to full white at brightness 255. */
API void sim_duty_lut(int br, float gamma, float *out)
{
    g_gamma = gamma;                                             /* demo.c's dither follows the scan engine gamma */
    for (int i = 0; i < 256; i++) {
        float v = powf(i / 255.0f, gamma) * 255.0f + 0.5f;
        uint8_t g = (uint8_t)(v > 255 ? 255 : v);
        uint32_t on = 0;
        for (int k = 0; k < 8; k++) if ((g >> k) & 1) on += ((2u << k) * (uint32_t)br + 127) / 255;
        out[i] = on / 510.0f;
    }
}

/* demo.c dither, for the host test: level the firmware emits for intensity v at pixel (r,c), frame t */
API int sim_dither_level(float v, uint32_t t, int r, int c)
{
    dither_build();
    int k = (int)(v * (DITH_N - 1) + 0.5f); if (k <= 0) return 0; if (k >= DITH_N) k = DITH_N - 1;
    int thr = (BAYER4[r & 3][c & 3] + (int)(t & 3) * 4 + ((t >> 2) & 1) * 2) & 15;
    return (s_dfr[k] > thr * 16 + 8) ? s_dhi[k] : s_dlo[k];
}
