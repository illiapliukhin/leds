"""Cube rig at true scale (mm): LED grid with per-axis pitch, the electronics tower beside the cube (one mono_electronics
v15 board per layer + garland_breakout for the wire grid), and every cable as a real routed path with its length,
the standard length you would buy, and the electrical budget (row drop per hardware/wire_grid_32x32/dropcalc.py,
LED_INTERFACE_STANDARD §5: ≤ 0.35 V at I_ROW = 0.32 A). Pure geometry, no pygame: autotest checks it directly."""
import math
from .world import BOARD_W, BOARD_H, BOARD_CONN, SIDE_OFF, FFC_LENGTHS, JST_LENGTHS, RIBBON_LENGTHS, panel_data, PANEL_CONN

GB_W, GB_H = 60.0, 145.0                     # hardware/garland_breakout: 60 × 145 mm
GB = {'J_ROW': (-24.0, -20.2), 'J_COL': (-24.0, 45.8), 'J_R1': (14.0, -64.5), 'J_R2': (14.0, -34.5), 'J_C1': (14.0, 1.5), 'J_C2': (14.0, 31.5)}
RAIL_GAP, FRAME_W = 15.0, 12.0               # wire_grid_32x32/params.py
R28, RFFC, R_IDC, R_GB, R_SOLDER = 0.23, 1.64, 0.010, 0.030, 0.002   # Ω/m, Ω/m, Ω, Ω, Ω (dropcalc.py)
RHO_CU = 1.72e-8 * (1 + 0.00393 * 5)
I_ROW, LIMIT_V = 0.32, 0.35
COMB_MAX = 200.0                             # BUILD.md: longest comb conductor ≤ 200 mm
TOWER_PITCH = 16.0                           # board stack: 1.6 mm PCB + 12 mm stand-off + parts
GAP = 50.0                                   # cube frame → electronics, clear air
SLACK = 1.12                                 # world.pick_len service-loop factor
KINDS = {'wire': ('wire', 'провода 10 мм'), 'lattice': ('lattice', 'решётка'), 'full_cube': ('full', 'full: N на высоту')}
PITCH_RANGE = {'xy': (5.0, 40.0), 'z': (8.0, 120.0)}

def nominal(kind):
    pd = panel_data(KINDS[kind][0]); return (pd['hi'][0] - pd['lo'][0]) / 31, pd['size']
def default_z(kind, n):
    p, _ = nominal(kind); return p * (32 / max(n, 1)) if kind == 'full_cube' else p
def r_wire(d_mm): return RHO_CU / (math.pi * (d_mm * 1e-3) ** 2 / 4)
def plen(pts): return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
def pick(need, options):
    for L in options:
        if L >= need * SLACK: return L, True
    return options[-1], False

