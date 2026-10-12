#!/usr/bin/env python3
"""Virtual bench bring-up of mono_electronics v11c + mono_panel_32x32.
Real firmware in Espressif QEMU (MONO_SIM build) -> scan tap -> netlist-driven board/FFC/panel model -> pygame scene.
Scripted bench session with automatic verification and one fault-injection run; ends in `demo cycle`."""
import argparse, json, math, os, re, socket, subprocess, threading, time, queue
import pygame
import netmodel, panels
from gstream import parse_g, full_scale_duty, hw_cpu_pct

D = os.path.dirname(os.path.abspath(__file__))
SIM = '/workspace/sim'
W, H = 1900, 1150
ROW_PERIOD = 78
ANSI = re.compile(r'\x1b\[[0-9;]*m')

# ---------------------------------------------------------------- QEMU link
class Qemu:
    def __init__(self):
        self.proc = None; self.sock = None; self.lines = queue.Queue(); self.console = []; self.frames = queue.Queue(maxsize=4)
    def start(self):
        # only our own instance (port 5555): other sims (e.g. the stacking sim) run their own QEMUs concurrently
        subprocess.run(['pkill', '-f', 'bench-bringup-xtensa-emu.*bench_bringup_fw.*tcp:127.0.0.1:5555'], stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        q = open(os.path.join(SIM, 'qemu_path')).read().strip()
        # run QEMU under a private name: concurrent sims clean up their own 'qemu-system-xtensa' processes by name
        alias = '/tmp/bench-bringup-xtensa-emu'
        if os.path.realpath(alias) != os.path.realpath(q):
            if os.path.lexists(alias): os.remove(alias)
            os.symlink(q, alias)
        q = alias
        flash = '/tmp/bench_bringup_fw.bin'                                  # private copy: never write the shared image
        import shutil; shutil.copyfile(os.path.join(SIM, 'flash_qemu.bin'), flash)
        self.proc = subprocess.Popen([q, '-nographic', '-machine', 'esp32s3', '-m', '4M', '-drive', 'file=%s,if=mtd,format=raw' % flash,
                                      '-serial', 'tcp:127.0.0.1:5555,server=on,wait=on', '-monitor', 'none'], stdout=subprocess.DEVNULL, stderr=open('/tmp/bench_bringup_qemu.err', 'w'))
        for _ in range(50):
            try:
                self.sock = socket.create_connection(('127.0.0.1', 5555)); break
            except OSError:
                time.sleep(0.1)
        threading.Thread(target=self._rx, daemon=True).start()
    def _rx(self):
        buf = b''
        while True:
            d = self.sock.recv(65536)
            if not d: break
            buf += d
            while b'\n' in buf:
                l, buf = buf.split(b'\n', 1)
                s = ANSI.sub('', l.decode(errors='replace')).replace('\r', '')
                if '@G' in s:
                    pre, f = s.split('@G', 1)
                    if pre.strip(): self._log(pre)
                    try:
                        self.frames.put_nowait('@G' + f)
                    except queue.Full:
                        try: self.frames.get_nowait()
                        except queue.Empty: pass
                        self.frames.put_nowait('@G' + f)
                else:
                    self._log(s)
    def _log(self, s):
        s = s.strip()
        if not s: return
        self.console.append(s); self.lines.put(s)
        del self.console[:-300]
    def send(self, cmd):
        self.console.append('mono> ' + cmd)
        self.sock.sendall(cmd.encode() + b'\r\n')
    def wait_for(self, pat, timeout=30):
        t = time.time()
        while time.time() - t < timeout:
            try:
                s = self.lines.get(timeout=0.2)
                if re.search(pat, s): return s
            except queue.Empty:
                pass
        return None

def parse(line):
    p = line.split()
    if len(p) < 41: return None
    rows = []
    for tok in p[9:41]:
        b0, s0, m0, b1, s1, m1 = tok.split(':')
        rows.append((int(b0, 16), int(s0), int(b1, 16), int(s1)))
    return {'fps': int(p[2]) / 10, 'cur': int(p[3]), 'gen': int(p[4]), 'rows': rows}

# ---------------------------------------------------------------- verification
class Check:
    def __init__(self, name, kind):
        self.name, self.kind = name, kind
        self.row_bad = [0] * 32; self.col_bad = [0] * 32; self.cover_r = [False] * 32; self.cover_c = [False] * 32
        self.snaps = 0; self.mism = 0; self.phases = set(); self.examples = []
    def feed(self, model, act, exp):
        self.snaps += 1
        A = [a > 0.02 for a in act]; E = [e > 0.02 for e in exp]
        er = [0] * 32; ec = [0] * 32
        for i, l in enumerate(model.leds):
            if E[i]: er[l['row']] += 1; ec[l['col']] += 1
            if A[i] != E[i]:
                self.row_bad[l['row']] += 1; self.col_bad[l['col']] += 1; self.mism += 1
                if len(self.examples) < 4: self.examples.append('%s (ROW_%02d x COL_%02d) %s' % (l['ref'], l['row'] + 1, l['col'] + 1, 'dark, expected lit' if E[i] else 'lit, expected dark'))
        if self.kind == 'all':
            for r in range(32): self.cover_r[r] |= er[r] == 32
            for c in range(32): self.cover_c[c] |= ec[c] == 32
        elif self.kind == 'row':
            full = [r for r in range(32) if er[r] == 32]
            if len(full) == 1 and sum(er) == 32: self.cover_r[full[0]] = True
            self.cover_c = [True] * 32
        elif self.kind == 'col':
            full = [c for c in range(32) if ec[c] == 32]
            if len(full) == 1 and sum(ec) == 32: self.cover_c[full[0]] = True
            self.cover_r = [True] * 32
        elif self.kind == 'checker':
            if sum(er) == 512:
                i0 = model.by_rc[(0, 0)]; self.phases.add(E[i0])
            if len(self.phases) == 2: self.cover_r = [True] * 32; self.cover_c = [True] * 32
    def rows_ok(self): return [self.cover_r[r] and not self.row_bad[r] for r in range(32)]
    def cols_ok(self): return [self.cover_c[c] and not self.col_bad[c] for c in range(32)]
    def passed(self): return self.snaps > 0 and all(self.rows_ok()) and all(self.cols_ok())

# ---------------------------------------------------------------- scene
class Scene:
    def __init__(self, model):
        pygame.init()
        self.scr = pygame.display.set_mode((W, H))
        pygame.display.set_caption('mono_split bench bring-up - mono_electronics v11c + %s (virtual)' % panels.CFG['title'])
        self.f = pygame.font.SysFont('dejavusansmono', 14); self.fs = pygame.font.SysFont('dejavusansmono', 12)
        self.fb = pygame.font.SysFont('dejavusans', 19, bold=True); self.fh = pygame.font.SysFont('dejavusans', 26, bold=True)
        self.m = model
        img = pygame.image.load(os.path.join(D, 'board_top.png'))
        self.bx, self.by, self.bw = 20, 60, 760
        self.bs = self.bw / 148.09; self.bh = int(99.55 * self.bs)
        self.board = pygame.transform.smoothscale(img, (self.bw, self.bh))
        self.px, self.py, self.pw = 1110, 40, 600
        ex, ey, ew, eh = netmodel.P['edge']                                 # panel outline bbox from its .kicad_pcb
        self.pex, self.pey = ex, ey; self.ps = self.pw / max(ew, eh); self.pph = int(eh * self.ps)
        self.pbg = None
        if panels.CFG['bg'] and os.path.exists(panels.CFG['bg']):
            self.pbg = pygame.transform.smoothscale(pygame.image.load(panels.CFG['bg']), (int(ew * self.ps), self.pph))
        self.lum = [0.0] * len(model.leds)
        self.rails = {}; self.stage = ''; self.results = []; self.banner = ''; self.banner_col = (255, 255, 255); self.report = None
        self.fps = 0; self.fps_obs = 0; self.full = 0.78; self.levels = 0; self.cur = 0; self.stats = [(0, 0)] * 32; self.gen = 0; self.cable_label = ''; self.fault = None
    def bpt(self, x, y): return (self.bx + x * self.bs, self.by + y * self.bs)
    def ppt(self, x, y): return (self.px + (x - self.pex) * self.ps, self.py + (y - self.pey) * self.ps)
    def ribbon(self, p0, p1, c1, c2, width, color, label, label_at):
        pts = []
        for i in range(41):
            t = i / 40
            x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * c1[0] + 3 * (1 - t) * t * t * c2[0] + t ** 3 * p1[0]
            y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * c1[1] + 3 * (1 - t) * t * t * c2[1] + t ** 3 * p1[1]
            pts.append((x, y))
        left, right = [], []
        for i, (x, y) in enumerate(pts):
            a = pts[min(i + 1, 40)]; b = pts[max(i - 1, 0)]
            dx, dy = a[0] - b[0], a[1] - b[1]; n = math.hypot(dx, dy) or 1
            nx, ny = -dy / n * width / 2, dx / n * width / 2
            left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
        pygame.draw.polygon(self.scr, color, left + right[::-1])
        for k in range(1, 8):
            f = k / 8
            line = [(l[0] * f + r[0] * (1 - f), l[1] * f + r[1] * (1 - f)) for l, r in zip(left, right)]
            pygame.draw.lines(self.scr, (205, 160, 70), False, line, 1)
        pygame.draw.lines(self.scr, (60, 60, 200), False, left, 3)            # blue edge = conductor 1 side (board pin 1)
        mid = pts[label_at]
        t = self.fs.render(label, True, (240, 240, 240)); pygame.draw.rect(self.scr, (0, 0, 0), (mid[0] - 4, mid[1] - 30, t.get_width() + 8, 18)); self.scr.blit(t, (mid[0], mid[1] - 29))
        return pts
    def draw(self, q, steps):
        s = self.scr; s.fill((22, 24, 28))
        s.blit(self.fh.render('Bench bring-up: mono_electronics v11c  +  %s' % panels.CFG['title'], True, (255, 180, 60)), (20, 14))
        # board
        s.blit(self.board, (self.bx, self.by))
        pygame.draw.rect(s, (90, 90, 90), (self.bx - 1, self.by - 1, self.bw + 2, self.bh + 2), 1)
        # status LED-ish: AON indicator near U1
        if self.rails.get('AON_3V3'): pygame.draw.circle(s, (60, 255, 80), (int(self.bx + 66 * self.bs), int(self.by + 6 * self.bs)), 5)
        # USB cable
        ux, uy = self.bpt(0, 18.0)
        if self.rails.get('VBUS'):
            pygame.draw.rect(s, (40, 40, 40), (0, uy - 9, ux + 6, 18), border_radius=4)
            pygame.draw.rect(s, (160, 160, 160), (ux - 4, uy - 6, 12, 12))
            s.blit(self.fs.render('USB-C 5V', True, (230, 230, 230)), (4, uy + 12))
        # panel
        if self.pbg is not None:                                              # lattice: see-through bars, bench shows through
            s.blit(self.pbg, (self.px, self.py))
            s.blit(self.fs.render(('%s (front; bars + windows from its geometry, LEDs from its .kicad_pcb; FFCs on the back of the tab)' if panels.NAME == 'lattice' else '%s (front; LEDs on wires, no PCB: 0.5 mm row / 0.25 mm column wires, 10 mm pitch; breakout tab south)' if panels.NAME == 'wire' else '%s (front, edge-to-edge; LEDs from its .kicad_pcb; FFCs + ribbons are on the back)') % panels.CFG['title'], True, (150, 170, 150)), (self.px - 300, self.py + self.pph + 4))
        else:
            pygame.draw.rect(s, (14, 40, 24), (self.px, self.py, self.pw, self.pw), border_radius=4)
            pygame.draw.rect(s, (80, 120, 90), (self.px, self.py, self.pw, self.pw), 1)
            s.blit(self.fs.render('mono_panel_32x32 (front, LED positions from its .kicad_pcb; FFC receptacles on the back)', True, (150, 170, 150)), (self.px, self.py + self.pw + 4))
        for name in ('J_ROW', 'J_COL'):
            f = netmodel.PF[name]; xs = [p['x'] for p in f['pads']]; ys = [p['y'] for p in f['pads']]
            a = self.ppt(min(xs) - 1, min(ys) - 1); b = self.ppt(max(xs) + 1, max(ys) + 1)
            pygame.draw.rect(s, (200, 200, 200), (a[0], a[1], b[0] - a[0], b[1] - a[1]), 1)
        # ribbons
        rb = netmodel.BF['J_ROW1']; cb = netmodel.BF['J_COL1']
        col = (150, 105, 35) if not self.fault else (170, 60, 40)
        if panels.NAME in ('lattice', 'full', 'wire'):                        # receptacles side by side, cables exit south
            jr, jc = netmodel.PF['J_ROW'], netmodel.PF['J_COL']; yb = max(p['y'] for p in jr['pads']) + 1.5
            p_row_b = self.bpt(148.5, rb['y']); p_row_p = self.ppt(jr['x'], yb)
            self.ribbon(p_row_b, p_row_p, (p_row_b[0] + 200, p_row_b[1]), (p_row_p[0], p_row_p[1] + 200), 30, col, 'J_ROW1 -> J_ROW  ' + self.cable_label, 6)
            p_col_b = self.bpt(148.5, cb['y']); p_col_p = self.ppt(jc['x'], yb)
            pts = self.ribbon(p_col_b, p_col_p, (p_col_b[0] + 260, p_col_b[1] + 60), (p_col_p[0], p_col_p[1] + 300), 30, col, 'J_COL1 -> J_COL', 14)
        else:
            p_row_b = self.bpt(148.5, rb['y']); p_row_p = self.ppt(4, netmodel.PF['J_ROW']['y'])
            self.ribbon(p_row_b, p_row_p, (p_row_b[0] + 160, p_row_b[1]), (p_row_p[0] - 160, p_row_p[1]), 34, col, 'J_ROW1 -> J_ROW  ' + self.cable_label, 4)
            p_col_b = self.bpt(148.5, cb['y']); p_col_p = self.ppt(netmodel.PF['J_COL']['x'], 166)
            pts = self.ribbon(p_col_b, p_col_p, (p_col_b[0] + 220, p_col_b[1] + 40), (p_col_p[0], p_col_p[1] + 260), 34, col, 'J_COL1 -> J_COL  ' + self.cable_label, 14)
        if self.fault and 'COL_07' in self.fault:
            x, y = pts[10]; pygame.draw.circle(s, (255, 40, 40), (int(x), int(y)), 14, 3)
            s.blit(self.fs.render('OPEN: COL_07', True, (255, 80, 80)), (x + 16, y - 6))
        # LEDs
        r = max(3, int(self.ps * (0.8 if panels.NAME == 'lattice' else 1.15)))
        for i, l in enumerate(self.m.leds):
            v = min(1.0, max(0.0, self.lum[i]) / self.full) ** (1 / 2.2)   # LED light is linear; show it gamma-encoded
            c = (int(40 + 215 * v), int(16 + 150 * v * v), int(6 + 20 * v)) if v > 0.03 else (40, 22, 10)
            x, y = self.ppt(l['x'], l['y'] + panels.CFG.get('led_dy', 0.0))   # lattice: LED body centre
            if v > 0.3: pygame.draw.circle(s, (c[0] // 3, c[1] // 4, 0), (int(x), int(y)), r + 3)
            pygame.draw.circle(s, c, (int(x), int(y)), r)
        # per-row readout
        x0 = self.px + self.pw + 16
        s.blit(self.f.render('row  I(mA)  drop(mV)', True, (200, 200, 200)), (x0, self.py))
        for rr in range(32):
            i_row, v = self.stats[rr]; y = self.py + 20 + rr * 17.5
            c = (255, 190, 60) if rr == self.cur else (170, 170, 170)
            s.blit(self.fs.render('%2d %6.0f %7.1f' % (rr + 1, i_row * 1e3, v * 1e3), True, c), (x0, y))
            pygame.draw.rect(s, (200, 120, 30), (x0 + 128, y + 3, int(min(1, i_row / 0.33) * 40), 7))
        s.blit(self.fs.render('I = lit cols x 10.2 mA (est.)', True, (120, 120, 120)), (x0, self.py + 20 + 32 * 17.5 + 2))
        s.blit(self.fs.render('drop = I x R(row) ir_v3.json', True, (120, 120, 120)), (x0, self.py + 36 + 32 * 17.5 + 2))
        s.blit(self.fs.render('scan %.0f Hz HW (QEMU %.0f)' % (self.fps, self.fps_obs), True, (150, 150, 150)), (x0, self.py + 56 + 32 * 17.5))
        s.blit(self.fs.render('8-bit BCM, %d levels shown' % self.levels, True, (150, 150, 150)), (x0, self.py + 72 + 32 * 17.5))
        s.blit(self.fs.render('scan CPU %.1f%% (HW est.)' % hw_cpu_pct(), True, (150, 150, 150)), (x0, self.py + 88 + 32 * 17.5))
        # rails
        y0 = self.by + self.bh + 14
        s.blit(self.fb.render('Power rails', True, (255, 200, 90)), (20, y0))
        for k, (name, desc) in enumerate((('VBUS', '5 V USB-C'), ('SYS', 'BQ25185 4.5 V'), ('AON_3V3', 'TLV75733P'), ('CHIP_PU', 'ESP32-S3 EN'),
                                           ('LED_LOGIC_3V3', 'TPS22917'), ('LED_4V1', 'TPS63802'), ('XLAT_OE', 'LVC8T245 /OE'))):
            on = self.rails.get(name); xx = 20 + (k % 4) * 190; yy = y0 + 28 + (k // 4) * 40
            pygame.draw.circle(s, (60, 255, 90) if on else (70, 30, 30), (xx + 8, yy + 9), 7)
            s.blit(self.f.render(name, True, (230, 230, 230) if on else (120, 120, 120)), (xx + 22, yy))
            s.blit(self.fs.render(('%s  t=%s' % (desc, on)) if on else desc, True, (140, 140, 140)), (xx + 22, yy + 16))
        # bench steps
        y1 = y0 + 120
        s.blit(self.fb.render('Bench session', True, (255, 200, 90)), (20, y1))
        for k, (txt, st) in enumerate(steps[-14:]):
            c = {'PASS': (90, 255, 110), 'FAIL': (255, 80, 80), 'RUN': (255, 210, 80), 'INFO': (170, 190, 255)}.get(st, (200, 200, 200))
            s.blit(self.f.render('%-5s %s' % (st, txt), True, c), (20, y1 + 28 + k * 19))
        # console
        cx, cy, cw, ch = 800, 690, 1080, 445
        pygame.draw.rect(s, (8, 8, 10), (cx, cy, cw, ch), border_radius=6)
        s.blit(self.fb.render('ESP32-S3 console (QEMU UART0)', True, (255, 200, 90)), (cx + 10, cy + 6))
        lines = [l for l in q.console if not l.startswith('@G')][-24:]
        for k, l in enumerate(lines):
            c = (120, 255, 140) if l.startswith('mono>') else ((255, 120, 120) if l.startswith(('E (', 'W (')) else (200, 200, 200))
            s.blit(self.fs.render(l[:150], True, c), (cx + 10, cy + 34 + k * 17))
        if self.banner:
            t = self.fb.render(self.banner, True, self.banner_col); yb = self.py + max(self.pw, self.pph) + 22
            if self.pbg is not None: yb = self.by + self.bh + 80
            bx = self.px if self.pbg is None else 20
            pygame.draw.rect(s, (0, 0, 0), (bx, yb, t.get_width() + 16, 30)); s.blit(t, (bx + 8, yb + 4))
        if self.report:
            bw, bh = 760, 22 * len(self.report) + 20
            pygame.draw.rect(s, (12, 12, 16), (20, 70, bw, bh), border_radius=8); pygame.draw.rect(s, (255, 180, 60), (20, 70, bw, bh), 2, border_radius=8)
            for k, (l, c) in enumerate(self.report):
                s.blit(self.f.render(l, True, c), (32, 80 + k * 22))
        pygame.display.flip()

# ---------------------------------------------------------------- session
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--fast', action='store_true')
    ap.add_argument('--panel', choices=sorted(panels.PANELS), default=panels.NAME, help='panel under test (read at import by panels.py)'); a = ap.parse_args()
    model = netmodel.Model(); q = Qemu(); sc = Scene(model)
    steps = []; checks = []; state = {'check': None, 'done': False}
    log = open(os.path.join(D, 'bench_session.log' if panels.NAME == 'mono32' else 'bench_session_%s.log' % panels.NAME), 'w')
    def step(txt, st='INFO'):
        steps.append([txt, st]); log.write('%7.2f %-5s %s\n' % (time.time() - T0, st, txt)); log.flush(); return steps[-1]
    T0 = time.time()

    def run_check(name, kind, cmd, dur, settle=0.8):
        st = step('%s: `%s`' % (name, cmd), 'RUN')
        q.send(cmd); time.sleep(settle)
        c = Check(name, kind); state['check'] = c; time.sleep(dur * 0.6)
        if panels.NAME != 'mono32': state['shot'] = os.path.join(D, 'png', 'bringup_%s_%s.png' % (panels.NAME, re.sub(r'\W+', '_', name).strip('_').lower()))
        time.sleep(dur * 0.4); state['check'] = None
        ok = c.passed(); st[1] = 'PASS' if ok else 'FAIL'
        st[0] = '%s: `%s`  %d scans, rows %d/32, cols %d/32 ok' % (name, cmd, c.snaps, sum(c.rows_ok()), sum(c.cols_ok()))
        checks.append(c); log.write('        examples: %s\n' % c.examples)
        return c

    def session():
        sc.cable_label = 'FFC 40P 0.5 mm, Type B (opposite-side contacts)'
        import cable; cc = cable.main() if panels.NAME != 'mono32' else json.load(open(os.path.join(D, 'cable_check.json')))
        step('Cable check from pad geometry: Type A mirrors pin 1->%d (%d net errors), Type B pin 1->%d (%d)' % (
            cc['J_ROW1->J_ROW typeA']['pin1_to'], cc['J_ROW1->J_ROW typeA']['net_mismatches'], cc['J_ROW1->J_ROW typeB']['pin1_to'], cc['J_ROW1->J_ROW typeB']['net_mismatches']))
        time.sleep(1.5)
        # power-up timeline (datasheet values, shown slowed down)
        st = step('Plug USB-C: VBUS 5 V', 'RUN'); sc.rails['VBUS'] = '0 ms'; time.sleep(0.8)
        sc.rails['SYS'] = '~1 ms'; step('BQ25185 power path: SYS 4.5 V (~1 ms class)'); time.sleep(0.8)
        sc.rails['AON_3V3'] = '~1.5 ms'; step('TLV75733P soft start: AON_3V3 (sub-ms)'); time.sleep(0.8)
        sc.rails['CHIP_PU'] = '~12 ms'; step('CHIP_PU RC releases, ESP32-S3 boots (QEMU)'); st[1] = 'PASS'
        q.start()
        if not q.wait_for(r'Ready\.|Returned from app_main', 40):
            step('ESP32 did not reach the prompt', 'FAIL'); return
        step('Firmware up: LED rails OFF at boot (on demand)', 'PASS'); time.sleep(1)
        st = step('I2C scan: expect BMI270 0x68, MAX17048 0x36 (sim-mocked)', 'RUN'); q.send('i2cscan')
        seen = set(); t = time.time()
        while time.time() - t < 4 and len(seen) < 3:
            try: l = q.lines.get(timeout=0.3)
            except queue.Empty: continue
            for k in ('0x68', '0x36', 'CHIP_ID=0x24'):
                if k in l: seen.add(k)
        st[1] = 'PASS' if len(seen) == 3 else 'FAIL'; st[0] = 'I2C scan: found %s' % ', '.join(sorted(seen))
        checks.append(type('I2C', (), {'name': 'i2c', 'passed': lambda self, ok=len(seen) == 3: ok})())
        q.send('panel 32'); time.sleep(0.5)
        # LED rails come up with the first test command: follow the real firmware log
        def railwatch():
            l = q.wait_for(r'LED_LOGIC_EN\(GPIO21\)=1', 20)
            if l: sc.rails['LED_LOGIC_3V3'] = re.search(r't=\+?(\d+) us', l).group(1) + ' us'
            l = q.wait_for(r'LED_EN\(GPIO18\)=1', 5)
            if l: sc.rails['LED_4V1'] = '%.1f ms' % (int(re.search(r't=\+?(\d+) us', l).group(1)) / 1000 + 1.0)
            l = q.wait_for(r'ROW_XLAT_OE_N\(GPIO44\)=0', 5)
            if l: sc.rails['XLAT_OE'] = '%.1f ms' % (int(re.search(r't=\+?(\d+) us', l).group(1)) / 1000)
        threading.Thread(target=railwatch, daemon=True).start()
        run_check('All on', 'all', 'test all', 2.5)
        run_check('Row walk', 'row', 'test row', 5.2, settle=0.3)
        run_check('Column walk', 'col', 'test col', 5.2, settle=0.3)
        run_check('Checkerboard', 'checker', 'test checker', 2.0, settle=0.4)
        q.send('test off'); time.sleep(0.5)
        good = [c for c in checks if c.passed()]
        sc.banner = 'Nominal run: %d/%d checks PASS' % (len(good), len(checks)); sc.banner_col = (90, 255, 110) if len(good) == len(checks) else (255, 80, 80)
        nominal = list(checks)
        time.sleep(2)
        # ---- fault injection 1: wrong cable (Type A, same-side contacts)
        step('FAULT 1: swap both FFCs for Type A (same-side contacts) cables', 'INFO')
        sc.banner = 'FAULT 1 ACTIVE: Type A cables (pins mirrored)'; sc.banner_col = (255, 80, 80)
        model.set_cable('A', set()); sc.fault = 'Type A'; sc.cable_label = 'Type A (same-side) -> pins mirrored 1<->40'
        f1 = [run_check('[F1] All on', 'all', 'test all', 2.0), run_check('[F1] Row walk', 'row', 'test row', 4.5, settle=0.3)]
        q.send('test off'); time.sleep(0.5)
        # ---- fault injection 2: open conductor COL_07 on the correct cable
        step('FAULT 2: Type B cable, conductor 7 of the COL cable open (COL_07)', 'INFO')
        sc.banner = 'FAULT 2 ACTIVE: COL conductor 7 open'; sc.banner_col = (255, 80, 80)
        model.set_cable('B', {'COL_07'}); sc.fault = 'COL_07'; sc.cable_label = 'Type B, conductor 7 OPEN'
        f2 = [run_check('[F2] Column walk', 'col', 'test col', 5.2, settle=0.3)]
        q.send('test off'); time.sleep(0.5)
        model.set_cable('B', set()); sc.fault = None; sc.cable_label = 'FFC 40P 0.5 mm, Type B (opposite-side contacts)'
        step('Faults removed, correct Type B cables back in', 'INFO')
        sc.banner = 'Faults removed - Type B cables back in'; sc.banner_col = (170, 190, 255)
        # ---- report
        rep = [('BENCH REPORT  mono_electronics v11c + %s' % panels.CFG['title'], (255, 190, 60))]
        for c in nominal:
            if isinstance(c, Check):
                rep.append(('%-14s %s  rows %2d/32  cols %2d/32  (%d scans)' % (c.name, 'PASS' if c.passed() else 'FAIL', sum(c.rows_ok()), sum(c.cols_ok()), c.snaps), (90, 255, 110) if c.passed() else (255, 80, 80)))
            else:
                rep.append(('I2C scan       %s  0x68 BMI270, 0x36 MAX17048 (mocked)' % ('PASS' if c.passed() else 'FAIL'), (90, 255, 110) if c.passed() else (255, 80, 80)))
        for c in f1 + f2:
            bad_r = [r + 1 for r, ok in enumerate(c.rows_ok()) if not ok]; bad_c = [k + 1 for k, ok in enumerate(c.cols_ok()) if not ok]
            caught = c.snaps > 0 and not c.passed()
            rep.append(('%-14s %s  bad rows %s  bad cols %s' % (c.name, 'CAUGHT' if caught else 'MISSED', (str(bad_r[:6]) + ('..' if len(bad_r) > 6 else '')) if bad_r else '-', (str(bad_c[:6]) + ('..' if len(bad_c) > 6 else '')) if bad_c else '-'), (255, 170, 60) if caught else (255, 80, 80)))
        allpass = all(c.passed() for c in nominal); caught = all(c.snaps > 0 and not c.passed() for c in f1 + f2)
        rep.append(('VERDICT: nominal %s, faults %s' % ('PASS' if allpass else 'FAIL', 'all caught' if caught else 'NOT all caught'), (90, 255, 110) if allpass and caught else (255, 80, 80)))
        sc.report = rep
        with open(os.path.join(D, 'bench_report.md' if panels.NAME == 'mono32' else 'bench_report_%s.md' % panels.NAME), 'w') as f:
            f.write('# Virtual bench report\n\n')
            for l, _ in rep: f.write('    %s\n' % l)
            f.write('\n## Details\n\n')
            for c in nominal + f1 + f2:
                if isinstance(c, Check):
                    f.write('- **%s**: %d scans, %d LED mismatches; rows ok %s; cols ok %s; examples: %s\n' % (c.name, c.snaps, c.mism, sum(c.rows_ok()), sum(c.cols_ok()), '; '.join(c.examples) or '-'))
            f.write('\nRow chain (netlist walk): %s\n\nColumn chain: SDI -> %s -> %s, bit c -> COL_(c+1)\n' % (model.row_trace[:3] + model.row_trace[16:17], *model.chain))
        step('Bench report written: %s' % ('bench_report.md' if panels.NAME == 'mono32' else 'bench_report_%s.md' % panels.NAME), 'PASS' if allpass and caught else 'FAIL')
        if panels.NAME != 'mono32': time.sleep(0.5); state['shot'] = os.path.join(D, 'png', 'bringup_%s_report.png' % panels.NAME)
        time.sleep(1)
        step('Demo: `demo cycle` (left running)', 'RUN'); q.send('demo cycle')
        sc.banner = 'Bring-up complete - demo cycle running'; sc.banner_col = (90, 255, 110)
        state['done'] = True
        time.sleep(25); sc.report = None

    threading.Thread(target=session, daemon=True).start()
    clock = pygame.time.Clock(); k = 1 - math.exp(-(1 / 30) / 0.04)
    act = [0.0] * len(model.leds)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                if q.proc: q.proc.kill()
                return
        try:
            while True:
                fr = parse_g(q.frames.get_nowait())
                if not fr: continue
                act, exp, stats = model.light(fr['rows'], fr['row_samples'])
                sc.stats, sc.fps, sc.gen = stats, fr['fps_nom'], fr['gen']
                sc.fps_obs, sc.full = fr['fps_obs'], full_scale_duty(fr['row_samples'])
                sc.cur = max(range(32), key=lambda r: stats[r][0])
                sc.levels = len(set(round(a * fr['row_samples']) for a in act))
                c = state['check']
                if c: c.feed(model, act, exp)
        except queue.Empty:
            pass
        for i in range(len(act)): sc.lum[i] += (act[i] - sc.lum[i]) * k
        sc.draw(q, steps)
        if state.get('shot'):
            os.makedirs(os.path.dirname(state['shot']), exist_ok=True); pygame.image.save(sc.scr, state['shot']); state['shot'] = None
        clock.tick(30)

if __name__ == '__main__':
    main()
