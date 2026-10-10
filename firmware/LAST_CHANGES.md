# Latest firmware changes

## Mono split bring-up (2026-10-10)

- Added **`firmware/mono_split/`** ESP-IDF 5.x project for ESP32-S3FN8 mono matrix electronics.
- **`main/board_pins.h`**: single GPIO/net table aligned with `hardware/common/MONO_SPLIT_ARCHITECTURE.md`.
- **`tools/check_pins.py`**: fails CI if header and architecture GPIO table diverge.
- Display: MBI5124 SPI shift @ 20 MHz, 1/32 row scan, blank-before-row-change, refresh task on core 1 @ 400 Hz target.
- Power sequencing: LED_LOGIC_EN → LED_EN → row translator enable, OE blanked until rails up.
- BMI270 chip ID read + I2C bus scan on boot.
- USB Serial/JTAG console: panel geometry, test patterns, per-pixel set, brightness.
- CI: `.github/workflows/mono_split_firmware.yml` (Espressif IDF Docker image); Build step sources `${IDF_PATH}/export.sh` before `idf.py`.
