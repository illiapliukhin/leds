"""Physical layout (boards, panels, FFCs, stacking cables) + the batched firmware model + pixel pipeline."""
import json, math, random
import numpy as np
from . import host
from .stack_model import Node, OFF, LEAD, FOLLOW, WAIT, STATE_NAMES

BOARD_W, BOARD_H = 148.0, 99.5
PANELS = {   # kind -> (size mm, cable/LED data file, title)
    'full': (160.0, 'cable_full.json', 'mono_panel_32x32_full 160 мм, шаг 5.0'),
    'flat': (166.7, 'cable_mono32.json', 'mono_panel_32x32 166.7 мм, шаг 2.54'),
    'lattice': (166.7, 'cable_lattice.json', 'mono_panel_32x32_lattice'),
}
_pd = {}
def panel_data(kind):
    if kind not in _pd:
        d = json.load(open(host.data_path(PANELS[kind][1])))
        pos = np.array(d['pos'], np.float32)
        size = PANELS[kind][0]
        if kind == 'full': pos = pos - pos.min(0) + 2.5               # LED centres 2.5 + 5(i-1)
        else: pos = pos - pos.min(0) + (size - (pos.max(0) - pos.min(0))) / 2
        _pd[kind] = {'lo': pos.min(0).tolist(), 'hi': pos.max(0).tolist(), 'A': np.array(d['A'], np.int32).reshape(-1), 'B': np.array(d['B'], np.int32).reshape(-1), 'pos': pos, 'size': size}
    return _pd[kind]

SIDE_OFF = [(0, -BOARD_H / 2), (BOARD_W / 2, 0), (0, BOARD_H / 2), (-BOARD_W / 2, 0)]
def rotv(x, y, r):
    for _ in range(r & 3): x, y = -y, x
    return x, y

class Board:
    def __init__(s, world, x, y, bid=None, rot=0):
        s.x, s.y, s.rot, s.powered = x, y, rot, True
        s.id = bid if bid is not None else world.new_id()
        s.node = Node(world, s.id)
        s.tile = np.zeros((32, 32), np.uint8); s.pdemo = 0; s.pdemo_t = 0
    def port_pos(s, side):
        dx, dy = rotv(*SIDE_OFF[side], s.rot); return s.x + dx, s.y + dy
    def world_dir(s, side): return (side + s.rot) & 3

class Panel:
    def __init__(s, kind, x, y, rot=0):
        s.kind, s.x, s.y, s.rot = kind, x, y, rot
        s.board = None; s.ffc = 'B'; s.open_col = -1
        s.duty = np.zeros(1024, np.float32)
    @property
    def size(s): return PANELS[s.kind][0]

class Cable:
    def __init__(s, a, as_, b, bs, ctype='B'):
        s.a, s.as_, s.b, s.bs, s.type, s.plugged = a, as_, b, bs, ctype, True

