#pragma once
/* Stacking-port hardware abstraction: RS-485 (THVD1406 on UART1, GPIO34 TX / GPIO33 RX, 500 kbps),
 * per-side PRES lines (N/E/S/W = GPIO3/47/35/26) and the shared FRAME_SYNC (GPIO48).
 * MONO_SIM: UART1 is the same driver (QEMU routes it to a TCP socket that the host RS-485 bus model
 * serves); PRES/FRAME_SYNC levels travel as side-band frames on the same UART (QEMU cannot drive GPIO inputs). */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"

#define STACK_BAUD 500000            /* THVD1406 max data rate */
enum { SIDE_N = 0, SIDE_E, SIDE_S, SIDE_W };

typedef void (*shal_sync_cb_t)(int64_t t_us);

void shal_init(shal_sync_cb_t cb);
void shal_bus_write(const uint8_t *data, size_t len);     /* returns after the bytes are on the wire */
int shal_bus_read(uint8_t *buf, size_t max, TickType_t to);
void shal_pres_drive(int side, bool high);                 /* high = push-pull 1, false = input + pull-down */
bool shal_pres_read(int side);
void shal_sync_role(bool leader);                          /* leader drives FRAME_SYNC, others listen */
void shal_sync_pulse(void);                                /* leader: one rising edge (~2 us pulse) */
uint64_t shal_mac(void);
void shal_report(const char *fmt, ...);
#ifdef MONO_SIM
void shal_sim_rx(uint8_t type, const uint8_t *pl, int len);   /* host side-band frames (type >= 0xF1) */
#endif                    /* sim side-band telemetry (no-op on HW) */
