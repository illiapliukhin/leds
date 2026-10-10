#pragma once
/* Sim-only scan tap. QEMU's ESP32-S3 GPIO/SPI models do not expose pin levels, so the
 * low-level drivers report what they put on the pins: row address (row_select), the 32
 * column bits shifted into the MBI5124 chain, the LE latch, and the OE_N low time.
 * A low-priority task streams one snapshot of the last full scan per ~50 ms on the console
 * UART as "@F ..." lines for the host-side virtual board (sim/virtual_board.py).
 * In non-MONO_SIM builds all hooks compile to nothing. */
#include <stdbool.h>
#include <stdint.h>

#ifdef MONO_SIM
void sim_scan_note_row(uint8_t row);
void sim_scan_note_shift(uint32_t bits);
void sim_scan_note_latch(void);
void sim_scan_note_oe(bool lit);
void sim_scan_note_frame(uint32_t gen);
void sim_scan_note_slot(uint32_t us);
void sim_scan_start(void);
#else
static inline void sim_scan_note_row(uint8_t row) { (void)row; }
static inline void sim_scan_note_shift(uint32_t bits) { (void)bits; }
static inline void sim_scan_note_latch(void) {}
static inline void sim_scan_note_oe(bool lit) { (void)lit; }
static inline void sim_scan_note_frame(uint32_t gen) { (void)gen; }
static inline void sim_scan_note_slot(uint32_t us) { (void)us; }
static inline void sim_scan_start(void) {}
#endif
