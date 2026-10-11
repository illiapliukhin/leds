/* Stacking protocol (see MONO_SPLIT_ARCHITECTURE.md § Stacking ports and § Stacking protocol).
 * Election (lowest MAC) -> token-based PRES discovery -> leader computes grid/rotation -> MAP ->
 * run: leader drives FRAME_SYNC every content frame, followers swap on the edge and phase-lock the
 * scan engine to it. Content: shared-generative (default) or leader-streamed 4-bit RLE tiles. */
#include "stack.h"
#include "patterns.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "console_test.h"
#include "demo.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "matrix_refresh.h"
#include "stack_hal.h"

static const char *TAG = "stack";

#ifdef MONO_SIM
#define T_SETTLE_MS 25      /* QEMU side-band round trip */
#define T_SEEN_MS 110
#define T_TOKEN_MS 450
#define T_ELECT_MS 1500
#define T_LOST_MS 2500
#define T_MEMBER_LOST_MS 1600
#define DEFAULT_FPS 30
#else
#define T_SETTLE_MS 1
#define T_SEEN_MS 6
#define T_TOKEN_MS 20
#define T_ELECT_MS 600
#define T_LOST_MS 600
#define T_MEMBER_LOST_MS 400
#define DEFAULT_FPS 60
#endif
#define MAXB 128                 /* boards per stack (RAM ~6 KB for all tables) */
#define MAXE (MAXB * 2)          /* grid edges: <= 2 per board */

enum { T_HELLO = 1, T_LEADER, T_TOKEN, T_PRESHI, T_SEEN, T_TOKDONE, T_MAP, T_TIME, T_PING, T_PONG, T_TILE };
#define BCAST 0xFFFFFFFFu

typedef struct { uint32_t id; int8_t x, y, rot; bool placed; } tile_t;
typedef struct { uint32_t a; uint8_t as; uint32_t b; uint8_t bs; } edge_t;

static matrix_panel_t *s_panel;
static uint32_t s_id;
static volatile stack_state_t s_state;
static volatile uint32_t s_leader;
static stack_mode_t s_mode = STACK_MODE_GEN;
static volatile int s_demo = -1, s_fps = DEFAULT_FPS;
static SemaphoreHandle_t s_lock, s_txlock;
static uint32_t s_members[MAXB]; static int s_nmem;
static int64_t s_last_seen[MAXB];
static tile_t s_tiles[MAXB]; static int s_ntiles; static int s_W = 1, s_H = 1;   /* canvas in tiles */
static tile_t s_me = {0, 0, 0, 0, true};
static edge_t s_edges[MAXE]; static int s_nedges;
static volatile uint32_t s_frame;             /* content frame number (shared time base) */
static volatile int64_t s_last_leader_msg;
static TaskHandle_t s_render_task;
static esp_timer_handle_t s_sync_timer;
static volatile uint32_t s_swaps, s_rx_bad, s_rx_ok, s_tx_bytes;
static volatile int64_t s_edge_t;
static volatile bool s_abort;
static volatile bool s_foreign;          /* another (higher-ID) leader probed while we discovered: edges suspect */            /* a lower-ID leader appeared while we lead/discover */
/* stream mode */
static uint8_t s_rx_tile[32 * 32]; static uint32_t s_rx_frame; static uint8_t s_rx_got[16]; static int s_rx_n;
static volatile bool s_stream_ready; static uint8_t s_stream_tile[32 * 32];
static volatile uint32_t s_stream_frames, s_stream_bytes;

/* ------------------------------------------------------------------ framing */
static uint8_t crc8(const uint8_t *d, int n)
{
    uint8_t c = 0;
    for (int i = 0; i < n; i++) {
        c ^= d[i];
        for (int k = 0; k < 8; k++) c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1);
    }
    return c;
}

static void put32(uint8_t *p, uint32_t v) { p[0] = v >> 24; p[1] = v >> 16; p[2] = v >> 8; p[3] = v; }
static uint32_t get32(const uint8_t *p) { return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }

/* 0x7E len type src[4] dst[4] payload[len] crc8 */
static void send_msg(uint8_t type, uint32_t dst, const uint8_t *pl, int len)
{
    uint8_t b[12 + 256];
    b[0] = 0x7E; b[1] = (uint8_t)len; b[2] = type;
    put32(b + 3, s_id); put32(b + 7, dst);
    if (len) memcpy(b + 11, pl, len);
    b[11 + len] = crc8(b + 1, 10 + len);
    xSemaphoreTake(s_txlock, portMAX_DELAY);
    shal_bus_write(b, 12 + len);
    s_tx_bytes += 12 + len;
    xSemaphoreGive(s_txlock);
}

typedef struct { uint8_t type; uint32_t src, dst; uint8_t len; uint8_t pl[256]; } msg_t;
static uint8_t s_rb[12 + 256]; static int s_rn;

