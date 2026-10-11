#!/usr/bin/env bash
# Regenerate board, DRC, renders and fab zip for the garland breakout.
set -euo pipefail
cd "$(dirname "$0")"
source ../tools/kicad10_env.sh
python3.11 gen_garland_breakout.py
kicad-cli pcb drc --refill-zones --save-board -o fab/drc_report.txt garland_breakout.kicad_pcb
mkdir -p img fab/.g
kicad-cli pcb render --side top -w 900 -h 1600 -o img/garland_breakout_top.png garland_breakout.kicad_pcb
kicad-cli pcb render --side bottom -w 900 -h 1600 -o img/garland_breakout_bottom.png garland_breakout.kicad_pcb
kicad-cli pcb render --side top --perspective --rotate "-40,0,25" -w 1400 -h 1100 -o img/garland_breakout_iso.png garland_breakout.kicad_pcb
kicad-cli pcb export gerbers -l F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts -o fab/.g/ garland_breakout.kicad_pcb
kicad-cli pcb export drill -o fab/.g/ garland_breakout.kicad_pcb
kicad-cli pcb export pos --side both --format csv --units mm -o fab/garland_breakout_cpl.csv garland_breakout.kicad_pcb
python3 - <<'P'
import zipfile, glob, os
z = zipfile.ZipFile('fab/garland_breakout_fab.zip', 'w', zipfile.ZIP_DEFLATED)
for f in sorted(glob.glob('fab/.g/*')) + ['fab/garland_breakout_bom.csv', 'fab/garland_breakout_cpl.csv']:
    z.write(f, os.path.basename(f))
print(z.namelist())
P
rm -rf fab/.g
