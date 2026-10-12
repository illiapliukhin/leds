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
python3 - <<'PY'
# JLC/LCSC reference unit prices (USD, list price at assembly qty, Oct 2026; ESTIMATE, re-check in the JLC BOM tool)
import csv, json
P = {'C84265': (0.0068, 'extended'), 'C202114': (0.62, 'extended'), 'C2655410': (0.27, 'extended'), 'C1525': (0.0005, 'basic')}
rows = list(csv.DictReader(open('fab/BOM_mono_panel_32x32_full_JLCPCB.csv')))
tot = 0; ext = 0
with open('fab/BOM_mono_panel_32x32_full_priced.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['Comment', 'Qty', 'Footprint', 'LCSC Part #', 'JLC type', 'Unit USD (est.)', 'Line USD (est.)', 'Side'])
    for r in rows:
        q = len(r['Designator'].split(',')); u, t = P[r['LCSC Part #']]; tot += q * u; ext += t == 'extended'
        w.writerow([r['Comment'], q, r['Footprint'], r['LCSC Part #'], t, u, round(q * u, 2), 'Top' if r['Comment'] == 'NCD0603W1' else 'Bottom'])
pcb5 = 70.0                                                       # 4L 160x160 1.6 mm 1 oz inner, 5 pcs (estimate)
est = dict(parts_per_board=round(tot, 2), extended_part_types=ext, extended_fee_per_order=3.0 * ext,
           smt_setup_double_sided=2 * 25.0, placement_per_board=round(1028 * 0.0017 + 1.5, 2), pcb_5pcs=pcb5)
q = 5; per = (pcb5 + est['smt_setup_double_sided'] + est['extended_fee_per_order']) / q + est['parts_per_board'] + est['placement_per_board']
est['per_assembled_board_qty5_usd'] = round(per, 1)
q = 30; est['per_assembled_board_qty30_usd'] = round((pcb5 * 4.2 + est['smt_setup_double_sided'] + est['extended_fee_per_order']) / q + est['parts_per_board'] * 0.95 + est['placement_per_board'], 1)
est['note'] = 'ESTIMATE from JLC/LCSC list prices; top-only assembly + hand-soldered back parts saves ~25 USD setup'
json.dump(est, open('fab/price_estimate.json', 'w'), indent=1); print(est)
PY
python3 -c "import shutil; shutil.make_archive('mono_panel_32x32_full_fab', 'zip', 'fab')"
ls -la mono_panel_32x32_full_fab.zip
