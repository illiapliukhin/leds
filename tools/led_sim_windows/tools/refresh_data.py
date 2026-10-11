"""Re-export every hardware/firmware artefact the simulator embeds from the CURRENT repo checkout and write
data/versions.json (git SHA of the last commit touching each source + sha256 of the source and of the export).
Usage (from tools/led_sim_windows):  python tools/refresh_data.py [--kicad-cli PATH]
- PCB JSON (outline, footprints, pads, tracks, vias, zones, graphics, holes) for the current board + panels + breakout
- schematic PDF + KiCad netlist for every board that has a schematic (kicad-cli)
- connector positions of the current electronics board (data/board_conn.json)
- the BOM values the Lab model uses (R_ILIM1, R_ILM1, F_BAT1, J_BAT1, FFC length) -> data/bom_v15.json
The app and the autotest compare data/versions.json against the repo (ledsim/versions.py)."""
import gzip, hashlib, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); APP = os.path.dirname(HERE); REPO = os.path.abspath(os.path.join(APP, '..', '..'))
sys.path.insert(0, HERE); import export_pcb

CURRENT_BOARD = 'board_v15'
PCB = {  # key -> (kicad_pcb, title, schematic or None)
    CURRENT_BOARD: ('hardware/mono_electronics/mono_electronics.kicad_pcb', 'mono_electronics v15', 'hardware/mono_schematic/mono_electronics.kicad_sch'),
    'panel_full': ('hardware/mono_panel_32x32_full/mono_panel_32x32_full.kicad_pcb', 'mono_panel_32x32_full (edge-to-edge)', None),
    'panel_flat': ('hardware/mono_panel_32x32/mono_panel_32x32.kicad_pcb', 'mono_panel_32x32 (flat, old)', None),
    'panel_lattice': ('hardware/mono_panel_32x32_lattice/mono_panel_32x32_lattice.kicad_pcb', 'mono_panel_32x32_lattice', None),
    'panel_20x20': ('hardware/mono_panel_20x20/mono_panel_20x20.kicad_pcb', 'mono_panel_20x20', None),
    'garland': ('hardware/garland_breakout/garland_breakout.kicad_pcb', 'garland_breakout', None),
}
FIRMWARE = ['firmware/mono_split/main/demo.c', 'firmware/mono_split/main/stack.c', 'firmware/mono_split/main/patterns.c',
            'firmware/mono_split/main/matrix_refresh.c', 'firmware/mono_split/main/matrix_refresh.h', 'firmware/mono_split/main/stack.h',
            'firmware/mono_split/main/demo.h', 'firmware/mono_split/main/patterns.h', 'firmware/panel_id/panel_id.c', 'firmware/panel_id/panel_id.h']

def sha(p):
    with open(p, 'rb') as f: return hashlib.sha256(f.read()).hexdigest()
def git_sha(rel): return subprocess.run(['git', '-C', REPO, 'log', '-1', '--format=%H', '--', rel], capture_output=True, text=True).stdout.strip()

def kicad_cli(argv):
    for c in [a for a in argv if a.startswith('--kicad-cli=')] + ['/workspace/.kicad10/AppDir/bin/kicad-cli', 'kicad-cli']:
        c = c.split('=', 1)[-1]
        if os.path.exists(c) or c == 'kicad-cli': return c

