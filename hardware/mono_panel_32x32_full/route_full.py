#!/usr/bin/env python3
"""Grid maze router (A*, 0.125 mm, 8-way + vias) for the FFC fan-out of mono_panel_32x32_full.
Reads fixed.json (copper placed by gen_full.py base), routes J_ROW pin r -> row r bus (F.Cu, via at the end) and
J_COL pin c -> any cathode via of column c, on In2.Cu and B.Cu. Clearance: real >= 0.10 mm (raster margin 0.09).
Writes routes.json (tracks [x0,y0,x1,y1,w,layer,net], vias [x,y,net]) and route_stats.json (lengths per net)."""
import heapq, json, math, os, sys, random
import numpy as np
from scipy.ndimage import distance_transform_edt
H = os.path.dirname(os.path.abspath(__file__)); D = json.load(open(os.path.join(H, 'fixed.json')))
G = 0.125; S = D['size']; n = int(round(S / G)) + 1
CLR, DELTA, MARG = 0.10, 0.09, 0.19          # MARG = CLR + raster error (0.0884)
VIA_R = 0.225; EDGE = 0.25
W = {'ROW': 0.3, 'COL': 0.2, 'SIG': 0.2}
LCOST = {'ROW': (1.6, 1.0), 'COL': (1.0, 1.8), 'SIG': (1.4, 1.0)}   # (In2, B)
COL_BAND = 12.0
LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']; RL = [2, 3]          # routing layers
nets = sorted({p['net'] for p in D['pads'] if p['net']}); NID = {s: i + 1 for i, s in enumerate(nets)}
nm = np.zeros((4, n, n), np.int16); core = np.zeros((4, n, n), np.int16)
ys, xs = np.mgrid[0:n, 0:n] * G
def paint(l, mask, nid): nm[l][mask & (nm[l] == 0)] = nid
def win(x0, y0, x1, y1):
    i0, i1 = max(0, int((y0 - 1) / G)), min(n, int((y1 + 1) / G) + 1); j0, j1 = max(0, int((x0 - 1) / G)), min(n, int((x1 + 1) / G) + 1)
    return slice(i0, i1), slice(j0, j1)
def rect(l, x0, y0, x1, y1, nid, d=DELTA):
    si, sj = win(x0, y0, x1, y1); X, Y = xs[si, sj], ys[si, sj]
    m = (X >= x0 - d) & (X <= x1 + d) & (Y >= y0 - d) & (Y <= y1 + d); sub = nm[l][si, sj]; sub[m & (sub == 0)] = nid
    c = (X >= x0 + 0.05) & (X <= x1 - 0.05) & (Y >= y0 + 0.05) & (Y <= y1 - 0.05); cs = core[l][si, sj]; cs[c] = nid
def circ(l, x, y, r, nid, d=DELTA):
    si, sj = win(x - r, y - r, x + r, y + r); X, Y = xs[si, sj], ys[si, sj]
    m = (X - x) ** 2 + (Y - y) ** 2 <= (r + d) ** 2; sub = nm[l][si, sj]; sub[m & (sub == 0)] = nid
    c = (X - x) ** 2 + (Y - y) ** 2 <= max(r - 0.05, 0.01) ** 2; cs = core[l][si, sj]; cs[c] = nid
def seg(l, x0, y0, x1, y1, w, nid, d=DELTA):
    si, sj = win(min(x0, x1) - w, min(y0, y1) - w, max(x0, x1) + w, max(y0, y1) + w); X, Y = xs[si, sj], ys[si, sj]
    dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy or 1e-12
    t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0, 1)
    dd = (X - x0 - t * dx) ** 2 + (Y - y0 - t * dy) ** 2; m = dd <= (w / 2 + d) ** 2; sub = nm[l][si, sj]; sub[m & (sub == 0)] = nid
    c = dd <= max(w / 2 - 0.05, 0.02) ** 2; cs = core[l][si, sj]; cs[c] = nid
for p in D['pads']:
    nid = NID.get(p['net'], -2)
    for ln in p['layers']:
        l = LAYERS.index(ln)
        if p['round']: circ(l, p['x'], p['y'], (p['bx1'] - p['bx0']) / 2, nid)
        else: rect(l, p['bx0'], p['by0'], p['bx1'], p['by1'], nid)
for t in D['tracks']:
    seg(LAYERS.index(t['layer']), t['x0'], t['y0'], t['x1'], t['y1'], t['w'], NID[t['net']])
