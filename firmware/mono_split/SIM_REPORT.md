# mono_electronics power-up simulation (PCB v11b / PR #4)

Two parts: (A) the real firmware booted in Espressif's QEMU for ESP32-S3, and (B) a static, datasheet-based timeline of the board-level power-up. Run A again with `sim/run_qemu.sh`; full log in `sim/qemu_boot_v11.log`.

## A. Firmware in QEMU

Setup: ESP-IDF v5.3.6, `qemu-xtensa` esp_develop_9.0.0_20240606, `-machine esp32s3`, 8 MB flash image. QEMU variant = production code plus `sdkconfig.qemu` (console on UART0 instead of USB-Serial-JTAG, which QEMU does not model) and `-D MONO_SIM=1` (MBI5124 SPI shift stubbed: QEMU has no GPSPI2 for the S3). In that build GPIO44 is left as U0RXD; on the real board it is `ROW_XLAT_OE_N`. QEMU's GPIO block does not latch the OUT/ENABLE registers, so pin levels are taken from the driver's `gpio_config` dump, not from a readback.

### Bugs the simulation found (fixed in this commit)
1. **Boot loop.** `app_main` called `esp_console_init()` and then `esp_console_new_repl_usb_serial_jtag()`, which calls it again → `ESP_ERR_INVALID_STATE` → `ESP_ERROR_CHECK` abort → reboot every ~4 s. This would also have happened on hardware. Fixed: REPL is created first, then help + test commands registered.
2. **Power-sequencing delays were zero.** At the default 100 Hz tick, `pdMS_TO_TICKS(5)` = 0 and `pdMS_TO_TICKS(1)` = 0: LED_EN followed LED_LOGIC_EN after 0.4 ms instead of 5 ms. Fixed with `CONFIG_FREERTOS_HZ=1000`.
3. **Enable-pin glitch.** `gpio_reset_pin()` turns on the ~45 kΩ internal pull-up; against the 100 kΩ external pull-downs (R_EN_PD, R_LOGIC_PD, R_AUD_PD) that lifts LED_EN / LED_LOGIC_EN / AUDIO_EN to ≈2.3 V for a few µs during init. Fixed: the safe level is written first, then `gpio_config()` enables the driver with no pulls.

### Power sequencing (v11b firmware: LED rails on demand)
At boot only the safe-idle step runs: LED_EN=0, LED_LOGIC_EN=0, AUDIO_EN=0, ROW_XLAT_OE_N=1, LED_OE_N=1, DEC_A/B_EN_N=1, ROW_A*=0; RS485_TX/RX, FRAME_SYNC, PRES_N/E/S/W = input + pull-down. **The LED rails stay off** until the first `test <mode>`, `bright <n>` or `display on`; `display off` takes them down again (refresh stopped, OE/decoders blanked, translator off, LED_EN off, 2 ms, LED_LOGIC_EN off). Invalid commands (`test bogus`) and `test off` with the display off do not power anything.

QEMU log, first `test all` (≈21 s after boot):
| t (from step start) | Action | GPIO |
|---|---|---|
| +0 µs | LED_LOGIC_EN = 1 (TPS22917 → LED_LOGIC_3V3: MBI5124s, LV125A, THVD1406) | GPIO21 |
| +5 ms (QEMU shows 5–14 ms; emulated ticks stretch under host load) | LED_EN = 1 → RC 100 k/10 nF → TPS63802 EN (+≈0.45 ms to VIH) | GPIO18 |
| +10 ms after that | ROW_XLAT_OE_N = 0 (decoder enables are still 1 = no row) | GPIO44 |
| then | refresh task, 400 Hz frame, 78 µs row period | |

