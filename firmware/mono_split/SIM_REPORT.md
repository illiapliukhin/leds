# mono_electronics power-up simulation (PCB v11 / PR #4)

Two parts: (A) the real firmware booted in Espressif's QEMU for ESP32-S3, and (B) a static, datasheet-based timeline of the board-level power-up. Run A again with `sim/run_qemu.sh`; full log in `sim/qemu_boot_v11.log`.

## A. Firmware in QEMU

Setup: ESP-IDF v5.3.6, `qemu-xtensa` esp_develop_9.0.0_20240606, `-machine esp32s3`, 8 MB flash image. QEMU variant = production code plus `sdkconfig.qemu` (console on UART0 instead of USB-Serial-JTAG, which QEMU does not model) and `-D MONO_SIM=1` (MBI5124 SPI shift stubbed: QEMU has no GPSPI2 for the S3). In that build GPIO44 is left as U0RXD; on the real board it is `ROW_XLAT_OE_N`. QEMU's GPIO block does not latch the OUT/ENABLE registers, so pin levels are taken from the driver's `gpio_config` dump, not from a readback.

### Bugs the simulation found (fixed in this commit)
1. **Boot loop.** `app_main` called `esp_console_init()` and then `esp_console_new_repl_usb_serial_jtag()`, which calls it again → `ESP_ERR_INVALID_STATE` → `ESP_ERROR_CHECK` abort → reboot every ~4 s. This would also have happened on hardware. Fixed: REPL is created first, then help + test commands registered.
2. **Power-sequencing delays were zero.** At the default 100 Hz tick, `pdMS_TO_TICKS(5)` = 0 and `pdMS_TO_TICKS(1)` = 0: LED_EN followed LED_LOGIC_EN after 0.4 ms instead of 5 ms. Fixed with `CONFIG_FREERTOS_HZ=1000`.
3. **Enable-pin glitch.** `gpio_reset_pin()` turns on the ~45 kΩ internal pull-up; against the 100 kΩ external pull-downs (R_EN_PD, R_LOGIC_PD, R_AUD_PD) that lifts LED_EN / LED_LOGIC_EN / AUDIO_EN to ≈2.3 V for a few µs during init. Fixed: the safe level is written first, then `gpio_config()` enables the driver with no pulls.

### Power sequencing (from the log, after the fixes)
| t (from step start) | Action | GPIO |
|---|---|---|
| boot +~0.16 s | all rails held off, matrix blanked: LED_EN=0, LED_LOGIC_EN=0, AUDIO_EN=0, ROW_XLAT_OE_N=1, LED_OE_N=1, DEC_A/B_EN_N=1, ROW_A*=0; RS485_TX/RX, FRAME_SYNC, PRES_N/E/S/W = input + pull-down | |
| +0 µs | LED_LOGIC_EN = 1 (TPS22917 → LED_LOGIC_3V3, also powers MBI5124s, LV125A buffer, THVD1406) | GPIO21 |
| +5.4 ms | LED_EN = 1 (TPS63802 → LED_4V1) | GPIO18 |
| +15.4 ms | ROW_XLAT_OE_N = 0 (SN74LVC8T245 drives the decoder enables, which are still 1 = no row) | GPIO44 |
| then | refresh task, 400 Hz frame, 78 µs row period, panel blank | |

Note: firmware turns the LED rails on at every boot, before any console command. Nothing lights, because the frame buffer is empty and the decoder enables stay high until the refresh task selects a row. To save battery, consider enabling the rails only on the first `test` command.

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
`help`, `panel 20|32`, `test off|all|row|col|checker|scroll|pixel x y v`, `bright [0-255]` all respond. An unknown mode returns an error code without crashing. Log excerpt:
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
| 3 | TPS7A2033 | SYS → AON_3V3, always on (no EN control), internal soft start | tSTR 750 µs typ / 1150 µs max |
| 4 | ESP32-S3 | CHIP_PU RC (R_CHIP_PU 10 k / C_CHIP_PU) releases after AON is stable; ROM → bootloader → app_main ≈ 0.1–0.3 s | |
| 5 | TPS22917 (LED_LOGIC) | GPIO21 → ON, CT open | tON 120 µs, tR 65 µs @ 3.6 V |
| 6 | TPS63802 | GPIO18 → EN, +5 ms after stage 5 | Tdelay 321 µs + current-limit ramp 224 µs, then charges 2 × 22 µF |
| 7 | SN74LVC8T245 | /OE low, +10 ms after stage 6 | — |
| — | TPS22917 (AUDIO) | GPIO6, only when audio is used | same as stage 5 |

## Risks
- **R1 — AON LDO headroom (medium).** TPS7A2033 is a 300 mA LDO feeding the ESP32-S3 plus IMU, gauge pull-ups and both TPS22917 inputs. ESP32-S3 RF TX peaks can approach ~340 mA. Today's firmware does not use the radio. If Wi-Fi/BLE is enabled, expect brownouts: move to a ≥500 mA regulator or add bulk capacitance and limit TX power.
- **R2 — LED_LOGIC inrush on AON (low).** CT open gives tR ≈ 65 µs into ≈1.7 µF (C_LL1 1 µ + 7 × 100 n), about 90 mA, taken from AON while the MCU runs. Fine, but a 1–2 nF CT cap (≈2–4 ms ramp) costs nothing.
- **R3 — GPIO18 power-up glitch (low).** The S3 drives GPIO18 high for about 60 µs at power-up. That is shorter than the TPS63802 enable delay (321 µs), and LED_LOGIC_3V3 and the row-FET gate pull-ups are unpowered then, so the LEDs cannot flash. Next respin: put LED_EN on a glitch-free pin, or add 1 nF on LED_EN.
- **R4 — Back-powering (handled).** RS485_TX/FRAME_SYNC/PRES are inputs while LED_LOGIC_3V3 is off (THVD1406 VCC). Firmware must keep TX as input before turning that rail off. LV125A and LVC8T245 have Ioff/VCC isolation. The 74HC154s sit behind the translator on LED_4V1. The MBI5124 inputs come from the LV125A on the same rail. I2C pull-ups go to AON, and the gauge runs from BAT_RAW: with AON off it sees SDA/SCL low and goes to sleep after 2.5 s (by design, it wakes when the bus comes back).
- **R5 — Battery inrush into LED_4V1 (low).** 44 µF charged during the 224 µs current-limit ramp ≈ 0.8 A from BAT through J_BAT (PicoBlade, 1 A/contact). Within ratings. Do not add more output capacitance without slowing the start.
- **R6 — LED rails on at every boot (low, firmware policy).** See above.
- **R7 — USB VBUS capacitance.** 10.1 µF is at the USB 2.0 10 µF limit. Do not increase C_CHG_IN.
