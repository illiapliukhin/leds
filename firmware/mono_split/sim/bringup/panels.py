"""Panel selection for the bring-up sim: `--panel mono32` (default, mono_panel_32x32), `--panel lattice`
(hardware/mono_panel_32x32_lattice) or `--panel full` (hardware/mono_panel_32x32_full, edge-to-edge). Also BRINGUP_PANEL=lattice. Read at import so netmodel/cable pick it up.
The panel dump (pads, nets, positions) is regenerated from the panel's .kicad_pcb with pdump.py (KiCad python)
whenever the .kicad_pcb is newer than the dump."""
import json, os, subprocess, sys
D = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(D, '..', '..', '..', '..'))
HW = os.path.join(REPO, 'hardware')
KICAD_PY = os.path.join(os.environ.get('KICAD10_ROOT', '/workspace/.kicad10/squashfs-root'), 'usr/bin/python3.11')

PANELS = {
    'mono32': dict(title='mono_panel_32x32', json='panel.json', pcb=os.path.join(HW, 'mono_panel_32x32', 'mono_panel_32x32.kicad_pcb'),
                   exit={'J_ROW': (-1.0, 0, 0), 'J_COL': (0, -1.0, 0)}, cable_json='cable_check.json', bg=None, ir=None),
    'lattice': dict(title='mono_panel_32x32_lattice', json='panel_lattice.json',
                    pcb=os.path.join(HW, 'mono_panel_32x32_lattice', 'mono_panel_32x32_lattice.kicad_pcb'),
                    exit={'J_ROW': (0, -1.0, 0), 'J_COL': (0, -1.0, 0)},          # both receptacles on the south tab, cable exits south
                    cable_json='cable_check_lattice.json',
                    bg=os.path.join(HW, 'mono_panel_32x32_lattice', 'renders', 'lattice_sim_bg.png'),
                    ir=os.path.join(HW, 'mono_panel_32x32_lattice', 'analysis.json'), led_dy=0.775),
    'full': dict(title='mono_panel_32x32_full', json='panel_full.json',
                 pcb=os.path.join(HW, 'mono_panel_32x32_full', 'mono_panel_32x32_full.kicad_pcb'),
                 exit={'J_ROW': (0, -1.0, 0), 'J_COL': (0, -1.0, 0)},             # both receptacles mid-back, cable exits south
                 cable_json='cable_check_full.json',
                 bg=os.path.join(HW, 'mono_panel_32x32_full', 'renders', 'full_sim_bg.png'),
                 ir=os.path.join(HW, 'mono_panel_32x32_full', 'analysis.json'), led_dy=0.0),
}

def _pick():
    name = os.environ.get('BRINGUP_PANEL', 'mono32')
    for i, a in enumerate(sys.argv):
        if a == '--panel' and i + 1 < len(sys.argv): name = sys.argv[i + 1]
        elif a.startswith('--panel='): name = a.split('=', 1)[1]
    if name not in PANELS: raise SystemExit('unknown --panel %r (choose %s)' % (name, ', '.join(PANELS)))
    return name

NAME = _pick()
CFG = PANELS[NAME]

def json_path():
    p = os.path.join(D, CFG['json'])
    stale = not os.path.exists(p) or (os.path.exists(CFG['pcb']) and os.path.getmtime(CFG['pcb']) > os.path.getmtime(p))
    if stale and NAME != 'mono32' and os.path.exists(KICAD_PY):      # mono32 dump is committed as-is
        env = dict(os.environ); root = os.path.dirname(os.path.dirname(os.path.dirname(KICAD_PY)))
        env['LD_LIBRARY_PATH'] = '%s/usr/lib/x86_64-linux-gnu:%s/usr/lib:%s' % (root, root, env.get('LD_LIBRARY_PATH', ''))
        subprocess.run([KICAD_PY, os.path.join(D, 'pdump.py'), CFG['pcb'], p, 'D,J'], env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p

def load():
    return json.load(open(json_path()))

def ir(base):
    """per-row [board R, panel R]: lattice/full keep the board part of ir_v3 and swaps in the lattice panel copper."""
    if not CFG['ir']: return base
    eff = json.load(open(CFG['ir']))['row_R_eff_ohm']
    return {k: [v[0], eff[k]] for k, v in base.items()}
