#!/usr/bin/env python3
"""Grid router (A*, 0.125 mm, 8-way + through vias) for the FFC fan-out of mono_panel_32x32_v2.
Clearance is checked on an exact distance field (analytic distance from every cell centre to every copper shape of
another net), not on a dilated raster, so the 0.5 mm FFC pads escape at the true 0.127 mm rule (+0.023 mm margin for
cell-to-cell chords and arc fillets).
  ROW_rr : J_ROW pad -> 0.6/0.3 via onto row bus rr (B.Cu only, 0.3 mm)
  COL_cc : J_COL pad -> any cathode via of column cc (B.Cu + In2.Cu, 0.2 mm; the cathode vias are through vias)
  GND/ID : multi-terminal trees (B.Cu + In2.Cu)
Reads fixed.json (gen_pcb.py base), writes routes.json + route_stats.json."""
import heapq, json, math, os, sys, time
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); D = json.load(open(os.path.join(H, 'fixed.json')))
G = 0.125; S = D['size']; n = int(round(S / G)) + 1
CLR = 0.15                      # 0.127 rule + 0.023 margin
EDGE = 0.32; VIA_R = 0.3; RMAX = 1.0
W = {'ROW': 0.3, 'COL': 0.2, 'SIG': 0.25}
LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']; RL = [2, 3]
nets = sorted({p['net'] for p in D['pads'] if p['net']} | {t['net'] for t in D['tracks']} | {v['net'] for v in D['vias']})
NID = {s: i + 1 for i, s in enumerate(nets)}
xs1 = np.arange(n) * G
D1 = np.full((4, n, n), RMAX, np.float32); N1 = np.zeros((4, n, n), np.int32); D2 = np.full((4, n, n), RMAX, np.float32)
OWN = np.zeros((4, n, n), np.int32)          # net id of copper covering the cell (core), for goals

def upd(l, si, sj, d, nid):
    a1, b1, a2 = D1[l][si, sj], N1[l][si, sj], D2[l][si, sj]
    closer = d < a1
    diff = b1 != nid
    newD2 = np.where(closer, np.where(diff, a1, a2), np.where((~closer) & (nid != b1), np.minimum(a2, d), a2))
    D1[l][si, sj] = np.where(closer, d, a1); N1[l][si, sj] = np.where(closer, nid, b1); D2[l][si, sj] = newD2
    core = OWN[l][si, sj]; core[d <= -0.03] = nid

def window(x0, y0, x1, y1, m=RMAX):
    i0, i1 = max(0, int((y0 - m) / G)), min(n, int((y1 + m) / G) + 2); j0, j1 = max(0, int((x0 - m) / G)), min(n, int((x1 + m) / G) + 2)
    return slice(i0, i1), slice(j0, j1)
def add_rect(l, x0, y0, x1, y1, nid):
    si, sj = window(x0, y0, x1, y1); Y = xs1[si][:, None]; X = xs1[sj][None, :]
    dx = np.maximum(np.maximum(x0 - X, 0), X - x1); dy = np.maximum(np.maximum(y0 - Y, 0), Y - y1)
    inside = (dx == 0) & (dy == 0)
    d = np.hypot(dx, dy); din = -np.minimum(np.minimum(X - x0, x1 - X), np.minimum(Y - y0, y1 - Y))
    upd(l, si, sj, np.where(inside, din, d).astype(np.float32), nid)
def add_seg(l, x0, y0, x1, y1, w, nid):
    si, sj = window(min(x0, x1) - w, min(y0, y1) - w, max(x0, x1) + w, max(y0, y1) + w); Y = xs1[si][:, None]; X = xs1[sj][None, :]
    dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy or 1e-12
    t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0, 1)
    d = np.hypot(X - x0 - t * dx, Y - y0 - t * dy) - w / 2
    upd(l, si, sj, d.astype(np.float32), nid)
def add_circ(l, x, y, r, nid):
    si, sj = window(x - r, y - r, x + r, y + r); Y = xs1[si][:, None]; X = xs1[sj][None, :]
    upd(l, si, sj, (np.hypot(X - x, Y - y) - r).astype(np.float32), nid)

