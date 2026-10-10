#include "sim_scan.h"

#ifdef MONO_SIM
#include <stdio.h>
#include <string.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "matrix_refresh.h"

#define SIM_ROWS 32
#define SIM_SLOTS 2

/* Per row: up to two latched column words (BCM planes) and how long OE was low for each. */
typedef struct {
    uint32_t bits[SIM_SLOTS];
    uint32_t on_us[SIM_SLOTS];
    uint8_t n;
} sim_row_t;

static sim_row_t s_live[SIM_ROWS];
static volatile uint8_t s_row;
static uint32_t s_shift;
static uint32_t s_latched;
static int64_t s_oe_t0;
static volatile uint32_t s_rows_scanned;
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

void sim_scan_note_row(uint8_t row)
{
    portENTER_CRITICAL(&s_mux);
    s_row = row % SIM_ROWS;
    s_live[s_row].n = 0;
    s_live[s_row].bits[0] = s_live[s_row].bits[1] = 0;
    s_live[s_row].on_us[0] = s_live[s_row].on_us[1] = 0;
    s_rows_scanned++;
    portEXIT_CRITICAL(&s_mux);
}

void sim_scan_note_shift(uint32_t bits) { s_shift = bits; }

void sim_scan_note_latch(void)
{
    portENTER_CRITICAL(&s_mux);
    s_latched = s_shift;
    sim_row_t *r = &s_live[s_row];
    if (r->n < SIM_SLOTS) {
        r->bits[r->n] = s_latched;
        r->on_us[r->n] = 0;
        r->n++;
    }
    portEXIT_CRITICAL(&s_mux);
}

void sim_scan_note_oe(bool lit)
{
    int64_t now = esp_timer_get_time();
    if (lit) {
        s_oe_t0 = now;
        return;
    }
    if (s_oe_t0 == 0) {
        return;
    }
    portENTER_CRITICAL(&s_mux);
    sim_row_t *r = &s_live[s_row];
    if (r->n > 0) {
        r->on_us[r->n - 1] += (uint32_t)(now - s_oe_t0);
    }
    portEXIT_CRITICAL(&s_mux);
    s_oe_t0 = 0;
}

static void sim_stream_task(void *arg)
{
    (void)arg;
    static sim_row_t snap[SIM_ROWS];
    static char line[SIM_ROWS * 40 + 96];
    uint32_t seq = 0, last_frames = matrix_refresh_frame_count();
    int64_t last_t = esp_timer_get_time();
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(50));
        portENTER_CRITICAL(&s_mux);
        memcpy(snap, s_live, sizeof(snap));
        uint8_t cur_row = s_row;
        portEXIT_CRITICAL(&s_mux);
        uint32_t frames = matrix_refresh_frame_count();
        int64_t t = esp_timer_get_time();
        uint32_t fps_x10 = (uint32_t)((frames - last_frames) * 10000000LL / (t - last_t + 1));
        last_frames = frames;
        last_t = t;
        int n = snprintf(line, sizeof(line), "@F %lu %lu %u", (unsigned long)seq++, (unsigned long)fps_x10, cur_row);
        for (int r = 0; r < SIM_ROWS; r++) {
            n += snprintf(line + n, sizeof(line) - n, " %08lx:%lu:%08lx:%lu",
                (unsigned long)snap[r].bits[0], (unsigned long)snap[r].on_us[0],
                (unsigned long)snap[r].bits[1], (unsigned long)snap[r].on_us[1]);
        }
        line[n++] = '\n';
        line[n] = 0;
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