def main():
    cli = kicad_cli(sys.argv); out = {'repo_head': subprocess.run(['git', '-C', REPO, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
                                      'pcb': {}, 'sch': {}, 'firmware': {}}
    os.makedirs(os.path.join(APP, 'data', 'pcb'), exist_ok=True); os.makedirs(os.path.join(APP, 'data', 'sch'), exist_ok=True)
    for key, (rel, title, sch) in PCB.items():
        src = os.path.join(REPO, rel); dst = os.path.join(APP, 'data', 'pcb', key + '.json.gz')
        d = export_pcb.export(src, title)
        with gzip.GzipFile(dst, 'wb', mtime=0) as f: f.write(json.dumps(d, separators=(',', ':')).encode())   # mtime=0: reproducible
        out['pcb'][key] = dict(src=rel, git=git_sha(rel), src_sha256=sha(src), export_sha256=sha(dst), title=title)
        print('pcb', key, out['pcb'][key]['git'][:8], {k: len(v) for k, v in d.items() if isinstance(v, list)})
        if sch:
            s = os.path.join(REPO, sch); pdf = os.path.join(APP, 'data', 'sch', key + '.pdf'); net = os.path.join(APP, 'data', 'sch', key + '.net')
            r1 = subprocess.run([cli, 'sch', 'export', 'pdf', '-o', pdf, s], capture_output=True, text=True)
            r2 = subprocess.run([cli, 'sch', 'export', 'netlist', '-o', net, s], capture_output=True, text=True)
            ok = r1.returncode == 0 and r2.returncode == 0
            out['sch'][key] = dict(src=sch, git=git_sha(sch), src_sha256=sha(s), pdf=ok and os.path.exists(pdf), net=ok and os.path.exists(net),
                                   err=(r1.stderr + r2.stderr)[-400:] if not ok else '')
            print('sch', key, 'ok' if ok else 'FAILED ' + out['sch'][key]['err'])
            if key == CURRENT_BOARD: board_extras(d, key)
    for rel in FIRMWARE:
        out['firmware'][rel] = dict(git=git_sha(rel), sha256=sha(os.path.join(REPO, rel)))
    fw = subprocess.run(['git', '-C', REPO, 'log', '-1', '--format=%H %cI', '--', 'firmware/mono_split/main', 'firmware/panel_id'], capture_output=True, text=True).stdout.split()
    out['firmware_commit'], out['firmware_date'] = fw[0], fw[1]
    out['hardware_commit'] = subprocess.run(['git', '-C', REPO, 'log', '-1', '--format=%H', '--', 'hardware/mono_electronics', 'hardware/mono_panel_32x32_full', 'hardware/garland_breakout', 'hardware/mono_panel_32x32_lattice'], capture_output=True, text=True).stdout.strip()
    with open(os.path.join(APP, 'data', 'versions.json'), 'w') as f: json.dump(out, f, indent=1)
    print('versions.json: firmware', out['firmware_commit'][:8], 'hardware', out['hardware_commit'][:8])

def board_extras(d, key):
    """connector centres relative to the board centre + the BOM values the Lab model needs"""
    xs = [p[0] for seg in d['outline'] for p in (seg if isinstance(seg[0], list) else [seg])] if d['outline'] and isinstance(d['outline'][0], list) else []
    fp = {f[0]: f for f in d['fps']}
    x0, y0, x1, y1 = export_bbox(d)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    conn = {k: (round(fp[r][2] - cx, 2), round(fp[r][3] - cy, 2)) for k, r in
            (('J_ROW', 'J_ROW1'), ('J_COL', 'J_COL1'), ('J_USB', 'J_USB1'), ('J_BAT', 'J_BAT1'), ('J_RH', 'J_RH1'), ('J_CH', 'J_CH1'),
             ('J_PORT_N', 'J_PORT_N1'), ('J_PORT_E', 'J_PORT_E1'), ('J_PORT_S', 'J_PORT_S1'), ('J_PORT_W', 'J_PORT_W1')) if r in fp}
    size = (round(x1 - x0, 2), round(y1 - y0, 2))
    json.dump(dict(board=key, size_mm=size, conn=conn), open(os.path.join(APP, 'data', 'board_conn.json'), 'w'), indent=1)
    bom = {r: fp[r][1] for r in ('R_ILIM1', 'R_ILM1', 'F_BAT1', 'Q_BAT1', 'J_BAT1', 'U_OVP1', 'D_VBUS1', 'U_CHG1', 'R_ISET1', 'J_ROW1', 'J_COL1', 'J_RH1', 'J_CH1') if r in fp}
    json.dump(bom, open(os.path.join(APP, 'data', 'bom_v15.json'), 'w'), indent=1, ensure_ascii=False)
    print('board', size, 'conn', conn); print('bom', bom)

def export_bbox(d):
    pts = []
    for seg in d['outline']:
        for v in (seg if isinstance(seg, list) else []):
            if isinstance(v, list) and len(v) >= 2 and all(isinstance(t, (int, float)) for t in v[:2]): pts.append(v[:2])
            elif isinstance(v, (int, float)): pass
        if len(seg) >= 4 and all(isinstance(t, (int, float)) for t in seg[:4]): pts += [seg[:2], seg[2:4]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

if __name__ == '__main__': main()