t0 = time.time()
for p in D['pads']:
    nid = NID.get(p['net'], -1) if p['net'] else -1
    for ln in p['layers']: add_rect(LAYERS.index(ln), p['bx0'], p['by0'], p['bx1'], p['by1'], nid)
for t in D['tracks']: add_seg(LAYERS.index(t['layer']), t['x0'], t['y0'], t['x1'], t['y1'], t['w'], NID[t['net']])
for v in D['vias']:
    for l in range(4): add_circ(l, v['x'], v['y'], v['d'] / 2, NID[v['net']])
for h in D['holes']:
    for l in range(4): add_circ(l, h['x'], h['y'], h['r'] + 0.12, -2)       # hole clearance 0.25 = 0.127 + 0.12
print('fields %.1f s' % (time.time() - t0), flush=True)
Y2, X2 = np.meshgrid(xs1, xs1, indexing='ij')
edge_d = np.minimum(np.minimum(X2, S - X2), np.minimum(Y2, S - Y2)).astype(np.float32)
pad = {(p['ref'], p['n']): p for p in D['pads']}
cvias = {}
for v in D['vias']: cvias.setdefault(v['net'], []).append((v['x'], v['y']))
XL, YB = D['XL'], D['YB']

def route(net, kind, start, goal_fn, hfun, layers_ok=(True, True), via_cost=12.0, lcost=(1.0, 1.0), final_via=False, w=None):
    nid = NID[net]; w = w or W[kind]
    oth = [np.where(N1[l] == nid, D2[l], D1[l]) for l in range(4)]
    tok = [(oth[l] >= w / 2 + CLR) & (edge_d >= w / 2 + EDGE) & layers_ok[k] for k, l in enumerate(RL)]
    vok = (oth[0] >= VIA_R + CLR) & (oth[1] >= VIA_R + CLR) & (oth[2] >= VIA_R + CLR) & (oth[3] >= VIA_R + CLR) & (edge_d >= VIA_R + EDGE)
    gl = goal_fn(tok, vok, nid)
    si, sj = int(round(start[1] / G)), int(round(start[0] / G)); sl = 1
    tok[sl][si, sj] = True
    g = {(sl, si, sj): 0.0}; came = {}; hp = [(hfun(si, sj), 0.0, sl, si, sj)]
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    found = None; it = 0
    while hp:
        f, gg, l, i, j = heapq.heappop(hp); it += 1
        if gg > g.get((l, i, j), 1e18) + 1e-9: continue
        if gl[l][i, j]: found = (l, i, j); break
        if it > 3_000_000: break
        for di, dj, c in steps:
            a, b2 = i + di, j + dj
            if 0 <= a < n and 0 <= b2 < n and tok[l][a, b2]:
                if c > 1 and not (tok[l][a, j] and tok[l][i, b2]): continue       # no corner cutting
                ng = gg + c * lcost[l]
                if ng < g.get((l, a, b2), 1e18):
                    g[(l, a, b2)] = ng; came[(l, a, b2)] = (l, i, j); heapq.heappush(hp, (ng + 1.3 * hfun(a, b2), ng, l, a, b2))
        if vok[i, j] and layers_ok[1 - l]:
            l2 = 1 - l; ng = gg + via_cost
            if tok[l2][i, j] and ng < g.get((l2, i, j), 1e18):
                g[(l2, i, j)] = ng; came[(l2, i, j)] = (l, i, j); heapq.heappush(hp, (ng + 1.3 * hfun(i, j), ng, l2, i, j))
    if not found: return None
    path = [found]
    while path[-1] in came: path.append(came[path[-1]])
    path.reverse()
    paths, vias = [], []
    run = [path[0]]
    def flush(run):
        if len(run) < 2: return
        pts = [run[0]]
        for a, b2, c3 in zip(run, run[1:], run[2:]):
            if (b2[1] - a[1], b2[2] - a[2]) != (c3[1] - b2[1], c3[2] - b2[2]): pts.append(b2)
        pts.append(run[-1])
        paths.append(dict(net=net, layer=LAYERS[RL[run[0][0]]], w=w, pts=[[q[2] * G, q[1] * G] for q in pts]))
    for p, q in zip(path, path[1:]):
        if p[0] != q[0]: flush(run); vias.append([p[2] * G, p[1] * G, net]); run = [q]
        else: run.append(q)
    flush(run)
    if final_via: vias.append([found[2] * G, found[1] * G, net])
    # real start: pad centre (off-grid by < G/2, inside the pad)
    if paths and paths[0]['layer'] == 'B.Cu':
        paths[0]['pts'][0] = [start[0], start[1]] if abs(start[0] - paths[0]['pts'][0][0]) < 0.07 and abs(start[1] - paths[0]['pts'][0][1]) < 0.07 else paths[0]['pts'][0]
    for pth in paths:
        l = LAYERS.index(pth['layer'])
        for a, b2 in zip(pth['pts'], pth['pts'][1:]): add_seg(l, a[0], a[1], b2[0], b2[1], w, nid)
    for v in vias:
        for l in range(4): add_circ(l, v[0], v[1], VIA_R, nid)
    length = sum(math.hypot(b2[0] - a[0], b2[1] - a[1]) for pth in paths for a, b2 in zip(pth['pts'], pth['pts'][1:]))
    return paths, vias, dict(length=length, vias=len(vias), it=it)

