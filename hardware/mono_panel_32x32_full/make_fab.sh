#!/usr/bin/env bash
# Gerber/drill/BOM/CPL + zip for JLCPCB. Run from this directory after gen_lattice.py.
set -euo pipefail
cd "$(dirname "$0")"
source ../tools/kicad10_env.sh
B=mono_panel_32x32_full
F=fab; rm -rf $F; mkdir -p $F/gerbers
kicad-cli pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --no-x2 --subtract-soldermask --use-drill-file-origin -o $F/gerbers $B.kicad_pcb >/dev/null
kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 \
  --drill-origin plot -o $F/gerbers/ $B.kicad_pcb >/dev/null
kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp -o $F/pos_raw.csv $B.kicad_pcb >/dev/null
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open('fab/pos_raw.csv')))
lcsc = {'NCD0603W1': 'C84265', 'FFC_40P_050_ROW': 'C202114', 'FFC_40P_050_COL': 'C202114', '24LC02BT-I/OT': 'C2655410', '100n': 'C1525'}
cpl = [r for r in rows if r['Package'] in lcsc or r['Val'] in lcsc]
with open('fab/CPL_mono_panel_32x32_full.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in cpl: w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm', 'Top' if r['Side'] == 'top' else 'Bottom', r['Rot']])
groups = {}
for r in cpl:
    k = (r['Val'], r['Package']); groups.setdefault(k, []).append(r['Ref'])
key = lambda s: (s.rstrip('0123456789'), int(''.join(ch for ch in s if ch.isdigit()) or 0))
with open('fab/BOM_mono_panel_32x32_full_JLCPCB.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for (v, p), refs in sorted(groups.items()):
        w.writerow(['FH12-40S-0.5SH(55)' if 'FFC' in p else v, ','.join(sorted(refs, key=key)), p, lcsc.get(p) or lcsc.get(v)])
print('CPL', len(cpl), 'parts;', {k: len(v) for k, v in groups.items()})
PY
rm $F/pos_raw.csv
python3 -c "import shutil; shutil.make_archive('mono_panel_32x32_full_fab', 'zip', 'fab')"
ls -la mono_panel_32x32_full_fab.zip
