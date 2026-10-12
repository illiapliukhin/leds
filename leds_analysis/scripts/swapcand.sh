#!/bin/bash
cd /workspace/leds_analysis; source tools/kicad10_env.sh; T=$1; mkdir -p cand/$T
python3.11 scripts/swap.py mono_electronics.kicad_pcb cand/$T/b.kicad_pcb $2
cp mono_electronics.kicad_pro cand/$T/b.kicad_pro
kicad-cli pcb drc --format json --all-track-errors -o cand/$T/drc.json cand/$T/b.kicad_pcb | tail -1
python3.11 scripts/dump.py cand/$T/b.kicad_pcb cand/$T/geom.json
GEOM=cand/$T/geom.json DRCF=cand/$T/drc.json /workspace/leds_analysis/venv/bin/python scripts/expB.py $T 1.5 1,1,1,0.9
