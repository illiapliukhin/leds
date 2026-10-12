#!/bin/bash
# tag x y rot fix
cd /workspace/leds_analysis; source tools/kicad10_env.sh
T=$1; mkdir -p cand/$T
python3.11 scripts/move.py mono_electronics.kicad_pcb cand/$T/b.kicad_pcb $2 $3 $4 $5
cp mono_electronics.kicad_pro cand/$T/b.kicad_pro
kicad-cli pcb drc --format json --all-track-errors -o cand/$T/drc.json cand/$T/b.kicad_pcb | tail -2
python3.11 scripts/dump.py cand/$T/b.kicad_pcb cand/$T/geom.json
/workspace/leds_analysis/venv/bin/python -c "
import json,collections;d=json.load(open('cand/$T/drc.json'));print('PRE',collections.Counter(v['type'] for v in d['violations'] if v['type'] in ('clearance','shorting_items','tracks_crossing','hole_clearance','courtyards_overlap','solder_mask_bridge')),len(d['unconnected_items']))"
GEOM=cand/$T/geom.json DRCF=cand/$T/drc.json /workspace/leds_analysis/venv/bin/python scripts/iter.py $T 1.5 1,1,1,0.9