def goal_row(r):
    yb = YB[r - 1]
    def f(tok, vok, nid):
        m = vok & (np.abs(Y2 - yb) <= 0.26) & (X2 >= 6.0) & (X2 <= S - 3.0)
        return [np.zeros_like(m), m & tok[1]]
    return f, (lambda i, j: abs(i * G - yb) / G)
def goal_col(c):
    net = 'COL_%02d' % c; xl = XL[c - 1]
    def f(tok, vok, nid):
        m = np.zeros((n, n), bool)
        for (x, y) in cvias[net]:
            i, j = int(round(y / G)), int(round(x / G)); m[i - 1:i + 2, j - 1:j + 2] = True
        m &= OWN[2] == nid
        return [m & tok[0], m & tok[1]]
    return f, (lambda i, j: abs(j * G - xl) / G)
CONN = {}
def goal_sig(group):
    def f(tok, vok, nid):
        m = CONN[group]; return [m[0] & tok[0], m[1] & tok[1]]
    return f
def conn_init(group, p):
    nid = NID[p['net']]; m = [np.zeros((n, n), bool), np.zeros((n, n), bool)]
    si, sj = window(p['bx0'], p['by0'], p['bx1'], p['by1'], 0)
    sub = (OWN[3][si, sj] == nid) & (Y2[si, sj] >= p['by0']) & (Y2[si, sj] <= p['by1']) & (X2[si, sj] >= p['bx0']) & (X2[si, sj] <= p['bx1'])
    m[1][si, sj] = sub; CONN[group] = m
def conn_add(group, paths, vias, endpad=None):
    m = CONN[group]
    for pth in paths:
        k = RL.index(LAYERS.index(pth['layer']))
        for a, b2 in zip(pth['pts'], pth['pts'][1:]):
            L_ = max(1, int(math.hypot(b2[0] - a[0], b2[1] - a[1]) / (G / 2)))
            for t in range(L_ + 1):
                x = a[0] + (b2[0] - a[0]) * t / L_; y = a[1] + (b2[1] - a[1]) * t / L_
                m[k][int(round(y / G)), int(round(x / G))] = True
    for v in vias:
        i, j = int(round(v[1] / G)), int(round(v[0] / G)); m[0][i, j] = m[1][i, j] = True
    if endpad is not None:
        p = endpad; si, sj = window(p['bx0'], p['by0'], p['bx1'], p['by1'], 0)
        m[1][si, sj] |= (X2[si, sj] >= p['bx0'] + 0.05) & (X2[si, sj] <= p['bx1'] - 0.05) & (Y2[si, sj] >= p['by0'] + 0.05) & (Y2[si, sj] <= p['by1'] - 0.05)

allp, allv, stats, fail = [], [], {}, []
def run(net, kind, start, gfun, hfun, **kw):
    t = time.time(); res = route(net, kind, start, gfun, hfun, **kw)
    if res is None: fail.append(net); print('FAIL', net, flush=True); return None
    p, v, s_ = res; allp.extend(p); allv.extend(v); stats.setdefault(net, []).append(s_)
    print('%-10s len %6.1f vias %d it %7d  %.1fs' % (net, s_['length'], s_['vias'], s_['it'], time.time() - t), flush=True)
    return res

