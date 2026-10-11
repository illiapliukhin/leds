"""Batched host model of firmware/mono_split/main/stack.c: one generator per board, all boards stepped
together in 1 ms ticks by World.step() (no threads; 100+ boards cost ~1 resume/board/ms).
The generators are a line-by-line port of stack_task()/discover()/probe_side()/handle_common() with the
hardware (non-MONO_SIM) timings; compute_grid() and render_tile() are the real C code via host.py.
RS-485 is one shared bus per cable-connected group; PRES and FRAME_SYNC are wires derived from cables."""
import random
from collections import deque
from . import host

# stack.c timing sets. 'hw' = the #else branch (real board), 'sim' = the MONO_SIM branch validated by the
# QEMU regress (48/48). NOTE: with 'hw', the leader pings one member per 150 ms, so with >= 4 followers a
# member is pinged less often than T_MEMBER_LOST=400 ms and gets dropped -> endless re-discovery
# (the simulator reproduces this; see README). Default = 'hw+fix': HW timings with the proposed fix
# (ping period = min(150 ms, T_MEMBER_LOST / (2 * followers)) so every member is pinged in time).
PROFILES = {'hw': dict(SETTLE=1, SEEN=6, TOKEN=20, ELECT=600, LOST=600, MEMBER_LOST=400),
            'sim': dict(SETTLE=25, SEEN=110, TOKEN=450, ELECT=1500, LOST=2500, MEMBER_LOST=1600),
            'hw+fix': dict(SETTLE=1, SEEN=6, TOKEN=20, ELECT=600, LOST=600, MEMBER_LOST=400, PINGFIX=1)}
PING_FIX = True
T_SETTLE, T_SEEN, T_TOKEN, T_ELECT, T_LOST, T_MEMBER_LOST = 1, 6, 20, 600, 600, 400
PROFILE = 'hw+fix'
def set_profile(name):
    global T_SETTLE, T_SEEN, T_TOKEN, T_ELECT, T_LOST, T_MEMBER_LOST, PING_FIX, PROFILE
    p = PROFILES[name]; PING_FIX = bool(p.get('PINGFIX')); PROFILE = name
    T_SETTLE, T_SEEN, T_TOKEN, T_ELECT, T_LOST, T_MEMBER_LOST = p['SETTLE'], p['SEEN'], p['TOKEN'], p['ELECT'], p['LOST'], p['MEMBER_LOST']
from collections import namedtuple
class LeaderChunk(namedtuple('LeaderChunk', 'total start ids')):
    def nbytes(s): return 2 + 4 * len(s.ids)
class MapChunk(namedtuple('MapChunk', 'W H total start tiles')):
    def nbytes(s): return 4 + 7 * len(s.tiles)
(T_HELLO, T_LEADER, T_TOKEN_, T_PRESHI, T_SEEN_, T_TOKDONE, T_MAP, T_TIME, T_PING, T_PONG, T_TILE) = range(1, 12)
BCAST = 0xFFFFFFFF
OFF, ELECT, WAIT, DISCOVER, LEAD, FOLLOW = range(6)
STATE_NAMES = ['off', 'elect', 'wait', 'discover', 'LEADER', 'follower']
DX, DY = [0, 1, 0, -1], [-1, 0, 1, 0]
MSG_LEN = {T_HELLO: 1, T_TOKEN_: 1, T_PRESHI: 1, T_SEEN_: 6, T_TOKDONE: 0, T_TIME: 7, T_PING: 0, T_PONG: 10}

class Msg:
    __slots__ = ('type', 'src', 'dst', 'pl', 't')
    def __init__(s, type, src, dst, pl, t): s.type, s.src, s.dst, s.pl, s.t = type, src, dst, pl, t

def compute_grid_py(leader, members, edges):
    """Same BFS as stack.c compute_grid() (used only above the firmware's MAXB=16)."""
    t = {m: [False, 0, 0, 0] for m in members}
    if leader not in t: return {}, 1, 1
    t[leader] = [True, 0, 0, 0]
    changed = True
    while changed:
        changed = False
        for (a0, as0, b0, bs0) in edges:
            for d in (0, 1):
                a, b, as_, bs = (b0, a0, bs0, as0) if d else (a0, b0, as0, bs0)
                if a not in t or b not in t or not t[a][0] or t[b][0]: continue
                wd = (as_ + t[a][3]) & 3
                t[b] = [True, t[a][1] + DX[wd], t[a][2] + DY[wd], (((wd + 2) & 3) - bs + 4) & 3]; changed = True
    pl = [v for v in t.values() if v[0]]
    mx, my = min(v[1] for v in pl), min(v[2] for v in pl)
    W, H = max(v[1] for v in pl) - mx + 1, max(v[2] for v in pl) - my + 1
    return {k: (int(v[0]), v[1] - mx, v[2] - my, v[3]) for k, v in t.items()}, W, H

