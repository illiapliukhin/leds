#!/usr/bin/env python3
"""Presentation renderer: frame-exact video of the stack's LEDs from the simulator's JSONL scan log.
Real panel geometry (166.7 mm board, 2.54 mm pitch, butted), 8-bit duty decoded from the firmware's DMA stream,
gamma 2.2 display, soft LED glow, floor reflection, title cards.  numpy + PIL, piped into ffmpeg.

present.py LOG OUT.mp4 --t0 S --dur S --title "..." --sub "..." [--res 3840x2160] [--crf 15]
"""
import argparse, bisect, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logstate import decode_g

PANEL_MM, PITCH_MM, LED0_MM = 160.0, 5.0, 2.5     # mono_panel_32x32_full (035bd00): seamless
AMBER = np.array([255, 150, 30], np.float32)

ap = argparse.ArgumentParser()
ap.add_argument('log'); ap.add_argument('out')
ap.add_argument('--raw', nargs=2, type=int, metavar=('CW', 'CH'), help='LOG is a host_render frame file (canvas WxH)')
ap.add_argument('--t0', type=float, required=True); ap.add_argument('--dur', type=float, required=True)
ap.add_argument('--title', default=''); ap.add_argument('--sub', default=''); ap.add_argument('--cap', default='')
ap.add_argument('--res', default='3840x2160'); ap.add_argument('--fps', type=int, default=60)
ap.add_argument('--crf', type=int, default=15); ap.add_argument('--png', nargs='*', type=float, default=[])
ap.add_argument('--pngdir', default='.'); ap.add_argument('--only', type=float, default=None)
a = ap.parse_args()
W, H = map(int, a.res.split('x'))
k = H / 2160.0