### GPIO states
| Pin | Hardware at reset (datasheet table 2-1 + board) | After `power_seq_init()` |
|---|---|---|
| GPIO0 strap | WPU + R_BOOT0 10 k to 3V3 → SPI boot | untouched (input) |
| GPIO3 strap (PRES_N) | input; JTAG-source strap is ignored unless the eFuse is burned | input + pull-down |
| GPIO45 / GPIO46 straps | WPD, not connected | untouched |
| GPIO18 LED_EN | input; R_EN_PD 100 k → **0**. Datasheet: 60 µs high glitch at power-up (see risk R3) | output 0, no pull |
| GPIO21 LED_LOGIC_EN | floating + R_LOGIC_PD 100 k + TPS22917 internal 750 k → **0** | output 0 |
| GPIO6 AUDIO_EN | R_AUD_PD 100 k → **0** (60 µs low glitch, harmless) | output 0 |
| GPIO44 ROW_XLAT_OE_N | U0RXD WPU + R_XOE 10 k to AON → **1 = translator off** | output 1 |
| GPIO16 LED_OE_N | R_OE_PU 47 k to AON → 1 (blank); 60 µs low glitch while the LED_LOGIC rail is still off → no effect | output 1 |
| GPIO41/42 DEC_x_EN_N | behind the translator, which is off; R_ENA/R_ENB 47 k to LED_4V1 | output 1 |
| GPIO34 RS485_TX | input (transceiver unpowered) | input + pull-down |

### I2C with the IMU and gauge absent
`BMI270 not detected: ESP_ERR_INVALID_STATE` (both 0x68 and 0x69 tried), `MAX17048 not detected at 0x36`, then the scan of 0x08–0x77 reports 0 devices and boot carries on. QEMU has no S3 I2C controller, so every probe times out after 50 ms (≈6.5 s for the scan). On hardware, absent devices NACK and the scan takes milliseconds. Nothing hangs and nothing aborts.

### Console test modes (UART in QEMU, USB-CDC on hardware)
`help`, `display [on|off]`, `panel 20|32`, `test off|all|row|col|checker|scroll|pixel x y v`, `bright [0-255]` all respond. An unknown mode returns an error code without crashing. Log excerpt:
```
mono>  test checker
Test pattern: checkerboard
mono>  bright 64
Brightness set to 64
mono>  panel 32
Panel geometry: 32x32
mono>  test bogus
Unknown test mode
Command returned non-zero error code: 0x1 (ERROR)
```

## B. Static board power-up timeline (datasheet values)

| Stage | Part | What happens | Time (datasheet) |
|---|---|---|---|
| 1 | VBUS 5 V | J_USB → U_ESD → C_USB1 100 n + C_CHG_IN 10 µ (10.1 µF ≈ the USB 10 µF limit) | — |
| 2 | BQ25185 | VIN valid → SYS regulated at 4.5 V (VSYS_REG), input current limit (ILIM, R_ILIM 18 k), charges BAT_RAW; with no VBUS, BAT→SYS via its FET (≤3.1 A) | power-path, about 1 ms class |
| 3 | TLV75733P (v11b, 1 A) | SYS → AON_3V3, always on (EN tied to IN), built-in soft start, 22 µF bulk at the ESP32 | monotonic soft start, sub-ms class (TI does not specify tSTR as a single number) |
| 4 | ESP32-S3 | CHIP_PU RC (R_CHIP_PU 10 k / C_CHIP_PU) releases after AON is stable; ROM → bootloader → app_main ≈ 0.1–0.3 s | |
| 5 | TPS22917 (LED_LOGIC) | GPIO21 → ON, CT open | tON 120 µs, tR 65 µs @ 3.6 V |
| 6 | TPS63802 | GPIO18 → R_EN_SER1 100 k / C_EN1 10 nF → EN, +5 ms after stage 5 | RC ≈ 0.45 ms to VIH 1.2 V, then Tdelay 321 µs + current-limit ramp 224 µs, then charges 2 × 22 µF |
| 7 | SN74LVC8T245 | /OE low, +10 ms after stage 6 | — |
| — | TPS22917 (AUDIO) | GPIO6, only when audio is used | same as stage 5 |