/* feed bytes; returns true when a valid message is in *m */
static bool parse_byte(uint8_t ch, msg_t *m)
{
    if (s_rn == 0 && ch != 0x7E) return false;
    s_rb[s_rn++] = ch;
    while (s_rn >= 2 && s_rn >= 12 + s_rb[1]) {
        int len = s_rb[1];
        if (crc8(s_rb + 1, 10 + len) == s_rb[11 + len]) {
            m->len = len; m->type = s_rb[2]; m->src = get32(s_rb + 3); m->dst = get32(s_rb + 7);
            memcpy(m->pl, s_rb + 11, len);
            int rest = s_rn - (12 + len);
            memmove(s_rb, s_rb + 12 + len, rest);
            s_rn = rest;
            s_rx_ok++;
            return true;
        }
        s_rx_bad++;
        int k = 1;                                  /* resync on the next 0x7E and re-check */
        while (k < s_rn && s_rb[k] != 0x7E) k++;
        memmove(s_rb, s_rb + k, s_rn - k);
        s_rn -= k;
    }
    return false;
}

static bool recv_msg(msg_t *m, int timeout_ms)
{
    int64_t end = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    uint8_t ch;
    do {
        int64_t left = (end - esp_timer_get_time()) / 1000;
        if (shal_bus_read(&ch, 1, pdMS_TO_TICKS(left > 0 ? left : 0)) == 1) {
            if (parse_byte(ch, m)) {
#ifdef MONO_SIM
                if (m->type >= 0xF0) { shal_sim_rx(m->type, m->pl, m->len); continue; }
#endif
                return true;
            }
        }
    } while (esp_timer_get_time() < end);
    return false;
}

/* ------------------------------------------------------------------ canvas rendering */
static const char *MSG = "ILLIA PLIUKHIN   ";
enum { D_SCROLL = 0, D_BALL, D_PLASMA, D_WIPE, D_VYSH, D_AURORA, D_KINETIC, D_N };
static const char *DNAMES[D_N] = {"scroll", "ball", "plasma", "wipe", "vyshyvanka", "aurora", "kinetic"};
static const int DSECS[D_N] = {12, 8, 8, 6, 28, 16, 18};

static int demo_for_frame(uint32_t f, int fps)
{
    if (s_demo >= 0) return s_demo;
    uint32_t total = 0;
    for (int i = 0; i < D_N; i++) total += DSECS[i];
    uint32_t t = (f / fps) % total;
    for (int i = 0; i < D_N; i++) { if (t < (uint32_t)DSECS[i]) return i; t -= DSECS[i]; }
    return 0;
}

static float tri(float x, float span) { float m = fmodf(x, 2 * span); if (m < 0) m += 2 * span; return m < span ? m : 2 * span - m; }

static bool font_on(int u, int v)   /* font pixel at (col u, row v) of the message */
{
    int len = (int)strlen(MSG);
    if (v < 0 || v > 6 || u < 0) return false;
    int ch = u / 6, cx = u % 6;
    if (ch >= len || cx == 5) return false;
    return (demo_glyph(MSG[ch])[cx] >> v) & 1;
}

/* intensity 0..1 of canvas pixel (X,Y) for frame f */
static float canvas_px(int d, int X, int Y, uint32_t f, int fps, int W, int H)
{
    float t = (float)f / fps;
    switch (d) {
    case D_SCROLL: {
        int s = H >= 64 ? 4 : 2;
        int tw = (int)strlen(MSG) * 6 * s;
        float x0 = W - fmodf(t * 8.0f * s, (float)(tw + W));
        int y0 = (H - 7 * s) / 2;
        float fx = X - x0;
        int u0 = (int)floorf(fx); float fr = fx - u0;
        if (Y < y0) return 0;
        int v = (Y - y0) / s;
        float a = font_on((int)floorf((float)u0 / s), v) ? 1.f : 0.f;
        float b = font_on((int)floorf((float)(u0 + 1) / s), v) ? 1.f : 0.f;
        float base = 0.04f * (0.5f + 0.5f * sinf(X * 0.15f + t));
        float val = a * (1 - fr) + b * fr;
        return val > base ? val : base;
    }
    case D_BALL: {
        float r = H / 9.0f;
        float bx = r + tri(t * 31.0f, W - 2 * r), by = r + tri(t * 23.0f, H - 2 * r);
        float dd = sqrtf((X + 0.5f - bx) * (X + 0.5f - bx) + (Y + 0.5f - by) * (Y + 0.5f - by));
        float cov = r + 0.5f - dd;
        float v = cov > 1 ? 1 : cov < 0 ? 0 : cov;
        for (int k = 1; k <= 6; k++) {   /* trail */
            float tk = t - k * 0.04f;
            float tx = r + tri(tk * 31.0f, W - 2 * r), ty = r + tri(tk * 23.0f, H - 2 * r);
            float d2 = sqrtf((X + 0.5f - tx) * (X + 0.5f - tx) + (Y + 0.5f - ty) * (Y + 0.5f - ty));
            float c2 = (r * 0.7f + 0.5f - d2) * 0.4f * (7 - k) / 7.0f;
            if (c2 > v) v = c2 > 1 ? 1 : c2;
        }
        return v;
    }
    case D_PLASMA: {
        float x = X * 32.0f / H, y = Y * 32.0f / H;
        float v = sinf(x * 0.16f + t * 1.1f) + sinf(y * 0.21f - t * 0.8f) + sinf((x + y) * 0.11f + t * 1.4f) +
                  sinf(sqrtf((x - W * 16.0f / H) * (x - W * 16.0f / H) + (y - 16) * (y - 16)) * 0.25f - t * 1.6f);
        return (v + 4.0f) / 8.0f;
    }
    case D_VYSH:    return pattern_px(PAT_VYSH, X, Y, W, H, t);
    case D_AURORA:  return pattern_px(PAT_AURORA, X, Y, W, H, t);
    case D_KINETIC: return pattern_px(PAT_KINETIC, X, Y, W, H, t);
    case D_WIPE: {
        /* frame-exact sweep: one column per frame across the whole canvas + a row sweep */
        int cx = (int)(f % (uint32_t)(W + 6)) - 3, ry = (int)((f / 2) % (uint32_t)H);
        float v = 0;
        if (X >= cx && X < cx + 3) v = 1;
        if (Y == ry) v = v > 0.5f ? v : 0.55f;
        if (X % 32 == 0 || Y % 32 == 0 || X % 32 == 31 || Y % 32 == 31) v = v > 0.12f ? v : 0.12f;  /* tile frames */
        return v;
    }
    }
    return 0;
}

