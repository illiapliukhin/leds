"""Cube mode: N stacked 32x32 layers (lattice / full panels) as an N x 32 x 32 volume, software 3D
(numpy projection + additive splat + bloom), volumetric demos and 2D firmware demos mapped onto layers."""
import math, time
import numpy as np
import pygame
from . import host
from .ui import T, text
from .world import PANELS

DEMOS3D = ['shapes', 'wave', 'rain', 'sphere', 'text', 'slices2d', 'extrude2d']
DEMO_RU = {'shapes': 'Вращающиеся фигуры', 'wave': '3D-волна', 'rain': 'Дождь', 'sphere': 'Сфера', 'text': '3D-текст (проход)',
           'slices2d': '2D-демо по слоям (срезы)', 'extrude2d': '2D-демо выдавливанием'}
GLYPH = {}
def glyph_cols(ch):
    if ch not in GLYPH:
        from .host import L
        GLYPH[ch] = None
    return GLYPH[ch]

class CubeView:
    def __init__(s, app):
        s.app = app; s.N = 8; s.kind = 'lattice'; s.demo = 0; s.yaw, s.pitch, s.dist = 0.6, 0.45, 2.6
        s.t0 = time.time(); s.rain = None; s.d2 = 0; s.drag = False
        s._grid()
    def _grid(s):
        n = s.N
        z, y, x = np.meshgrid(np.arange(n), np.arange(32), np.arange(32), indexing='ij')
        s.X, s.Y, s.Z = x.astype(np.float32), y.astype(np.float32), z.astype(np.float32)
        s.rain = np.random.rand(48, 3).astype(np.float32) * [32, 32, 1]
    # normalized coords -1..1 (layer axis scaled by the layer pitch ratio)
    def ncoords(s):
        return (s.X - 15.5) / 16, (s.Y - 15.5) / 16, (s.Z - (s.N - 1) / 2) / 16 * s.zpitch()
    def zpitch(s): return 32 / max(s.N, 1) if s.kind == 'full_cube' else 1.0

    def volume(s, t):
        x, y, z = s.ncoords(); name = DEMOS3D[s.demo]; n = s.N
        if name == 'shapes':
            a, b = t * 0.7, t * 0.45
            ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
            xr = x * ca - z * sa; zr = x * sa + z * ca; yr = y * cb - zr * sb; zr = y * sb + zr * cb
            k = 0.62 + 0.08 * math.sin(t * 1.3)
            ax, ay, az = np.abs(xr), np.abs(yr), np.abs(zr)
            edge = np.minimum(np.minimum(np.maximum(ax, ay), np.maximum(ay, az)), np.maximum(ax, az))   # wire cube edges
            mx = np.maximum(np.maximum(ax, ay), az)
            v = np.clip(1 - np.abs(mx - k) * 14, 0, 1) * np.clip(1 - (k - edge) * 14, 0, 1)
            octa = np.clip(1 - np.abs(ax + ay + az - k * 0.9) * 10, 0, 1) * 0.45
            return np.maximum(v, octa)
        if name == 'wave':
            r = np.sqrt(x * x + y * y)
            h = 0.55 * np.sin(r * 7 - t * 3) * np.exp(-r * 0.8)
            return np.clip(1 - np.abs(z - h) * (8 if n > 4 else 3), 0, 1)
        if name == 'rain':
            v = np.zeros_like(x)
            dt = 1 / 60; s.rain[:, 2] -= dt * (0.6 + 0.4 * (np.arange(48) % 3)) / 1.5
            dead = s.rain[:, 2] < -0.2; s.rain[dead] = np.c_[np.random.rand(dead.sum(), 2) * 32, np.ones(dead.sum()) * 1.0]
            for (dx, dy, dz) in s.rain:
                L = int(np.clip(dz, 0, 0.999) * n)
                c, rr = int(dx) % 32, int(dy) % 32
                v[n - 1 - L, rr, c] = 1.0
                if L + 1 < n: v[n - 2 - L, rr, c] = max(v[n - 2 - L, rr, c], 0.35)
            v[0] = np.maximum(v[0], 0.08 * (0.5 + 0.5 * np.sin(s.X[0] * 0.5 + t * 4) * np.sin(s.Y[0] * 0.5 - t * 3)))
            return v
        if name == 'sphere':
            R = 0.55 + 0.25 * math.sin(t * 1.4)
            d = np.sqrt(x * x + y * y + z * z)
            shell = np.clip(1 - np.abs(d - R) * 12, 0, 1)
            band = 0.5 + 0.5 * np.sin(np.arctan2(y, x) * 6 + t * 3)
            return shell * (0.35 + 0.65 * band)
        if name == 'text':
            img = host.tile(0, 0, 0, 1, 1, 0, 60, int(t * 60))      # stack.c scroll canvas, 1 tile
            ph = (t * 0.6) % 1.0; L = ph * (n - 1)
            v = np.zeros_like(x)
            for k in range(n):
                w = max(0, 1 - abs(k - L) * (1.2 if n > 4 else 0.6))
                v[k] = img / 255.0 * w
            return v
        if name == 'slices2d':
            f = int(t * 60); return np.stack([host.tile(0, 0, 0, 1, 1, s.d2, 60, f - k * 6) for k in range(n)]).astype(np.float32) / 255
        if name == 'extrude2d':
            img = host.tile(0, 0, 0, 1, 1, s.d2, 60, int(t * 60)).astype(np.float32) / 255
            return np.stack([img * (0.4 + 0.6 * (k == 0 or k == n - 1)) for k in range(n)])
        return np.zeros_like(x)

    def event(s, e, view):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3) and view.collidepoint(e.pos) and not s.app.ui.consumed: s.drag = True
        elif e.type == pygame.MOUSEBUTTONUP: s.drag = False
        elif e.type == pygame.MOUSEMOTION and s.drag:
            s.yaw += e.rel[0] * 0.01; s.pitch = max(-1.5, min(1.5, s.pitch + e.rel[1] * 0.01))
        elif e.type == pygame.MOUSEWHEEL: s.dist = max(1.2, min(8, s.dist * (0.9 ** e.y)))

    def draw(s, surf, view):
        t = time.time() - s.t0
        sv = s.app.views['system'].w
        vol = np.clip(s.volume(t), 0, 1)
        lv = (vol * 255 + 0.5).astype(np.uint8)
        duty = host.duty_lut(sv.brightness, sv.gamma)[lv]                # same 8-bit gamma/BCM as the firmware
        x, y, z = s.ncoords()
        cy, sy, cp, sp = math.cos(s.yaw), math.sin(s.yaw), math.cos(s.pitch), math.sin(s.pitch)
        # world: layer axis vertical (layers stacked upward)
        X, Y, Z = x, -z, y
        xr = X * cy - Z * sy; zr = X * sy + Z * cy
        yr = Y * cp - zr * sp; zr = Y * sp + zr * cp
        zc = zr + s.dist; f = min(view.w, view.h) * 0.9
        W, H = view.w // 2, view.h // 2
        px = (xr / zc * f / 2 + W / 2).astype(np.int32); py = (yr / zc * f / 2 + H / 2).astype(np.int32)
        ok = (zc > 0.1) & (px >= 1) & (px < W - 1) & (py >= 1) & (py < H - 1)
        buf = np.zeros((H, W), np.float32)
        base = 0.004                                                       # unlit LED die visibility
        w = (duty * 4.0 + base) * (2.2 / np.maximum(zc, 0.1)) ** 1.2
        np.add.at(buf, (py[ok], px[ok]), w[ok])
        lit = ok & (duty > 0.01)                                           # lit LEDs: 2x2 splat so they read as dots
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            np.add.at(buf, (py[lit] + dy, px[lit] + dx), w[lit] * 0.6)
        img = np.clip(buf, 0, 1.5)
        rgb = (np.clip(img, 0, 1)[..., None] ** (1 / 2.2) * np.array([255, 246, 228], np.float32)).astype(np.uint8)
        small = pygame.surfarray.make_surface(np.ascontiguousarray(rgb.transpose(1, 0, 2)))
        surf.fill((8, 9, 12), view)
        big = pygame.transform.smoothscale(small, view.size)
        glow = pygame.transform.smoothscale(pygame.transform.smoothscale(small, (W // 6, H // 6)), view.size)
        surf.blit(big, view.topleft); surf.blit(glow, view.topleft, special_flags=pygame.BLEND_ADD)
        # layer frames
        n = s.N
        for k in (0, n - 1):
            zz = (k - (n - 1) / 2) / 16 * s.zpitch()
            pts = []
            for (a, b) in [(-1.03, -1.03), (1.03, -1.03), (1.03, 1.03), (-1.03, 1.03)]:
                Xx, Yy, Zz = a, -zz, b
                xr2 = Xx * cy - Zz * sy; zr2 = Xx * sy + Zz * cy; yr2 = Yy * cp - zr2 * sp; zr2 = Yy * sp + zr2 * cp + s.dist
                pts.append((view.x + (xr2 / zr2 * f / 2 + W / 2) * 2, view.y + (yr2 / zr2 * f / 2 + H / 2) * 2))
            pygame.draw.lines(surf, (60, 70, 90), True, pts, 1)
        text(surf, '%d × 32 × 32  (%d LED)  —  %s' % (n, n * 1024, DEMO_RU[DEMOS3D[s.demo]]), (view.x + 10, view.y + 8), (255, 220, 140), 16)
        text(surf, T('hint_cube'), (view.x + 8, view.bottom - 20), (140, 146, 160), 11)

    def panel(s, surf, ui, r):
        x, y, W = r.x + 10, r.y + 8, r.w - 20
        text(surf, T('cube_demo'), (x, y), (170, 180, 200), 12); y += 18
        for i, nm in enumerate(DEMOS3D):
            if ui.button(surf, (x, y, W, 24), DEMO_RU[nm] if T('lang') == 'EN' else nm, on=i == s.demo, sz=12): s.demo = i
            y += 27
        if DEMOS3D[s.demo] in ('slices2d', 'extrude2d'):
            if ui.button(surf, (x, y, W, 24), '2D: ' + host.CANVAS[s.d2], sz=12): s.d2 = (s.d2 + 1) % len(host.CANVAS)
            y += 30
        y += 20
        n = int(ui.slider(surf, (x, y, W, 10), T('layers_n'), s.N, 2, 32))
        if n != s.N: s.N = n; s._grid()
        y += 30
        text(surf, T('cube_panel'), (x, y), (170, 180, 200), 12); y += 18
        for k, lab in (('lattice', 'lattice (решётка, шаг слоёв = шаг LED)'), ('full_cube', 'full: N слоёв на высоту куба')):
            if ui.button(surf, (x, y, W, 24), lab, on=s.kind == k, sz=11): s.kind = k
            y += 27
        y += 8
        sv = s.app.views['system'].w
        sv.brightness = int(ui.slider(surf, (x, y + 16, W, 10), T('brightness'), sv.brightness, 0, 255)); y += 50
        sv.gamma = round(ui.slider(surf, (x, y, W, 10), T('gamma'), sv.gamma, 1.0, 3.0, '%.2f'), 2)
