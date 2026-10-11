"""Copper network of one net from the real .kicad_pcb geometry (exported JSON): every track segment is a
resistor R = rho*L/(w*t) (rho_Cu(T) = 1.724e-8*(1+0.00393*(T-20)) ohm*m), every via a barrel resistor,
pads join the segment ends they touch. Two-terminal resistance and the current in every segment come from
nodal analysis (Laplacian solve). Zones are not counted (conservative, documented assumption)."""
import gzip, json, math
import numpy as np

T_CU = {0: 35e-6, 1: 17.5e-6, 2: 17.5e-6, 3: 35e-6}     # outer 1 oz, inner 0.5 oz  (assumption: fab stackup not in repo)
BOARD_T = 1.6e-3
VIA_PLATING = 20e-6                                     # IPC class 2 min average plating (assumption)
def rho_cu(T=20.0): return 1.724e-8 * (1 + 0.00393 * (T - 20))

class NetModel:
    def __init__(s, pcb, net, T=25.0):
        s.net = net; nodes = {}; s.seg = []                 # (n1, n2, R, width_m, thick_m, layer, xy)
        def nid(x, y, L):
            k = (round(x, 2), round(y, 2), L)
            if k not in nodes: nodes[k] = len(nodes)
            return nodes[k]
        rho = rho_cu(T)
        for t in pcb['tracks']:
            if t[2] != net: continue
            L, w, P = t[0], t[1] * 1e-3, t[3]
            for k in range(0, len(P) - 2, 2):
                x0, y0, x1, y1 = P[k:k + 4]; ln = math.hypot(x1 - x0, y1 - y0) * 1e-3
                if ln <= 0: continue
                s.seg.append((nid(x0, y0, L), nid(x1, y1, L), rho * ln / (w * T_CU[L]), w, T_CU[L], L, ((x0 + x1) / 2, (y0 + y1) / 2), ln))
        s.vias = []
        for v in pcb['vias']:
            if v[3] != net: continue
            d = max(v[2] - 0.3, 0.3) * 1e-3                # drill ~ size - 2*annular (assumption)
            R = rho * BOARD_T / (math.pi * d * VIA_PLATING)
            ids = [nid(v[0], v[1], L) for L in range(4)]
            for L in range(3): s.seg.append((ids[L], ids[L + 1], R / 3, None, None, -1, (v[0], v[1]), 0))
        s.nodes = nodes
        # snap: join every node to any other node on any layer within 0.12 mm (ends meeting at vias / T-joins)
        keys = list(nodes); arr = np.array([(k[0], k[1]) for k in keys]) if keys else np.zeros((0, 2))
        s.pads = [p for p in pcb['pads'] if p[9] == net]
        s.fps = pcb['fps']
        s.join = []
        for i, k in enumerate(keys):
            d = np.hypot(arr[:, 0] - k[0], arr[:, 1] - k[1])
            for j in np.nonzero((d < 0.12) & (np.arange(len(keys)) > i))[0]:
                s.join.append((i, int(j)))
        s.n = len(nodes); s.keys = keys
    def pad_nodes(s, ref, pin=None):
        out = []
        for p in s.pads:
            if s.fps[p[0]][0] != ref or (pin is not None and p[1] != str(pin)): continue
            hw, hh = p[4] / 2 + 0.05, p[5] / 2 + 0.05
            if int(round(p[6])) % 180 == 90: hw, hh = hh, hw
            for i, k in enumerate(s.keys):
                if abs(k[0] - p[2]) <= hw and abs(k[1] - p[3]) <= hh and (p[8] >> max(k[2], 0)) & 1 or (abs(k[0] - p[2]) <= hw and abs(k[1] - p[3]) <= hh and p[8] == 15):
                    out.append(i)
        return sorted(set(out))
    def solve(s, ref_a, ref_b, I=1.0):
        """inject I at pads of ref_a, extract at ref_b -> (R_ohm, per-segment currents, node voltages)"""
        A, B = s.pad_nodes(ref_a), s.pad_nodes(ref_b)
        if not A or not B: return None
        n = s.n + 2; a, b = s.n, s.n + 1                    # two super-nodes for the pads
        G = np.zeros((n, n))
        def add(i, j, g): G[i, i] += g; G[j, j] += g; G[i, j] -= g; G[j, i] -= g
        for (i, j, R, *_r) in s.seg: add(i, j, 1 / R)
        for (i, j) in s.join: add(i, j, 1e4)
        for i in A: add(a, i, 1e4)
        for i in B: add(b, i, 1e4)
        rhs = np.zeros(n); rhs[a] = I
        keep = [k for k in range(n) if k != b]             # ground node b
        v = np.zeros(n)
        try: v[keep] = np.linalg.solve(G[np.ix_(keep, keep)] + np.eye(len(keep)) * 1e-12, rhs[keep])
        except np.linalg.LinAlgError: return None
        cur = [abs(v[i] - v[j]) / R for (i, j, R, *_r) in s.seg]
        return (v[a] - v[b]) / I, cur, v

def onderdonk_time(I, area_m2, Ta=25.0, Tm=1083.0):
    """Onderdonk fusing equation (basis of IPC-2152/Brooks fusing charts): time (s) for a copper conductor of
    cross-section A to reach melting under current I. I = A_cmil*sqrt(log10((Tm-Ta)/(234+Ta)+1)/(33*t))."""
    if I <= 0: return float('inf')
    cmil = area_m2 / (math.pi * (0.0254e-3 / 2) ** 2)
    return math.log10((Tm - Ta) / (234 + Ta) + 1) * cmil ** 2 / (33 * I ** 2)

_cache = {}
def board_net(key, net, path):
    k = (key, net)
    if k not in _cache: _cache[k] = NetModel(json.load(gzip.open(path, 'rt', encoding='utf-8')), net)
    return _cache[k]