# ---------------------------------------------------------------- frame source
if a.raw:
    CW, CH = a.raw
    RAW = np.memmap(a.log, dtype=np.uint8, mode='r').reshape(-1, CH, CW)
    boards = [(x, y, 0, 0) for y in range(CH // 32) for x in range(CW // 32)]
    n = len(boards); GAIN = 1.0
    def board_frame(i, t):
        fi = min(len(RAW) - 1, int(round((t - a.t0) * a.fps)))          # frame-exact: video frame n = firmware frame n
        x, y = boards[i][0], boards[i][1]
        return RAW[fi, y * 32:(y + 1) * 32, x * 32:(x + 1) * 32].astype(np.float32) / 255.0
else:
    boards = None; samples = {}
    t_lo, t_hi = a.t0 - 1, a.t0 + a.dur + 1
    with open(a.log) as fh:
        for line in fh:
            if '"layout"' in line and boards is None:
                r = json.loads(line); boards = [tuple(b) for b in r['boards']]; continue
            if '"raw"' not in line: continue
            r = json.loads(line)
            if r['t'] < t_lo: continue
            if r['t'] > t_hi: break
            samples.setdefault(r['g'], []).append((r['t'], decode_g(r['raw'])))
    n = len(boards)
    # normalise to the firmware's full-scale duty (global brightness setting) seen in this clip
    _all = np.concatenate([np.stack([f for _, f in samples[i]]).ravel() for i in samples])
    GAIN = 1.0 / max(1e-3, float(np.percentile(_all, 99.95)))
    del _all
    print('gain %.2f' % GAIN)
    times = {i: [s[0] for s in samples.get(i, [])] for i in range(n)}

    def board_frame(i, t):
        """linear duty (0..1) at host time t, interpolated between consecutive logged scan frames"""
        ts = times[i]
        if not ts: return np.zeros((32, 32), np.float32)
        j = bisect.bisect(ts, t)
        if j <= 0: return samples[i][0][1]
        if j >= len(ts): return samples[i][-1][1]
        (ta, fa), (tb, fb) = samples[i][j - 1], samples[i][j]
        w = (t - ta) / max(1e-6, tb - ta)
        return fa * (1 - w) + fb * w

def to_phys(rot, f):          # board-local scan frame -> panel physical orientation (tile_xy in stack_view)
    out = np.zeros_like(f)
    rr, cc = np.mgrid[0:32, 0:32]
    if rot == 0: X, Y = cc, rr
    elif rot == 1: X, Y = 31 - rr, cc
    elif rot == 2: X, Y = 31 - cc, 31 - rr
    else: X, Y = rr, 31 - cc
    out[Y, X] = f
    return out

# ---------------------------------------------------------------- geometry
nx = max(b[0] for b in boards) + 1; ny = max(b[1] for b in boards) + 1
cell = max(4, int(round(min(W * 0.80 / nx, H * 0.66 / ny) / PANEL_MM * PITCH_MM)))   # integer LED pitch in px
P = cell / PITCH_MM * PANEL_MM; led0 = LED0_MM / PITCH_MM * cell
TW, TH = nx * P, ny * P
ox = (W - TW) / 2; oy = H * 0.43 - TH / 2

# LED kernel: anti-aliased disc (die + lens), hot core
yy, xx = (np.mgrid[0:cell, 0:cell] + 0.5 - cell / 2)
rad = np.hypot(xx, yy)
r_led = cell * 0.40
disc = np.clip(r_led + 0.5 - rad, 0, 1).astype(np.float32)
core = np.clip(r_led * 0.45 + 0.5 - rad, 0, 1).astype(np.float32)

def led_layer(v):
    """v: 32x32 display brightness 0..1 -> (32cell, 32cell, 3) float RGB 0..1"""
    vv = np.kron(v, np.ones((cell, cell), np.float32))
    dd = np.tile(disc, (32, 32)); cc = np.tile(core, (32, 32))
    off = np.array([22, 9, 4], np.float32) / 255.0             # unlit die
    lit = AMBER / 255.0
    base = off[None, None, :] * dd[..., None] * (1 - vv[..., None]) + lit[None, None, :] * (vv * dd)[..., None]
    hot = (cc * vv ** 3)[..., None] * (1 - lit[None, None, :]) * 0.45
    return base + hot

# static backdrop: vignette + panel bodies + seams
bg = np.zeros((H, W, 3), np.float32)
gy, gx = np.mgrid[0:H, 0:W]
vig = 1 - 0.55 * (((gx - W / 2) / (W * 0.62)) ** 2 + ((gy - H * 0.45) / (H * 0.75)) ** 2)
bg[:] = (np.clip(vig, 0, 1)[..., None] * np.array([13, 13, 17], np.float32) / 255.0)
del gy, gx, vig
X0, Y0, X1, Y1 = int(ox), int(oy), int(ox + TW), int(oy + TH)
bg[Y0:Y1, X0:X1] = np.array([9, 9, 11], np.float32) / 255.0
for i in range(1, nx): bg[Y0:Y1, int(ox + i * P)] = np.array([26, 26, 30], np.float32) / 255.0
for j in range(1, ny): bg[int(oy + j * P), X0:X1] = np.array([26, 26, 30], np.float32) / 255.0
bg[Y0, X0:X1] = bg[Y1 - 1, X0:X1] = np.array([34, 34, 40], np.float32) / 255.0
bg[Y0:Y1, X0] = bg[Y0:Y1, X1 - 1] = np.array([34, 34, 40], np.float32) / 255.0

def font(sz, bold=False):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if bold else '')
    return ImageFont.truetype(p, int(sz))
F_T, F_S, F_C = font(110 * k, True), font(46 * k), font(30 * k)

def text_layer(alpha_title, alpha_cap):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if alpha_title > 0:
        d.rectangle((0, 0, W, H), fill=(4, 4, 6, int(170 * alpha_title)))
        tw = d.textlength(a.title, font=F_T); d.text(((W - tw) / 2, H * 0.40), a.title, font=F_T, fill=(255, 196, 120, int(255 * alpha_title)))
        sw = d.textlength(a.sub, font=F_S); d.text(((W - sw) / 2, H * 0.40 + 150 * k), a.sub, font=F_S, fill=(200, 200, 205, int(255 * alpha_title)))
    if alpha_cap > 0 and a.cap:
        d.text((70 * k, H - 90 * k), a.cap, font=F_C, fill=(150, 150, 158, int(200 * alpha_cap)))
    return im

def frame(t_rel):
    t = a.t0 + t_rel
    img = bg.copy()
    leds = np.zeros((H, W, 3), np.float32)
    for i, b in enumerate(boards):
        v = to_phys(b[2], np.clip(board_frame(i, t) * GAIN, 0, 1)) ** (1 / 2.2)      # gamma 2.2 display
        L = led_layer(v)
        px = int(round(ox + b[0] * P + led0 - cell / 2)); py = int(round(oy + b[1] * P + led0 - cell / 2))
        leds[py:py + 32 * cell, px:px + 32 * cell] = L
    # glow: two blur radii at reduced resolution
    small = Image.fromarray((np.clip(leds, 0, 1) * 255).astype(np.uint8)).resize((W // 8, H // 8), Image.BILINEAR)
    g1 = np.asarray(small.filter(ImageFilter.GaussianBlur(2.2 * k * 2)).resize((W, H), Image.BILINEAR), np.float32) / 255
    g2 = np.asarray(small.filter(ImageFilter.GaussianBlur(7 * k * 2)).resize((W, H), Image.BILINEAR), np.float32) / 255
    img += leds + 0.55 * g1 + 0.45 * g2
    # floor reflection under the stack
    ry0 = Y1 + int(18 * k); rh = min(H - ry0, int(TH * 0.42))
    if rh > 0:
        src = img[Y1 - rh:Y1][::-1]
        fade = (np.linspace(0.20, 0.0, rh, dtype=np.float32) ** 1.3)[:, None, None]
        refl = np.asarray(Image.fromarray((np.clip(src, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3 * k)), np.float32) / 255
        img[ry0:ry0 + rh] += refl * fade
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    # titles: open card 0..4.5 s, end card in the last 3.5 s, caption in between
    D = a.dur
    at = max(0.0, min(1.0, (4.5 - t_rel) / 1.2)) if t_rel < 4.5 else max(0.0, min(1.0, (t_rel - (D - 3.5)) / 1.0))
    ac = min(1.0, max(0.0, (t_rel - 4.0) / 1.5), max(0.0, (D - 3.0 - t_rel) / 1.0))
    if at > 0 or ac > 0:
        out = Image.alpha_composite(out.convert('RGBA'), text_layer(at, ac)).convert('RGB')
    return out

ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                       '-r', str(a.fps), '-i', '-', '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'slow',
                       '-crf', str(a.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out], stdin=subprocess.PIPE)
N = int(a.dur * a.fps); pngs = sorted(a.png)
for fi in (range(N) if a.only is None else [int(a.only * a.fps)]):
    tr = fi / a.fps
    im = frame(tr)
    ff.stdin.write(im.tobytes())
    while pngs and tr >= pngs[0]:
        im.save(os.path.join(a.pngdir, '%s_%04.1fs.png' % (os.path.splitext(os.path.basename(a.out))[0], pngs[0]))); pngs.pop(0)
    if fi % 600 == 0: print('frame %d/%d' % (fi, N), flush=True)
ff.stdin.close(); ff.wait()
print('done', a.out, os.path.getsize(a.out))
