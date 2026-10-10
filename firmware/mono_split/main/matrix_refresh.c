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

static const char *TAG = "matrix_refresh";

static matrix_panel_t *s_panel;
static TaskHandle_t s_refresh_task;
static volatile bool s_running;
static volatile uint8_t s_brightness = 64;
static SemaphoreHandle_t s_panel_mutex;

static void row_select(uint8_t row_index)
{
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

static void refresh_task(void *argument)
{
    (void)argument;
    const uint32_t row_period_us =
        (1000000U / MATRIX_TARGET_REFRESH_HZ) / BOARD_MATRIX_ROWS;
    const uint32_t blank_us = 3;
    const uint32_t pm_off_us = 2;

    ESP_LOGI(
        TAG,
        "Refresh task: %d Hz frame, row period %lu us (core %d)",
        MATRIX_TARGET_REFRESH_HZ,
        (unsigned long)row_period_us,
        xPortGetCoreID());

    uint8_t row = 0;
    while (s_running) {
        uint32_t column_bits = 0;
        if (xSemaphoreTake(s_panel_mutex, portMAX_DELAY) == pdTRUE) {
            column_bits = matrix_panel_row_bits(s_panel, row);
            xSemaphoreGive(s_panel_mutex);
        }

        mbi5124_set_blank(true);
        row_disable_all();
        esp_rom_delay_us(pm_off_us);

        row_select(row);
        mbi5124_shift_columns(column_bits);
        mbi5124_latch();
        esp_rom_delay_us(blank_us);

        mbi5124_set_blank(false);

        uint32_t on_us = (row_period_us * s_brightness) / 255U;
        if (on_us > blank_us + pm_off_us) {
            on_us -= blank_us + pm_off_us;
        }
        if (on_us > 0) {
            esp_rom_delay_us(on_us);
        }

        row = (row + 1) % BOARD_MATRIX_ROWS;
    }
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
    if (s_panel_mutex) {
        xSemaphoreGive(s_panel_mutex);
    }
}
