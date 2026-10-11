#include "matrix_refresh.h"

#include <math.h>
#include <string.h>

#include "board_pins.h"
#include "driver/gpio.h"
#include "esp_cpu.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "mbi5124_driver.h"
#include "sim_scan.h"
#ifndef MONO_SIM
#include "esp_lcd_io_i80.h"
#include "esp_lcd_panel_io.h"
#include "esp_rom_gpio.h"
#include "soc/lcd_periph.h"
#endif

static const char *TAG = "matrix_refresh";

/* ---------------------------------------------------------------- layout
 * Per row (samples of 50 ns):
 *   G0  4  guard: OE_N=1, both decoders off, address = row
 *   P0 32  shift plane 0 (decoder of this row enabled, OE_N=1); LE on the last sample
 *   for k = 0..7:  window W_k (fixed, from full-scale slots): OE_N=0 for slot_k(brightness) samples
 *                  from its start; for k<7 the next plane's 32 bits occupy the window's last 31
 *                  samples + 1 LE sample (OE_N=1). PCLK runs continuously: the MBI5124 latches the
 *                  last 32 bits clocked before LE falls, so shifting during OE is harmless.
 *   G1  4  guard: OE_N=1, decoders off
 * Full-scale slot_k = 2^(k+1) samples (LSB 100 ns >= MBI5124 OE min 50 ns).
 */
#define G0 4
#define G1 4
static uint16_t s_win[MATRIX_PLANES];          /* window length per plane (excl. LE sample) */
static uint32_t s_row_samples, s_frame_samples;
static uint16_t s_data_at[MATRIX_PLANES];      /* index of the LE sample that latches plane k */

static void compute_layout(void)
{
    uint32_t n = G0 + 32;                      /* LE for plane 0 at n-1 */
    s_data_at[0] = n - 1;
    for (int k = 0; k < MATRIX_PLANES; k++) {
        uint32_t full = 2u << k;
        if (k < MATRIX_PLANES - 1) {
            s_win[k] = full > 31 ? full : 31;
            n += s_win[k] + 1;
            s_data_at[k + 1] = n - 1;
        } else {
            s_win[k] = full;
            n += s_win[k];
        }
    }
    n += G1;
    s_row_samples = n;
    s_frame_samples = n * MATRIX_ROWS;
}

/* ---------------------------------------------------------------- state */
static matrix_panel_t *s_panel;
static SemaphoreHandle_t s_panel_mutex;
static volatile bool s_running;
static volatile uint8_t s_brightness = 128;
static float s_gamma_val = 2.2f;
static uint8_t s_gamma[256];
static uint16_t *s_buf[3];
static int s_tmpl_br[3] = {-1, -1, -1};      /* brightness each buffer's control bits were built for */
static volatile int s_ready = -1, s_sending = -1;
static volatile uint32_t s_frames, s_gen, s_ready_gen, s_sent_gen, s_build_cycles;
static uint8_t s_levels[MATRIX_ROWS][32];
static TaskHandle_t s_tx_task;
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

static void build_gamma(void)
{
    for (int i = 0; i < 256; i++) {
        float v = powf(i / 255.0f, s_gamma_val) * 255.0f + 0.5f;
        s_gamma[i] = (uint8_t)(v > 255 ? 255 : v);
        if (i && !s_gamma[i] && s_gamma_val > 0) s_gamma[i] = 0; /* keep monotonic, 0 stays 0 */
    }
}

/* control bits (OE/LE/address/decoder) for all rows, for the current brightness */
static void build_template(uint16_t *b)
{
    uint8_t br = s_brightness;
    for (int r = 0; r < MATRIX_ROWS; r++) {
        uint16_t addr = (uint16_t)((r & 15) << 3);
        uint16_t dec_on = (r < 16) ? MBUS_DECB_N : MBUS_DECA_N;          /* active-low: the other one stays 1 */
        uint16_t dec_off = MBUS_DECA_N | MBUS_DECB_N;
        uint16_t *p = b + r * s_row_samples;
        uint32_t i = 0;
        for (int j = 0; j < G0; j++) p[i++] = MBUS_OE_N | dec_off | addr;
        for (int j = 0; j < 32; j++) p[i++] = MBUS_OE_N | dec_on | addr;
        p[i - 1] |= MBUS_LE;
        for (int k = 0; k < MATRIX_PLANES; k++) {
            uint32_t slot = ((2u << k) * br + 127) / 255;
            for (uint32_t j = 0; j < s_win[k]; j++) p[i++] = (j < slot ? 0 : MBUS_OE_N) | dec_on | addr;
            if (k < MATRIX_PLANES - 1) p[i++] = MBUS_OE_N | MBUS_LE | dec_on | addr;
        }
        for (int j = 0; j < G1; j++) p[i++] = MBUS_OE_N | dec_off | addr;
    }
}

