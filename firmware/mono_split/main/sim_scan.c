#include "sim_scan.h"

#ifdef MONO_SIM
#include <stdio.h>
#include <string.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "matrix_refresh.h"

#define SIM_ROWS 32

/* One complete scan: per row the two latched column words, the commanded OE slot (timer-based,
 * nominal) and the measured OE-low time; all rows belong to framebuffer generation `gen`. */
typedef struct {
    uint32_t bits[SIM_ROWS][2];
    uint16_t slot[SIM_ROWS][2];
    uint16_t meas[SIM_ROWS][2];
    uint8_t n[SIM_ROWS];
    uint32_t gen;
    uint32_t rows_seen;
} scan_t;

static scan_t s_live, s_done;
static volatile bool s_done_valid;
static volatile uint32_t s_done_seq;
static uint8_t s_row;
static uint32_t s_shift;
static int64_t s_oe_t0, s_row_t_prev;
/* row-period statistics since the last emit */
static int64_t s_rp_min = 1 << 30, s_rp_max, s_rp_sum, s_rp_sq;
static uint32_t s_rp_n;
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

void sim_scan_note_frame(uint32_t gen)
{
    /* called before row 0: the previous scan is complete -> publish it if it was whole */
    portENTER_CRITICAL(&s_mux);
    if (s_live.rows_seen == SIM_ROWS) {
        memcpy(&s_done, &s_live, sizeof(s_done));
        s_done_valid = true;
        s_done_seq++;
    }
    memset(&s_live, 0, sizeof(s_live));
    s_live.gen = gen;
    portEXIT_CRITICAL(&s_mux);
}

void sim_scan_note_row(uint8_t row)
{
    int64_t now = esp_timer_get_time();
    portENTER_CRITICAL(&s_mux);
    if (s_row_t_prev) {
        int64_t p = now - s_row_t_prev;
        if (p < s_rp_min) s_rp_min = p;
        if (p > s_rp_max) s_rp_max = p;
        s_rp_sum += p; s_rp_sq += p * p; s_rp_n++;
    }
    s_row_t_prev = now;
    s_row = row % SIM_ROWS;
    s_live.n[s_row] = 0;
    s_live.rows_seen++;
    portEXIT_CRITICAL(&s_mux);
}

void sim_scan_note_shift(uint32_t bits) { s_shift = bits; }

void sim_scan_note_latch(void)
{
    portENTER_CRITICAL(&s_mux);
    uint8_t k = s_live.n[s_row];
    if (k < 2) {
        s_live.bits[s_row][k] = s_shift;
        s_live.slot[s_row][k] = 0;
        s_live.meas[s_row][k] = 0;
        s_live.n[s_row] = k + 1;
    }
    portEXIT_CRITICAL(&s_mux);
}

void sim_scan_note_slot(uint32_t us)
{
    uint8_t k = s_live.n[s_row];
    if (k) s_live.slot[s_row][k - 1] = (uint16_t)us;
}

void sim_scan_note_oe(bool lit)
{
    int64_t now = esp_timer_get_time();
    if (lit) { s_oe_t0 = now; return; }
    if (!s_oe_t0) return;
    portENTER_CRITICAL(&s_mux);
    uint8_t k = s_live.n[s_row];
    if (k) s_live.meas[s_row][k - 1] += (uint16_t)(now - s_oe_t0);
    portEXIT_CRITICAL(&s_mux);
    s_oe_t0 = 0;
}

static void sim_stream_task(void *arg)
{
    (void)arg;
    static scan_t snap;
    static char line[SIM_ROWS * 48 + 160];
    uint32_t last_seq = 0, last_frames = matrix_refresh_frame_count(), out = 0;
    int64_t last_t = esp_timer_get_time();
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(50));
        portENTER_CRITICAL(&s_mux);
        bool fresh = s_done_valid && s_done_seq != last_seq;
        if (fresh) { memcpy(&snap, &s_done, sizeof(snap)); last_seq = s_done_seq; }
        int64_t mn = s_rp_min, mx = s_rp_max, sum = s_rp_sum, sq = s_rp_sq; uint32_t n = s_rp_n;
        s_rp_min = 1 << 30; s_rp_max = s_rp_sum = s_rp_sq = 0; s_rp_n = 0;
        uint8_t cur = s_row;
        portEXIT_CRITICAL(&s_mux);
        if (!fresh) continue;
        uint32_t frames = matrix_refresh_frame_count();
        int64_t t = esp_timer_get_time();
        uint32_t fps_x10 = (uint32_t)((frames - last_frames) * 10000000LL / (t - last_t + 1));
        last_frames = frames; last_t = t;
        uint32_t mean_x10 = n ? (uint32_t)(sum * 10 / n) : 0;
        uint32_t var_x100 = n ? (uint32_t)((sq * 100 / n) - (int64_t)mean_x10 * mean_x10) : 0;
        /* @F seq fps_x10 cur_row gen rp_min rp_max rp_mean_x10 rp_var_x100 | 32 x b0:slot0:meas0:b1:slot1:meas1 */
        int k = snprintf(line, sizeof(line), "@F %lu %lu %u %lu %lld %lld %lu %lu", (unsigned long)out++, (unsigned long)fps_x10, cur,
            (unsigned long)snap.gen, (long long)(n ? mn : 0), (long long)mx, (unsigned long)mean_x10, (unsigned long)var_x100);
        for (int r = 0; r < SIM_ROWS; r++) {
            k += snprintf(line + k, sizeof(line) - k, " %lx:%u:%u:%lx:%u:%u", (unsigned long)snap.bits[r][0], snap.slot[r][0], snap.meas[r][0],
                (unsigned long)snap.bits[r][1], snap.slot[r][1], snap.meas[r][1]);
        }
        line[k++] = '\n'; line[k] = 0;
        fputs(line, stdout);
        fflush(stdout);
    }
}

void sim_scan_start(void)
{
    static bool started;
    if (!started) {
        started = true;
        xTaskCreatePinnedToCore(sim_stream_task, "sim_scan", 4096, NULL, 2, NULL, 0);
    }
}
#endif
