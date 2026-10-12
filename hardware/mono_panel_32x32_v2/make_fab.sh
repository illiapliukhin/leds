#!/usr/bin/env bash
# JLC fab package: zones refilled (gen_final fills; refill again here before plotting), gerbers, drill, BOM, CPL, zip.
set -euo pipefail
cd "$(dirname "$0")"; source ../tools/kicad10_env.sh
P=mono_panel_32x32_v2.kicad_pcb
python3.11 - <<'P'
import pcbnew; b = pcbnew.LoadBoard('mono_panel_32x32_v2.kicad_pcb'); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save('mono_panel_32x32_v2.kicad_pcb')
P
python3 fix_pro.py
rm -rf fab/gerbers && mkdir -p fab/gerbers
kicad-cli pcb export gerbers -o fab/gerbers -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts --subtract-soldermask $P
kicad-cli pcb export drill -o fab/gerbers/ --format excellon --excellon-separate-th --generate-map --map-format gerberx2 $P
kicad-cli pcb export pos -o fab/pos_all.csv --format csv --units mm --side both --exclude-dnp $P
python3 - <<'P'
import csv, json, collections
f = json.load(open('sch_fields.json'))['fields']
rows = list(csv.DictReader(open('fab/pos_all.csv')))
with open('fab/CPL_JLC.csv', 'w', newline='') as o:
    w = csv.writer(o); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in rows:
        if r['Ref'] not in f: continue
        w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm', 'Top' if r['Side'] == 'top' else 'Bottom', r['Rot']])
g = collections.OrderedDict()
for ref, d in f.items(): g.setdefault((d.get('LCSC'), d.get('MPN')), []).append(ref)
fp = {r['Ref']: r['Package'] for r in rows}
with open('fab/BOM_JLC.csv', 'w', newline='') as o:
    w = csv.writer(o); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Qty'])
    for (l, m), refs in g.items(): w.writerow([m, ','.join(refs), fp[refs[0]], l, len(refs)])
print('CPL', sum(1 for r in rows if r['Ref'] in f), 'BOM lines', len(g))
P
rm -f fab/pos_all.csv
python3 -c "import zipfile,glob,os; z=zipfile.ZipFile('fab/mono_panel_32x32_v2_gerbers.zip','w',zipfile.ZIP_DEFLATED); [z.write(f,os.path.basename(f)) for f in sorted(glob.glob('fab/gerbers/*'))]"
ls fab fab/gerbers
