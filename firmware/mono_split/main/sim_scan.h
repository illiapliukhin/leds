#pragma once
/* Sim-only scan tap (MONO_SIM). The v13 scan engine builds the exact LCD_CAM DMA sample stream it
 * would clock out on hardware; in QEMU (no LCD_CAM model) the sim backend hands each frame buffer
 * here. A low-priority task decodes the most recent frame every 50 ms exactly like the panel would
 * see it - bits clocked on SDI before each LE, OE_N low time per plane, row address and decoder
 * enable during OE - and streams it as "@G ..." lines on UART0 for the host-side viewers. */
#include <stdbool.h>
#include <stdint.h>

#ifdef MONO_SIM
void sim_scan_note_buffer(const uint16_t *frame, uint32_t gen);
void sim_scan_start(void);
#else
static inline void sim_scan_note_buffer(const uint16_t *frame, uint32_t gen) { (void)frame; (void)gen; }
static inline void sim_scan_start(void) {}
#endif