/* tile pixel (rr,c) of a board at grid (gx,gy) with rotation rot -> canvas (X,Y) */
static void tile_xy(const tile_t *t, int rr, int c, int *X, int *Y)
{
    int bx = t->x * 32, by = t->y * 32;
    switch (t->rot & 3) {
    case 0: *X = bx + c; *Y = by + rr; break;
    case 1: *X = bx + 31 - rr; *Y = by + c; break;
    case 2: *X = bx + 31 - c; *Y = by + 31 - rr; break;
    default: *X = bx + rr; *Y = by + 31 - c; break;
    }
}

static void render_tile(const tile_t *t, uint32_t f, uint8_t *out /*32x32*/)
{
    int fps = s_fps, W = s_W * 32, H = s_H * 32;
    int d = demo_for_frame(f, fps);
    for (int rr = 0; rr < 32; rr++) for (int c = 0; c < 32; c++) {
        int X, Y;
        tile_xy(t, rr, c, &X, &Y);
        float v = canvas_px(d, X, Y, f, fps, W, H);
        int q = (int)(v * 255 + 0.5f);
        out[rr * 32 + c] = (uint8_t)(q > 255 ? 255 : q < 0 ? 0 : q);
    }
}

/* ------------------------------------------------------------------ sync + render */
static void IRAM_ATTR on_sync(int64_t t_us)
{
    s_edge_t = t_us;
    s_frame++;
    matrix_refresh_sync_swap();          /* staged frame -> scan, burst restarts on this edge */
    if (s_render_task) {
        BaseType_t hp = pdFALSE;
        if (xPortInIsrContext()) { vTaskNotifyGiveFromISR(s_render_task, &hp); portYIELD_FROM_ISR(hp); }
        else xTaskNotifyGive(s_render_task);
    }
}

static void render_task(void *arg)
{
    static uint8_t tile[32 * 32];
    while (true) {
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(200));
        uint32_t f = s_frame;
        int64_t lat = esp_timer_get_time() - s_edge_t;
        s_swaps++;
        shal_report("W%lu %ld %d", (unsigned long)f, (long)lat, demo_for_frame(f, s_fps));
        tile_t me;
        xSemaphoreTake(s_lock, portMAX_DELAY); me = s_me; xSemaphoreGive(s_lock);
        if (!me.placed) {
            memset(tile, 0, sizeof(tile));
            for (int i = 0; i < 32; i++) tile[i * 32 + i] = tile[i * 32 + 31 - i] = (f / 15) & 1 ? 120 : 30;  /* "unplaced" X */
        } else if (s_mode == STACK_MODE_STREAM && s_state == STACK_FOLLOW) {
            if (s_stream_ready) { memcpy(tile, s_stream_tile, sizeof(tile)); }
        } else {
            render_tile(&me, f + 1, tile);   /* shown on the next edge */
        }
        matrix_refresh_lock_panel();
        for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) matrix_panel_set_level(s_panel, r, c, tile[r * 32 + c]);
        matrix_refresh_unlock_panel();       /* sync mode: staged until the next FRAME_SYNC edge */
    }
}

static volatile uint32_t s_tcb, s_tcb_done;
static void IRAM_ATTR sync_timer_cb(void *arg) { s_tcb++; shal_sync_pulse(); s_tcb_done++; }

#ifdef MONO_SIM
/* QEMU's systimer does not fire alarms that are already in the past, so a late esp_timer periodic
 * callback stops the timer for good; the sim paces FRAME_SYNC from a high-priority task instead. */
static volatile bool s_sync_run;
static void sync_task(void *arg)
{
    TickType_t w = xTaskGetTickCount();
    uint32_t n = 0;
    while (true) {
        int fps = s_fps;
        TickType_t per = pdMS_TO_TICKS(1000 / fps) + ((n++ % 3) == 0 && fps == 30 ? 1 : 0);   /* 33,34,33 ms */
        vTaskDelayUntil(&w, per);
        if (s_sync_run) sync_timer_cb(NULL);
    }
}
#endif

static void lead_sync(bool on)
{
    shal_sync_role(on);
#ifdef MONO_SIM
    s_sync_run = on;
#else
    if (on) {
        esp_timer_stop(s_sync_timer);
        esp_timer_start_periodic(s_sync_timer, 1000000 / s_fps);
    } else {
        esp_timer_stop(s_sync_timer);
    }
#endif
}

