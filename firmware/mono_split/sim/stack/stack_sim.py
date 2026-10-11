#!/usr/bin/env python3
"""Host side of the 6-board stack simulation.

Runs N QEMU instances of the real mono_split firmware (MONO_SIM build). Per board:
  UART0 (TCP) = console + '@G' decoded scan stream,  UART1 (TCP) = RS-485 transceiver D/R.
The host models the physical arrangement: boards on a grid with a physical rotation, JST-SH cables
between facing ports (pin 1<->1, see design notes), one RS-485 multi-drop segment per connected
group (half duplex, 500 kbps, 20 us/byte, collisions corrupt both frames), the shared FRAME_SYNC net
and the per-cable PRES nets (pin 5 <-> pin 5, internal pull-downs, high if either end drives).
Side-band frames (type >= 0xF0) carry PRES/FRAME_SYNC levels and telemetry and take no wire time.
Everything is logged to a JSONL file with host timestamps for frame-exact offline video rendering.
"""
import argparse, heapq, queue, json, os, random, select, socket, subprocess, sys, threading, time

QEMU = open('/workspace/sim/qemu_path').read().strip()
FLASH = '/workspace/sim/flash_qemu.bin'
DX, DY = [0, 1, 0, -1], [-1, 0, 1, 0]
BYTE_US = 20.0          # 10 bits at 500 kbps

LAYOUTS = {
    # (gx, gy, physical rotation in quarter turns clockwise)
    '3x2': [(0, 0, 0), (1, 0, 1), (2, 0, 0), (0, 1, 2), (1, 1, 0), (2, 1, 3)],
    '1x1': [(0, 0, 0)],
    '6x1': [(0, 0, 0), (1, 0, 2), (2, 0, 0), (3, 0, 1), (4, 0, 0), (5, 0, 3)],
}
# eFuse-MAC stand-ins (QEMU's eFuse is blank). Lowest -> leader. Not in board order on purpose.
MACS = [0x24EC4A3B9D17, 0x24EC4A1F02C4, 0x24EC4A7A51E0, 0x24EC4A55C3A9, 0x24EC4A0C88F2, 0x24EC4A6E1D3B]



def layout_boards(layout):
    """named layouts, or any 'CxR' grid with pseudo-random rotations"""
    if layout in LAYOUTS: return LAYOUTS[layout]
    c, r = map(int, layout.split('x'))
    rng = random.Random(c * 100 + r)
    return [(x, y, rng.randrange(4)) for y in range(r) for x in range(c)]


def mac_for(i):
    if i < len(MACS): return MACS[i]
    return 0x24EC4A000000 | (random.Random(1000 + i).randrange(0x100000, 0xFFFFFF))


def crc8(d):
    c = 0
    for x in d:
        c ^= x
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def frame(t, pl=b''):
    b = bytes([len(pl), t]) + b'\xff\xff\xff\xfe' + b'\x00\x00\x00\x00' + pl
    return b'\x7e' + b + bytes([crc8(b)])


class Board:
    def __init__(self, i, gx, gy, rot, mac, base):
        self.i, self.gx, self.gy, self.rot, self.mac = i, gx, gy, rot, mac
        self.pcon, self.pbus = base + 10 * i, base + 10 * i + 1
        self.plugged = True
        self.drive = [0, 0, 0, 0]          # PRES this board drives, per side
        self.role = 'boot'; self.tile = None; self.canvas = (1, 1); self.leader = 0; self.role_t = 0.0
        self.frame = None; self.fid = 0; self.swaps = []; self.last_w = None
        self.con_buf = b''; self.bus_buf = b''; self.console = []
        self.tx_bytes = 0; self.proc = None; self.started = False; self.slock = threading.Lock(); self.outq = queue.Queue()


