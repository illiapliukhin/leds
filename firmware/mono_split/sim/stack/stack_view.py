"""Combined viewer for the 6-board stack (live window and offline frame-exact renderer)."""
import math, os, statistics, time
import numpy as np
import pygame

PORT_FRAC = {0: (0.851, 0.0), 1: (1.0, 0.422), 2: (0.432, 1.0), 3: (0.0, 0.884)}   # N,E,S,W on the v11c PCB
DX, DY = [0, 1, 0, -1], [-1, 0, 1, 0]
AMBER = (255, 150, 30)
# real mono_panel_32x32 geometry (hardware/mono_panel_32x32/mono_panel_32x32.kicad_pcb)
PANEL_MM = 160.0          # mono_panel_32x32_full outline (seamless when butted)
LED_PITCH_MM = 5.0
LED0_MM = 2.5             # pitch/2: seam pitch = 5.0 mm


def rot_pt(u, v, rot):
    """local (u,v) in [0,1]^2 of a board -> world-local after rot quarter turns clockwise"""
    for _ in range(rot % 4):
        u, v = 1 - v, u
    return u, v


def tile_xy(rot, rr, c):
    if rot == 0: return c, rr
    if rot == 1: return 31 - rr, c
    if rot == 2: return 31 - c, 31 - rr
    return rr, 31 - c