## Risks
- **R1 — AON headroom (FIXED in v11b).** TPS7A2033 (300 mA) replaced by TLV75733PDBVR (1 A, current limit ≥1.2 A, same SOT-23-5 pinout) plus 22 µF at the ESP32. Remaining trade-offs: dropout 180/255 mV typ/max at 600 mA, so AON stays regulated during radio bursts down to VBAT ≈ 3.56 V (≈3.36 V at 150 mA average); ground current ≤ 33 µA vs ~6.5 µA before (+≈27 µA in deep sleep, ≈0.65 mAh/day); dissipation on USB power (4.5 V SYS) at 250 mA average ≈ 0.3 W → +30…70 °C depending on copper (RθJA 100.8 °C/W EVM, 231 °C/W JEDEC). A buck-boost would remove the dropout limit if low-battery radio use matters.
- **R2 — LED_LOGIC inrush on AON (low).** CT open gives tR ≈ 65 µs into ≈1.7 µF, about 90 mA, now from a 1 A LDO with 22 µF bulk — negligible.
- **R3 — GPIO18 power-up glitch (FIXED in v11b).** 100 k/10 nF RC at the TPS63802 EN: the 60 µs pulse reaches ≈0.19 V (VIL 0.4 V).
- **R4 — Back-powering (handled).** RS485_TX/FRAME_SYNC/PRES are inputs while LED_LOGIC_3V3 is off (THVD1406 VCC). Firmware must keep TX as input before turning that rail off. LV125A and LVC8T245 have Ioff/VCC isolation. The 74HC154s sit behind the translator on LED_4V1. The MBI5124 inputs come from the LV125A on the same rail. I2C pull-ups go to AON, and the gauge runs from BAT_RAW: with AON off it sees SDA/SCL low and goes to sleep after 2.5 s (by design, it wakes when the bus comes back).
- **R5 — Battery inrush into LED_4V1 (low).** 44 µF charged during the 224 µs current-limit ramp ≈ 0.8 A from BAT through J_BAT (PicoBlade, 1 A/contact). Within ratings. Do not add more output capacitance without slowing the start.
- **R6 — LED rails at boot (FIXED).** Rails are now on demand only.
- **R7 — USB VBUS capacitance.** 10.1 µF is at the USB 2.0 10 µF limit. Do not increase C_CHG_IN.

## v12 — 32×32 matrix demo in QEMU with a virtual board

**Firmware.** `matrix_panel` now holds two bit planes (4 grey levels). `matrix_refresh` scans 32 rows at a 400 Hz target. For each row it selects the row (ROW_A0..A3 + DEC_A/B_EN_N), then for each plane it shifts 32 column bits to the MBI5124 chain, pulses LE, and drives OE_N low for 1/3 (plane 0) or 2/3 (plane 1) of the row's on-time (binary-code modulation). `demo.c` renders at 25 fps: `smiley`, `logo` (star + "LED"), `scroll` ("ILLIA"), `ball`, `life`, `ring`, `plasma` and `tilt` (the IMU is mocked in QEMU). New console command: `demo <name>|cycle|stop`. It powers the LED rails on demand, the same way as `test`.

**What's real and what's sim-hooked.** QEMU's ESP32-S3 model doesn't expose pin levels or GPSPI2, so `sim_scan.c` (MONO_SIM builds only; the hooks are empty inlines in production) taps the low-level drivers at `row_select()`, `mbi5124_shift_columns()`, `mbi5124_latch()` and `mbi5124_set_blank()`. From those calls it records each row's latched column words and the measured OE-low time. Every 50 ms it prints a snapshot of the last full scan as an `@F seq fps×10 cur_row  b0:on0:b1:on1 ×32` line on UART0. The GPIO writes still go to the real pins; only the SPI shift itself is stubbed in the sim.

**Virtual board.** `sim/matrix/virtual_board.py` (pygame) connects to QEMU's UART over TCP. Each LED's brightness is the time OE was low with its bit set, divided by the row period. Persistence is modelled with a 40 ms exponential filter. A side panel shows the scan FPS, the current row and decoder, the row's peak current and the average current. Current is estimated at about 10.2 mA per column (MBI5124 at 1.24 V/1.82 kΩ ×15).

**Measured.** The scan runs at about 260–300 Hz in QEMU (the 400 Hz target is QEMU-paced) and the stream at about 16–20 snapshots/s. The worst row peak (plasma or a full ring row) is about 320 mA, and the average LED current is 3–100 mA depending on the demo.

Run: `/workspace/sim/run_matrix_sim.sh [--record]` (copy in `sim/matrix/`).
