#!/usr/bin/env bash
# Full rebuild: schematic -> PCB base -> router -> PCB final (arcs, stitching, zones filled) -> ERC / DRC + parity
set -euo pipefail
cd "$(dirname "$0")"
source ../tools/kicad10_env.sh
python3 gen_sch.py
python3.11 gen_pcb.py base
for i in 1 2 3 4 5 6 7 8; do python3 route_v2.py > route.log 2>&1 && break; tail -1 route.log; done
python3.11 gen_pcb.py final
python3 fix_pro.py
kicad-cli sch erc --severity-all --format json -o erc.json mono_panel_32x32_v2.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all --format json -o drc.json mono_panel_32x32_v2.kicad_pcb
python3 - <<'P'
import json, collections
e = json.load(open('erc.json')); ev = [x for s in e['sheets'] for x in s['violations']]
d = json.load(open('drc.json'))
print('ERC', len(ev), collections.Counter(x['type'] for x in ev).most_common(5))
print('DRC', len(d['violations']), 'unconnected', len(d['unconnected_items']), 'parity', len(d.get('schematic_parity', [])))
for x in (d['violations'] + d.get('schematic_parity', []))[:12]: print(' ', x['type'], x['description'][:90], [i['description'][:50] for i in x['items']][:2])
P
