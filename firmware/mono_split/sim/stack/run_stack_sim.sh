#!/usr/bin/env bash
# 6-board stack simulation: 6 QEMU instances + RS-485/FRAME_SYNC/PRES host model + combined viewer.
#   ./run_stack_sim.sh [3x2|6x1] [--headless --duration N]
set -euo pipefail
cd "$(dirname "$0")"
export DISPLAY=${DISPLAY:-:4}
L=${1:-3x2}; shift || true
pkill -f stack_view.py 2>/dev/null || true; pkill -f stack_sim.py 2>/dev/null || true; pkill -f virtual_board.py 2>/dev/null || true; pkill -f bringup.py 2>/dev/null || true
pkill -f qemu-system-xtensa 2>/dev/null || true; sleep 0.5
setsid nohup /workspace/sim/venv/bin/python stack_sim.py --layout "$L" "$@" > stack_$L.log 2>&1 &
echo "stack sim ($L) started on $DISPLAY, log: $(pwd)/stack_$L.log"
