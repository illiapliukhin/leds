#!/usr/bin/env python3
"""Virtual 32x32 LED panel for the mono_split firmware running in Espressif QEMU.

Reads the firmware's v13 sim tap ("@G" lines = decoded LCD_CAM frames, 8-bit BCM; on the QEMU UART, TCP socket) and lights the
matrix the way the real panel would: every row holds the column words that were latched into
the MBI5124 chain while that row's decoder output was active, and each LED's brightness is the
time OE_N was low with its bit set, divided by the row period (binary-code modulation, 2 planes).
Eye/LED persistence is modelled as a ~40 ms exponential filter.
"""
import argparse, math, os, socket, subprocess, sys, time

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gstream import parse_g, full_scale_duty, hw_cpu_pct

ROWS = COLS = 32
ROW_PERIOD_US = (1_000_000 // 400) // 32       # nominal row period (78 us), as in the firmware
I_COL_MA = 1.24 / 1820 * 15 * 1000              # MBI5124 Iout ~ 15 * 1.24 V / Rext(1.82 k) ~ 10.2 mA (estimate)
CELL = 22
PANEL_W = 300

def parse(line):
    """@F seq fps_x10 cur_row gen rp_min rp_max rp_mean_x10 rp_var_x100 + 32 x b0:slot0:meas0:b1:slot1:meas1.
    Each line is one COMPLETE scan of a single framebuffer generation (the firmware drops partial scans).
    Brightness uses the commanded (timer-nominal) OE slot, not the QEMU-jittered measured one."""
    p = line.split()
    if len(p) < 9 + ROWS or p[0] != '@F':
        return None
    seq, fps_x10, cur, gen = int(p[1]), int(p[2]), int(p[3]), int(p[4])
    rp = (int(p[5]), int(p[6]), int(p[7]) / 10.0, max(int(p[8]), 0) ** 0.5 / 10.0)
    rows = []
    for tok in p[9:9 + ROWS]:
        b0, s0, m0, b1, s1, m1 = tok.split(':')
        rows.append((int(b0, 16), int(s0), int(b1, 16), int(s1)))
    return seq, fps_x10 / 10.0, cur, gen, rp, rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1'); ap.add_argument('--port', type=int, default=5555)
    ap.add_argument('--cmd', action='append', default=[], help='console command(s) sent after the prompt')
    ap.add_argument('--record', help='mp4 path'); ap.add_argument('--record-seconds', type=float, default=22)
    ap.add_argument('--png-dir'); ap.add_argument('--log')
    a = ap.parse_args()

    pygame.init()
    W, H = COLS * CELL + 40 + PANEL_W, ROWS * CELL + 40
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('mono_split virtual board - 32x32 matrix (ESP32-S3 in QEMU)')
    font = pygame.font.SysFont('dejavusansmono', 15); big = pygame.font.SysFont('dejavusans', 20, bold=True)

    sock = None
    while sock is None:
        try:
            sock = socket.create_connection((a.host, a.port), timeout=1)
        except OSError:
            screen.fill((0, 0, 0)); screen.blit(big.render('waiting for QEMU UART on :%d ...' % a.port, True, (200, 120, 0)), (20, 20))
            pygame.display.flip(); pygame.event.pump(); time.sleep(0.3)
    sock.setblocking(False)
    logf = open(a.log, 'w') if a.log else None

    lum = [[0.0] * COLS for _ in range(ROWS)]
    target = [[0.0] * COLS for _ in range(ROWS)]
    buf = b''; sent = False; fps = 0.0; cur_row = 0; seq = 0; last_seq_t = time.time(); stream_hz = 0.0
    demo = '-'; gen = 0; fps_obs = 0; full = 0.78; levels = 0; bright = 128; gam = 2.2; row_peak = [0.0] * ROWS; avg_ma = 0.0
    rec = None; rec_t0 = None; png_n = 0; last_png = 0
    clock = pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return
        try:
            d = sock.recv(65536)
            if not d:
                break
            buf += d
        except BlockingIOError:
            pass
        if not sent and b'mono>' in buf:
            time.sleep(0.3)
            for c in (a.cmd or ['demo cycle']):
                sock.sendall(c.encode() + b'\r\n')
            sent = True
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            s = line.decode(errors='replace').strip().replace('mono>', '').strip()
            if logf and not s.startswith('@G'):
                logf.write(s + '\n'); logf.flush()
            if 'demo: demo: ' in s:
                demo = s.split('demo: demo: ')[1].split('\x1b')[0]
            if not s.startswith('@G'):
                continue
            r = parse_g(s)
            if not r:
                continue
            seq, gen, rows, RS = r['seq'], r['gen'], r['rows'], r['row_samples']
            fps, fps_obs, full = r['fps_nom'], r['fps_obs'], full_scale_duty(RS)
            bright, gam = r['bright'], r['gamma']
            now = time.time(); stream_hz = 0.8 * stream_hz + 0.2 / max(now - last_seq_t, 1e-3); last_seq_t = now
            tot = 0.0; duties = set()
            for y, (drow, planes) in enumerate(rows):
                yy = drow if 0 <= drow < 32 else y        # light the row the decoded address actually selects
                for x in range(COLS):
                    t_on = sum(on for bits, on in planes if (bits >> x) & 1)
                    target[yy][x] = t_on / RS; duties.add(t_on)
                peak = max((bin(bits).count('1') for bits, on in planes if on), default=0)
                row_peak[yy] = peak * I_COL_MA
                tot += sum(bin(bits).count('1') * on for bits, on in planes) * I_COL_MA / RS
            avg_ma = tot / ROWS; levels = len(duties)
            cur_row = max(range(32), key=lambda q: row_peak[q])
        # persistence (~40 ms) and drawing
        k = 1 - math.exp(-(1 / 30) / 0.04)
        screen.fill((8, 8, 8))
        for y in range(ROWS):
            for x in range(COLS):
                lum[y][x] += (target[y][x] - lum[y][x]) * k
                v = min(1.0, max(0.0, lum[y][x]) / full) ** (1 / 2.2)     # linear LED light, shown gamma-encoded (256 levels)
                col = (int(30 + 225 * v), int(12 + 140 * v * v), int(4 + 20 * v)) if v > 0.02 else (28, 14, 6)
                cx, cy = 20 + x * CELL + CELL // 2, 20 + y * CELL + CELL // 2
                if v > 0.3:
                    pygame.draw.circle(screen, (col[0] // 4, col[1] // 5, 0), (cx, cy), CELL // 2)
                pygame.draw.circle(screen, col, (cx, cy), CELL // 2 - 3)
        px0 = COLS * CELL + 40
        pygame.draw.rect(screen, (24, 24, 28), (px0 - 10, 10, PANEL_W, H - 20), border_radius=8)
        y0 = 24
        def txt(s, c=(220, 220, 220), f=font):
            nonlocal y0
            screen.blit(f.render(s, True, c), (px0, y0)); y0 += f.get_height() + 6
        txt('mono_split  32x32', (255, 170, 40), big)
        txt('ESP32-S3 firmware in QEMU', (150, 150, 150))
        txt('')
        txt('demo:        %s' % demo, (255, 200, 80))
        txt('refresh:     %.0f Hz (HW timing)' % fps)
        txt('  QEMU-paced %.0f Hz' % fps_obs, (130, 130, 130))
        txt('grey:        8-bit BCM, %d levels' % levels)
        txt('gamma %.1f  bright %d' % (gam, bright), (150, 150, 150))
        txt('scan CPU:    %.1f%% core1 (HW est.)' % hw_cpu_pct())
        txt('  was 100%% (busy-wait, v12)', (130, 130, 130))
        txt('stream:      %.0f snapshots/s' % stream_hz)
        txt('current row: %2d  (A3..A0=%d%d%d%d %s)' % (cur_row, cur_row >> 3 & 1, cur_row >> 2 & 1, cur_row >> 1 & 1, cur_row & 1, 'DEC_A' if cur_row < 16 else 'DEC_B'))
        txt('row peak I:  %.0f mA' % row_peak[cur_row])
        txt('max row I:   %.0f mA' % max(row_peak))
        txt('avg LED I:   %.1f mA' % avg_ma)
        txt('  est. %.1f mA/col (1.24V/1k82 x15)' % I_COL_MA, (130, 130, 130))
        txt('frame gen %d  seq %d' % (gen, seq), (150, 150, 150))
        # per-row bars
        for yy in range(ROWS):
            w = int(min(1.0, row_peak[yy] / (32 * I_COL_MA)) * (PANEL_W - 40))
            c = (255, 160, 40) if yy == cur_row else (120, 70, 20)
            pygame.draw.rect(screen, c, (px0, y0 + yy * 6, max(1, w), 4))
        screen.blit(font.render('row peak current (bar = 32 cols)', True, (130, 130, 130)), (px0, y0 + ROWS * 6 + 4))
        pygame.display.flip()
        if a.record and sent:
            if rec is None:
                rec = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', '30', '-i', '-',
                                        '-pix_fmt', 'yuv420p', '-vcodec', 'libx264', '-crf', '23', a.record], stdin=subprocess.PIPE)
                rec_t0 = time.time()
            if rec_t0 and time.time() - rec_t0 < a.record_seconds:
                rec.stdin.write(pygame.image.tostring(screen, 'RGB'))
                if a.png_dir and time.time() - last_png > 2.6:
                    os.makedirs(a.png_dir, exist_ok=True); png_n += 1; last_png = time.time()
                    pygame.image.save(screen, os.path.join(a.png_dir, 'frame_%02d_%s.png' % (png_n, demo)))
            elif rec_t0:
                rec.stdin.close(); rec.wait(); rec_t0 = None
                print('recorded', a.record, flush=True)
        clock.tick(30)

if __name__ == '__main__':
    main()
