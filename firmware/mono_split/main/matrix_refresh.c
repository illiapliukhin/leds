#include "matrix_refresh.h"

#include "board_pins.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "esp_rom_sys.h"
#include "mbi5124_driver.h"
#include "sim_scan.h"

static const char *TAG = "matrix_refresh";

static matrix_panel_t *s_panel;
static TaskHandle_t s_refresh_task;
static volatile bool s_running;
static volatile uint8_t s_brightness = 64;
static SemaphoreHandle_t s_panel_mutex;
static volatile uint32_t s_frames;

uint32_t matrix_refresh_frame_count(void)
{
    return s_frames;
}

static void row_select(uint8_t row_index)
{
    sim_scan_note_row(row_index);
    uint8_t address = row_index & 0x0F;
    gpio_set_level(BOARD_PIN_GPIO_ROW_A0, (address >> 0) & 1);
    gpio_set_level(BOARD_PIN_GPIO_ROW_A1, (address >> 1) & 1);
    gpio_set_level(BOARD_PIN_GPIO_ROW_A2, (address >> 2) & 1);
    gpio_set_level(BOARD_PIN_GPIO_ROW_A3, (address >> 3) & 1);

    if (row_index < 16) {
        gpio_set_level(BOARD_PIN_GPIO_DEC_A_EN_N, BOARD_ACTIVE_DEC_EN_N);
        gpio_set_level(BOARD_PIN_GPIO_DEC_B_EN_N, 1);
    } else {
        gpio_set_level(BOARD_PIN_GPIO_DEC_A_EN_N, 1);
        gpio_set_level(BOARD_PIN_GPIO_DEC_B_EN_N, BOARD_ACTIVE_DEC_EN_N);
    }
}

static void row_disable_all(void)
{
    gpio_set_level(BOARD_PIN_GPIO_DEC_A_EN_N, 1);
    gpio_set_level(BOARD_PIN_GPIO_DEC_B_EN_N, 1);
}

/* Double buffer: writers edit s_panel under s_panel_mutex, and unlock publishes a copy into the
 * back buffer. The scan task swaps front/back only at a frame boundary (before row 0), so a
 * frame is never torn and the scan loop never waits on the writers' mutex mid-frame. */
typedef struct {
    uint32_t plane[2][32];
    uint32_t gen;
} scan_frame_t;
static scan_frame_t s_frames_buf[2];
static volatile int s_front;
static volatile bool s_pending;
static volatile uint32_t s_gen;
static portMUX_TYPE s_swap_mux = portMUX_INITIALIZER_UNLOCKED;

static void publish(const matrix_panel_t *panel)
{
    portENTER_CRITICAL(&s_swap_mux);
    scan_frame_t *back = &s_frames_buf[s_front ^ 1];
    for (int r = 0; r < 32; r++) {
        back->plane[0][r] = matrix_panel_row_plane(panel, r, 0);
        back->plane[1][r] = matrix_panel_row_plane(panel, r, 1);
    }
    back->gen = ++s_gen;
    s_pending = true;
    portEXIT_CRITICAL(&s_swap_mux);
}

static inline void wait_until(int64_t t)
{
    while (esp_timer_get_time() < t) {
    }
}

static void refresh_task(void *argument)
{
    (void)argument;
    const int64_t row_period_us = (1000000 / MATRIX_TARGET_REFRESH_HZ) / BOARD_MATRIX_ROWS;
    const int64_t guard_us = 3; /* OE high around address change and latch (anti-ghosting) */

    ESP_LOGI(TAG, "Refresh task: %d Hz frame, row period %lld us, timer-paced, double-buffered (core %d)",
        MATRIX_TARGET_REFRESH_HZ, (long long)row_period_us, xPortGetCoreID());

    uint8_t row = 0;
    int64_t row_t0 = esp_timer_get_time();
    const scan_frame_t *f = &s_frames_buf[s_front];
    while (s_running) {
        if (row == 0) {
            portENTER_CRITICAL(&s_swap_mux);
            if (s_pending) {
                s_front ^= 1;
                s_pending = false;
            }
            f = &s_frames_buf[s_front];
            portEXIT_CRITICAL(&s_swap_mux);
            sim_scan_note_frame(f->gen);
        }
        /* Fixed time grid: every row gets exactly row_period_us, independent of loop speed. */
        int64_t now = esp_timer_get_time();
        if (now - row_t0 > 4 * row_period_us) {
            row_t0 = now; /* fell far behind (debugger/IRQ storm): resync, don't burst */
        }
        uint32_t on_us = (uint32_t)((row_period_us - 4 * guard_us) * s_brightness / 255);
        uint32_t slot[2] = {on_us / 3, on_us - on_us / 3};

        /* Order: blank (OE_N high) -> decoders off -> new address -> shift -> LE -> OE low. */
        mbi5124_set_blank(true);
        row_disable_all();
        row_select(row);
        int64_t t = row_t0 + guard_us;
        for (int plane = 0; plane < 2; plane++) {
            mbi5124_shift_columns(f->plane[plane][row]);
            mbi5124_latch();
            wait_until(t);
            sim_scan_note_slot(slot[plane]);
            if (slot[plane] && f->plane[plane][row]) {
                mbi5124_set_blank(false);
                wait_until(t + slot[plane]);
                mbi5124_set_blank(true);
            }
            t += slot[plane] + guard_us;
        }
        row_t0 += row_period_us;
        wait_until(row_t0);
        row = (row + 1) % BOARD_MATRIX_ROWS;
        if (row == 0) {
            s_frames++;
        }
    }
    mbi5124_set_blank(true);
    vTaskDelete(NULL);
}

esp_err_t matrix_refresh_start(matrix_panel_t *panel)
{
    if (s_running) {
        return ESP_ERR_INVALID_STATE;
    }
    s_panel = panel;
    s_panel_mutex = xSemaphoreCreateMutex();
    if (s_panel_mutex == NULL) {
        return ESP_ERR_NO_MEM;
    }
    publish(panel);
    s_running = true;
    BaseType_t created = xTaskCreatePinnedToCore(
        refresh_task,
        "matrix_refresh",
        4096,
        NULL,
        configMAX_PRIORITIES - 2,
        &s_refresh_task,
        1);
    if (created != pdPASS) {
        s_running = false;
        vSemaphoreDelete(s_panel_mutex);
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void matrix_refresh_stop(void)
{
    if (!s_running) {
        return;
    }
    s_running = false;
    vTaskDelay(pdMS_TO_TICKS(20));
    mbi5124_set_blank(true);
    row_disable_all();
    if (s_panel_mutex) {
        vSemaphoreDelete(s_panel_mutex);
        s_panel_mutex = NULL;
    }
}

void matrix_refresh_set_brightness(uint8_t level_0_255)
{
    s_brightness = level_0_255;
}

uint8_t matrix_refresh_get_brightness(void)
{
    return s_brightness;
}

void matrix_refresh_lock_panel(void)
{
    if (s_panel_mutex) {
        xSemaphoreTake(s_panel_mutex, portMAX_DELAY);
    }
}

void matrix_refresh_unlock_panel(void)
{
    if (s_panel) {
        publish(s_panel);
    }
    if (s_panel_mutex) {
        xSemaphoreGive(s_panel_mutex);
    }
}