for v in D['vias']:
    for l in range(4): circ(l, v['x'], v['y'], v['d'] / 2, NID[v['net']])
edge_d = np.minimum(np.minimum(xs, S - xs), np.minimum(ys, S - ys))
anode = {}                                    # own anode pads: no via-in-pad
for p in D['pads']:
    if p['ref'].startswith('D') and p['n'] == '2': anode.setdefault(p['net'], []).append(p)
pad = {(p['ref'], p['n']): p for p in D['pads']}
cvias = {}
for v in D['vias']: cvias.setdefault(v['net'], []).append((v['x'], v['y']))
XN, YN = D['nodes_x'], D['nodes_y']

def route(net, kind, start_xy):
    key = net; net = net.split('#')[0]
    if kind == 'SIG':
        k = int(key.split('#')[1]); terms = SIGNETS[net]
        SIGSTART[net] = pad[terms[k + 1]]; tp = pad[terms[0]]; SIGTGT[net] = (tp['x'], tp['y'])
    nid = NID[net]; w = W[kind]
    other = (nm != 0) & (nm != nid)
    if kind == 'ROW':                                   # forbid via-in-pad on own anode pads
        extra = np.zeros((n, n), bool)
        for p in anode[net]:
            si, sj = win(p['bx0'], p['by0'], p['bx1'], p['by1']); X, Y = xs[si, sj], ys[si, sj]
            extra[si, sj] |= (X >= p['bx0'] - DELTA) & (X <= p['bx1'] + DELTA) & (Y >= p['by0'] - DELTA) & (Y <= p['by1'] + DELTA)
        otherF = other[0] | extra
    else:
        otherF = other[0]
    edt = [distance_transform_edt(~o) * G for o in (otherF, other[1], other[2], other[3])]
    tok = [(edt[l] >= w / 2 + MARG) & (edge_d >= w / 2 + EDGE) for l in RL]
    vok = (edt[0] >= VIA_R + MARG) & (edt[1] >= VIA_R + MARG) & (edt[2] >= VIA_R + MARG) & (edt[3] >= VIA_R + MARG) & (edge_d >= VIA_R + EDGE)
    if kind == 'ROW':
        r = int(net[4:6]) - 1; yb = YN[r] + D['bus_dy']
        goal = vok & (np.abs(ys - yb) <= 0.5 - VIA_R - 0.02) & (xs >= XN[0]) & (xs <= XN[-1])
        hfun = lambda i, j: abs(i * G - yb) / G
    elif kind == 'SIG':
        sp = SIGSTART[net]
        own = np.zeros((n, n), bool); si_, sj_ = win(sp['bx0'], sp['by0'], sp['bx1'], sp['by1']); X, Y = xs[si_, sj_], ys[si_, sj_]
        own[si_, sj_] = (X >= sp['bx0'] - 0.3) & (X <= sp['bx1'] + 0.3) & (Y >= sp['by0'] - 0.3) & (Y <= sp['by1'] + 0.3)
        if k == 0 or net not in CONN:
            CONN[net] = np.zeros((4, n, n), bool); p0 = pad[terms[0]]; si_, sj_ = win(p0['bx0'], p0['by0'], p0['bx1'], p0['by1'])
            CONN[net][3][si_, sj_] = (core[3][si_, sj_] == nid) & (xs[si_, sj_] >= p0['bx0']) & (xs[si_, sj_] <= p0['bx1']) & (ys[si_, sj_] >= p0['by0']) & (ys[si_, sj_] <= p0['by1'])
        goal = [CONN[net][l] & ~own for l in (2, 3)]
        tx, ty = SIGTGT[net]
        hfun = lambda i, j: math.hypot(j * G - tx, i * G - ty) / G
    else:
        goal = np.zeros((n, n), bool); jy = start_xy[1]
        for (x, y) in cvias[net]:
            if abs(y - jy) <= COL_BAND: goal |= (xs - x) ** 2 + (ys - y) ** 2 <= 0.15 ** 2
        xc = cvias[net][0][0]
        hfun = lambda i, j: (abs(j * G - xc) + max(0.0, abs(i * G - jy) - COL_BAND)) / G
    gl = [goal[0] & tok[0], goal[1] & tok[1]] if isinstance(goal, list) else [goal & tok[0], goal & tok[1]]
    si, sj = int(round(start_xy[1] / G)), int(round(start_xy[0] / G))
    tok[1][si, sj] = True                              # start on own pad (B.Cu)
    gsc = np.full((2, n, n), np.inf, np.float32); came = np.full((2, n, n), -1, np.int64)
    gsc[1, si, sj] = 0; hp = [(1.6 * hfun(si, sj), 0.0, 1, si, sj)]
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    VC = 10.0; lc = LCOST[kind]; found = None; it = 0
    while hp:
        f, g, l, i, j = heapq.heappop(hp); it += 1
        if g > gsc[l, i, j]: continue
        if gl[l][i, j] and (kind == 'COL' or True):
            found = (l, i, j); break
        if it > 1_500_000: break
        for di, dj, c in steps:
            a, b2 = i + di, j + dj
            if 0 <= a < n and 0 <= b2 < n and tok[l][a, b2]:
                ng = g + c * lc[l]
                if ng < gsc[l, a, b2]:
                    gsc[l, a, b2] = ng; came[l, a, b2] = (l * n + i) * n + j; heapq.heappush(hp, (ng + 1.6 * hfun(a, b2), ng, l, a, b2))
        if vok[i, j]:
            l2 = 1 - l; ng = g + VC
            if tok[l2][i, j] and ng < gsc[l2, i, j]:
                gsc[l2, i, j] = ng; came[l2, i, j] = (l * n + i) * n + j; heapq.heappush(hp, (ng + 1.6 * hfun(i, j), ng, l2, i, j))
    if not found: return None
    path = [found]
    while True:
        l, i, j = path[-1]; k = came[l, i, j]
        if k < 0: break
        path.append((int(k // (n * n)), int(k // n % n), int(k % n)))
    path.reverse()
    tracks, vias = [], []
    run = [path[0]]
    def flush(run):
        if len(run) < 2: return
        pts = [run[0]]
        for a, b2, c3 in zip(run, run[1:], run[2:]):
            if (b2[1] - a[1], b2[2] - a[2]) != (c3[1] - b2[1], c3[2] - b2[2]): pts.append(b2)
        pts.append(run[-1])
        for a, b2 in zip(pts, pts[1:]):
            tracks.append([a[2] * G, a[1] * G, b2[2] * G, b2[1] * G, w, LAYERS[RL[a[0]]], net])
    for p, q in zip(path, path[1:]):
        if p[0] != q[0]:
            flush(run); vias.append([p[2] * G, p[1] * G, net]); run = [q]
        else: run.append(q)
    flush(run)
    if kind == 'ROW': vias.append([found[2] * G, found[1] * G, net])
    before = core == nid
    for t in tracks: seg(LAYERS.index(t[5]), t[0], t[1], t[2], t[3], t[4], nid)
    for v in vias:
        for l in range(4): circ(l, v[0], v[1], VIA_R, nid)
    if kind == 'SIG':
        new = (core == nid) & ~before
        sp = SIGSTART[net]; si_, sj_ = win(sp['bx0'], sp['by0'], sp['bx1'], sp['by1'])
        new[3][si_, sj_] |= (core[3][si_, sj_] == nid) & (xs[si_, sj_] >= sp['bx0']) & (xs[si_, sj_] <= sp['bx1']) & (ys[si_, sj_] >= sp['by0']) & (ys[si_, sj_] <= sp['by1'])
        CONN[net] |= new
    length = sum(math.hypot(t[2] - t[0], t[3] - t[1]) for t in tracks)
    return tracks, vias, dict(length=length, vias=len(vias), it=it, layers={ln: sum(math.hypot(t[2] - t[0], t[3] - t[1]) for t in tracks if t[5] == ln) for ln in ('In2.Cu', 'B.Cu')})


def plan_rows():
    """Deterministic row escape: 8 lines per via channel, straight on B.Cu to each row bus, via at the bus."""
    Xs = [x for x in XN]
    X = min(x for x in Xs if x > pad[('J_ROW', '1')]['x'] - 1.0)          # via column just left of pin 1
    X = pad[('J_ROW', '1')]['x'] - 0.5
    shift = {p: (0 if p <= 8 else 1.0) for p in range(1, 17)}
    shift.update({p: (-1.0 if p <= 20 else 0 if p <= 28 else 1.0) for p in range(17, 33)})
    T, V = [], []
    for p in range(1, 33):
        net = 'ROW_%02d_ANODE' % p; pp = pad[('J_ROW', str(p))]; px, py = pp['x'], pp['y']; xl = px + shift[p]
        yb = YN[p - 1] + D['bus_dy']; up = p <= 16; sgn = -1 if up else 1
        y1 = py + (-0.95 if up else 1.25); y2 = y1 + sgn * abs(shift[p])
        if p == 17:                       # bus at the pad row: go under pins 1..16 (no lines there) to a via left of pin 1
            yh = py + 0.9; xv = pad[('J_ROW', '1')]['x'] - 1.0
            pts = [(px, py), (px, yh), (xv, yh), (xv, yb)]
        else:
            pts = [(px, py), (px, y1), (xl, y2), (xl, yb)]
            cand = [round(xl + sgn * -1 * k * 0.05, 3) for k in range(11, 200)]   # right of line (up) / left (down)
            xv = next(x for x in cand if min(abs(x - c) for c in XN) >= 0.75)
            pts.append((xv, yb))
        for a, b in zip(pts, pts[1:]):
            if a != b:
                w = 0.2 if (a[0] != b[0] and a[1] != b[1]) or (p == 17 and a[1] == b[1]) else W['ROW']
                T.append([a[0], a[1], b[0], b[1], w, 'B.Cu', net])
        V.append([xv, yb, net])
    return T, V

order = [('ROW_%02d_ANODE' % r, 'ROW', ('J_ROW', str(r))) for r in range(1, 33)] + [('COL_%02d' % c, 'COL', ('J_COL', str(c))) for c in range(1, 33)]
oi = lambda k: [k[i // 2] if i % 2 == 0 else k[-1 - i // 2] for i in range(len(k))]   # outer pins first
order = oi(order[:32]) + oi(order[32:])

import copy
rT, rV = plan_rows()
for t in rT: seg(LAYERS.index(t[5]), t[0], t[1], t[2], t[3], t[4], NID[t[6]])
for v in rV:
    for l in range(4): circ(l, v[0], v[1], VIA_R, NID[v[2]])
rstats = {}
for t in rT: rstats.setdefault(t[6], {'length': 0, 'vias': 1, 'layers': {'B.Cu': 0}}); rstats[t[6]]['length'] += math.hypot(t[2]-t[0], t[3]-t[1])
for k in rstats: rstats[k]['layers']['B.Cu'] = rstats[k]['length']
order = [o for o in order if o[1] == 'COL']
SIGNETS = {'GND': [('U_ID', '2'), ('U_ID', '5'), ('C_ID', '2'), ('J_ROW', '38'), ('J_ROW', '39'), ('J_ROW', '40'), ('J_ROW', '33'),
                   ('J_COL', '33'), ('J_COL', '38'), ('J_COL', '40')],
           'ID_SDA': [('J_ROW', '35'), ('U_ID', '3')], 'ID_SCL': [('J_ROW', '36'), ('U_ID', '1')],
           'ID_3V3': [('J_ROW', '37'), ('U_ID', '4'), ('C_ID', '1')]}
SIGSTART, SIGTGT, CONN, sig_order = {}, {}, {}, []
for netn, terms in SIGNETS.items():
    for k, t in enumerate(terms[1:]): sig_order.append((netn + '#%d' % k, 'SIG', t))

nm0 = nm.copy(); core0 = core.copy(); first = []
for attempt in range(6):
    nm[:] = nm0; core[:] = core0; CONN.clear()
    seq = [o for o in order if o[0] in first] + [o for o in order if o[0] not in first] + sig_order
    allt, allv, stats, fail = list(rT), list(rV), dict(rstats), []
    for net, kind, pk in seq:
        p = pad[pk]; res = route(net, kind, (p['x'], p['y']))
        if res is None:
            fail.append(net); print('FAIL', net, flush=True); continue
        t, v, s_ = res; allt += t; allv += v; stats[net] = s_
        print('%-14s len %6.1f mm vias %d it %d' % (net, s_['length'], s_['vias'], s_['it']), flush=True)
    print('attempt', attempt, 'failed:', fail, flush=True)
    if not fail: break
    first = fail + [f for f in first if f not in fail]
json.dump({'tracks': allt, 'vias': allv}, open(os.path.join(H, 'routes.json'), 'w'))
json.dump({'stats': stats, 'fail': fail}, open(os.path.join(H, 'route_stats.json'), 'w'), indent=1)
print('failed:', fail)