class Node:
    """One board's firmware instance (stack.c statics)."""
    def __init__(s, world, bid):
        s.w, s.id = world, bid
        s.reset()

    def reset(s):
        s.state = OFF; s.leader = 0; s.members = []; s.last_seen = {}; s.tiles = {}; s.W = s.H = 1
        s.me = (False, 0, 0, 0); s.edges = []; s.frame = 0; s.last_leader_msg = 0; s.abort = False; s.foreign = False
        s.demo = -1; s.fps = 60; s.mode = 0; s.inbox = deque(); s.pres_out = [False] * 4; s.sync_on = False
        s.sync_next = 0; s.sync_n = 0; s.swaps = 0; s.rx_ok = 0; s.tx_bytes = 0; s.edge_times = deque(); s.skew_us = 0.0
        s.gen = None; s.wake = 0; s.log = deque(maxlen=8); s.retries = 0

    # ---- HAL
    def now(s): return s.w.now
    def send(s, type, dst, pl=()):
        n = MSG_LEN.get(type) or (pl.nbytes() if hasattr(pl, 'nbytes') else len(pl) if isinstance(pl, (list, tuple)) else 8)
        s.tx_bytes += 12 + n
        s.w.bus_send(s, Msg(type, s.id, dst, pl, s.w.now + 1))
    def pres_read(s, side): return s.w.pres_read(s, side)
    def report(s, txt): s.log.append('%7.3f %s' % (s.w.now / 1000, txt))

    def add_member(s, i):
        if i in s.last_seen or len(s.members) >= s.w.maxb: return
        s.members.append(i); s.members.sort(); s.last_seen[i] = s.now()
    def remove_member(s, i):
        if i in s.last_seen: s.members.remove(i); del s.last_seen[i]

    # ---- coroutine helpers: every `yield` is 1 ms of board time
    # a generator yields the board time it wants to be resumed at (World skips it until then, unless
    # a bus message arrives first) - this is what makes 100+ boards cheap.
    def sleep(s, ms):
        end = s.now() + ms
        while s.now() < end: yield end
    def recv(s, to):
        end = s.now() + to
        while True:
            if s.inbox and s.inbox[0].t <= s.now():
                s.rx_ok += 1; return s.inbox.popleft()
            if s.now() >= end: return None
            yield end

    def lead_sync(s, on):
        s.sync_on = on
        if on: s.sync_next = s.now(); s.sync_n = 0

    def add_edge(s, a, as_, b, bs):
        if len(s.edges) >= (64 if s.w.maxb <= 16 else 4 * s.w.maxb) or (b, bs, a) in [(e[0], e[1], e[2]) for e in s.edges] or (a, as_, b) in [(e[0], e[1], e[2]) for e in s.edges]: return
        s.edges.append((a, as_, b, bs))

    def handle_common(s, m):
        if s.state in (LEAD, DISCOVER) and m.type in (T_LEADER, T_TIME, T_MAP) and m.src < s.id: s.abort = True
        if s.state == DISCOVER and m.src > s.id and m.type in (T_LEADER, T_TOKEN_, T_MAP): s.foreign = True
        if s.state == DISCOVER and m.type == T_HELLO and m.src not in s.last_seen: s.add_member(m.src)
        if m.src == s.leader: s.last_leader_msg = s.now()
        if m.src in s.last_seen: s.last_seen[m.src] = s.now()
        t = m.type
        if t == T_PRESHI and m.src != s.id:
            for side in range(4):
                if s.pres_read(side):
                    if s.state == DISCOVER: s.add_edge(m.src, m.pl[0], s.id, side)
                    else: s.send(T_SEEN_, BCAST, (side, m.src, m.pl[0]))
        elif t == T_SEEN_ and s.state == DISCOVER:
            s.add_edge(m.pl[1], m.pl[2], m.src, m.pl[0])
            if m.src not in s.last_seen: s.add_member(m.src)
        elif t == T_TOKEN_ and m.dst == s.id:
            yield from s.probe_side(m.pl[0]); s.send(T_TOKDONE, m.src)
        elif t == T_MAP and s.state not in (LEAD, DISCOVER) and m.src == s.leader:
            pl = m.pl
            if pl.start == 0: s._map_acc = {}
            s._map_acc = getattr(s, '_map_acc', {}); s._map_acc.update(dict(pl.tiles)); s.W, s.H = pl.W, pl.H
            if pl.start + len(pl.tiles) >= pl.total:                     # last chunk: map complete
                s.tiles = dict(s._map_acc); s.state = FOLLOW; s.apply_map_self()
        elif t == T_TIME and m.src == s.leader and s.state == FOLLOW:
            f = m.pl[0]; d = s.frame - f
            if d < 0 or d > 1: s.frame = f
            s.mode, s.demo = m.pl[2], m.pl[1]
            if m.pl[3] and m.pl[3] != s.fps: s.fps = m.pl[3]
        elif t == T_PING and m.dst == s.id:
            s.send(T_PONG, m.src, (s.swaps, 0, s.me[0]))

    def probe_side(s, side):
        s.pres_out[side] = True
        yield from s.sleep(T_SETTLE)
        s.send(T_PRESHI, BCAST, (side,))
        end = s.now() + T_SEEN
        while s.now() < end and not s.abort:
            m = yield from s.recv(10)
            if m: yield from s.handle_common(m)
        s.pres_out[side] = False
        yield from s.sleep(T_SETTLE)

    def compute_grid(s):
        if len(s.members) <= host.MAXB: s.tiles, s.W, s.H = host.compute_grid(s.id, list(s.members), s.edges)
        else: s.tiles, s.W, s.H = compute_grid_py(s.id, list(s.members), s.edges)

    def apply_map_self(s):
        t = s.tiles.get(s.id)
        s.me = (bool(t[0]), t[1], t[2], t[3]) if t and t[0] else (False, 0, 0, 0)
        s.report('%s tile %s (%d,%d) rot %d canvas %dx%d' % ('LEAD' if s.state == LEAD else 'FOLLOW', 'ok' if s.me[0] else 'UNPLACED', s.me[1], s.me[2], s.me[3] * 90, s.W * 32, s.H * 32))

    # stack.c (ef91197): LEADER and MAP are split into chunks (LCHUNK 60 ids, MCHUNK 34 tiles) with (n_total, start)
    LCHUNK, MCHUNK = 60, 34
    def beacon(s):
        n = len(s.members); st = 0
        while True:
            c = min(s.LCHUNK, n - st)
            s.send(T_LEADER, BCAST, LeaderChunk(n, st, tuple(s.members[st:st + c])))
            st += c
            if st >= n: break
    def send_map(s):
        items = list(s.tiles.items()); n = len(items); st = 0
        while True:
            c = min(s.MCHUNK, n - st)
            s.send(T_MAP, BCAST, MapChunk(s.W, s.H, n, st, tuple(items[st:st + c])))
            st += c
            if st >= n: break

    def discover(s):
        attempt = 0
        while True:
            s.state = DISCOVER; s.edges = []; s.foreign = False
            alive = {}
            for i in list(s.members):
                if s.abort: break
                if i not in s.last_seen: continue
                if i == s.id: alive[i] = True
                s.beacon()
                for side in range(4):
                    if s.abort: break
                    if i == s.id: yield from s.probe_side(side); continue
                    s.send(T_TOKEN_, i, (side,))
                    end = s.now() + T_TOKEN; done = False
                    while not done and not s.abort and s.now() < end:
                        m = yield from s.recv(10)
                        if m:
                            if m.type == T_TOKDONE and m.src == i: done = True; alive[i] = True
                            else: yield from s.handle_common(m)
            if s.abort: return
            for i in list(s.members):
                if not alive.get(i): s.report('member %08x silent -> dropped' % i); s.remove_member(i)
            s.compute_grid()
            placed = [v for v in s.tiles.values() if v[0]]
            clash = len({(v[1], v[2]) for v in placed}) != len(placed)
            if (len(placed) == len(s.members) and not clash and not s.foreign) or attempt >= 5: break
            s.report('discovery inconsistent (%d/%d) retry' % (len(placed), len(s.members))); s.retries += 1
            end = s.now() + 200 + random.randrange(300)
            while s.now() < end and not s.abort:
                m = yield from s.recv(10)
                if m: yield from s.handle_common(m)
            if s.abort: return
            attempt += 1
        s.state = LEAD; s.leader = s.id
        s.send_map()
        yield from s.sleep(5)
        s.send_map()
        s.apply_map_self()
        s.report('topology: %d edges' % len(s.edges))
        for i in s.members: s.last_seen[i] = s.now()

    def run(s):
        """stack_task()"""
        yield from s.sleep(random.randrange(5, 40))          # boot
        while True:
            s.state = ELECT; s.lead_sync(False); s.members = []; s.last_seen = {}; s.add_member(s.id); s.leader = 0
            s.report('ELECT %08x' % s.id)
            end = s.now() + T_ELECT; next_hello = s.now() + random.randrange(200); join = 0
            while s.now() < end and not join:
                if s.now() >= next_hello:
                    s.send(T_HELLO, BCAST, (0,)); next_hello = s.now() + 150 + random.randrange(250)
                m = yield from s.recv(10)
                if m:
                    if m.src not in s.last_seen: s.add_member(m.src); end = s.now() + T_ELECT // 2
                    if m.type in (T_LEADER, T_TIME, T_MAP) and m.src < s.id: join = m.src
                    if m.type in (T_PRESHI, T_TOKEN_): yield from s.handle_common(m)
            if join or s.members[0] != s.id:
                s.leader = join or s.members[0]; s.state = WAIT; s.last_leader_msg = s.now()
                s.report('follower of %08x' % s.leader)
                s.send(T_HELLO, s.leader, (1,))
                while True:
                    m = yield from s.recv(20)
                    if m:
                        if m.type in (T_LEADER, T_TIME) and m.src < s.leader:
                            s.leader = m.src; s.last_leader_msg = s.now(); s.send(T_HELLO, s.leader, (1,))
                        if m.type == T_LEADER and m.src == s.leader:
                            if m.pl.start == 0: s._listed = False
                            if s.id in m.pl.ids: s._listed = True
                            if m.pl.start + len(m.pl.ids) >= m.pl.total and not getattr(s, '_listed', False): s.send(T_HELLO, s.leader, (1,))
                        yield from s.handle_common(m)
                    if s.now() - s.last_leader_msg > T_LOST:
                        s.report('leader %08x lost' % s.leader); s.me = (False, 0, 0, 0); break
                continue
            s.leader = s.id; s.abort = False; s.report('LEADER of %d' % len(s.members))
            s.lead_sync(True)
            yield from s.discover()
            next_time = next_ping = next_beacon = 0; ping_i = 0; redo = False
            while True:
                now = s.now()
                if now >= next_time: s.send(T_TIME, BCAST, (s.frame, s.demo, s.mode, s.fps)); next_time = now + 500
                if now >= next_beacon: s.beacon(); next_beacon = now + 1000
                if now >= next_ping and len(s.members) > 1:
                    ping_i = (ping_i + 1) % len(s.members)
                    if s.members[ping_i] == s.id: ping_i = (ping_i + 1) % len(s.members)
                    s.send(T_PING, s.members[ping_i]); next_ping = now + (min(150, max(1, round(T_MEMBER_LOST / (2 * (len(s.members) - 1))))) if PING_FIX else 150)   # stack.c: per = LOST/(2·(n−1)) µs
                for i in list(s.members):
                    if i != s.id and now - s.last_seen[i] > T_MEMBER_LOST:
                        s.report('member %08x lost -> re-discovery' % i); s.remove_member(i); redo = True; break
                m = yield from s.recv(10)
                stepdown = False
                if m:
                    if m.type in (T_LEADER, T_TIME) and m.src != s.id:
                        if m.src < s.id: s.report('lower leader %08x: step down' % m.src); s.lead_sync(False); stepdown = True
                        else: next_beacon = 0
                    if not stepdown:
                        if m.type == T_HELLO and m.src not in s.last_seen: s.report('new board %08x' % m.src); s.add_member(m.src); redo = True
                        if m.type in (T_PONG, T_HELLO) and m.src in s.last_seen: s.last_seen[m.src] = s.now()
                        yield from s.handle_common(m)
                if stepdown: break
                if redo: yield from s.discover(); redo = False
                if s.abort: s.report('lower-ID leader present: step down'); s.lead_sync(False); break
                if s.leader != s.id: break

    wake = 0
    def step(s):
        now = s.w.now
        if s.wake > now and not (s.inbox and s.inbox[0].t <= now): return
        if s.gen is None: s.gen = s.run()
        s.wake = next(s.gen) or now + 1
