#include "sim_scan.h"

#ifdef MONO_SIM
#include <stdio.h>
#include <string.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "matrix_refresh.h"

static const uint16_t *volatile s_frame;
static volatile uint32_t s_gen;
static volatile uint32_t s_cpu_busy_us;      /* time spent in this decoder (not part of the HW scan) */

void sim_scan_note_buffer(const uint16_t *frame, uint32_t gen)
{
    s_frame = frame;
    s_gen = gen;
}

/* Decode one frame the way the panel hardware sees it. */
typedef struct {
    int row;                 /* decoded from A3..A0 + which decoder was enabled while OE_N was low, -1 = none */
    uint32_t bits[8];        /* 32-bit shift register contents latched at each LE */
    uint16_t on[8];          /* OE_N-low samples following that LE */
    uint8_t n;
} drow_t;

static int decode(const uint16_t *f, uint32_t nrow_samples, drow_t *out)
{
    int rows = 0;
    uint32_t sr = 0;
    int cur = -1;
    for (uint32_t r = 0; r < 32; r++) {
        drow_t *d = &out[r];
        memset(d, 0, sizeof(*d));
        d->row = -1;
        cur = -1;
        const uint16_t *p = f + r * nrow_samples;
        for (uint32_t i = 0; i < nrow_samples; i++) {
            uint16_t s = p[i];
            sr = (sr << 1) | (s & MBUS_SDI);              /* rising PCLK edge shifts SDI in: first bit ends at bit 31 */
            if (s & MBUS_LE) {                            /* latch the shift register */
                if (d->n < 8) { cur = d->n++; d->bits[cur] = sr; d->on[cur] = 0; }
            }
            if (!(s & MBUS_OE_N) && cur >= 0) {
                d->on[cur]++;
                int a = (s >> 3) & 15;
                bool deca = !(s & MBUS_DECA_N), decb = !(s & MBUS_DECB_N);
                d->row = (deca && !decb) ? a : (decb && !deca) ? 16 + a : -2;  /* -2 = both/none on: fault */
            }
        }
        rows++;
    }
    return rows;
}

static void sim_stream_task(void *arg)
{
    (void)arg;
    static drow_t d[32];
    static char line[32 * 80 + 256];
    uint32_t seq = 0, last_frames = matrix_refresh_frame_count();
    int64_t last_t = esp_timer_get_time();
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(50));
        const uint16_t *f = s_frame;
        if (!f) continue;
        uint32_t gen = s_gen;
        decode(f, matrix_refresh_row_samples(), d);
        uint32_t frames = matrix_refresh_frame_count();
        int64_t t = esp_timer_get_time();
        uint32_t fps_x10 = (uint32_t)((frames - last_frames) * 10000000LL / (t - last_t + 1));
        last_frames = frames; last_t = t;
        /* @G seq obs_fps_x10 nominal_hz_x10 gen sample_ns row_samples build_cycles brightness gamma_x100
         *    slots(row0, samples) s0..s7 | 32 x row:w0,w1,..,w7 (hex) [:on0,..,on7 if a row's slots differ] */
        int n = snprintf(line, sizeof(line), "@G %lu %lu %lu %lu %d %lu %lu %u %u",
            (unsigned long)seq++, (unsigned long)fps_x10, (unsigned long)(matrix_refresh_nominal_hz() * 10), (unsigned long)gen,
            MATRIX_SAMPLE_NS, (unsigned long)matrix_refresh_row_samples(), (unsigned long)matrix_refresh_build_cycles(),
            matrix_refresh_get_brightness(), (unsigned)(matrix_refresh_get_gamma() * 100));
        for (int k = 0; k < 8; k++) n += snprintf(line + n, sizeof(line) - n, " %u", d[0].on[k]);
        for (int r = 0; r < 32; r++) {
            n += snprintf(line + n, sizeof(line) - n, " %d", d[r].row);
            for (int k = 0; k < 8; k++) n += snprintf(line + n, sizeof(line) - n, "%c%lx", k ? ',' : ':', (unsigned long)d[r].bits[k]);
            if (memcmp(d[r].on, d[0].on, sizeof(d[0].on)) != 0) {
                for (int k = 0; k < 8; k++) n += snprintf(line + n, sizeof(line) - n, "%c%u", k ? ',' : ':', d[r].on[k]);
            }
        }
        line[n++] = '\n'; line[n] = 0;
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