/* SDI bits: plane k of row r = bits of gamma(level); bit c goes out in sample LE-c (bit31 first). */
static void build_data(uint16_t *b)
{
    for (int r = 0; r < MATRIX_ROWS; r++) {
        uint16_t *p = b + r * s_row_samples;
        uint8_t g[32];
        for (int c = 0; c < 32; c++) g[c] = s_gamma[s_levels[r][c]];
        for (int k = 0; k < MATRIX_PLANES; k++) {
            uint16_t *le = p + s_data_at[k];
            for (int c = 0; c < 32; c++) {
                uint16_t v = le[-c] & ~MBUS_SDI;
                le[-c] = v | ((g[c] >> k) & 1);
            }
        }
    }
}

static int pick_free(void)
{
    for (int i = 0; i < 3; i++) if (i != s_ready && i != s_sending) return i;
    return -1;
}

static void publish(void)
{
    /* snapshot levels from the panel (caller holds the panel mutex), then build a full frame */
    for (int r = 0; r < MATRIX_ROWS; r++) for (int c = 0; c < 32; c++) s_levels[r][c] = matrix_panel_get_level(s_panel, r, c);
    portENTER_CRITICAL(&s_mux);
    int idx = pick_free();
    portEXIT_CRITICAL(&s_mux);
    if (idx < 0) return;
    uint32_t t0 = esp_cpu_get_cycle_count();
    if (s_tmpl_br[idx] != s_brightness) {        /* control bits only change with brightness */
        build_template(s_buf[idx]);
        s_tmpl_br[idx] = s_brightness;
    }
    build_data(s_buf[idx]);
    s_build_cycles = esp_cpu_get_cycle_count() - t0;
    portENTER_CRITICAL(&s_mux);
    s_ready = idx;
    s_ready_gen = ++s_gen;
    portEXIT_CRITICAL(&s_mux);
}

static int take_next(void)
{
    portENTER_CRITICAL(&s_mux);
    if (s_ready >= 0) { s_sending = s_ready; s_sent_gen = s_ready_gen; s_ready = -1; }
    int i = s_sending;
    portEXIT_CRITICAL(&s_mux);
    return i;
}

/* ---------------------------------------------------------------- backends */
#ifndef MONO_SIM
static esp_lcd_i80_bus_handle_t s_bus;
static esp_lcd_panel_io_handle_t s_io;
static const int s_bus_pins[9] = {
    BOARD_PIN_GPIO_LED_SDI, BOARD_PIN_GPIO_LED_LE, BOARD_PIN_GPIO_LED_OE_N,
    BOARD_PIN_GPIO_ROW_A0, BOARD_PIN_GPIO_ROW_A1, BOARD_PIN_GPIO_ROW_A2, BOARD_PIN_GPIO_ROW_A3,
    BOARD_PIN_GPIO_DEC_A_EN_N, BOARD_PIN_GPIO_DEC_B_EN_N,
};

static esp_err_t hw_init(void)
{
    /* esp_lcd wants 16 valid data pins + DC: point the unused ones at DEC_B_EN_N, then re-route
     * every real pin to its own data signal afterwards (the last connect wins in the GPIO matrix). */
    esp_lcd_i80_bus_config_t bc = {
        .clk_src = LCD_CLK_SRC_DEFAULT,
        .dc_gpio_num = BOARD_PIN_GPIO_DEC_B_EN_N,
        .wr_gpio_num = BOARD_PIN_GPIO_LED_CLK,
        .bus_width = 16,
        .max_transfer_bytes = s_frame_samples * 2,
        .psram_trans_align = 64,
        .sram_trans_align = 4,
    };
    for (int i = 0; i < 16; i++) bc.data_gpio_nums[i] = i < 9 ? s_bus_pins[i] : BOARD_PIN_GPIO_DEC_B_EN_N;
    esp_err_t err = esp_lcd_new_i80_bus(&bc, &s_bus);
    if (err != ESP_OK) return err;
    esp_lcd_panel_io_i80_config_t ic = {
        .cs_gpio_num = -1,
        .pclk_hz = MATRIX_PCLK_HZ,
        .trans_queue_depth = 1,
        .lcd_cmd_bits = 0,
        .lcd_param_bits = 0,
        .dc_levels = {.dc_idle_level = 1, .dc_cmd_level = 1, .dc_dummy_level = 1, .dc_data_level = 1},
    };
    err = esp_lcd_new_panel_io_i80(s_bus, &ic, &s_io);
    if (err != ESP_OK) return err;
    int bus_id = 0;
    for (int i = 0; i < 9; i++) {
        esp_rom_gpio_connect_out_signal(s_bus_pins[i], lcd_periph_i80_signals.buses[bus_id].data_sigs[i], false, false);
    }
    return ESP_OK;
}

