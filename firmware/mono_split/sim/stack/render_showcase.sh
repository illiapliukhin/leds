#!/bin/bash
# Frame-exact showcase videos: host build of firmware patterns.c (fixed 60 fps clock) -> present.py (4K60, CRF 15)
cd /workspace/stack
PY=/workspace/sim/venv/bin/python
V=/workspace/videos
C3="mono_split · 3×2 stack, 96×64 px · mono_panel_32x32_full, 5.0 mm, seamless · firmware patterns.c, 60 fps · 8-bit BCM, γ 2.2"
C1="mono_split · single 32×32 panel · mono_panel_32x32_full · firmware patterns.c, 60 fps · 8-bit BCM, γ 2.2"
$PY present.py $V/vysh.raw $V/vyshyvanka_1440p.mp4 --raw 96 64 --t0 0 --dur 90 --crf 15 --res 2560x1440 \
  --title "ВИШИВАНКА" --sub "Alatyr · rhombus · oblique cross · tree of life, stitch by stitch" --cap "$C3" \
  --png 10 24 38 52 66 80 --pngdir $V/png > $V/vysh.log 2>&1 &
$PY present.py $V/aurora.raw $V/aurora_1440p.mp4 --raw 96 64 --t0 0 --dur 85 --crf 15 --res 2560x1440 \
  --title "AURORA" --sub "layered curtains, flow and shimmer in 256 grey levels" --cap "$C3" \
  --png 15 40 65 --pngdir $V/png > $V/aurora.log 2>&1 &
$PY present.py $V/kinetic.raw $V/kinetic_1440p.mp4 --raw 32 32 --t0 0 --dur 81 --crf 15 --res 2560x1440 \
  --title "KINETIC" --sub "moiré · tunnel · Lissajous ribbon · ripples" --cap "$C1" \
  --png 10 28 46 64 --pngdir $V/png > $V/kinetic.log 2>&1 &
wait
for n in vyshyvanka aurora kinetic; do
  ffmpeg -loglevel error -y -i $V/${n}_1440p.mp4 -vf scale=1920:1080:flags=lanczos -c:v libx264 -profile:v high -preset slow \
    -crf 23 -maxrate 1.9M -bufsize 3.8M -pix_fmt yuv420p -movflags +faststart $V/${n}_1080p_chat.mp4
done
echo ALLDONE > $V/done.flag
