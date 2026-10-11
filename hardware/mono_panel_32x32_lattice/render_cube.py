#!/usr/bin/env python3
"""Mock renders from lattice_geometry.json (PIL): stacked cube (N layers at 5.2 mm = cubic voxels) and a lit top view.
usage: python3 render_cube.py [layers]"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFilter
H = os.path.dirname(os.path.abspath(__file__)); g = json.load(open(os.path.join(H, 'lattice_geometry.json')))
XN, YN, P = g['nodes_x'], g['nodes_y'], g['pitch']; bh, bv = g['bar_h'], g['bar_v']
EL, ET, ER, ETAB = g['edge']; EB = g['edge_b']; TL, TR = g['tab']
LL, LT, LR, LB = g['lattice']
cx, cy = (EL + ER) / 2, (ET + EB) / 2

def lit_pattern(nl):
    """voxel (r, c, layer) -> on: a sine-wave surface through the cube plus a ring on the top layer."""
    on = set()
    for r in range(32):
        for c in range(32):
            h = (nl - 1) / 2 * (1 + math.sin(c / 31 * 2 * math.pi) * math.cos(r / 31 * math.pi))
            on.add((r, c, int(round(h))))
            if math.hypot(r - 15.5, c - 15.5) // 1 in (13,): on.add((r, c, nl - 1))
    return on

def cube(nl=6, W=2000, Hh=1500, out='renders/lattice_cube_stack.png', s=6.0, el_deg=22, focus=None):
    az, el = math.radians(35), math.radians(el_deg)
    global cx, cy
    cx, cy = focus or ((EL + ER) / 2, (ET + EB) / 2)
    def pr(x, y, z):
        x, y = x - cx, y - cy
        u = x * math.cos(az) - y * math.sin(az)
        v = (x * math.sin(az) + y * math.cos(az)) * math.sin(el) - z * math.cos(el) * 1.0
        return (W / 2 + u * s, Hh * 0.58 + v * s)
    img = Image.new('RGBA', (W, Hh), (12, 14, 18, 255)); on = lit_pattern(nl)
    for L in range(nl):                      # painter: bottom layer first
        z = L * P
        lay = Image.new('RGBA', (W, Hh), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        sub = Image.new('RGBA', (W, Hh), (0, 0, 0, 0)); ds = ImageDraw.Draw(sub)
        fr = (40, 110, 70, 110)
        poly = lambda pts, col: d.polygon([pr(x, y, z) for x, y in pts], fill=col)
        # frame (4 strips + tab)
        for a in ([(EL, ET), (ER, ET), (ER, LT), (EL, LT)], [(EL, LB), (ER, LB), (ER, EB), (EL, EB)], [(EL, LT), (LL, LT), (LL, LB), (EL, LB)],
                  [(LR, LT), (ER, LT), (ER, LB), (LR, LB)], [(TL, EB), (TR, EB), (TR, ETAB), (TL, ETAB)]):
            poly(a, fr)
        bar = (70, 160, 105, 95)
        for y in YN: poly([(LL, y - bh / 2), (LR, y - bh / 2), (LR, y + bh / 2), (LL, y + bh / 2)], bar)
        for x in XN: poly([(x - bv / 2, LT), (x + bv / 2, LT), (x + bv / 2, LB), (x - bv / 2, LB)], bar)
        for r, y in enumerate(YN):
            for c, x in enumerate(XN):
                X, Y = pr(x, y + 0.775, z + 0.5)
                if (r, c, L) in on:
                    rr = 1.5 * s; ds.ellipse([X - rr, Y - rr, X + rr, Y + rr], fill=(255, 190, 90, 150))
                    d.ellipse([X - s / 2, Y - s / 2, X + s / 2, Y + s / 2], fill=(255, 245, 225, 255))
                else:
                    d.rectangle([X - s / 4, Y - s / 4, X + s / 4, Y + s / 4], fill=(220, 220, 210, 170))
        img = Image.alpha_composite(img, lay)
        img = Image.alpha_composite(img, sub.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(img)
    d.text((30, 30), '%d x mono_panel_32x32_lattice stacked at %.1f mm (cubic 5.2 mm voxels, 32x32x%d) - mock' % (nl, P, nl), fill=(230, 230, 230))
    d.text((30, 50), 'FR4 0.8 mm, bars %.1f/%.1f mm, windows %.1fx%.1f mm, M2.5 corner spacers %.1f mm' % (bh, bv, *g['win'], P - 0.8), fill=(170, 170, 170))
    img.convert('RGB').save(os.path.join(H, out)); print(out)

def top_lit(W=1400, out='renders/lattice_top_lit.png'):
    s = W / (ER - EL); Hh = int((ETAB - ET) * s)
    img = Image.new('RGBA', (W, Hh), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    p = lambda x, y: ((x - EL) * s, (y - ET) * s)
    def rect(x0, y0, x1, y1, col): d.rectangle([*p(x0, y0), *p(x1, y1)], fill=col)
    fr = (28, 92, 52, 255)
    rect(EL, ET, ER, LT, fr); rect(EL, LB, ER, EB, fr); rect(EL, LT, LL, LB, fr); rect(LR, LT, ER, LB, fr); rect(TL, EB, TR, ETAB, fr)
    for y in YN: rect(LL, y - bh / 2, LR, y + bh / 2, fr)
    for x in XN: rect(x - bv / 2, LT, x + bv / 2, LB, fr)
    for y in YN: rect(LL, y - 0.25, LR, y + 0.25, (190, 150, 70, 255))
    img.save(os.path.join(H, 'renders/lattice_sim_bg.png'))
    glow = Image.new('RGBA', img.size, (0, 0, 0, 0)); dg = ImageDraw.Draw(glow)
    for r, y in enumerate(YN):
        for c, x in enumerate(XN):
            X, Y = p(x, y + 0.775)
            if (r // 4 + c // 4) % 2 == 0:
                dg.ellipse([X - 7, Y - 7, X + 7, Y + 7], fill=(255, 200, 110, 170)); d.ellipse([X - 2.5, Y - 4, X + 2.5, Y + 4], fill=(255, 250, 235, 255))
            else:
                d.rectangle([X - 2, Y - 3.5, X + 2, Y + 3.5], fill=(225, 225, 215, 255))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(3)))
    bg = Image.new('RGBA', img.size, (14, 16, 20, 255)); Image.alpha_composite(bg, img).convert('RGB').save(os.path.join(H, out)); print(out)

if __name__ == '__main__':
    os.makedirs(os.path.join(H, 'renders'), exist_ok=True)
    top_lit()
    for n in ([int(sys.argv[1])] if len(sys.argv) > 1 else [6, 8]):
        cube(n, out='renders/lattice_cube_stack_%d.png' % n)
    cube(6, out='renders/lattice_cube_stack_6_closeup.png', s=22.0, el_deg=25, focus=(XN[12], YN[16]))
