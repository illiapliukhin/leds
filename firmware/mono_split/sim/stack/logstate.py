"""Rebuild the stack's visible state from the simulator's JSONL log (live tail or offline)."""
import numpy as np

DX, DY = [0, 1, 0, -1], [-1, 0, 1, 0]
FULL = 510.0          # full-scale OE samples per row (sum of 2^(k+1))


def decode_g(raw):
    p = raw.split()
    RS = int(p[5]); slots = [int(x) for x in p[9:17]]
    duty = np.zeros((32, 32), np.float32)
    for y, tok in enumerate(p[17:17 + 32]):
        parts = tok.split(':')
        drow = int(parts[0]); words = [int(w, 16) for w in parts[1].split(',')]
        on = [int(x) for x in parts[2].split(',')] if len(parts) > 2 else slots
        yy = drow if 0 <= drow < 32 else y
        row = np.zeros(32, np.float32)
        for w, o in zip(words, on):
            if w and o:
                row += o * ((w >> np.arange(32)) & 1)
        duty[yy] = row / FULL       # 1.0 = full-scale BCM duty
    return duty


class LogState:
    def __init__(self):
        self.t = 0.0
        self.layout = None; self.boards = []
        self.frames = []; self.plugged = []; self.unplug_t = []
        self.info = []; self.events = []; self.skew = []; self.coll = 0; self.cont = 0
        self.demo = ''; self.stream = {}

    def feed(self, r):
        self.t = r.get('t', self.t)
        if 'layout' in r:
            self.layout = r['layout']; self.boards = [tuple(b) for b in r['boards']]
            n = len(self.boards)
            self.frames = [None] * n; self.plugged = [True] * n; self.unplug_t = [None] * n
            self.info = [dict(id=b[3] & 0xFFFFFFFF, role='boot') for b in self.boards]
        elif 'g' in r:
            try: self.frames[r['g']] = decode_g(r['raw'])
            except Exception: pass
        elif 'plug' in r:
            for i, p in enumerate(r['plug']):
                if not p and self.plugged[i]: self.unplug_t[i] = r['t']
                if p: self.unplug_t[i] = None
            self.plugged = list(r['plug'])
        elif 'ev' in r:
            self.events.append((r['t'], r['ev'])); self.events = self.events[-14:]
        elif 'stats' in r:
            self.info = r['stats']; self.skew = r.get('skew', []); self.coll = r.get('coll', 0); self.cont = r.get('cont', 0)
        elif 'demo' in r:
            self.demo = r['demo']
        elif 'stream' in r:
            self.stream[r['stream']] = (r['bytes'], r['us'])

    def cables(self):
        pos = {(b[0], b[1]): (i, b) for i, b in enumerate(self.boards)}
        out = []
        for i, b in enumerate(self.boards):
            if not self.plugged[i]: continue
            for s in range(4):
                d = (s + b[2]) % 4
                n = pos.get((b[0] + DX[d], b[1] + DY[d]))
                if not n or not self.plugged[n[0]] or n[0] < i: continue
                s2 = [k for k in range(4) if (k + n[1][2]) % 4 == (d + 2) % 4][0]
                out.append((i, s, n[0], s2))
        return out

    def view(self):
        lead = [s for s in self.info if s.get('role') == 'LEAD' and s.get('plugged', True)]
        cw, ch = (lead[0].get('canvas') or (1, 1)) if lead else (1, 1)
        extra = ['bus collisions %d   FRAME_SYNC contention %d' % (self.coll, self.cont)]
        if self.demo: extra.insert(0, 'demo: %s' % self.demo)
        if self.stream:
            b = max(self.stream.values())
            extra.append('stream: %d B/frame of RLE tiles (%.1f ms on the wire)' % (b[0], b[0] * 0.02))
        return dict(frames=self.frames, plugged=self.plugged, info=self.info, cables=self.cables(),
                    title='6-board stack  %s  ->  %dx%d canvas' % (self.layout, cw * 32, ch * 32),
                    sub='real firmware x6 in QEMU, RS-485 500 kbps bus model, FRAME_SYNC + PRES nets  |  t=%.1f s' % self.t,
                    skew=self.skew, events=self.events,
                    unplug_age=[(self.t - u) if u is not None else 0 for u in self.unplug_t], extra=extra)
