#!/usr/bin/env bash
# Regenerate everything from params.py (needs python3 + matplotlib + cadquery + pillow).
set -euo pipefail; cd "$(dirname "$0")"
python3 dropcalc.py > /dev/null
python3 gen_drawings.py
python3 gen_3d.py --sub && python3 gen_3d.py && gzip -9 -f wire_grid_32x32.step
python3 render.py
python3 gen_sim_bg.py
python3 ../../firmware/panel_id/mkpanelid.py --preset wire32 --serial 1 -o out/wire32_serial1.bin