class Rig:
    def __init__(s, kind, n, px, py, pz):
        s.kind, s.n, s.px, s.py, s.pz = kind, n, px, py, pz
        s.p0, s.size = nominal(kind); s.wire = kind == 'wire'
        # LED grid / frame extents (mm, cube centre = origin; x = columns, y = rows (depth), z = up)
        s.lx, s.ly = 15.5 * px, 15.5 * py
        if s.wire: s.rx, s.ry = s.lx + RAIL_GAP, s.ly + RAIL_GAP; s.hx, s.hy = s.rx + FRAME_W, s.ry + FRAME_W
        else: s.rx = s.hx = s.size / 2; s.ry = s.hy = s.size / 2
        s.zl = [(k - (n - 1) / 2) * pz for k in range(n)]
        s.floor = s.zl[0] - 30.0
        # tower: boards aligned with the layers when the layer pitch leaves room, else a 16 mm stack (2 stacks if tall)
        s.tp = max(TOWER_PITCH, pz); s.aligned = pz >= TOWER_PITCH
        per = n if (s.aligned or n * s.tp <= 400.0) else (n + 1) // 2
        s.ntw = (n + per - 1) // per
        s.ax = s.hx + GAP + GB_W / 2 if s.wire else None                       # breakout (rotated 180°: IDC faces the cube)
        s.bx = (s.ax + GB_W / 2 + 15 + BOARD_W / 2) if s.wire else (s.hx + GAP + BOARD_W / 2)   # board rotated 180°: FFC faces the cube
        s.units = []
        for k in range(n):
            t, j = divmod(k, per)
            ty = (t - (s.ntw - 1) / 2) * (GB_H + 20 if s.wire else BOARD_H + 20)
            if t % 2: j = per - 1 - j                                            # 2nd stack runs top-down: short JST hop at the top
            zk = s.zl[k] if s.aligned else s.floor + 20 + j * s.tp
            s.units.append((ty, zk))
        s.psu = (s.bx + BOARD_W / 2 + 40 + 45, 0.0)                               # 5 V PSU brick 90 × 60 on the floor
        s.cables = [s.route(k) for k in range(n)]
        s.stack = []
        for k in range(n - 1):
            (y0, z0), (y1, z1) = s.units[k], s.units[k + 1]
            a = s.bpt(k, SIDE_OFF[2]); b = s.bpt(k + 1, SIDE_OFF[2])
            pts = [a, (a[0], a[1], (z0 + z1) / 2 + 0), b] if y0 == y1 else [a, (a[0] + 30, a[1], a[2]), (b[0] + 30, b[1], b[2]), b]
            need = plen(pts) + 20; L, ok = pick(need, JST_LENGTHS); s.stack.append(dict(pts=pts, need=need, std=L, ok=ok))
    # board / breakout local mm (KiCad orientation, centre origin) -> rig mm; both are rotated 180° about z
    def bpt(s, k, loc): ty, zk = s.units[k]; return (s.bx - loc[0], ty - loc[1], zk)
    def gpt(s, k, loc): ty, zk = s.units[k]; return (s.ax - loc[0], ty - loc[1], zk)
    def route(s, k):
        ty, zk = s.units[k]; zl = s.zl[k]; out = {}
        if s.wire:
            fpts = [s.bpt(k, BOARD_CONN['J_ROW']), s.gpt(k, GB['J_ROW'])]
            need = plen(fpts) + 20; L, ok = pick(need, FFC_LENGTHS)
            out['ffc'] = dict(pts=fpts, need=need, std=L, ok=ok)
            looms = []
            for hdr in ('J_R1', 'J_R2', 'J_C1', 'J_C2'):
                h = s.gpt(k, GB[hdr]); row = hdr[2] == 'R'; half = 0 if hdr[3] == '1' else 1
                if row:     # 16 row wires on the +x rail, comb anchor at the middle of its half
                    anc = (s.rx, (half - 0.5) * 16 * s.py, zl)
                    riser = s.hx + 8 + 4 * half                                     # shared riser = the row bundle
                    pts = [h, (riser, h[1], zk), (riser, anc[1], zk), (riser, anc[1], zl), anc]
                else:       # 16 column wires on the front (−y) rail
                    anc = ((half - 0.5) * 16 * s.px, -s.ry, zl); cy = -s.ry - FRAME_W / 2 - 2 + 4 * half   # dressed along the frame bar
                    pts = [h, (h[0], cy, zk), (h[0], cy, zl), (anc[0], cy, zl), anc] if h[0] > s.hx else [h, (s.hx + 8, h[1], zk), (s.hx + 8, cy, zk), (s.hx + 8, cy, zl), (anc[0], cy, zl), anc]
                need = plen(pts) + 30; L, ok = pick(need, RIBBON_LENGTHS)
                comb = 7.5 * (s.py if row else s.px) + 50.0                       # longest pigtail from the anchor (≤ 200 mm at 10 mm)
                looms.append(dict(hdr=hdr, pts=pts, anc=anc, row=row, half=half, need=need, std=L, ok=ok, comb=comb, comb_ok=comb <= COMB_MAX))
            out['looms'] = looms
            # row drop budget: the actual cables you'd buy (standard lengths), worst row loom of this layer
            lr = max((l for l in looms if l['row']), key=lambda l: l['std'])
            Lf = out['ffc']['std']; items = [('FFC %d мм' % Lf, RFFC * Lf / 1e3), ('breakout + IDC', R_GB + R_IDC), ('шлейф %d мм' % max(lr['std'], lr['need'] * SLACK), R28 * max(lr['std'], lr['need'] * SLACK) / 1e3),
                     ('гребёнка %.0f мм' % lr['comb'], R28 * lr['comb'] / 1e3), ('пайка', R_SOLDER),
                     ('строка Ø0.50, %.0f мм, ½' % (2 * s.rx), r_wire(0.5) * 2 * s.rx / 1e3 / 2)]
            R = sum(r for _, r in items); out['drop_mV'] = R * I_ROW * 1e3; out['drop_ok'] = out['drop_mV'] <= LIMIT_V * 1e3; out['items'] = items
        else:
            # PCB panel: FFC straight from the board to the panel back connectors (rotated so they face the tower)
            pc = PANEL_CONN[KINDS[s.kind][0]]
            ffcs = []
            for nm in ('J_ROW', 'J_COL'):
                cx, cy = pc[nm]; tgt = (cy, -cx, zl - 2.0)                         # panel rotated −90°: connector side faces +x
                a = s.bpt(k, BOARD_CONN[nm]); pts = [a, (a[0] - 10, a[1], zk), (tgt[0] + 10, tgt[1], tgt[2]) if tgt[0] < s.hx else tgt, tgt]
                need = plen(pts) + 20; L, ok = pick(need, FFC_LENGTHS); ffcs.append(dict(nm=nm, pts=pts, need=need, std=L, ok=ok))
            out['ffcs'] = ffcs; out['drop_ok'] = True; out['drop_mV'] = None
        return out
    def footprints(s):
        """top-view rectangles (x0, y0, x1, y1, name) of every object: autotest checks they don't overlap"""
        r = [(-s.hx, -s.hy, s.hx, s.hy, 'куб')]
        for k, (ty, zk) in enumerate(s.units):
            if k and s.units[k - 1][0] == ty: continue                          # stacked boards share one footprint column
            r.append((s.bx - BOARD_W / 2, ty - BOARD_H / 2, s.bx + BOARD_W / 2, ty + BOARD_H / 2, 'плата%d' % k))
            if s.wire: r.append((s.ax - GB_W / 2, ty - GB_H / 2, s.ax + GB_W / 2, ty + GB_H / 2, 'breakout%d' % k))
        r.append((s.psu[0] - 45, s.psu[1] - 30, s.psu[0] + 45, s.psu[1] + 30, 'БП'))
        return r
    def overlaps(s):
        f = s.footprints(); bad = []
        for i in range(len(f)):
            for j in range(i + 1, len(f)):
                a, b = f[i], f[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]: bad.append((a[4], b[4]))
        return bad
    def flags(s):
        """[(severity, text)] — 'err' = would exceed real hardware / standard parts"""
        out = []
        if not s.wire and (abs(s.px - s.p0) > 1e-6 or abs(s.py - s.p0) > 1e-6): out.append(('err', 'шаг X/Y печатной панели фиксирован (%.2f мм)' % s.p0))
        allc = [c for r in s.cables for c in (r.get('looms') or []) + ([r['ffc']] if 'ffc' in r else []) + (r.get('ffcs') or [])] + s.stack
        nbad = [c for c in allc if not c['ok']]
        if nbad: out.append(('err', '%d кабел. длиннее стандартных (нужно до %.0f мм)' % (len(nbad), max(c['need'] for c in nbad))))
        if s.wire:
            cb = [l for r in s.cables for l in r['looms'] if not l['comb_ok']]
            if cb: out.append(('err', 'гребёнка %.0f мм > %d мм (BUILD.md)' % (cb[0]['comb'], COMB_MAX)))
            d = max(r['drop_mV'] for r in s.cables)
            out.append(('err' if d > LIMIT_V * 1e3 else 'ok', 'падение на строке до %.0f мВ (предел %d мВ при %.2f А)' % (d, LIMIT_V * 1e3, I_ROW)))
        if not out or all(f[0] == 'ok' for f in out): out.append(('ok', 'все кабели стандартной длины, в пределах железа'))
        return out
    def summary(s):
        """side-panel lines: cable kinds with need range -> chosen standard length"""
        L = []
        def rng(cs, nm):
            if not cs: return
            a, b = min(c['need'] for c in cs), max(c['need'] for c in cs); st = sorted({c['std'] for c in cs})
            L.append(('%s ×%d: нужно %.0f…%.0f мм → стандарт %s мм' % (nm, len(cs), a, b, '/'.join('%d' % x for x in st)), all(c['ok'] for c in cs)))
        if s.wire:
            rng([r['ffc'] for r in s.cables], 'FFC 40P (плата→breakout)')
            rng([l for r in s.cables for l in r['looms'] if l['row']], 'шлейф строк 16ж 28AWG')
            rng([l for r in s.cables for l in r['looms'] if not l['row']], 'шлейф столбцов 16ж')
            c = s.cables[0]['looms'][0]['comb']; L.append(('гребёнка: до %.0f мм (≤ %d)' % (c, COMB_MAX), c <= COMB_MAX))
        else:
            rng([f for r in s.cables for f in r['ffcs']], 'FFC 40P (плата→панель)')
        rng(s.stack, 'стек JST-SH 5P')
        return L