/* ------------------------------------------------------------------ topology */
static int member_idx(uint32_t id)
{
    for (int i = 0; i < s_nmem; i++) if (s_members[i] == id) return i;
    return -1;
}
static void add_member(uint32_t id)
{
    if (member_idx(id) >= 0 || s_nmem >= MAXB) return;
    int i = s_nmem++;
    while (i > 0 && s_members[i - 1] > id) { s_members[i] = s_members[i - 1]; s_last_seen[i] = s_last_seen[i - 1]; i--; }
    s_members[i] = id; s_last_seen[i] = esp_timer_get_time();
}
static void remove_member(uint32_t id)
{
    int i = member_idx(id);
    if (i < 0) return;
    for (; i < s_nmem - 1; i++) { s_members[i] = s_members[i + 1]; s_last_seen[i] = s_last_seen[i + 1]; }
    s_nmem--;
}

static const int DX[4] = {0, 1, 0, -1}, DY[4] = {-1, 0, 1, 0};

/* BFS from the leader: B sits next to A in world direction (as+rotA); B's port bs faces back. */
static void compute_grid(void)
{
    tile_t t[MAXB]; int n = s_nmem;
    for (int i = 0; i < n; i++) { t[i].id = s_members[i]; t[i].placed = false; }
    int li = member_idx(s_id);
    t[li].x = 0; t[li].y = 0; t[li].rot = 0; t[li].placed = true;
    bool changed = true;
    while (changed) {
        changed = false;
        for (int e = 0; e < s_nedges; e++) {
            for (int dir = 0; dir < 2; dir++) {
                uint32_t a = dir ? s_edges[e].b : s_edges[e].a, b = dir ? s_edges[e].a : s_edges[e].b;
                int as = dir ? s_edges[e].bs : s_edges[e].as, bs = dir ? s_edges[e].as : s_edges[e].bs;
                int ia = member_idx(a), ib = member_idx(b);
                if (ia < 0 || ib < 0 || !t[ia].placed || t[ib].placed) continue;
                int wd = (as + t[ia].rot) & 3;
                t[ib].x = t[ia].x + DX[wd]; t[ib].y = t[ia].y + DY[wd];
                t[ib].rot = (int8_t)((((wd + 2) & 3) - bs + 4) & 3);
                t[ib].placed = true; changed = true;
            }
        }
    }
    int minx = 99, miny = 99, maxx = -99, maxy = -99;
    for (int i = 0; i < n; i++) if (t[i].placed) {
        if (t[i].x < minx) minx = t[i].x;
        if (t[i].y < miny) miny = t[i].y;
        if (t[i].x > maxx) maxx = t[i].x;
        if (t[i].y > maxy) maxy = t[i].y;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    for (int i = 0; i < n; i++) { t[i].x -= minx; t[i].y -= miny; s_tiles[i] = t[i]; }
    s_ntiles = n; s_W = maxx - minx + 1; s_H = maxy - miny + 1;
    xSemaphoreGive(s_lock);
}

static void apply_map_self(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_me.placed = false; s_me.id = s_id;
    for (int i = 0; i < s_ntiles; i++) if (s_tiles[i].id == s_id) s_me = s_tiles[i];
    tile_t me = s_me; int W = s_W, H = s_H;
    xSemaphoreGive(s_lock);
    ESP_LOGI(TAG, "tile: %s at (%d,%d) rot %d, canvas %dx%d px", me.placed ? "placed" : "UNPLACED", me.x, me.y, me.rot * 90, W * 32, H * 32);
    shal_report("R %s %08lx %08lx %d %d %d %d %d %d", s_state == STACK_LEAD ? "LEAD" : "FOLLOW", (unsigned long)s_id,
                (unsigned long)s_leader, me.placed, me.x, me.y, me.rot, W, H);
}

#define LCHUNK 60                /* member ids per LEADER message (8-bit length field) */
#define MCHUNK 34                /* tiles per MAP message */
static void send_leader(void)
{
    /* payload: n_total, start, ids[count]  (one or more messages) */
    int st = 0;
    do {
        uint8_t pl[2 + LCHUNK * 4]; int n = 0, c = s_nmem - st > LCHUNK ? LCHUNK : s_nmem - st;
        pl[n++] = (uint8_t)s_nmem; pl[n++] = (uint8_t)st;
        for (int k = 0; k < c; k++) { put32(pl + n, s_members[st + k]); n += 4; }
        send_msg(T_LEADER, BCAST, pl, n);
        st += c;
    } while (st < s_nmem);
}

static void send_map(void)
{
    /* payload: W, H, n_total, start, tiles[count] x 7 bytes */
    xSemaphoreTake(s_lock, portMAX_DELAY);
    int st = 0;
    do {
        uint8_t pl[4 + MCHUNK * 7]; int n = 0, c = s_ntiles - st > MCHUNK ? MCHUNK : s_ntiles - st;
        pl[n++] = (uint8_t)s_W; pl[n++] = (uint8_t)s_H; pl[n++] = (uint8_t)s_ntiles; pl[n++] = (uint8_t)st;
        for (int i = st; i < st + c; i++) {
            put32(pl + n, s_tiles[i].id); n += 4;
            pl[n++] = s_tiles[i].placed ? (uint8_t)s_tiles[i].x : 0xFF; pl[n++] = (uint8_t)s_tiles[i].y; pl[n++] = (uint8_t)s_tiles[i].rot;
        }
        send_msg(T_MAP, BCAST, pl, n);
        st += c;
    } while (st < s_ntiles);
    xSemaphoreGive(s_lock);
}

static void handle_common(const msg_t *m);

/* PRES probe of one of my own ports (token holder) */
static void add_edge(uint32_t a, int as, uint32_t b, int bs)
{
    if (s_nedges >= MAXE) return;
    edge_t e = {a, (uint8_t)as, b, (uint8_t)bs};
    for (int i = 0; i < s_nedges; i++)
        if ((s_edges[i].a == e.b && s_edges[i].as == e.bs && s_edges[i].b == e.a) ||
            (s_edges[i].a == e.a && s_edges[i].as == e.as && s_edges[i].b == e.b)) return;
    s_edges[s_nedges++] = e;
}

static void probe_side(int side)
{
    shal_pres_drive(side, true);
    vTaskDelay(pdMS_TO_TICKS(T_SETTLE_MS));
    uint8_t pl[1] = {(uint8_t)side};
    send_msg(T_PRESHI, BCAST, pl, 1);
    int64_t end = esp_timer_get_time() + T_SEEN_MS * 1000;
    msg_t m;
    while (esp_timer_get_time() < end && !s_abort) {
        if (recv_msg(&m, 10)) handle_common(&m);
    }
    shal_pres_drive(side, false);
    vTaskDelay(pdMS_TO_TICKS(T_SETTLE_MS));
}

static void discover(void)
{
  for (int attempt = 0; ; attempt++) {
    s_state = STACK_DISCOVER;
    s_nedges = 0; s_foreign = false;
    ESP_LOGI(TAG, "discovery: %d members (attempt %d)", s_nmem, attempt + 1);
    bool alive[MAXB] = {0};
    for (int i = 0; i < s_nmem && !s_abort; i++) {
        uint32_t id = s_members[i];
        if (id == s_id) alive[i] = true;
        send_leader();   /* beacon before every member: a merging higher-ID leader hears us and stops probing */
        for (int side = 0; side < 4 && !s_abort; side++) {
            if (id == s_id) { probe_side(side); continue; }
            uint8_t sp[1] = {(uint8_t)side};
            send_msg(T_TOKEN, id, sp, 1);
            int64_t end = esp_timer_get_time() + T_TOKEN_MS * 1000;
            msg_t m; bool done = false;
            while (!done && !s_abort && esp_timer_get_time() < end) {
                if (recv_msg(&m, 10)) {
                    if (m.type == T_TOKDONE && m.src == id) { done = true; alive[i] = true; }
                    else handle_common(&m);
                }
            }
        }
    }
    if (s_abort) return;
    /* drop members that answered no token: they are on another bus segment now (split) or gone */
    for (int i = s_nmem - 1; i >= 0; i--) if (!alive[i]) {
        ESP_LOGW(TAG, "member %08lx silent in discovery -> dropped", (unsigned long)s_members[i]);
        uint32_t gone = s_members[i];
        remove_member(gone);
        for (int k = i; k < s_nmem; k++) alive[k] = alive[k + 1];
    }
    compute_grid();
    int placed = 0; bool clash = false;
    for (int i = 0; i < s_ntiles; i++) {
        if (!s_tiles[i].placed) continue;
        placed++;
        for (int j = 0; j < i; j++)
            if (s_tiles[j].placed && s_tiles[j].x == s_tiles[i].x && s_tiles[j].y == s_tiles[i].y) clash = true;
    }
    if ((placed == s_nmem && !clash && !s_foreign) || attempt >= 5) break;
    ESP_LOGW(TAG, "discovery inconsistent (%d/%d placed%s%s): retry", placed, s_nmem, clash ? ", overlap" : "", s_foreign ? ", foreign leader" : "");
    shal_report("R RETRY %08lx %d %d", (unsigned long)s_id, placed, s_nmem);
    int64_t end = esp_timer_get_time() + (200 + esp_random() % 300) * 1000;
    msg_t m;
    while (esp_timer_get_time() < end && !s_abort) if (recv_msg(&m, 10)) handle_common(&m);
    if (s_abort) return;
  }
    s_state = STACK_LEAD;
    s_leader = s_id;
    send_map();
    vTaskDelay(pdMS_TO_TICKS(5));
    send_map();
    apply_map_self();
    char buf[200]; int k = 0;
    for (int e = 0; e < s_nedges; e++) k += snprintf(buf + k, sizeof(buf) - k, " %04lx.%c-%04lx.%c", (unsigned long)(s_edges[e].a & 0xFFFF),
                                                     "NESW"[s_edges[e].as], (unsigned long)(s_edges[e].b & 0xFFFF), "NESW"[s_edges[e].bs]);
    ESP_LOGI(TAG, "topology: %d edges:%s", s_nedges, buf);
    shal_report("E%s", buf);
    for (int i = 0; i < s_nmem; i++) s_last_seen[i] = esp_timer_get_time();
}

/* messages every state handles */
static void handle_common(const msg_t *m)
{
    if ((s_state == STACK_LEAD || s_state == STACK_DISCOVER) && (m->type == T_LEADER || m->type == T_TIME || m->type == T_MAP) &&
        m->src < s_id) s_abort = true;
    if (s_state == STACK_DISCOVER && m->src > s_id && (m->type == T_LEADER || m->type == T_TOKEN || m->type == T_MAP)) s_foreign = true;
    if (s_state == STACK_DISCOVER && m->type == T_HELLO && member_idx(m->src) < 0) add_member(m->src);
    if (m->src == s_leader) s_last_leader_msg = esp_timer_get_time();
    int mi = member_idx(m->src);
    if (mi >= 0) s_last_seen[mi] = esp_timer_get_time();
    switch (m->type) {
    case T_PRESHI:
        if (m->src != s_id) {
            for (int side = 0; side < 4; side++) if (shal_pres_read(side)) {
                uint8_t pl[6] = {(uint8_t)side, 0, 0, 0, 0, m->pl[0]};
                put32(pl + 1, m->src);
                if (s_state == STACK_DISCOVER) add_edge(m->src, m->pl[0], s_id, side);   /* the bus doesn't echo to the leader */
                else send_msg(T_SEEN, BCAST, pl, 6);
            }
        }
        break;
    case T_SEEN:
        if (s_state == STACK_DISCOVER) {
            add_edge(get32(m->pl + 1), m->pl[5], m->src, m->pl[0]);
            if (member_idx(m->src) < 0) add_member(m->src);
        }
        break;
    case T_TOKEN:
        if (m->dst == s_id) {
            probe_side(m->pl[0]);
            send_msg(T_TOKDONE, m->src, NULL, 0);
        }
        break;
    case T_MAP:
        if (s_state != STACK_LEAD && s_state != STACK_DISCOVER && m->src == s_leader) {
            xSemaphoreTake(s_lock, portMAX_DELAY);
            s_W = m->pl[0]; s_H = m->pl[1]; s_ntiles = m->pl[2];
            int st = m->pl[3], c = (m->len - 4) / 7;
            for (int i = 0; i < c && st + i < MAXB; i++) {
                const uint8_t *p = m->pl + 4 + i * 7;
                tile_t *tt = &s_tiles[st + i];
                tt->id = get32(p); tt->placed = p[4] != 0xFF;
                tt->x = (int8_t)p[4]; tt->y = (int8_t)p[5]; tt->rot = (int8_t)p[6];
            }
            xSemaphoreGive(s_lock);
            if (st + c >= s_ntiles) {                  /* last chunk: map complete */
                s_state = STACK_FOLLOW;
                apply_map_self();
            }
        }
        break;
    case T_TIME:
        if (m->src == s_leader && s_state == STACK_FOLLOW) {
            uint32_t f = get32(m->pl);
            /* frame-number correction for missed/extra edges. TIME(f) can arrive just after edge f+1
             * (the edge is a wire, the message waits for the bus), so a one-frame lead is not an error. */
            int32_t d = (int32_t)(s_frame - f);
            if (d < 0 || d > 1) s_frame = f;
            s_mode = (stack_mode_t)m->pl[5];
            s_demo = (int8_t)m->pl[4];
            if (m->pl[6] && m->pl[6] != s_fps) s_fps = m->pl[6];
        }
        break;
    case T_PING:
        if (m->dst == s_id) {
            uint8_t pl[10];
            put32(pl, s_swaps); put32(pl + 4, s_rx_bad); pl[8] = s_me.placed; pl[9] = 0;
            send_msg(T_PONG, m->src, pl, 10);
        }
        break;
    case T_TILE:
        if (m->dst == s_id && m->len > 6) {
            uint32_t f = get32(m->pl); int ci = m->pl[4], cn = m->pl[5];
            if (f != s_rx_frame) { s_rx_frame = f; memset(s_rx_got, 0, sizeof(s_rx_got)); s_rx_n = 0; }
            /* chunk: offset(2) + RLE bytes */
            int off = (m->pl[6] << 8) | m->pl[7], pos = off;
            for (int i = 8; i < m->len && pos < 1024; i++) {
                int run = (m->pl[i] >> 4) + 1, v = (m->pl[i] & 15) * 17;
                while (run-- && pos < 1024) s_rx_tile[pos++] = (uint8_t)v;
            }
            if (ci < 16 && !s_rx_got[ci]) { s_rx_got[ci] = 1; s_rx_n++; }
            if (s_rx_n == cn) { memcpy(s_stream_tile, s_rx_tile, 1024); s_stream_ready = true; s_stream_frames++; }
        }
        break;
    default:
        break;
    }
}

/* ------------------------------------------------------------------ stream mode (leader) */
static void stream_task(void *arg)
{
    static uint8_t tile[1024];
    static uint8_t chunk[8 + 200];
    while (true) {
        if (s_state != STACK_LEAD || s_mode != STACK_MODE_STREAM) { vTaskDelay(pdMS_TO_TICKS(50)); continue; }
        uint32_t f = s_frame + 2;
        int64_t t0 = esp_timer_get_time();
        tile_t tl[MAXB]; int nt;
        xSemaphoreTake(s_lock, portMAX_DELAY); nt = s_ntiles; memcpy(tl, s_tiles, sizeof(tl)); xSemaphoreGive(s_lock);
        uint32_t bytes = 0;
        for (int i = 0; i < nt; i++) {
            if (tl[i].id == s_id || !tl[i].placed) continue;
            render_tile(&tl[i], f, tile);
            /* 4-bit RLE, split into <=200-byte chunks */
            int nch = 0, pos = 0;
            while (pos < 1024) {
                int n = 8, start = pos;
                while (pos < 1024 && n < 8 + 200) {
                    int v = tile[pos] >> 4, run = 1;
                    while (pos + run < 1024 && run < 16 && (tile[pos + run] >> 4) == v) run++;
                    chunk[n++] = (uint8_t)(((run - 1) << 4) | v);
                    pos += run;
                }
                put32(chunk, f); chunk[4] = (uint8_t)nch; chunk[6] = start >> 8; chunk[7] = start & 0xFF;
                nch++;
                /* chunks are stashed and sent once the count is known */
                static uint8_t store[16][8 + 200]; static int slen[16];
                if (nch <= 16) { memcpy(store[nch - 1], chunk, n); slen[nch - 1] = n; }
                if (pos >= 1024) {
                    for (int k = 0; k < nch && k < 16; k++) { store[k][5] = (uint8_t)nch; send_msg(T_TILE, tl[i].id, store[k], slen[k]); bytes += slen[k] + 12; }
                }
            }
        }
        s_stream_bytes = bytes;
        s_stream_frames++;
        int64_t dt = esp_timer_get_time() - t0;
        shal_report("T %lu %lu", (unsigned long)bytes, (unsigned long)dt);
        vTaskDelay(1);
    }
}

/* ------------------------------------------------------------------ main state machine */
static void stack_task(void *arg)
{
    msg_t m;
    while (true) {
        /* ---- election */
        s_state = STACK_ELECT;
        lead_sync(false);
        s_nmem = 0; add_member(s_id);
        s_leader = 0;
        shal_report("R ELECT %08lx", (unsigned long)s_id);
        int64_t end = esp_timer_get_time() + T_ELECT_MS * 1000, next_hello = esp_timer_get_time() + (esp_random() % 200) * 1000;
        uint32_t join_leader = 0;
        while (esp_timer_get_time() < end && !join_leader) {
            if (esp_timer_get_time() >= next_hello) {
                uint8_t pl[1] = {0};
                send_msg(T_HELLO, BCAST, pl, 1);
                next_hello = esp_timer_get_time() + (150 + esp_random() % 250) * 1000;
            }
            if (recv_msg(&m, 10)) {
                if (member_idx(m.src) < 0) { add_member(m.src); end = esp_timer_get_time() + T_ELECT_MS * 1000 / 2; }
                if ((m.type == T_LEADER || m.type == T_TIME || m.type == T_MAP) && m.src < s_id) join_leader = m.src;
                if (m.type == T_PRESHI || m.type == T_TOKEN) handle_common(&m);
            }
        }
        if (join_leader || s_members[0] != s_id) {
            /* ---- follower */
            s_leader = join_leader ? join_leader : s_members[0];
            s_state = STACK_WAIT;
            s_last_leader_msg = esp_timer_get_time();
            ESP_LOGI(TAG, "follower of %08lx", (unsigned long)s_leader);
            shal_report("R WAIT %08lx %08lx", (unsigned long)s_id, (unsigned long)s_leader);
            uint8_t pl[1] = {1};
            send_msg(T_HELLO, s_leader, pl, 1);
            while (true) {
                if (recv_msg(&m, 20)) {
                    if ((m.type == T_LEADER || m.type == T_TIME) && m.src < s_leader) {   /* a lower leader appeared */
                        s_leader = m.src; s_last_leader_msg = esp_timer_get_time();
                        send_msg(T_HELLO, s_leader, pl, 1);
                    }
                    if (m.type == T_LEADER && m.src == s_leader) {
                        static bool listed;
                        int tot = m.pl[0], st = m.pl[1], c = (m.len - 2) / 4;
                        if (st == 0) listed = false;
                        for (int i = 0; i < c; i++) if (get32(m.pl + 2 + 4 * i) == s_id) listed = true;
                        if (st + c >= tot && !listed) send_msg(T_HELLO, s_leader, pl, 1);
                    }
                    handle_common(&m);
                }
                if (esp_timer_get_time() - s_last_leader_msg > T_LOST_MS * 1000) {
                    ESP_LOGW(TAG, "leader %08lx lost", (unsigned long)s_leader);
                    s_me.placed = false;
                    break;
                }
            }
            continue;
        }
        /* ---- leader */
        s_leader = s_id;
        ESP_LOGI(TAG, "LEADER (lowest id of %d)", s_nmem);
        s_abort = false;
        lead_sync(true);
        discover();
        int64_t next_time = 0, next_ping = 0, next_beacon = 0;
        int ping_i = 0;
        bool redo = false;
        while (!redo) {
            int64_t now = esp_timer_get_time();
            if (now >= next_time) {
                uint8_t pl[7]; put32(pl, s_frame); pl[4] = (uint8_t)s_demo; pl[5] = (uint8_t)s_mode; pl[6] = (uint8_t)s_fps;
                send_msg(T_TIME, BCAST, pl, 7);
                next_time = now + 500000;
            }
            if (now >= next_beacon) {
                send_leader();
                next_beacon = now + 1000000;
            }
            if (now >= next_ping && s_nmem > 1) {
                ping_i = (ping_i + 1) % s_nmem;
                if (s_members[ping_i] == s_id) ping_i = (ping_i + 1) % s_nmem;
                send_msg(T_PING, s_members[ping_i], NULL, 0);
                int per = T_MEMBER_LOST_MS * 1000 / (2 * (s_nmem - 1));   /* every member pinged >= 2x per loss window */
                next_ping = now + (per < 150000 ? per : 150000);
            }
            for (int i = 0; i < s_nmem; i++) {
                if (s_members[i] != s_id && now - s_last_seen[i] > T_MEMBER_LOST_MS * 1000) {
                    ESP_LOGW(TAG, "member %08lx lost -> re-discovery", (unsigned long)s_members[i]);
                    shal_report("L %08lx", (unsigned long)s_members[i]);
                    remove_member(s_members[i]);
                    redo = true;
                    break;
                }
            }
            if (recv_msg(&m, 10)) {
                if ((m.type == T_LEADER || m.type == T_TIME) && m.src != s_id) {
                    if (m.src < s_id) {                    /* merge: the lower leader wins */
                        ESP_LOGW(TAG, "leader %08lx is lower: stepping down", (unsigned long)m.src);
                        lead_sync(false);
                        break;
                    }
                    next_beacon = 0;                       /* tell the other one we're lower */
                }
                if (m.type == T_HELLO && member_idx(m.src) < 0) {
                    ESP_LOGI(TAG, "new board %08lx -> re-discovery", (unsigned long)m.src);
                    add_member(m.src);
                    redo = true;
                }
                if (m.type == T_PONG || m.type == T_HELLO) {
                    int i = member_idx(m.src);
                    if (i >= 0) s_last_seen[i] = now;
                }
                handle_common(&m);
            }
            if (redo) { discover(); redo = false; }
            if (s_abort) {
                ESP_LOGW(TAG, "lower-ID leader present: stepping down");
                lead_sync(false);
                break;
            }
            if (s_leader != s_id) break;
        }
    }
}

esp_err_t stack_start(matrix_panel_t *panel)
{
    if (s_lock) return ESP_ERR_INVALID_STATE;
    s_panel = panel;
    s_lock = xSemaphoreCreateMutex();
    s_txlock = xSemaphoreCreateMutex();
    esp_err_t err = console_display_on();      /* also powers LED_LOGIC_3V3 = THVD1406 VCC */
    if (err != ESP_OK) return err;
    if (s_panel->geometry != MATRIX_PANEL_32X32) matrix_panel_init(s_panel, MATRIX_PANEL_32X32);
    demo_stop();
    vTaskDelay(pdMS_TO_TICKS(20));
    shal_init(on_sync);
#ifdef MONO_SIM
    { msg_t m; shal_report("H"); int64_t e = esp_timer_get_time() + 3000000;   /* host assigns the eFuse-MAC stand-in */
      while (esp_timer_get_time() < e && recv_msg(&m, 50) == false && shal_mac() == 0) {}
      if (shal_mac() == 0) recv_msg(&m, 500); }
#endif
    s_id = (uint32_t)(shal_mac() & 0xFFFFFFFFu);
    s_me.id = s_id; s_me.placed = false;
    ESP_LOGI(TAG, "stack start: id %08lx (MAC %012llx), RS-485 %d bps", (unsigned long)s_id, (unsigned long long)shal_mac(), STACK_BAUD);
    matrix_refresh_set_sync(true, 960 / s_fps);
    const esp_timer_create_args_t ta = {.callback = sync_timer_cb, .name = "fsync", .dispatch_method = ESP_TIMER_TASK};
    esp_timer_create(&ta, &s_sync_timer);
#ifdef MONO_SIM
    xTaskCreatePinnedToCore(sync_task, "fsync", 3072, NULL, configMAX_PRIORITIES - 2, NULL, 1);
#endif
    xTaskCreatePinnedToCore(render_task, "stack_rnd", 4096, NULL, 4, &s_render_task, 1);   /* rendering must never delay edge handling */
    xTaskCreatePinnedToCore(stack_task, "stack", 10240, NULL, 7, NULL, 0);
    xTaskCreatePinnedToCore(stream_task, "stack_str", 6144, NULL, 3, NULL, 0);
    return ESP_OK;
}

void stack_set_mode(stack_mode_t m) { s_mode = m; }
void stack_set_demo(int d) { s_demo = d < D_N ? d : -1; }
void stack_set_fps(int fps)
{
    if (fps < 10 || fps > 60) return;
    s_fps = fps;
    matrix_refresh_set_sync(true, 960 / fps);
    if (s_state == STACK_LEAD) lead_sync(true);
}

void stack_print_status(void)
{
    static const char *st[] = {"off", "elect", "wait", "discover", "LEADER", "follower"};
    printf("stack: id %08lx state %s leader %08lx members %d canvas %dx%d tile (%d,%d) rot %d placed %d mode %s demo %s fps %d frame %lu swaps %lu rx ok %lu bad %lu tx %lu B stream %lu B/frame tcb %lu/%lu\n",
           (unsigned long)s_id, st[s_state], (unsigned long)s_leader, s_nmem, s_W * 32, s_H * 32, s_me.x, s_me.y, s_me.rot * 90, s_me.placed,
           s_mode ? "stream" : "generative", s_demo < 0 ? "cycle" : DNAMES[s_demo], s_fps, (unsigned long)s_frame, (unsigned long)s_swaps,
           (unsigned long)s_rx_ok, (unsigned long)s_rx_bad, (unsigned long)s_tx_bytes, (unsigned long)s_stream_bytes, (unsigned long)s_tcb, (unsigned long)s_tcb_done);
}
