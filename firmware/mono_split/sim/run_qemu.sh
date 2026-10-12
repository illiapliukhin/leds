#!/usr/bin/env bash
# Build the QEMU variant (UART console, SPI shift stubbed) and boot it in Espressif's qemu-xtensa.
set -euo pipefail
cd "$(dirname "$0")/.."
source "${IDF_PATH:-$HOME/esp/esp-idf}/export.sh" >/dev/null
idf.py -B build_qemu -D SDKCONFIG=build_qemu/sdkconfig -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.qemu" -D MONO_SIM=1 set-target esp32s3 build
(cd build_qemu && python -m esptool --chip esp32s3 merge_bin --fill-flash-size 8MB -o flash_qemu.bin @flash_args)
qemu-system-xtensa -nographic -machine esp32s3 -m 4M -drive file=build_qemu/flash_qemu.bin,if=mtd,format=raw -serial mon:stdio
