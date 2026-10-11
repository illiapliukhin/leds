#!/bin/bash
cd /workspace/stack
PY=/workspace/sim/venv/bin/python
CAP="mono_split · 3×2 stack, 96×64 px, mono_panel_32x32_full (5.0 mm, seamless) · real firmware ×6 in QEMU · 8-bit BCM, γ 2.2"
$PY present.py /workspace/videos/run_show_snapshot.jsonl /workspace/videos/vyshyvanka_4k.mp4 --t0 17.93 --dur 90 --crf 15 \
  --title "ВИШИВАНКА" --sub "Alatyr · rhombus · oblique cross · tree of life, stitch by stitch" --cap "$CAP" \
  --png 12 26 40 54 68 82 --pngdir /workspace/videos/png > /workspace/videos/vysh.log 2>&1 &
$PY present.py /workspace/videos/run_show_snapshot.jsonl /workspace/videos/aurora_4k.mp4 --t0 115 --dur 85 --crf 15 \
  --title "AURORA" --sub "layered curtains, flow and shimmer in 256 grey levels" --cap "$CAP" \
  --png 15 40 65 --pngdir /workspace/videos/png > /workspace/videos/aurora.log 2>&1 &
wait
