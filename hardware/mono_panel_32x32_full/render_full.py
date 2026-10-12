#!/usr/bin/env python3
"""Mock renders for mono_panel_32x32_full (PIL): lit front, sim background, back (copper from fixed.json + routes.json),
and a 3x2 tile showing the seamless seam (pitch continuous across board edges)."""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, 'renders')
D = json.load(open(os.path.join(H, 'fixed.json'))); R = json.load(open(os.path.join(H, 'routes.json')))
S, P = D['size'], 5.0
def pattern(t, r, c):                                        # a test image spanning the whole tiled wall
    return 0.5 + 0.5 * math.sin(0.11 * c + 0.07 * r + t) * math.cos(0.05 * c - 0.09 * r)
def front(px_mm, gr0=0, gc0=0, lit=True, R_=192):
    W = int(S * px_mm); im = Image.new('RGB', (W, W), (18, 20, 22)); d = ImageDraw.Draw(im)
    glow = Image.new('RGB', (W, W), (0, 0, 0)); g = ImageDraw.Draw(glow)
    for r in range(32):
        for c in range(32):
            x, y = D['nodes_x'][c] * px_mm, D['nodes_y'][r] * px_mm
            v = pattern(0.0, gr0 + r, gc0 + c) if lit else 0
            d.rectangle([x - 0.4 * px_mm, y - 0.8 * px_mm, x + 0.4 * px_mm, y + 0.8 * px_mm], fill=(225, 225, 210))
            if v > 0.05:
                rr = 1.7 * px_mm; g.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(int(255 * v), int(235 * v), int(200 * v)))
                d.rectangle([x - 0.4 * px_mm, y - 0.8 * px_mm, x + 0.4 * px_mm, y + 0.8 * px_mm], fill=(255, 250, 235))
    glow = glow.filter(ImageFilter.GaussianBlur(px_mm * 1.2))
    return Image.fromarray(np.clip(np.asarray(im, float) + np.asarray(glow, float), 0, 255).astype('uint8'))
os.makedirs(OUT, exist_ok=True)
front(8).save(os.path.join(OUT, 'full_front_lit.png'))
front(6, lit=False).save(os.path.join(OUT, 'full_sim_bg.png'))
# back view (mirrored, seen from behind): copper of all layers + parts on B
k = 8; W = int(S * k); im = Image.new('RGB', (W, W), (12, 60, 30)); d = ImageDraw.Draw(im)
X = lambda x: (S - x) * k
col = {'F.Cu': (40, 90, 50), 'In1.Cu': (50, 110, 70), 'In2.Cu': (90, 170, 90), 'B.Cu': (200, 160, 70)}
for lay in ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'):
    for t in D['tracks']:
        if t['layer'] == lay: d.line([(X(t['x0']), t['y0'] * k), (X(t['x1']), t['y1'] * k)], fill=col[lay], width=max(1, int(t['w'] * k)))
    for t in R['tracks']:
        if t[5] == lay: d.line([(X(t[0]), t[1] * k), (X(t[2]), t[3] * k)], fill=col[lay], width=max(1, int(t[4] * k)))
for v in D['vias'] + [dict(x=v[0], y=v[1]) for v in R['vias']]:
    d.ellipse([X(v['x']) - 2, v['y'] * k - 2, X(v['x']) + 2, v['y'] * k + 2], fill=(210, 180, 90))
for p in D['pads']:
    if 'B.Cu' in p['layers']:
        if p['round']: d.ellipse([X(p['bx1']), p['by0'] * k, X(p['bx0']), p['by1'] * k], fill=(220, 220, 225))
        else: d.rectangle([X(p['bx1']), p['by0'] * k, X(p['bx0']), p['by1'] * k], fill=(230, 200, 120))
for ref, cx in (('J_ROW', 72.75), ('J_COL', 107.75)):
    d.rectangle([X(cx + 12.5), 77.0 * k, X(cx - 12.5), 81.0 * k], fill=(235, 235, 225), outline=(60, 60, 60))
    d.text((X(cx) - 20, 77.8 * k), ref, fill=(20, 20, 20))
d.rectangle([X(92.6), 75.6 * k, X(89.4), 78.2 * k], fill=(30, 30, 30)); d.text((X(92.6), 78.6 * k), 'U_ID 24LC02', fill=(255, 255, 255))
im.save(os.path.join(OUT, 'full_back.png'))
# 3x2 tile, butted, with the seam marked by ticks only outside the image
k = 4; Wt = int(S * k); tile = Image.new('RGB', (3 * Wt + 40, 2 * Wt + 70), (5, 5, 5)); dt = ImageDraw.Draw(tile)
for br in range(2):
    for bc in range(3):
        tile.paste(front(k, br * 32, bc * 32), (20 + bc * Wt, 20 + br * Wt))
for bc in range(1, 3): dt.line([(20 + bc * Wt, 2), (20 + bc * Wt, 16)], fill=(255, 80, 80), width=2); dt.line([(20 + bc * Wt, 24 + 2 * Wt), (20 + bc * Wt, 38 + 2 * Wt)], fill=(255, 80, 80), width=2)
dt.line([(2, 20 + Wt), (16, 20 + Wt)], fill=(255, 80, 80), width=2)
dt.text((20, 2 * Wt + 46), '3x2 mono_panel_32x32_full, butted edge to edge: 96x64 LEDs at a continuous 5.0 mm pitch (red ticks = board seams), 480x320 mm', fill=(220, 220, 220))
tile.save(os.path.join(OUT, 'full_tiled_3x2.png'))
# seam close-up
z = tile.crop((20 + Wt - 60, 20 + Wt - 60, 20 + Wt + 60, 20 + Wt + 60)).resize((480, 480), Image.NEAREST); z.save(os.path.join(OUT, 'full_seam_closeup.png'))
print('ok')
