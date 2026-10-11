"""Cube mode: N stacked 32x32 layers (lattice / full panels) as an N x 32 x 32 volume, software 3D
(numpy projection + additive splat + bloom), volumetric demos and 2D firmware demos mapped onto layers."""
import math, time
import numpy as np
import pygame
from . import host
from .ui import T, text
from .world import PANELS
from .camera import OrbitCam
from . import cube_fx, image3d

DEMOS3D = ['ambigram', 'anamorph', 'image', 'tsweep', 'life', 'fireworks', 'snake', 'heart', 'ripples', 'plasma', 'dna', 'shapes', 'wave', 'rain', 'sphere', 'text', 'slices2d', 'extrude2d']
DEMO_RU = {'shapes': 'Вращающиеся фигуры', 'wave': '3D-волна', 'rain': 'Дождь', 'sphere': 'Сфера', 'text': '3D-текст (проход)',
           'slices2d': '2D-демо по слоям (срезы)', 'extrude2d': '2D-демо выдавливанием',
           'ambigram': 'Амбиграмма (3 слова)', 'anamorph': 'Анаморфоз', 'image': 'Картинка → 3D', 'tsweep': 'Вращающийся 3D-текст', 'life': '3D «Жизнь»',
           'fireworks': 'Фейерверк', 'snake': '3D-змейка', 'heart': 'Воксельное сердце', 'ripples': 'Круги на воде', 'plasma': 'Плазма', 'dna': 'ДНК (двойная спираль)'}
GLYPH = {}
def glyph_cols(ch):
    if ch not in GLYPH:
        from .host import L
        GLYPH[ch] = None
    return GLYPH[ch]