static void hw_send(const uint16_t *frame)
{
    /* queue depth 1: blocks until the previous frame is out, so the loop is paced by the hardware */
    esp_lcd_panel_io_tx_color(s_io, -1, frame, s_frame_samples * 2);
}

static void hw_deinit(void)
{
    if (s_io) { esp_lcd_panel_io_del(s_io); s_io = NULL; }
    if (s_bus) { esp_lcd_del_i80_bus(s_bus); s_bus = NULL; }
}
#else
static esp_err_t hw_init(void) { return ESP_OK; }
static void hw_send(const uint16_t *frame)
{
    /* QEMU has no LCD_CAM: the sample stream is built exactly as for the hardware and handed to the
     * sim tap, which decodes it; frame pacing = nominal frame time (approximated with 1 ms ticks). */
    sim_scan_note_buffer(frame, s_sent_gen);
    vTaskDelay(1);
}
static void hw_deinit(void) {}
#endif

static void tx_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "scan engine: LCD_CAM i80 @ %d MHz, %lu samples/row, %lu/frame (%u KB), nominal %.0f Hz, 8 planes BCM",
             MATRIX_PCLK_HZ / 1000000, (unsigned long)s_row_samples, (unsigned long)s_frame_samples,
             (unsigned)(s_frame_samples * 2 / 1024), matrix_refresh_nominal_hz());
    while (s_running) {
        int i = take_next();
        if (i >= 0) {
            hw_send(s_buf[i]);
            s_frames++;
        } else {
            vTaskDelay(1);
        }
    }
    s_tx_task = NULL;
    vTaskDelete(NULL);
}

esp_err_t matrix_refresh_start(matrix_panel_t *panel)
{
    if (s_running) return ESP_ERR_INVALID_STATE;
    compute_layout();
    build_gamma();
    s_panel = panel;
    if (!s_panel_mutex) s_panel_mutex = xSemaphoreCreateMutex();
    for (int i = 0; i < 3; i++) {
        if (!s_buf[i]) s_buf[i] = heap_caps_aligned_calloc(64, 1, s_frame_samples * 2, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
        if (!s_buf[i]) return ESP_ERR_NO_MEM;
    }
    s_ready = s_sending = -1;
    xSemaphoreTake(s_panel_mutex, portMAX_DELAY);
    publish();
    xSemaphoreGive(s_panel_mutex);
    esp_err_t err = hw_init();
    if (err != ESP_OK) { ESP_LOGE(TAG, "i80 init failed: %s", esp_err_to_name(err)); return err; }
    s_running = true;
    if (xTaskCreatePinnedToCore(tx_task, "matrix_tx", 3072, NULL, configMAX_PRIORITIES - 2, &s_tx_task, 1) != pdPASS) {
        s_running = false;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void matrix_refresh_stop(void)
{
    if (!s_running) return;
    s_running = false;
    vTaskDelay(pdMS_TO_TICKS(20));
    hw_deinit();
    /* back to plain GPIO, everything blanked */
    mbi5124_driver_init();
    gpio_set_level(BOARD_PIN_GPIO_DEC_A_EN_N, 1);
    gpio_set_level(BOARD_PIN_GPIO_DEC_B_EN_N, 1);
}

void matrix_refresh_set_brightness(uint8_t level_0_255)
{
    s_brightness = level_0_255;
    if (s_running) { matrix_refresh_lock_panel(); matrix_refresh_unlock_panel(); }
}
uint8_t matrix_refresh_get_brightness(void) { return s_brightness; }

void matrix_refresh_set_gamma(float gamma)
{
    s_gamma_val = gamma;
    build_gamma();
    if (s_running) { matrix_refresh_lock_panel(); matrix_refresh_unlock_panel(); }
}
float matrix_refresh_get_gamma(void) { return s_gamma_val; }

void matrix_refresh_lock_panel(void)
{
    if (s_panel_mutex) xSemaphoreTake(s_panel_mutex, portMAX_DELAY);
}

void matrix_refresh_unlock_panel(void)
{
    if (s_panel && s_buf[0]) publish();
    if (s_panel_mutex) xSemaphoreGive(s_panel_mutex);
}

uint32_t matrix_refresh_frame_count(void) { return s_frames; }
uint32_t matrix_refresh_row_samples(void) { return s_row_samples; }
uint32_t matrix_refresh_frame_samples(void) { return s_frame_samples; }
float matrix_refresh_nominal_hz(void) { return 1e9f / ((float)s_frame_samples * MATRIX_SAMPLE_NS); }
uint32_t matrix_refresh_build_cycles(void) { return s_build_cycles; }
const uint16_t *matrix_refresh_front_buffer(uint32_t *gen)
{
    if (gen) *gen = s_sent_gen;
    return s_sending >= 0 ? s_buf[s_sending] : NULL;
}
