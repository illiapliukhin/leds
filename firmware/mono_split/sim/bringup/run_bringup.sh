#!/usr/bin/env bash
# Virtual bench bring-up: QEMU firmware + netlist-driven board/FFC/panel model + scripted test session.
set -euo pipefail
cd "$(dirname "$0")"
export DISPLAY=${DISPLAY:-:4}
[[ -f /workspace/sim/flash_qemu.bin ]] || /workspace/sim/run_matrix_sim.sh   # builds the MONO_SIM image if missing
pkill -f "bringup.py" 2>/dev/null || true; pkill -f "virtual_board.py" 2>/dev/null || true
nohup /workspace/sim/venv/bin/python bringup.py "$@" > bringup.log 2>&1 &
echo "bench bring-up started on $DISPLAY"