class CubeView:
    def __init__(s, app):
        s.app = app; s.N = 8; s.kind = 'lattice'; s.demo = 0; s.cam = OrbitCam()
        s.t0 = time.time(); s.rain = None; s.d2 = 0; s.drag = False
        s.words = ['LED', 'ILLIA', 'MONO']; s.fx = cube_fx.FX(); s.amb = None; s.amb_key = None; s.ana = None; s.ana_key = None
        s.img = image3d.demo_image(); s.img2 = None; s.img_name = 'встроенная картинка'; s.imode = 0; s.igamma = 1.0; s.ithr = 0.5
        s.idither = False; s.iinvert = False; s.ifill = False; s.msg = ''
        s._grid()
    def _grid(s):
        n = s.N
        z, y, x = np.meshgrid(np.arange(n), np.arange(32), np.arange(32), indexing='ij')
        s.X, s.Y, s.Z = x.astype(np.float32), y.astype(np.float32), z.astype(np.float32)
        s.rain = np.random.rand(48, 3).astype(np.float32) * [32, 32, 1]
        if hasattr(s, 'fx'): s.fx.reset(n); s.amb_key = s.ana_key = None
    # normalized coords -1..1 (layer axis scaled by the layer pitch ratio)
    def ncoords(s):
        return (s.X - 15.5) / 16, (s.Y - 15.5) / 16, (s.Z - (s.N - 1) / 2) / 16 * s.zpitch()
    def zpitch(s): return 32 / max(s.N, 1) if s.kind == 'full_cube' else 1.0

    def volume(s, t):
        x, y, z = s.ncoords(); name = DEMOS3D[s.demo]; n = s.N; dt = min(0.1, s.app.dt)
        if s.fx.n != n: s.fx.reset(n)
        if name == 'ambigram':
            k = (tuple(s.words), n)
            if k != s.amb_key: s.amb, s.amb_rep = cube_fx.ambigram(s.words, n); s.amb_key = k
            return s.amb
        if name == 'anamorph':
            k = (s.words[0], n, s.kind)
            if k != s.ana_key: s.ana = cube_fx.anamorphic(cube_fx.text_mask(s.words[0], 32, 32), n, *s.READ['ana'], zpitch=s.zpitch()); s.ana_key = k
            return s.ana
        if name == 'image':
            g, m = image3d.preprocess(s.img, s.igamma, s.ithr, s.idither, s.iinvert)
            m2 = image3d.preprocess(s.img2, s.igamma, s.ithr, s.idither, s.iinvert)[1] if s.img2 is not None else None
            return image3d.volume(image3d.MODES[s.imode], g, m, n, t, mask2=m2, fill=s.ifill)
        if name == 'tsweep': return cube_fx.FX.text_sweep(s.words[0], x, y, z, t, n)
        if name == 'life': return s.fx.life3d(t, dt)
        if name == 'fireworks': return s.fx.fireworks(t, dt)
        if name == 'snake': return s.fx.snake3d(t, dt)
        if name == 'heart': return cube_fx.FX.heart(x, y, z, t)
        if name == 'ripples': return cube_fx.FX.ripples(x, y, z, t)
        if name == 'plasma': return cube_fx.FX.plasma(x, y, z, t)
        if name == 'dna': return cube_fx.FX.dna(x, y, z, t)
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

    def event(s, e, view): s.cam.event(e, view, s.app)

    def draw(s, surf, view):
        t = time.time() - s.t0
        sv = s.app.views['system'].w
        vol = np.clip(s.volume(t), 0, 1)
        lv = (vol * 255 + 0.5).astype(np.uint8); s.last_lv = lv
        duty = host.duty_lut(sv.brightness, sv.gamma)[lv]                # same 8-bit gamma/BCM as the firmware
        x, y, z = s.ncoords()
        c = s.cam; c.update(s.app.dt, s.app); tx, ty, tz = c.target
        cy, sy, cp, sp = math.cos(c.yaw), math.sin(c.yaw), math.cos(c.pitch), math.sin(c.pitch)
        # world: layer axis vertical (layers stacked upward); camera looks at c.target
        X, Y, Z = x - tx, -z - ty, y - tz
        xr = X * cy - Z * sy; zr = X * sy + Z * cy
        yr = Y * cp - zr * sp; zr = Y * sp + zr * cp
        zc = zr + c.dist; f = min(view.w, view.h) * 0.9 * (c.dist / 2.6 if getattr(c, 'tele', False) else 1.0)
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
                Xx, Yy, Zz = a - tx, -zz - ty, b - tz
                xr2 = Xx * cy - Zz * sy; zr2 = Xx * sy + Zz * cy; yr2 = Yy * cp - zr2 * sp; zr2 = Yy * sp + zr2 * cp + c.dist
                pts.append((view.x + (xr2 / zr2 * f / 2 + W / 2) * 2, view.y + (yr2 / zr2 * f / 2 + H / 2) * 2))
            pygame.draw.lines(surf, (60, 70, 90), True, pts, 1)
        text(surf, '%d × 32 × 32  (%d LED)  —  %s' % (n, n * 1024, DEMO_RU[DEMOS3D[s.demo]]), (view.x + 10, view.y + 8), (255, 220, 140), 16)
        text(surf, T('hint_cube'), (view.x + 8, view.bottom - 20), (140, 146, 160), 11)

    READ = {'w1': (0.0, 0.0), 'w2': (-math.pi / 2, 0.0), 'w3': (0.0, 1.55), 'ana': (0.62, 0.42)}
    def snap(s, k): s.cam.goal = s.READ[k] + (8.0,); s.cam.target = [0.0, 0.0, 0.0]; s.cam.tele = True       # far + long lens ≈ orthographic reading view
    def frames_for_export(s):
        name = DEMOS3D[s.demo]; static = name in ('ambigram', 'anamorph') or (name == 'image' and image3d.MODES[s.imode] in ('height', 'silhouette', 'bands', 'ambigram2', 'pseudo'))
        F = 1 if static else 180
        return [np.clip(s.volume(k / 30.0), 0, 1) for k in range(F)], 30
    def panel(s, surf, ui, r):
        x, y, W = r.x + 10, r.y + 6, r.w - 20
        text(surf, T('cube_demo'), (x, y), (170, 180, 200), 12); y += 16
        bw = (W - 4) // 2
        for i, nm in enumerate(DEMOS3D):
            if ui.button(surf, (x + (i % 2) * (bw + 4), y + (i // 2) * 21, bw, 19), DEMO_RU[nm], on=i == s.demo, sz=10): s.demo = i
        y += ((len(DEMOS3D) + 1) // 2) * 21 + 4
        name = DEMOS3D[s.demo]
        if name in ('ambigram', 'anamorph', 'tsweep'):
            labels = ('Спереди', 'Сбоку', 'Сверху') if name == 'ambigram' else ('Слово',)
            for i, lb in enumerate(labels):
                text(surf, lb, (x, y + 4), sz=11)
                s.words[i], _ = ui.field(surf, (x + 70, y, W - 70, 22), ('word', i), s.words[i]); s.words[i] = s.words[i][:10]; y += 25
            if name == 'ambigram':
                for i, (k, lb) in enumerate((('w1', 'Читать 1'), ('w2', 'Читать 2'), ('w3', 'Читать 3'))):
                    if ui.button(surf, (x + i * ((W - 8) // 3 + 4), y, (W - 8) // 3, 22), lb, sz=10): s.snap(k)
                y += 26
                if s.amb_key: text(surf, 'читаемость: %.0f%% / %.0f%% / %.0f%%' % tuple(100 * v for v in s.amb_rep), (x, y), (200, 220, 160), 11); y += 16
            if name == 'anamorph':
                if ui.button(surf, (x, y, W, 22), 'Камера в точку прочтения', sz=11): s.snap('ana')
                y += 26
        if name == 'image':
            if ui.button(surf, (x, y, bw, 22), 'Загрузить PNG/JPG', sz=10):
                pth = s.ask_image()
                if pth:
                    try: s.img = image3d.load_gray(pth); s.img_name = pth.replace('\\', '/').split('/')[-1]
                    except Exception as ex: s.msg = 'ошибка: %s' % ex
            if ui.button(surf, (x + bw + 4, y, bw, 22), '2-я (амбиграмма)', sz=10):
                pth = s.ask_image()
                if pth:
                    try: s.img2 = image3d.load_gray(pth)
                    except Exception as ex: s.msg = 'ошибка: %s' % ex
            y += 25; text(surf, s.img_name[:44], (x, y), (160, 170, 190), 10); y += 14
            for i, m in enumerate(image3d.MODES):
                if ui.button(surf, (x + (i % 2) * (bw + 4), y + (i // 2) * 21, bw, 19), image3d.MODE_RU[m][:26], on=i == s.imode, sz=9): s.imode = i
            y += ((len(image3d.MODES) + 1) // 2) * 21 + 18
            s.igamma = ui.slider(surf, (x, y, bw, 8), 'Гамма', s.igamma, 0.3, 3.0, '%.2f')
            s.ithr = ui.slider(surf, (x + bw + 4, y, bw, 8), 'Порог', s.ithr, 0.05, 0.95, '%.2f'); y += 14
            tb = (W - 8) // 3
            if ui.button(surf, (x, y, tb, 20), 'Дизеринг', on=s.idither, sz=10): s.idither = not s.idither
            if ui.button(surf, (x + tb + 4, y, tb, 20), 'Инверсия', on=s.iinvert, sz=10): s.iinvert = not s.iinvert
            if ui.button(surf, (x + 2 * (tb + 4), y, tb, 20), 'Заливка', on=s.ifill, sz=10): s.ifill = not s.ifill
            y += 24
            g, m = image3d.preprocess(s.img, s.igamma, s.ithr, s.idither, s.iinvert)
            for k, arr in enumerate((g, m.astype(np.float32))):
                sm = pygame.surfarray.make_surface((np.repeat(arr.T[..., None], 3, 2) * 255).astype(np.uint8))
                surf.blit(pygame.transform.scale(sm, (96, 96)), (x + k * 104, y))
            text(surf, 'превью 32×32: уровни / маска', (x + 210, y + 40), (150, 156, 170), 10); y += 100
            if ui.button(surf, (x, y, W, 22), 'Экспорт анимации .lv3d (для прошивки)', sz=11):
                import os, time as _t
                from .view_system import layout_dir
                fr, fps = s.frames_for_export(); pth = os.path.join(layout_dir(), _t.strftime('cube_%Y%m%d_%H%M%S.lv3d'))
                sz = image3d.export_lv3d(pth, fr, fps); s.msg = '%s: %d кадр., %d Б' % (pth.split(os.sep)[-1], len(fr), sz)
            y += 24
            if s.msg: text(surf, s.msg[:58], (x, y), (255, 230, 150), 10); y += 14
        y += 16
        n = int(ui.slider(surf, (x, y, W, 8), T('layers_n'), s.N, 2, 32))
        if n != s.N: s.N = n; s._grid()
        y += 14
        for i, (k, lab) in enumerate((('lattice', 'решётка'), ('full_cube', 'full: N на высоту'))):
            if ui.button(surf, (x + i * (bw + 4), y, bw, 20), lab, on=s.kind == k, sz=10): s.kind = k
        y += 24
        qb = (W - 12) // 4
        for i, (k, lab) in enumerate((('front', 'Спереди'), ('top', 'Сверху'), ('iso', 'Изо'), ('reset', 'Сброс'))):
            if ui.button(surf, (x + i * (qb + 4), y, qb, 20), lab, sz=10):
                s.cam.reset() if k == 'reset' else s.cam.preset(k)
        y += 38
        sv = s.app.views['system'].w
        sv.brightness = int(ui.slider(surf, (x, y, bw, 8), T('brightness'), sv.brightness, 0, 255))
        sv.gamma = round(ui.slider(surf, (x + bw + 4, y, bw, 8), T('gamma'), sv.gamma, 1.0, 3.0, '%.2f'), 2); y += 14
        lim = s.limits()
        for ln in lim:
            text(surf, ln, (x, y), (150, 160, 180), 10); y += 13
    def limits(s):
        sv = s.app.views['system'].w; lut = host.duty_lut(sv.brightness, sv.gamma)
        vol = getattr(s, 'last_lv', None)
        i_lay = 0.0
        if vol is not None: i_lay = float(lut[vol].sum(axis=(1, 2)).max()) * 0.0102 / 32       # avg LED current per layer (1/32 scan)
        return ['Аппаратные пределы: слоёв %d из 128 (MAXB), 60 кадр/с на слой (FRAME_SYNC),' % s.N,
                '8 бит BCM + гамма прошивки; ток слоя сейчас %.0f мА (макс. 327 мА, полный белый),' % (i_lay * 1e3),
                'весь куб %.2f А при 4.24 В; контент считается на каждой плате локально.' % (i_lay * s.N)]
    def ask_image(s):
        try:
            import tkinter as tk; from tkinter import filedialog
            r = tk.Tk(); r.withdraw(); p = filedialog.askopenfilename(filetypes=[('Изображения', '*.png *.jpg *.jpeg *.bmp *.gif')]); r.destroy(); return p or None
        except Exception: return None
