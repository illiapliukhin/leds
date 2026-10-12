#!/usr/bin/env bash
# One-shot: boot the mono_split firmware (MONO_SIM build) in Espressif QEMU, open the virtual
# 32x32 board on the desktop and send "demo cycle".  Usage: run_matrix_sim.sh [--record]
set -euo pipefail
SIM=/workspace/sim
FW=${FW:-/workspace/fw/firmware/mono_split}
export DISPLAY=${DISPLAY:-:4}
QEMU=$(cat $SIM/qemu_path 2>/dev/null || ls -d ~/.espressif/tools/qemu-xtensa/*/qemu/bin/qemu-system-xtensa | head -1)
if [[ ! -f $SIM/flash_qemu.bin || ${REBUILD:-0} == 1 ]]; then
  source ~/esp/esp-idf/export.sh >/dev/null
  (cd $FW && idf.py -B build_qemu -D SDKCONFIG=build_qemu/sdkconfig -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.qemu" -D MONO_SIM=1 build >/dev/null &&
   cd build_qemu && python -m esptool --chip esp32s3 merge_bin --fill-flash-size 8MB -o $SIM/flash_qemu.bin @flash_args >/dev/null)
fi
pkill -f "qemu-system-xtensa.*flash_qemu.bin" 2>/dev/null || true
pkill -f "virtual_board.py" 2>/dev/null || true
sleep 0.5
nohup "$QEMU" -nographic -machine esp32s3 -m 4M -drive file=$SIM/flash_qemu.bin,if=mtd,format=raw \
  -serial tcp:127.0.0.1:5555,server=on,wait=on -monitor none > $SIM/qemu.log 2>&1 &
sleep 1
ARGS=(--cmd "demo cycle" --log $SIM/console.log)
if [[ "${1:-}" == "--record" ]]; then ARGS+=(--record $SIM/matrix_demo.mp4 --record-seconds 22 --png-dir $SIM/frames); fi
nohup $SIM/venv/bin/python $SIM/virtual_board.py "${ARGS[@]}" > $SIM/viewer.log 2>&1 &
echo "QEMU + virtual board started on DISPLAY=$DISPLAY (logs in $SIM)"
