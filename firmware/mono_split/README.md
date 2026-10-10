# Mono split LED bring-up firmware

ESP-IDF 5.x firmware for the **mono_electronics** board driving **20×20** or **32×32** passive LED panels over FFC.

MCU: **ESP32-S3FN8** (8 MB quad flash, no PSRAM). Console and flashing via **USB Serial/JTAG** on GPIO19/20.

## Build

### Pin table guard

```bash
python3 firmware/mono_split/tools/check_pins.py
```

Compares `main/board_pins.h` against `hardware/common/MONO_SPLIT_ARCHITECTURE.md`.

### Docker (CI-equivalent)

```bash
firmware/mono_split/scripts/build_in_docker.sh
```

Uses `espressif/idf:release-v5.3`.

### Local ESP-IDF

```bash
firmware/mono_split/scripts/build_local.sh
```

Requires ESP-IDF v5.x with `esp32s3` tool chain (`export.sh`).

### GitHub Actions

Workflow: `.github/workflows/mono_split_firmware.yml` — same Docker image and steps.

## Flash and monitor

```bash
cd firmware/mono_split
idf.py -p /dev/ttyACM0 flash monitor
```

On Windows use the USB JTAG COM port exposed by the S3.

## Pin map

All functional GPIOs are defined in **`main/board_pins.h`** (generated/checkable against the architecture doc).

| GPIO | Net | Firmware use |
|---:|---|---|
| 13 | LED_CLK | SPI SCLK → MBI5124 |
| 14 | LED_SDI | SPI MOSI → MBI5124 |
| 15 | LED_LE | Latch strobe |
| 16 | LED_OE_N | Blank (active low) |
| 39–40, 38, 33 | ROW_A0–A3 | 74HC154 address |
| 41–42 | DEC_A/B_EN_N | Decoder enables (active low) |
| 47 | ROW_XLAT_OE_N | Level translator `/OE` (active low = outputs on) |
| 18 | LED_EN | TPS63802 enable |
| 21 | LED_LOGIC_EN | LED logic 3V3 switch |
| 8–10 | IMU_* | BMI270 I²C + INT1 |

## Display timing budget

Target **400 Hz** full-frame refresh (`MATRIX_TARGET_REFRESH_HZ` in `matrix_refresh.h`).

| Quantity | Value |
|---|---|
| Rows scanned | 32 (1/32 duty) |
| Row scan rate | 400 × 32 = **12.8 kHz** |
| Row period | **78.125 µs** |
| Column shift | 32 bits @ **20 MHz** → **1.6 µs** |
| LE pulse | **1 µs** |
| Blank + PMOS off | **3 + 2 µs** (EVT placeholders) |
| Row ON window | remainder × (`brightness` / 255) |

Ghosting sequence per row (see `matrix_refresh.c`):

1. Assert **LED_OE_N** (blank).
2. Disable both decoders (`DEC_*_EN_N` high).
3. Set row address and enable one decoder bank.
4. Shift column data, pulse **LED_LE**.
5. Deassert **LED_OE_N** for the brightness-limited slice of the row period.

Power-up follows `hardware/common/PCB_ARCHITECTURE.md`: **AON** (always on in hardware) → **LED_LOGIC_EN** → **LED_EN**, matrix blanked until rails settle.

## USB console test commands

| Command | Action |
|---|---|
| `panel 20` / `panel 32` | Select geometry |
| `test all` | All pixels on |
| `test row` / `test col` | Walking line |
| `test checker` | Animated checkerboard |
| `test scroll` | Scrolling banner |
| `test pixel <r> <c> <0\|1>` | Single LED |
| `test off` | Clear |
| `bright [0-255]` | Global brightness (row time modulation) |

## Electrical notes (firmware perspective, EVT)

These are **not** hardware changes — review during bring-up:

1. **Strapping:** `GPIO0` is boot strap; do not drive as output. `GPIO41/42` are JTAG strapping balls but acceptable when using USB Serial/JTAG only.
2. **SPICS0 (pad 32):** must stay NC — never tie to GND on FN8.
3. **Decoder polarity:** 74HC154 outputs are **active low**; only one row Y is low when enabled. Enables `DEC_*_EN_N` are **active low** on E0; E1 is hardwired GND on PCB.
4. **P-FET rows (AO3403):** gate pulled toward **LED_4V1**; decoder pulls gate **low** to turn **on** the row (verify `VGS` at 4.24 V rail).
5. **MBI5124 Rext:** 1.82 kΩ → ~10.05 mA/channel — measure temperature and white balance on EVT.
6. **LED rail:** mono target **4.24 V** (681/91 kΩ), not RGB 4.099 V divider — margin for white `VF` max + `VDS`.
7. **USB-C CC:** architecture backlog — **5.1 kΩ** CC pulldowns may be missing for C-to-C VBUS; use A-C cable or fix in hardware pass.
8. **MBI CLK:** 20 MHz firmware default; 24 MHz only after SI margin on EVT (4% below 25 MHz max).

## Layout

```
firmware/mono_split/
  main/           Application, drivers, refresh ISR task
  tools/          check_pins.py
  scripts/        build_local.sh, build_in_docker.sh
```