class Sim:
    def __init__(self, layout, log_path, base=5800):
        self.layout = layout
        self.boards = [Board(i, *p, mac_for(i), base) for i, p in enumerate(layout_boards(layout))]
        self.lock = threading.RLock()
        self.t0 = time.time()
        self.log = open(log_path, 'w')
        self.pending = []                  # heap of (end_time, seq, sender, bytes, comp_key)
        self.active = []                   # (start, end, sender, entry) transmissions on wire
        self.seq = 0
        self.busy = {}                     # component -> list of (start, end) for utilisation
        self.collisions = 0
        self.sync_drivers = {}             # component -> {board: last S time}
        self.contention = 0
        self.skew = {}                     # frame -> {board: host time}
        self.skews = []                    # recent (t, skew_ms)
        self.events = []
        self.running = True

    # ---------------------------------------------------------------- physical model
    def now(self): return time.time() - self.t0

    def L(self, **kw):
        kw['t'] = round(self.now(), 4)
        self.log.write(json.dumps(kw) + '\n')

    def event(self, text):
        with self.lock:
            self.events.append((self.now(), text)); self.events = self.events[-12:]
        self.L(ev=text)
        print('[%7.2f] %s' % (self.now(), text), flush=True)

    def cables(self):
        """(i, side_i, j, side_j) for facing ports of plugged neighbours."""
        pos = {(b.gx, b.gy): b for b in self.boards}
        out = []
        for b in self.boards:
            if not b.plugged: continue
            for s in range(4):
                d = (s + b.rot) % 4
                n = pos.get((b.gx + DX[d], b.gy + DY[d]))
                if not n or not n.plugged or n.i < b.i: continue
                s2 = [k for k in range(4) if (k + n.rot) % 4 == (d + 2) % 4][0]
                out.append((b.i, s, n.i, s2))
        return out

    def comps(self):
        par = list(range(len(self.boards)))
        def f(x):
            while par[x] != x: x = par[x]
            return x
        for a, _, c, _ in self.cables(): par[f(a)] = f(c)
        return [f(i) for i in range(len(self.boards))]

    def peer(self, i, s):
        for a, sa, c, sc in self.cables():
            if (a, sa) == (i, s): return c, sc
            if (c, sc) == (i, s): return a, sa
        return None

    def send(self, b, data):
        # never block the model (a blocked sendall while holding the lock deadlocks QEMU's UART chain):
        # queue per board, one writer thread per board keeps frames whole and in order
        b.outq.put(data)

    def writer(self, b):
        while self.running:
            data = b.outq.get()
            try: b.sock_bus.sendall(data)
            except OSError: pass

    def update_pres(self, i, s):
        b = self.boards[i]
        p = self.peer(i, s)
        lvl = b.drive[s] or (self.boards[p[0]].drive[p[1]] if p else 0)
        self.send(b, frame(0xF1, bytes([s, lvl])))
        if p: self.send(self.boards[p[0]], frame(0xF1, bytes([p[1], lvl])))

    def unplug(self, i, state):
        with self.lock:
            b = self.boards[i]
            old = [(a, sa, c, sc) for a, sa, c, sc in self.cables() if i in (a, c)]
            b.plugged = not state
            for a, sa, c, sc in old:          # cables pulled: PRES lines fall back to the pull-downs
                for k, sk in ((a, sa), (c, sc)): self.update_pres(k, sk)
            if b.plugged:
                for a, sa, c, sc in self.cables():
                    if i in (a, c):
                        for k, sk in ((a, sa), (c, sc)): self.update_pres(k, sk)
        self.event(('UNPLUG' if state else 'REPLUG') + ' board %d' % i)
        self.L(plug=[bb.plugged for bb in self.boards])

    # ---------------------------------------------------------------- side-band from a board
    def sideband(self, b, txt):
        if txt == 'H':
            b.started = True
            self.send(b, frame(0xF3, b.mac.to_bytes(6, 'big')))
        elif txt[0] == 'P':
            s, v = int(txt[1]), int(txt[2])
            with self.lock:
                b.drive[s] = v
                self.update_pres(b.i, s)
        elif txt == 'S':
            with self.lock:
                comp = self.comps(); me = comp[b.i]; t = self.now()
                drv = self.sync_drivers.setdefault(me, {})
                drv[b.i] = t
                self.L(s=b.i)
                others = [k for k, tt in drv.items() if k != b.i and t - tt < 0.1 and comp[k] == me]
                if others:
                    self.contention += 1
                    if self.contention % 30 == 1:
                        self.event('FRAME_SYNC contention: boards %s and %d both drive (merge window)' % (others, b.i))
                for o in self.boards:
                    if o is not b and comp[o.i] == me and o.started: self.send(o, frame(0xF2))
        elif txt[0] == 'W':
            p = txt[1:].split()
            f, demo = int(p[0]), int(p[2])
            t = self.now() - max(0, int(p[1])) / 1e6      # back-date to the board's own edge time
            with self.lock:
                b.swaps.append(t); b.swaps = b.swaps[-60:]; b.last_w = (f, demo)
                self.L(w=b.i, f=f, dm=demo, lat=int(p[1]))
                d = self.skew.setdefault(f, {})
                d[b.i] = t
                if len(self.skew) > 400:
                    for k in sorted(self.skew)[:100]: del self.skew[k]
        elif txt[0] == 'R':
            p = txt.split()
            with self.lock:
                b.role = p[1]; b.role_t = self.now()
                if p[1] in ('LEAD', 'FOLLOW') and len(p) >= 10:
                    b.leader = int(p[3], 16)
                    b.tile = (int(p[5]), int(p[6]), int(p[7])) if p[4] == '1' else None
                    b.canvas = (int(p[8]), int(p[9]))
            self.event('board %d (%s): %s' % (b.i, hex(b.mac & 0xFFFFFFFF), ' '.join(p[1:])))
            self.L(role=b.i, r=txt)
        elif txt[0] == 'E':
            self.event('topology from board %d:%s' % (b.i, txt[1:]))
        elif txt[0] == 'L':
            self.event('board %d: lost member %s' % (b.i, txt[2:]))
        elif txt[0] == 'T':
            p = txt.split()
            self.L(stream=b.i, bytes=int(p[1]), us=int(p[2]))

    # ---------------------------------------------------------------- RS-485 wire model
    def on_bus_frame(self, b, data):
        t = self.now()
        dur = len(data) * BYTE_US / 1e6
        with self.lock:
            comp = self.comps()[b.i]
            entry = {'t0': t, 't1': t + dur, 'src': b.i, 'data': data, 'comp': comp, 'bad': False}
            for a in self.active:
                if a['comp'] == comp and a['t1'] > t and a['src'] != b.i:
                    a['bad'] = entry['bad'] = True
                    self.collisions += 1
            self.active.append(entry)
            self.busy.setdefault(comp, []).append((t, t + dur))
            b.tx_bytes += len(data)
            self.seq += 1
            heapq.heappush(self.pending, (t + dur, self.seq, entry))

    def deliver_loop(self):
        while self.running:
            with self.lock:
                now = self.now()
                while self.pending and self.pending[0][0] <= now:
                    _, _, e = heapq.heappop(self.pending)
                    data = e['data']
                    if e['bad']:
                        data = bytes(x ^ random.choice((0x10, 0x42, 0x81)) for x in data)
                    comp = self.comps()
                    for o in self.boards:
                        if o.i != e['src'] and comp[o.i] == e['comp'] and self.boards[e['src']].plugged and o.plugged and o.started:
                            self.send(o, data)
                self.active = [a for a in self.active if a['t1'] > now - 0.01]
            time.sleep(0.0005)

    def utilisation(self, comp, win=1.0):
        now = self.now()
        lst = [(max(a, now - win), b) for a, b in self.busy.get(comp, []) if b > now - win]
        self.busy[comp] = [x for x in self.busy.get(comp, []) if x[1] > now - 5]
        return sum(b - a for a, b in lst) / win

    # ---------------------------------------------------------------- QEMU plumbing
    def start(self):
        for b in self.boards:
            b.proc = subprocess.Popen([QEMU, '-nographic', '-machine', 'esp32s3', '-m', '4M',
                '-drive', 'file=%s,if=mtd,format=raw,readonly=on' % FLASH,
                '-serial', 'tcp:127.0.0.1:%d,server=on,wait=on' % b.pcon,
                '-serial', 'tcp:127.0.0.1:%d,server=on,wait=off' % b.pbus, '-monitor', 'none'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        for b in self.boards:
            for _ in range(50):
                try:
                    b.sock_con = socket.create_connection(('127.0.0.1', b.pcon)); break
                except OSError: time.sleep(0.2)
            time.sleep(0.05)
            b.sock_bus = socket.create_connection(('127.0.0.1', b.pbus))
        for b in self.boards: threading.Thread(target=self.writer, args=(b,), daemon=True).start()
        threading.Thread(target=self.io_loop, daemon=True).start()
        threading.Thread(target=self.deliver_loop, daemon=True).start()
        self.L(layout=self.layout, boards=[(b.gx, b.gy, b.rot, b.mac) for b in self.boards])

    def stop(self):
        self.running = False
        for b in self.boards:
            if b.proc: b.proc.kill()

    def cmd(self, i, s):
        self.boards[i].sock_con.sendall((s + '\r\n').encode())

    def io_loop(self):
        socks = {}
        for b in self.boards:
            socks[b.sock_con] = (b, 'con'); socks[b.sock_bus] = (b, 'bus')
        while self.running:
            r, _, _ = select.select(list(socks), [], [], 0.05)
            for s in r:
                b, kind = socks[s]
                try: d = s.recv(65536)
                except OSError: d = b''
                if not d: continue
                if kind == 'con': self.on_con(b, d)
                else: self.on_bus_bytes(b, d)

    def on_bus_bytes(self, b, d):
        b.bus_buf += d
        buf = b.bus_buf
        while True:
            k = buf.find(b'\x7e')
            if k < 0: buf = b''; break
            buf = buf[k:]
            if len(buf) < 2 or len(buf) < 12 + buf[1]: break
            n = 12 + buf[1]
            fr, buf = buf[:n], buf[n:]
            if fr[2] >= 0xF0:
                if crc8(fr[1:-1]) == fr[-1]: self.sideband(b, fr[11:-1].decode(errors='replace'))
            elif b.plugged:
                self.on_bus_frame(b, fr)
        b.bus_buf = buf

    def on_con(self, b, d):
        b.con_buf += d
        while b'\n' in b.con_buf:
            line, b.con_buf = b.con_buf.split(b'\n', 1)
            s = line.decode(errors='replace').strip()
            if '@G' in s:
                pre, g = s.split('@G', 1)
                self.L(g=b.i, raw=g.strip())
                s = pre.strip()
            if s:
                s2 = s.replace('\x1b[0;32m', '').replace('\x1b[0;33m', '').replace('\x1b[0m', '')
                b.console.append(s2); b.console = b.console[-6:]
                if 'stack' in s2 or 'leader' in s2.lower():
                    self.L(con=b.i, s=s2[:160])

    # ---------------------------------------------------------------- stats for the sidebar
    def stats(self):
        with self.lock:
            comp = self.comps()
            out = []
            for b in self.boards:
                sw = [t for t in b.swaps if t > self.now() - 2]
                fps = (len(sw) - 1) / (sw[-1] - sw[0]) if len(sw) > 2 else 0
                out.append(dict(i=b.i, id=b.mac & 0xFFFFFFFF, role=b.role, tile=b.tile, fps=fps,
                                util=self.utilisation(comp[b.i]), plugged=b.plugged, canvas=b.canvas, comp=comp[b.i]))
            # skew over the last complete frames in the leader's component
            now = self.now()
            recent = [(f, d) for f, d in self.skew.items() if d and now - max(d.values()) > 0.3 and now - max(d.values()) < 2.0]
            sk = []
            for f, d in recent:
                grp = {}
                for k, t in d.items(): grp.setdefault(comp[k], []).append(t)
                for g in grp.values():
                    if len(g) >= 2: sk.append((max(g) - min(g)) * 1000)
            return out, sk


def scenario(sim, layout, args):
    """Scripted run. Times are host seconds."""
    def at(t):
        while sim.now() < t: time.sleep(0.05)
    at(4.0)
    order = list(range(len(sim.boards))); random.Random(3).shuffle(order)
    for k, i in enumerate(order):            # boards powered/started at slightly different times
        sim.cmd(i, 'stack start'); time.sleep(0.15 + 0.1 * k)
    sim.event('all boards: stack start')
    if args.short:
        return
    if args.show:
        while not check_formed(sim)[0]: time.sleep(0.2)
        sim.event('stack formed: %d boards placed' % len(sim.boards))
        lead = min(range(len(sim.boards)), key=lambda i: sim.boards[i].mac & 0xFFFFFFFF)
        time.sleep(1)
        for item in args.show.split(','):
            name, dur = item.split(':')
            sim.cmd(lead, 'stack demo ' + name); sim.event('demo: ' + name); sim.L(demo=name)
            if float(dur) <= 0: return
            time.sleep(float(dur))
        return
    t_run = None
    while t_run is None:
        st, _ = sim.stats()
        if sum(1 for s in st if s['role'] in ('LEAD', 'FOLLOW') and s['tile']) == len(sim.boards): t_run = sim.now()
        time.sleep(0.2)
    sim.event('stack formed: %d boards placed' % len(sim.boards))
    lead = min(range(len(sim.boards)), key=lambda i: sim.boards[i].mac & 0xFFFFFFFF)
    sim.L(phase='demos')
    for name, dur in (('scroll', 13), ('ball', 9), ('plasma', 8), ('wipe', 7)):
        sim.cmd(lead, 'stack demo ' + name); sim.event('demo: ' + name); sim.L(demo=name)
        time.sleep(dur)
    sim.cmd(lead, 'stack mode stream'); sim.cmd(lead, 'stack demo ball'); sim.event('mode: leader-streamed tiles (4-bit RLE)'); sim.L(demo='stream ball')
    time.sleep(8)
    sim.cmd(lead, 'stack mode gen'); sim.cmd(lead, 'stack demo scroll'); sim.event('mode: shared generative'); sim.L(demo='scroll')
    time.sleep(3)
    victim = args.victim if args.victim is not None else (2 if layout == '3x2' else 3)
    sim.unplug(victim, True)
    time.sleep(12)
    sim.unplug(victim, False)
    time.sleep(14)
    sim.cmd(lead, 'stack demo -'); sim.event('demo: cycle (left running)')
    sim.L(phase='steady')


def check_formed(sim, members=None, since=0.0):
    """True when every plugged board in `members` follows one leader, has a unique tile, and the tile map is an
    isometry of the physical layout (pairwise grid distances equal, rotation offset constant)."""
    st, _ = sim.stats()
    idx = members if members is not None else range(len(sim.boards))
    bs = [sim.boards[i] for i in idx]
    if any(b.role not in ('LEAD', 'FOLLOW') or not b.tile for b in bs): return False, 'unplaced'
    if any(b.role_t < since for b in bs): return False, 'stale (no re-formation yet)'
    if len({b.leader for b in bs}) != 1: return False, 'leaders %s' % sorted({hex(b.leader) for b in bs})
    if len({b.tile[:2] for b in bs}) != len(bs): return False, 'overlap'
    for a in bs:
        for c in bs:
            if abs(a.gx - c.gx) + abs(a.gy - c.gy) != abs(a.tile[0] - c.tile[0]) + abs(a.tile[1] - c.tile[1]):
                return False, 'geometry %d-%d' % (a.i, c.i)
    offs = {(b.tile[2] - b.rot) % 4 for b in bs}; offn = {(b.tile[2] + b.rot) % 4 for b in bs}
    if len(offs) != 1 and len(offn) != 1: return False, 'rotation'
    W, H = bs[0].canvas
    xs = [b.tile[0] for b in bs]; ys = [b.tile[1] for b in bs]
    if (W, H) != (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1): return False, 'canvas %dx%d' % (W, H)
    return True, 'ok'


def regress(sim, layout, args):
    """Unplug/replug every board position in turn; each step must re-form with all boards placed under one leader."""
    def wait(pred, tmo):
        t0 = sim.now()
        while sim.now() - t0 < tmo:
            ok, why = pred()
            if ok: return sim.now() - t0, 'ok'
            time.sleep(0.25)
        return None, pred()[1]
    time.sleep(4)
    order = list(range(len(sim.boards))); random.Random(3).shuffle(order)
    for k, i in enumerate(order):
        sim.cmd(i, 'stack start'); time.sleep(0.15 + 0.1 * k)
    res = {'layout': layout, 'steps': []}
    TMO = 60 + 4 * len(sim.boards)
    t, why = wait(lambda: check_formed(sim), TMO)
    res['form'] = t; sim.event('regress: initial formation %s (%s)' % ('%.1f s' % t if t else 'FAIL', why))
    ok_all = t is not None
    victims = list(range(len(sim.boards)))[:args.steps] if args.steps >= 0 else range(len(sim.boards))
    for v in victims:
        if not ok_all: break
        time.sleep(3)
        t_u = sim.now()
        sim.unplug(v, True)
        rest = [i for i in range(len(sim.boards)) if i != v]
        # with the victim gone, each remaining connected segment must be a consistent stack of its own
        def seg_ok():
            comp = sim.comps()
            for g in {comp[i] for i in rest}:
                mem = [i for i in rest if comp[i] == g]
                if len(mem) == 1:
                    continue
                ok, why = check_formed(sim, mem, t_u)
                if not ok: return False, why
            return True, 'ok'
        tu, wu = wait(seg_ok, TMO)
        t_r = sim.now()
        sim.unplug(v, False)
        tr, wr = wait(lambda: check_formed(sim, None, t_r), TMO)
        step = dict(victim=v, unplug_s=tu, unplug_why=wu, replug_s=tr, replug_why=wr, ok=tu is not None and tr is not None)
        res['steps'].append(step)
        sim.event('regress: board %d %s (split %s, merge %s)' % (v, 'PASS' if step['ok'] else 'FAIL',
                  '%.1fs' % tu if tu else wu, '%.1fs' % tr if tr else wr))
        if tr is None: ok_all = False
    res['pass'] = ok_all and len(res['steps']) == len(victims) and all(s['ok'] for s in res['steps'])
    json.dump(res, open(args.result, 'w'), indent=1)
    sim.event('regress: %s' % ('PASS' if res['pass'] else 'FAIL'))
    sim.L(regress=res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', default='3x2')
    ap.add_argument('--log', default=None)
    ap.add_argument('--headless', action='store_true')
    ap.add_argument('--duration', type=float, default=0)
    ap.add_argument('--short', action='store_true')
    ap.add_argument('--victim', type=int, default=None)
    ap.add_argument('--regress', action='store_true')
    ap.add_argument('--show', default='')
    ap.add_argument('--steps', type=int, default=-1)
    ap.add_argument('--result', default='/workspace/stack/regress.json')
    ap.add_argument('--base', type=int, default=5800)
    a = ap.parse_args()
    log = a.log or '/workspace/stack/run_%s.jsonl' % a.layout
    sim = Sim(a.layout, log, base=a.base)
    sim.start()
    th = threading.Thread(target=regress if a.regress else scenario, args=(sim, a.layout, a), daemon=True)
    th.start()
    try:
        viewer = None
        if not a.headless:
            viewer = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stack_view.py'), '--follow', log])
        end = a.duration or 1e9
        while sim.now() < end and (th.is_alive() or not a.regress):
            time.sleep(0.5)
            out, sk = sim.stats()
            sim.L(stats=[{k: v for k, v in o.items()} for o in out], skew=[round(x, 3) for x in sk[-40:]],
                  coll=sim.collisions, cont=sim.contention)
            sim.log.flush()
    finally:
        out, sk = sim.stats()
        sim.L(final=True, collisions=sim.collisions, contention=sim.contention)
        sim.log.flush()
        sim.stop()


if __name__ == '__main__':
    main()
