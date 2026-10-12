#include "stack_hal.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "board_pins.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_mac.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

#define BUS_UART UART_NUM_1
static shal_sync_cb_t s_cb;
static const int __attribute__((unused)) s_pres_gpio[4] = {BOARD_PIN_GPIO_PRES_N, BOARD_PIN_GPIO_PRES_E, BOARD_PIN_GPIO_PRES_S, BOARD_PIN_GPIO_PRES_W};
static bool s_leader;

static void bus_uart_init(void)
{
    uart_config_t c = {.baud_rate = STACK_BAUD, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE,
                       .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    uart_driver_install(BUS_UART, 4096, 4096, 0, NULL, 0);
    uart_param_config(BUS_UART, &c);
    uart_set_pin(BUS_UART, BOARD_PIN_GPIO_RS485_TX, BOARD_PIN_GPIO_RS485_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
}

int shal_bus_read(uint8_t *buf, size_t max, TickType_t to) { return uart_read_bytes(BUS_UART, buf, max, to); }

#ifndef MONO_SIM
/* ------------------------------------------------------------------ hardware */
static void IRAM_ATTR sync_isr(void *arg)
{
    if (s_cb) s_cb(esp_timer_get_time());
}

void shal_init(shal_sync_cb_t cb)
{
    s_cb = cb;
    bus_uart_init();   /* transceiver VCC = LED_LOGIC_3V3: caller powers the rail first */
    for (int i = 0; i < 4; i++) shal_pres_drive(i, false);
    gpio_config_t sc = {.pin_bit_mask = 1ULL << BOARD_PIN_GPIO_FRAME_SYNC, .mode = GPIO_MODE_INPUT,
                        .pull_down_en = 1, .intr_type = GPIO_INTR_POSEDGE};
    gpio_config(&sc);
    gpio_install_isr_service(ESP_INTR_FLAG_IRAM);
    gpio_isr_handler_add(BOARD_PIN_GPIO_FRAME_SYNC, sync_isr, NULL);
}

void shal_bus_write(const uint8_t *d, size_t n)
{
    uart_write_bytes(BUS_UART, d, n);
    uart_wait_tx_done(BUS_UART, pdMS_TO_TICKS(100));
    uart_flush_input(BUS_UART) ; /* drop our own echo (/RE tied low) -- collisions are caught by CRC */
}

void shal_pres_drive(int side, bool high)
{
    gpio_num_t g = s_pres_gpio[side];
    if (high) {
        gpio_set_level(g, 1);
        gpio_set_direction(g, GPIO_MODE_INPUT_OUTPUT);
    } else {
        gpio_set_direction(g, GPIO_MODE_INPUT);
        gpio_pulldown_en(g);
    }
}

bool shal_pres_read(int side) { return gpio_get_level(s_pres_gpio[side]); }

void shal_sync_role(bool leader)
{
    s_leader = leader;
    if (leader) {
        gpio_set_intr_type(BOARD_PIN_GPIO_FRAME_SYNC, GPIO_INTR_DISABLE);
        gpio_set_level(BOARD_PIN_GPIO_FRAME_SYNC, 0);
        gpio_set_direction(BOARD_PIN_GPIO_FRAME_SYNC, GPIO_MODE_OUTPUT);
    } else {
        gpio_set_direction(BOARD_PIN_GPIO_FRAME_SYNC, GPIO_MODE_INPUT);
        gpio_pulldown_en(BOARD_PIN_GPIO_FRAME_SYNC);
        gpio_set_intr_type(BOARD_PIN_GPIO_FRAME_SYNC, GPIO_INTR_POSEDGE);
    }
}

void shal_sync_pulse(void)
{
    gpio_set_level(BOARD_PIN_GPIO_FRAME_SYNC, 1);
    if (s_cb) s_cb(esp_timer_get_time());   /* the leader's own edge */
    esp_rom_delay_us(2);
    gpio_set_level(BOARD_PIN_GPIO_FRAME_SYNC, 0);
}

uint64_t shal_mac(void)
{
    uint8_t m[6] = {0};
    esp_efuse_mac_get_default(m);
    uint64_t v = 0;
    for (int i = 0; i < 6; i++) v = (v << 8) | m[i];
    return v;
}

void shal_report(const char *fmt, ...) { (void)fmt; }

#else
/* ------------------------------------------------------------------ QEMU
 * QEMU's ESP32-S3 model exposes UART0/UART1 only, so the PRES/FRAME_SYNC side-band rides on UART1 as
 * frames with type >= 0xF0 that the host bus model intercepts (they never occupy simulated wire time).
 * Host -> board side-band frames are handled in stack.c's receive path (shal_sim_rx). */
static volatile bool s_pres_in[4];
static volatile uint64_t s_mac_override;
static SemaphoreHandle_t s_wlock;

/* QEMU's UART model does not raise TX-FIFO-empty interrupts, so the driver's TX ring buffer would fill
 * and block forever: write straight into the FIFO (uart_tx_chars) under our own lock to keep frames whole. */
static void sim_write(const uint8_t *d, size_t n)
{
    xSemaphoreTake(s_wlock, portMAX_DELAY);
    while (n) {
        int k = uart_tx_chars(BUS_UART, (const char *)d, n);
        if (k <= 0) { esp_rom_delay_us(20); continue; }
        d += k; n -= k;
    }
    xSemaphoreGive(s_wlock);
}

static uint8_t crc8s(const uint8_t *d, int n)
{
    uint8_t c = 0;
    for (int i = 0; i < n; i++) {
        c ^= d[i];
        for (int k = 0; k < 8; k++) c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1);
    }
    return c;
}

void shal_report(const char *fmt, ...)
{
    uint8_t b[12 + 128];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf((char *)b + 11, 120, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if (n > 119) n = 119;
    b[0] = 0x7E; b[1] = (uint8_t)n; b[2] = 0xF0;
    memset(b + 3, 0, 8);
    b[11 + n] = crc8s(b + 1, 10 + n);
    sim_write(b, 12 + n);                    /* no wire time (host intercepts) */
}

void shal_sim_rx(uint8_t type, const uint8_t *pl, int len)
{
    if (type == 0xF1 && len >= 2 && pl[0] < 4) s_pres_in[pl[0]] = pl[1];
    else if (type == 0xF2) { if (s_cb && !s_leader) s_cb(esp_timer_get_time()); }
    else if (type == 0xF3 && len >= 6) { uint64_t v = 0; for (int i = 0; i < 6; i++) v = (v << 8) | pl[i]; s_mac_override = v; }
}

void shal_init(shal_sync_cb_t cb)
{
    static bool done;
    s_cb = cb;
    if (done) return;
    done = true;
    s_wlock = xSemaphoreCreateMutex();
    bus_uart_init();
    /* deliver every received byte at once (side-band FRAME_SYNC edges must not wait for a FIFO threshold) */
    uart_set_rx_full_threshold(BUS_UART, 1);
    uart_set_rx_timeout(BUS_UART, 1);
    uart_flush_input(BUS_UART);
}

void shal_bus_write(const uint8_t *d, size_t n)
{
    sim_write(d, n);
    /* QEMU's UART is instantaneous: model the wire time (10 bits/byte at 500 kbps = 20 us/byte) */
    uint32_t us = (uint32_t)n * 10u * 1000000u / STACK_BAUD;
    if (us >= 1000) vTaskDelay(pdMS_TO_TICKS(us / 1000)); else esp_rom_delay_us(us);
}

void shal_pres_drive(int side, bool high) { shal_report("P%d%d", side, high ? 1 : 0); }
bool shal_pres_read(int side) { return s_pres_in[side]; }
void shal_sync_role(bool leader) { s_leader = leader; }
void shal_sync_pulse(void)
{
    shal_report("S");
    if (s_cb) s_cb(esp_timer_get_time());
}

uint64_t shal_mac(void)
{
    if (s_mac_override) return s_mac_override;
    uint8_t m[6] = {0};
    esp_efuse_mac_get_default(m);
    uint64_t v = 0;
    for (int i = 0; i < 6; i++) v = (v << 8) | m[i];
    return v;
}
#endif