def sig(group, terms, w=0.25):
    root = pad[terms[0]]; conn_init(group, root)
    for t in terms[1:]:
        p = pad[t]; tx, ty = root['x'], root['y']
        res = run(p['net'], 'SIG', (p['x'], p['y']), goal_sig(group), lambda i, j: math.hypot(j * G - tx, i * G - ty) / G * 0.6,
                  via_cost=6.0, w=w)
        if res: conn_add(group, res[0], res[1], endpad=p)

ORDER = sys.argv[1:] or ['sig', 'rows', 'cols']
if 'sig' in ORDER:
    # ID bus + local GND (J_ROW south end -> U_ID / C_ID), B.Cu + In2
    sig('SDA', [('U_ID1', '5'), ('J_ROW1', '35')], 0.2)
    sig('SCL', [('U_ID1', '6'), ('J_ROW1', '36')], 0.2)
    sig('3V3', [('U_ID1', '8'), ('C_ID1', '1'), ('J_ROW1', '37')], 0.25)
    sig('GNDA', [('U_ID1', '4'), ('U_ID1', '3'), ('U_ID1', '2'), ('U_ID1', '1'), ('U_ID1', '7'), ('C_ID1', '2'), ('J_ROW1', '40'), ('J_ROW1', '39'), ('J_ROW1', '38'), ('J_ROW1', '33')], 0.25)
if 'rows' in ORDER:
    yp = {k: pad[('J_ROW1', str(k))]['y'] for k in range(1, 33)}
    north = [k for k in range(1, 33) if YB[k - 1] < yp[k]]; south = [k for k in range(1, 33) if YB[k - 1] >= yp[k]]
    for k in sorted(south, reverse=True) + sorted(north):
        p = pad[('J_ROW1', str(k))]; gf, hf = goal_row(k)
        run('ROW_%02d' % k, 'ROW', (p['x'], p['y']), gf, hf, layers_ok=(False, True), final_via=True)
if 'cols' in ORDER:
    cs = list(range(1, 33)); cs.sort(key=lambda c: -abs(XL[c - 1] - pad[('J_COL1', str(c))]['x']))
    pf = os.path.join(H, 'route_first.json'); first = json.load(open(pf)) if os.path.exists(pf) else []
    cs = [c for c in first if c in cs] + [c for c in cs if c not in first]
    for c in cs:
        p = pad[('J_COL1', str(c))]; gf, hf = goal_col(c)
        run('COL_%02d' % c, 'COL', (p['x'], p['y']), gf, hf, via_cost=8.0, lcost=(1.0, 1.6))
    sig('GNDB', [('J_COL1', '40'), ('J_COL1', '38'), ('J_COL1', '33')], 0.25)
# GND stitching vias (In2 plane <-> B.Cu pour) at the free corner of every other cell, if clear on all 4 layers
gid = NID['GND']; oth = [np.where(N1[l] == gid, D2[l], D1[l]) for l in range(4)]; stitch = []
for r in range(32):
    for c in range(32):
        if (r + c) % 2: continue
        x, y = D['XC'][c] + 4.0, D['YR'][r] + 4.0
        if x > S - 1.0 or y > S - 1.0: continue
        i, j = int(round(y / G)), int(round(x / G))
        if all(oth[l][i - 1:i + 2, j - 1:j + 2].min() >= VIA_R + CLR + 0.1 for l in range(4)): stitch.append([j * G, i * G])
print('stitch vias', len(stitch))
json.dump({'paths': allp, 'vias': allv, 'stitch': stitch}, open(os.path.join(H, 'routes.json'), 'w'))
json.dump({'stats': stats, 'fail': fail}, open(os.path.join(H, 'route_stats.json'), 'w'), indent=1)
print('failed:', fail)
if fail:
    pf = os.path.join(H, 'route_first.json'); first = json.load(open(pf)) if os.path.exists(pf) else []
    newf = [int(f[4:]) for f in fail if f.startswith('COL_')]
    json.dump(newf + [c for c in first if c not in newf], open(pf, 'w'))
    sys.exit(1)