class World:
    def __init__(s):
        s.boards, s.panels, s.cables = [], [], []
        s.now = 0; s.maxb = 16; s._comp = None; s.brightness = 128; s.gamma = 2.2
        s.bus_bytes = 0; s.paused = False; s.rng = random.Random(7)
        s.pd_cache = {}

    # ------------------------------------------------ edit
    def new_id(s):
        while True:
            i = s.rng.randrange(0x10000000, 0xFFFFFFF0)
            if all(b.id != i for b in s.boards): return i
    def dirty(s): s._comp = None
    def add_board(s, x, y, rot=0, bid=None):
        b = Board(s, x, y, bid, rot); s.boards.append(b); s.dirty(); return b
    def add_panel(s, kind, x, y, rot=0):
        p = Panel(kind, x, y, rot); s.panels.append(p); return p
    def remove_board(s, b):
        s.boards.remove(b); s.cables = [c for c in s.cables if c.a is not b and c.b is not b]
        for p in s.panels:
            if p.board is b: p.board = None
        s.dirty()
    def remove_panel(s, p): s.panels.remove(p)
    def cable_at(s, b, side):
        for c in s.cables:
            if (c.a is b and c.as_ == side) or (c.b is b and c.bs == side): return c
    def connect(s, a, as_, b, bs, ctype='B'):
        if a is b or s.cable_at(a, as_) or s.cable_at(b, bs): return None
        c = Cable(a, as_, b, bs, ctype); s.cables.append(c); s.dirty(); return c
    def remove_cable(s, c): s.cables.remove(c); s.dirty()
    def set_power(s, b, on):
        b.powered = on
        if not on: b.node.reset(); b.tile[:] = 0
        s.dirty()
    def auto_connect(s, pitch=None, tol=45):
        """cable every pair of boards whose facing ports sit one panel pitch apart"""
        n = 0
        for a in s.boards:
            for b in s.boards:
                if a is b: continue
                for side in range(4):
                    wd = a.world_dir(side); P = pitch or 160.0
                    ex, ey = a.x + [0, 1, 0, -1][wd] * P, a.y + [-1, 0, 1, 0][wd] * P
                    if abs(b.x - ex) > tol or abs(b.y - ey) > tol: continue
                    bs = ((wd + 2) - b.rot) & 3
                    if s.connect(a, side, b, bs): n += 1
        return n
    def auto_panels(s, kind):
        for b in s.boards:
            if not any(p.board is b for p in s.panels):
                p = s.add_panel(kind, b.x, b.y, b.rot); p.board = b

    # ------------------------------------------------ wires
    def comps(s):
        if s._comp is None:
            par = {b.id: b.id for b in s.boards}
            def f(x):
                while par[x] != x: par[x] = par[par[x]]; x = par[x]
                return x
            for c in s.cables:
                if c.plugged and c.type == 'B' and c.a.powered and c.b.powered: par[f(c.a.id)] = f(c.b.id)
            groups = {}
            for b in s.boards:
                if b.powered: groups.setdefault(f(b.id), []).append(b)
            s._comp = {b.id: g for g in groups.values() for b in g}
            s._cmap = {}
            for c in s.cables: s._cmap[(c.a.id, c.as_)] = c; s._cmap[(c.b.id, c.bs)] = c
        return s._comp
    def groups(s):
        seen, out = set(), []
        for b in s.boards:
            g = s.comps().get(b.id)
            if g and id(g) not in seen: seen.add(id(g)); out.append(g)
        return out
    def bus_send(s, node, m):
        s.bus_bytes += 12
        uni = m.dst != 0xFFFFFFFF
        for b in s.comps().get(node.id, ()):
            o = b.node
            if o is node: continue
            if uni and o.id != m.dst and o.state in (FOLLOW, WAIT):
                # fast path, same effect as stack.c parsing a frame addressed to someone else:
                # only s_last_leader_msg is refreshed (handle_common), nothing else changes
                if m.src == o.leader: o.last_leader_msg = m.t
                o.rx_ok += 1; continue
            o.inbox.append(m)
    def board_of(s, node):
        for b in s.boards:
            if b.node is node: return b
    def pres_read(s, node, side):
        b = s._bmap.get(node.id)
        c = s._cmap.get((node.id, side))
        if not c or not c.plugged or c.type != 'B': return False
        o, os_ = (c.b, c.bs) if c.a is b else (c.a, c.as_)
        return o.powered and o.node.pres_out[os_]

    # ------------------------------------------------ time
    def step(s, ms):
        s._bmap = {b.id: b for b in s.boards}
        s.comps()
        live = [b for b in s.boards if b.powered]
        for _ in range(ms):
            s.now += 1
            for b in live: b.node.step()
            for b in live:
                n = b.node
                if n.sync_on and s.now >= n.sync_next:
                    if n.sync_n == 0: n._t0 = n.sync_next
                    n.sync_n += 1; n.sync_next = n._t0 + n.sync_n * 1000 // n.fps
                    hops = s.hop_count(b)
                    for o in s.comps().get(b.id, ()):
                        s.on_sync(o, hops.get(o.id, 0))

    def hop_count(s, root):
        g = {b.id: [] for b in s.comps().get(root.id, ())}
        for c in s.cables:
            if c.plugged and c.type == 'B' and c.a.id in g and c.b.id in g: g[c.a.id].append(c.b.id); g[c.b.id].append(c.a.id)
        d, q = {root.id: 0}, [root.id]
        for x in q:
            for y in g.get(x, ()):
                if y not in d: d[y] = d[x] + 1; q.append(y)
        return d

    def on_sync(s, b, hops):
        n = b.node
        n.frame += 1; n.swaps += 1; n.edge_times.append(s.now)
        while n.edge_times and n.edge_times[0] < s.now - 1000: n.edge_times.popleft()
        # edge skew: 0.15 m JST-SH cable ~0.75 ns/hop + GPIO ISR entry jitter (~1..3 us on the S3)
        n.skew_us = 0.9 * n.skew_us + 0.1 * (hops * 0.00075 + s.rng.uniform(1.0, 3.0))
        b.dirty = True                      # tile for this edge is rendered lazily (once per displayed frame)

    # ------------------------------------------------ pixels (stack.c render_task)
    def render_board(s, b):
        n = b.node
        if not n.me[0]:
            t = np.zeros((32, 32), np.uint8); v = 120 if (n.frame // 15) & 1 else 30
            i = np.arange(32); t[i, i] = v; t[i, 31 - i] = v; b.tile = t; return
        if b.pdemo:                              # demo.c single-panel demo on every board of the group
            key = ('d', b.pdemo, s.now // 16)
            if key not in s.pd_cache:
                if len(s.pd_cache) > 32: s.pd_cache.clear()
                b.pdemo_t = getattr(s, 'pdt_%d' % b.pdemo, 0); setattr(s, 'pdt_%d' % b.pdemo, b.pdemo_t + 1)
                s.pd_cache[key] = host.demo_frame(b.pdemo, b.pdemo_t)
            b.tile = s.pd_cache[key]; return
        key = (n.me[1], n.me[2], n.me[3], n.W, n.H, n.demo, n.fps, n.frame + 1)
        t = s.pd_cache.get(key)
        if t is None:
            t = host.tile(n.me[1], n.me[2], n.me[3], n.W, n.H, n.demo, n.fps, n.frame + 1)
            if len(s.pd_cache) > 512: s.pd_cache.clear()
            s.pd_cache[key] = t
        b.tile = t

    def update_panels(s):
        lut = host.duty_lut(s.brightness, s.gamma)
        for b in s.boards:
            if getattr(b, 'dirty', False): b.dirty = False; s.render_board(b)
        for p in s.panels:
            b = p.board
            if b is None or b not in s.boards or not b.powered: p.duty[:] = 0; continue
            lv = lut[b.tile.reshape(-1)].copy()
            if p.open_col >= 0: lv.reshape(32, 32)[:, p.open_col] = 0
            m = panel_data(p.kind)[p.ffc]
            out = np.zeros(1024, np.float32); ok = m >= 0
            np.maximum.at(out, m[ok], lv[ok]); p.duty = out

    # ------------------------------------------------ info
    def board_info(s, b):
        n = b.node
        lead = None
        for o in s.comps().get(b.id, ()):
            if o.node.state == LEAD: lead = o
        df = (n.frame - lead.node.frame) if lead and n.state == FOLLOW else 0
        return dict(id='%08X' % b.id, state=STATE_NAMES[n.state] if b.powered else 'выкл', leader='%08X' % n.leader if n.leader else '-',
                    pos='(%d,%d) %d°' % (n.me[1], n.me[2], n.me[3] * 90) if n.me[0] else 'не размещена',
                    fps=len(n.edge_times), skew=n.skew_us, dframe=df, members=len(n.members), canvas='%dx%d' % (n.W * 32, n.H * 32))

    # ------------------------------------------------ save / load / presets
    def to_json(s):
        bi = {b: i for i, b in enumerate(s.boards)}
        return {'boards': [dict(id=b.id, x=b.x, y=b.y, rot=b.rot, powered=b.powered, pdemo=b.pdemo, demo=b.node.demo) for b in s.boards],
                'panels': [dict(kind=p.kind, x=p.x, y=p.y, rot=p.rot, board=bi.get(p.board, -1), ffc=p.ffc, open_col=p.open_col) for p in s.panels],
                'cables': [dict(a=bi[c.a], as_=c.as_, b=bi[c.b], bs=c.bs, type=c.type, plugged=c.plugged) for c in s.cables],
                'maxb': s.maxb, 'brightness': s.brightness, 'gamma': s.gamma}
    def from_json(s, d):
        s.__init__()
        for e in d['boards']:
            b = s.add_board(e['x'], e['y'], e.get('rot', 0), e['id']); b.powered = e.get('powered', True); b.pdemo = e.get('pdemo', 0); b.node.demo = e.get('demo', -1)
        for e in d['panels']:
            p = s.add_panel(e['kind'], e['x'], e['y'], e.get('rot', 0)); p.ffc = e.get('ffc', 'B'); p.open_col = e.get('open_col', -1)
            if e.get('board', -1) >= 0: p.board = s.boards[e['board']]
        for e in d['cables']:
            c = s.connect(s.boards[e['a']], e['as_'], s.boards[e['b']], e['bs'], e.get('type', 'B'))
            if c: c.plugged = e.get('plugged', True)
        s.maxb = d.get('maxb', 16); s.brightness = d.get('brightness', 128); s.gamma = d.get('gamma', 2.2)
    def preset(s, cols, rows, kind='full', pitch=None):
        s.__init__()
        P = pitch or PANELS[kind][0]
        if cols * rows > 16: s.maxb = 256
        for r in range(rows):
            for c in range(cols):
                s.add_board(c * P, r * P)
        s.auto_connect(P); s.auto_panels(kind)