class Renderer:
    def __init__(self, W, H, layout, boards):
        """boards: list of (gx, gy, rot, mac)"""
        self.W, self.H, self.layout, self.boards = W, H, layout, boards
        self.surf = pygame.Surface((W, H))
        nx = max(b[0] for b in boards) + 1; ny = max(b[1] for b in boards) + 1
        self.side = nx / ny <= 2          # sidebar on the right (3x2) or below (6x1)
        if self.side:
            self.area = (40, 100, W - 680, H - 150)
        else:
            self.area = (30, 110, W - 60, int(H * 0.42))
        gap = 0.0                          # panels butted edge to edge (production seam)
        ax, ay, aw, ah = self.area
        P = min(aw / (nx + (nx - 1) * gap), ah / (ny + (ny - 1) * gap))
        self.P = P; self.gap = gap * P
        tw, th = nx * P + (nx - 1) * self.gap, ny * P + (ny - 1) * self.gap
        self.ox, self.oy = ax + (aw - tw) / 2, ay + (ah - th) / 2
        self.mm = P / PANEL_MM
        self.pitch = LED_PITCH_MM * self.mm
        self.led0 = LED0_MM * self.mm
        self.mk_sprites()
        f = pygame.font.match_font('dejavusansmono') or None
        fb = pygame.font.match_font('dejavusans', bold=True) or None
        k = H / 1080
        self.f = pygame.font.Font(f, int(18 * k)); self.fs = pygame.font.Font(f, int(15 * k))
        self.fb = pygame.font.Font(fb, int(30 * k)); self.fm = pygame.font.Font(fb, int(21 * k))

    def mk_sprites(self):
        s = max(4, int(self.pitch * 2.2))
        self.sp = s
        r = self.pitch * 0.40
        self.sprites = []
        for q in range(65):
            v = q / 64.0
            big = pygame.Surface((s * 4, s * 4), pygame.SRCALPHA)
            c = s * 2
            base = (40, 12, 4)
            col = tuple(int(base[i] + (AMBER[i] - base[i]) * v) for i in range(3))
            hot = tuple(min(255, int(col[i] + (255 - col[i]) * 0.35 * v ** 3)) for i in range(3))
            pygame.draw.circle(big, col + (255,), (c, c), int(r * 4))
            pygame.draw.circle(big, hot + (255,), (c, c), max(1, int(r * 4 * 0.5)))
            self.sprites.append(pygame.transform.smoothscale(big, (s, s)))

    def board_rect(self, gx, gy, off=(0, 0)):
        return (self.ox + gx * (self.P + self.gap) + off[0], self.oy + gy * (self.P + self.gap) + off[1])

    def port_xy(self, i, side, offs):
        gx, gy, rot, _ = self.boards[i]
        x0, y0 = self.board_rect(gx, gy, offs[i])
        fu, fv = PORT_FRAC[side]
        u, v = (fu - 0.5) * 148, (fv - 0.5) * 99.5          # mm from the PCB centre, board frame
        for _ in range(rot % 4):
            u, v = -v, u
        return x0 + self.P / 2 + u * self.mm, y0 + self.P / 2 + v * self.mm

    def draw(self, st):
        """st: dict with frames[i] (32x32 0..1 linear duty/full) or None, plugged[i], info[i] dicts,
        cables [(i,si,j,sj)], title, sub, skew list, events, util, extra lines"""
        S = self.surf
        S.fill((7, 7, 9))
        offs = []
        for i, b in enumerate(self.boards):
            if st['plugged'][i]:
                offs.append((0, 0))
            else:
                k = min(1.0, st.get('unplug_age', [0] * 6)[i] / 0.6)
                cx = b[0] - (max(bb[0] for bb in self.boards)) / 2; cy = b[1] - (max(bb[1] for bb in self.boards)) / 2
                n = math.hypot(cx, cy) or 1
                d = self.P * 0.22 * k
                offs.append((cx / n * d, cy / n * d + (0 if n > 0.01 else d)))
        lay = pygame.Surface((self.W, self.H))
        lay.fill((0, 0, 0))
        # rear side: electronics boards (148 x 99.5 mm) and the stacking cables, seen through the panels
        for i, b in enumerate(self.boards):
            x0, y0 = self.board_rect(b[0], b[1], offs[i])
            cx, cy = x0 + self.P / 2, y0 + self.P / 2
            w, h = (148 * self.mm, 99.5 * self.mm) if b[2] % 2 == 0 else (99.5 * self.mm, 148 * self.mm)
            pygame.draw.rect(S, (16, 48, 30), (cx - w / 2, cy - h / 2, w, h), border_radius=6)
        # stacking cables (6 wires, JST-SH) between facing ports, behind the panels
        for (i, si, j, sj) in st['cables']:
            a = self.port_xy(i, si, offs); b = self.port_xy(j, sj, offs)
            da = [DX[(si + self.boards[i][2]) % 4], DY[(si + self.boards[i][2]) % 4]]
            db = [DX[(sj + self.boards[j][2]) % 4], DY[(sj + self.boards[j][2]) % 4]]
            L = self.P * 0.12
            pts = []
            for k in range(25):
                t = k / 24
                p0, p1 = a, (a[0] + da[0] * L, a[1] + da[1] * L)
                p2, p3 = (b[0] + db[0] * L, b[1] + db[1] * L), b
                x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0]
                y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]
                pts.append((x, y))
            cols = [(40, 40, 40), (230, 200, 40), (60, 140, 230), (90, 210, 90), (220, 80, 220), (40, 40, 40)]
            for w in range(6):
                o = (w - 2.5) * 1.6
                pp = [(x + o * abs(db[1] or da[1]), y + o * abs(db[0] or da[0])) for x, y in pts]
                pygame.draw.aalines(S, cols[w], False, pp)
        # boards (PCB) + panels
        for i, b in enumerate(self.boards):
            x0, y0 = self.board_rect(b[0], b[1], offs[i])
            m = 3
            pan = pygame.Surface((int(self.P) + 1, int(self.P) + 1), pygame.SRCALPHA)
            pan.fill((10, 10, 12, 215))
            S.blit(pan, (x0, y0))
            pygame.draw.rect(S, (38, 38, 44), (x0, y0, self.P + 1, self.P + 1), 1)
            fr = st['frames'][i]
            Q = (np.clip(np.asarray(fr, np.float32), 0, 1) ** (1 / 2.2) * 64 + 0.5).astype(int) if fr is not None else np.zeros((32, 32), int)
            for rr in range(32):
                for c in range(32):
                    q = Q[rr][c]
                    X, Y = tile_xy(b[2], rr, c)
                    lay.blit(self.sprites[q], (int(x0 + self.led0 + X * self.pitch - self.sp / 2), int(y0 + self.led0 + Y * self.pitch - self.sp / 2)))
            if not st['plugged'][i]:
                pygame.draw.rect(S, (230, 60, 50), (x0 - m, y0 - m, self.P + 2 * m, self.P + 2 * m), 3, border_radius=int(m))
        # bloom
        small = pygame.transform.smoothscale(lay, (self.W // 10, self.H // 10))
        small = pygame.transform.smoothscale(small, (self.W // 40, self.H // 40))
        glow = pygame.transform.smoothscale(small, (self.W, self.H))
        S.blit(lay, (0, 0), special_flags=pygame.BLEND_ADD)
        glow.fill((150, 150, 150), special_flags=pygame.BLEND_MULT)
        S.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)
        # labels on boards
        for i, b in enumerate(self.boards):
            x0, y0 = self.board_rect(b[0], b[1], offs[i])
            inf = st['info'][i]
            lab = '#%d %s' % (i, inf.get('role', ''))
            t = self.fs.render(lab, True, (150, 230, 160) if inf.get('role') == 'LEAD' else (150, 150, 150))
            S.blit(t, (x0 + 8, y0 + 6))
            if not st['plugged'][i]:
                S.blit(self.fm.render('UNPLUGGED', True, (240, 80, 70)), (x0 + self.P / 2 - 60, y0 + self.P / 2 - 12))
        # header
        S.blit(self.fb.render(st['title'], True, (255, 175, 60)), (40, 22))
        S.blit(self.f.render(st['sub'], True, (170, 170, 170)), (40, 60))
        self.sidebar(st)
        return S

    def sidebar(self, st):
        S = self.surf
        if self.side:
            x, y, w, h = self.W - 620, 90, 600, self.H - 130
        else:
            x, y, w, h = 30, int(self.H * 0.42) + 150, self.W - 60, self.H - int(self.H * 0.42) - 180
        pygame.draw.rect(S, (20, 20, 26), (x, y, w, h), border_radius=10)
        x += 16; y += 12
        lh = self.f.get_linesize()
        def line(s, c=(220, 220, 220), f=None):
            nonlocal y
            S.blit((f or self.f).render(s, True, c), (x, y)); y += (f or self.f).get_linesize()
        line('board  id        pos   rot role   fps  bus', (255, 190, 90))
        for i, inf in enumerate(st['info']):
            pos = '(%d,%d)' % tuple(inf['tile'][:2]) if inf.get('tile') else ' -  '
            rot = '%3d' % (inf['tile'][2] * 90) if inf.get('tile') else '  -'
            c = (240, 90, 80) if not st['plugged'][i] else (150, 230, 160) if inf.get('role') == 'LEAD' else (210, 210, 210)
            line(' #%d  %08x %-6s %s %-6s %4.1f %3.0f%%' % (i, inf.get('id', 0), pos, rot, (inf.get('role') or '')[:6],
                                                    inf.get('fps', 0), inf.get('util', 0) * 100), c)
        y += 6
        sk = st.get('skew') or []
        if sk:
            ss = sorted(sk)
            line('frame skew (QEMU, host clock): med %.2f ms  p95 %.2f ms' % (statistics.median(ss), ss[int(0.95 * (len(ss) - 1))]), (200, 200, 120))
        else:
            line('frame skew: -', (200, 200, 120))
        for s in st.get('extra', []):
            line(s, (170, 170, 200))
        y += 6
        line('events', (255, 190, 90))
        for t, e in st['events'][-(10 if self.side else 6):]:
            line('%6.1f  %s' % (t, e[:60 if self.side else 150]), (165, 165, 165), self.fs)


def follow(path):
    import json, sys
    from logstate import LogState
    os.environ.setdefault('DISPLAY', ':4')
    pygame.init()
    W, H = 1920, 1160
    win = pygame.display.set_mode((W, H), pygame.NOFRAME)
    pygame.display.set_caption('mono_split stack viewer')
    st = LogState(); R = None
    f = open(path)
    clock = pygame.time.Clock()
    buf = ''
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT: return
        chunk = f.read()
        if chunk:
            buf += chunk
            lines = buf.split('\n'); buf = lines.pop()
            for ln in lines:
                try: st.feed(json.loads(ln))
                except Exception: pass
        if st.boards and R is None:
            pygame.display.set_caption('mono_split stack - %s - 6 x ESP32-S3 in QEMU' % st.layout)
            R = Renderer(W, H, st.layout, st.boards)
        if R:
            win.blit(R.draw(st.view()), (0, 0))
            pygame.display.flip()
        clock.tick(20)


if __name__ == '__main__':
    import sys
    follow(sys.argv[sys.argv.index('--follow') + 1])
