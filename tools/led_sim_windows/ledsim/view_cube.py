"""Cube mode: N stacked 32x32 layers (lattice / full panels) as an N x 32 x 32 volume, software 3D
(numpy projection + additive splat + bloom), volumetric demos and 2D firmware demos mapped onto layers."""
import math, time
import numpy as np
from . import hwquant
import pygame
from . import host
from .ui import T, text
from .world import PANELS
from .camera import OrbitCam
from . import cube_fx, image3d, cube_rig
from .world import BOARD_W, BOARD_H, BOARD_CONN
from .cube_rig import GB, GB_W, GB_H, GAP

DEMOS3D = ['vysh3d', 'walker', 'runner', 'gogo', 'ambigram', 'anamorph', 'image', 'tsweep', 'life', 'fireworks', 'snake', 'heart', 'ripples', 'plasma', 'dna', 'shapes', 'wave', 'rain', 'sphere', 'text', 'slices2d', 'extrude2d']
DEMO_RU = {'shapes': 'Вращающиеся фигуры', 'wave': '3D-волна', 'rain': 'Дождь', 'sphere': 'Сфера', 'text': '3D-текст (проход)',
           'slices2d': '2D-демо по слоям (срезы)', 'extrude2d': '2D-демо выдавливанием',
           'ambigram': 'Амбиграмма (3 слова)', 'anamorph': 'Анаморфоз', 'image': 'Картинка → 3D', 'tsweep': 'Вращающийся 3D-текст', 'life': '3D «Жизнь»',
           'fireworks': 'Фейерверк', 'snake': '3D-змейка', 'heart': 'Воксельное сердце', 'ripples': 'Круги на воде', 'plasma': 'Плазма', 'dna': 'ДНК (двойная спираль)', 'walker': 'Идущий человек', 'runner': 'Бегущий человек', 'gogo': 'Гоу-гоу (танцовщица)', 'vysh3d': 'Вышиванка 3D'}
_GLUT = ((np.linspace(0, 1, 1024)[:, None] ** (1 / 2.2)) * np.array([255, 246, 228])).astype(np.uint8)
GLYPH = {}
# persistence (decay per frame at 60 fps) for fast-moving effects = temporal AA; 0 = none (static/slow effects)
PERSIST = {'rain': 0.55, 'fireworks': 0.6, 'snake': 0.4, 'tsweep': 0.35, 'shapes': 0.3, 'sphere': 0.3, 'dna': 0.35, 'wave': 0.25,
           'walker': 0.25, 'runner': 0.35, 'gogo': 0.3, 'text': 0.3, 'ripples': 0.2, 'heart': 0.2, 'vysh3d': 0.15}

STATIC3D = ('ambigram', 'anamorph')         # read-from-an-angle sculptures: deliberately still
FIG_LOOP = {'walker': 60, 'runner': 40, 'gogo': 225}     # loop length in frames @ 60 fps (flash clip)

def glyph_cols(ch):
    if ch not in GLYPH:
        from .host import L
        GLYPH[ch] = None
    return GLYPH[ch]

class CubeView:
    def __init__(s, app):
        s.app = app; s.clips = {}; s.N = 8; s.kind = 'lattice'; s.demo = DEMOS3D.index('vysh3d'); s.cam = OrbitCam()
        s.t0 = time.time(); s.rain = None; s.d2 = 0; s.drag = False
        s.words = ['LED', 'ILLIA', 'MONO']; s.fx = cube_fx.FX(); s.amb = None; s.amb_key = None; s.ana = None; s.ana_key = None
        s.img = image3d.demo_image(); s.img2 = None; s.img_name = 'встроенная картинка'; s.imode = 0; s.igamma = 1.0; s.ithr = 0.5
        s.idither = False; s.iinvert = False; s.ifill = False; s.msg = ''
        s.kind = 'wire'; s.show_hw = False; s.show_ruler = False; s.stretch = False; s.handles = {}; s.hdrag = None; s.ptxt = {}
        s._grid(); s.reset_pitch()
    def _grid(s):
        n = s.N
        z, y, x = np.meshgrid(np.arange(n), np.arange(32), np.arange(32), indexing='ij')
        s.X, s.Y, s.Z = x.astype(np.float32), y.astype(np.float32), z.astype(np.float32)
        s.rain = np.random.rand(48, 3).astype(np.float32) * [32, 32, 1]
        if hasattr(s, 'fx'): s.fx.reset(n); s.amb_key = s.ana_key = None
    # normalized coords -1..1 (layer axis scaled by the layer pitch ratio)
    def ncoords(s):
        return (s.X - 15.5) / 16, (s.Y - 15.5) / 16, (s.Z - (s.N - 1) / 2) / 16 * s.zpitch()
    def zpitch(s): return round(s.pz / s.px, 2) if hasattr(s, 'pz') else (32 / max(s.N, 1) if s.kind == 'full_cube' else 1.0)
    # ---- real pitch per axis (mm). PCB panels: X/Y fixed by the board, only Z (layer spacing) can change.
    def reset_pitch(s, z_only=False):
        p0, _ = cube_rig.nominal(s.kind)
        if not z_only: s.px = s.py = p0
        s.pz = cube_rig.default_z(s.kind, s.N); s._rig = None
    def set_pitch(s, ax, v):
        lo, hi = cube_rig.PITCH_RANGE['z' if ax == 'z' else 'xy']
        if ax != 'z' and s.kind != 'wire': return                                    # printed panel: pitch is copper
        setattr(s, 'p' + ax, round(max(lo, min(hi, float(v))), 2)); s._rig = None
    def U(s): return 1.0 / (16 * cube_rig.nominal(s.kind)[0])                        # mm -> render units (nominal grid = ±1)
    def rig(s):
        k = (s.kind, s.N, s.px, s.py, s.pz)
        if getattr(s, '_rig', None) is None or s._rig_key != k: s._rig = cube_rig.Rig(*k); s._rig_key = k
        return s._rig
    def fit_hw(s):
        """camera framing for the whole rig (cube + electronics) when the electronics are switched on"""
        r = s.rig(); U = s.U(); c = s.cam
        x0, x1 = -r.hx, (r.psu[0] + 50 if getattr(s, 'show_hw', False) else r.hx)
        c.target = [(x0 + x1) / 2 * U, 0.0, 0.0]; c.dist_t = max(2.6, (x1 - x0) / 2 * U * 1.8); c.R = None
        if c.goal: c.goal = tuple(c.goal[:2]) + (c.dist_t,)

    def volume(s, t):
        x, y, z = s.ncoords(); name = DEMOS3D[s.demo]; n = s.N; dt = min(0.1, s.app.dt)
        if s.fx.n != n: s.fx.reset(n)
        if name == 'ambigram':
            k = (tuple(s.words), n)
            if k != s.amb_key: s.amb, s.amb_rep = cube_fx.ambigram(s.words, n); s.amb_key = k
            return s.amb
        if name == 'anamorph':
            k = (s.words[0], n, s.kind, s.zpitch())
            if k != s.ana_key: s.ana = cube_fx.anamorphic(cube_fx.text_mask(s.words[0], 32, 32), n, *s.READ['ana'], zpitch=s.zpitch()); s.ana_key = k
            return s.ana
        if name == 'image':
            g, m = image3d.preprocess(s.img, s.igamma, s.ithr, s.idither, s.iinvert)
            m2 = image3d.preprocess(s.img2, s.igamma, s.ithr, s.idither, s.iinvert)[1] if s.img2 is not None else None
            return image3d.volume(image3d.MODES[s.imode], g, m, n, t, mask2=m2, fill=s.ifill)
        if name == 'tsweep': return cube_fx.FX.text_sweep(s.words[0], x, y, z, t, n)
        if name in ('walker', 'runner', 'gogo'):
            # The skeletal SDF figure costs 25–100 ms/frame on the S3 (see the autotest feasibility section), so on the board it
            # is PRECOMPUTED into flash: one gait/choreography loop (walk 1 s = 60, run 0.67 s = 40, go-go 8 beats @128 bpm =
            # 225 frames), 1 KB per frame per board (its own layer). The simulator does the same: it renders each loop phase
            # once (after one warm-up loop so hair/skirt physics are settled) and then plays the clip back.
            P = FIG_LOOP[name]; k = int(round(t * 60)) % P
            clip = s.clips.get((name, n, s.kind))
            if clip is None:
                if len(s.clips) > 3: s.clips.clear()
                clip = s.clips[(name, n, s.kind)] = {}
            if len(clip) == P: return clip[k].astype(np.float32) * (1 / 255)
            v = cube_fx.figure({'walker': 'walk', 'runner': 'run'}.get(name, name), x, y, z, t, dt)
            if t > P / 60 + 0.5 and k not in clip: clip[k] = (np.clip(v, 0, 1) * 255 + 0.5).astype(np.uint8)
            return v
        if name == 'vysh3d': return cube_fx.vysh3d(n, t, s.zpitch())
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

    def event(s, e, view):
        if getattr(s, 'stretch', False):                                   # pitch drag handles take the left button first
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not s.app.ui.consumed:
                for ax, (o, q) in s.handles.items():
                    if math.hypot(e.pos[0] - q[0], e.pos[1] - q[1]) < 11: s.hdrag = ax; return
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and s.hdrag: s.hdrag = None; return
            elif e.type == pygame.MOUSEMOTION and s.hdrag:
                o, q = s.handles.get(s.hdrag, (None, None))
                if o:
                    vx, vy = q[0] - o[0], q[1] - o[1]; Ln = math.hypot(vx, vy)
                    if Ln > 5:
                        d = (e.rel[0] * vx + e.rel[1] * vy) / Ln
                        s.set_pitch(s.hdrag, getattr(s, 'p' + s.hdrag) * (Ln + d) / Ln)
                return
        s.cam.event(e, view, s.app)

    def post(s, vol, t):
        """per-board output stage every effect shares (what the firmware does after the effect kernel): a phosphor-like
        persistence for fast movers (temporal anti-aliasing: a moving voxel leaves a 1–3 frame fading trail through the
        8-bit levels instead of jumping), and a 0.6 s smoothstep cross-fade when the effect or layer count changes.
        RAM: one float layer per board (4 KB)."""
        name = DEMOS3D[s.demo]; key = (name, s.N)
        prev = getattr(s, '_pv', None)
        if prev is not None and prev.shape == vol.shape and getattr(s, '_post_key', None) == key:
            d = PERSIST.get(name, 0.0)
            if d: vol = np.maximum(vol, prev * d)
        elif prev is not None and prev.shape == vol.shape:
            s._fade = (prev.copy(), t)                                       # effect switched: cross-fade from the last frame
        s._post_key = key
        fd = getattr(s, '_fade', None)
        if fd is not None:
            a = (t - fd[1]) / 0.6
            if a >= 1 or fd[0].shape != vol.shape: s._fade = None
            else: a = a * a * (3 - 2 * a); vol = fd[0] * (1 - a) + vol * a
        s._pv = vol
        return vol

    def draw(s, surf, view):
        t = time.time() - s.t0
        sv = s.app.views['system'].w
        vol = s.post(np.clip(s.volume(t), 0, 1).astype(np.float32), t)
        s.qframe = getattr(s, 'qframe', 0) + 1
        s.last_vol = vol; s.frames_drawn = getattr(s, 'frames_drawn', 0) + 1
        lv = hwquant.quantize(vol, s.qframe, sv.gamma); s.last_lv = lv      # firmware demo.c gamma-aware dither
        duty = host.duty_lut(sv.brightness, sv.gamma)[lv]                # same 8-bit gamma/BCM as the firmware
        x, y, z = s.ncoords()
        c = s.cam; c.update(s.app.dt, s.app); tx, ty, tz = c.target
        cy, sy, cp, sp = math.cos(c.yaw), math.sin(c.yaw), math.cos(c.pitch), math.sin(c.pitch); sp_cam = sp
        # world: layer axis vertical (layers stacked upward); camera looks at c.target
        M = c.matrix()
        pkey = (M.tobytes(), tuple(c.target), c.dist, getattr(c, 'tele', False), view.size, s.N, s.kind, s.px, s.py, s.pz)
        if pkey != getattr(s, '_pkey', None):                              # projection only changes with the camera / pitch
            U = s.U()                                                      # LED positions at the real pitch (mm) per axis
            xm = (s.X - 15.5) * (s.px * U); ym = (s.Y - 15.5) * (s.py * U); zm = (s.Z - (s.N - 1) / 2) * (s.pz * U)
            X, Y, Z = xm - tx, -zm - ty, ym - tz
            xr = M[0, 0] * X + M[0, 1] * Y + M[0, 2] * Z; yr = M[1, 0] * X + M[1, 1] * Y + M[1, 2] * Z; zr = M[2, 0] * X + M[2, 1] * Y + M[2, 2] * Z
            zc = zr + c.dist; f = min(view.w, view.h) * 0.9 * (c.dist / 2.6 if getattr(c, 'tele', False) else 1.0)
            W, H = view.w // 2, view.h // 2
            px = (xr / zc * f / 2 + W / 2).astype(np.int32); py = (yr / zc * f / 2 + H / 2).astype(np.int32)
            ok = (zc > 0.1) & (px >= 1) & (px < W - 1) & (py >= 1) & (py < H - 1)
            s._proj = (px, py, zc, ok, f, W, H, ((2.2 / np.maximum(zc, 0.1)) ** 1.2)[ok], (py * W + px)[ok]); s._pkey = pkey
        px, py, zc, ok, f, W, H, att, idx = s._proj
        base = 0.004                                                       # unlit LED die visibility
        dk = duty[ok]; wk = (dk * 4.0 + base) * att
        # bincount is ~10× faster than np.add.at for the splat
        acc = np.bincount(idx, wk, H * W)
        lit = dk > 0.01                                              # lit LEDs: 2x2 splat so they read as dots
        il, wl = idx[lit], wk[lit] * 0.6
        for d in (1, W, W + 1): acc += np.bincount(il + d, wl, H * W)
        buf = acc.reshape(H, W).astype(np.float32)
        # display gamma via a 1024-entry LUT (was a per-pixel float pow), built straight in (W, H, 3) order
        q = (np.minimum(buf.T, 1.0) * 1023).astype(np.int16)
        small = pygame.surfarray.make_surface(_GLUT[q])
        surf.fill((8, 9, 12), view); surf.set_clip(view)
        # glow added at half resolution, then ONE upscale (was two full-size smoothscales + a full-size additive blit)
        glow = pygame.transform.smoothscale(pygame.transform.smoothscale(small, (max(1, W // 6), max(1, H // 6))), (W, H))
        small.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)
        surf.blit(pygame.transform.smoothscale(small, view.size), view.topleft)
        # ---- true-scale overlay: every coordinate below is mm (cube centre = origin, z up), U = mm -> render units
        rig = s.rig(); U = s.U()
        def P3(a, b, zz):
            Xx, Yy, Zz = a - tx, -zz - ty, b - tz
            xr2 = M[0, 0] * Xx + M[0, 1] * Yy + M[0, 2] * Zz; yr2 = M[1, 0] * Xx + M[1, 1] * Yy + M[1, 2] * Zz; zr2 = M[2, 0] * Xx + M[2, 1] * Yy + M[2, 2] * Zz + c.dist
            if zr2 < 0.15: return None
            return (view.x + (xr2 / zr2 * f / 2 + W / 2) * 2, view.y + (yr2 / zr2 * f / 2 + H / 2) * 2)
        Pm = lambda x_, y_, z_: P3(x_ * U, y_ * U, z_ * U)
        s._Pm = Pm
        n = s.N
        hw = getattr(s, 'show_hw', False)
        for zz in (rig.zl if hw else (rig.zl[0], rig.zl[-1])):                # frame / panel outline (every layer with electronics on)
            pts = [Pm(a_ * rig.hx, b_ * rig.hy, zz) for a_, b_ in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            if all(pts): pygame.draw.lines(surf, (60, 70, 90), True, pts, 1)
        if hw: s.draw_hw(surf, Pm, rig)
        if getattr(s, 'show_ruler', False): s.draw_ruler(surf, Pm, rig, hw)
        if getattr(s, 'stretch', False): s.draw_handles(surf, Pm, rig)
        text(surf, '%d × 32 × 32  (%d LED)  —  %s' % (n, n * 1024, DEMO_RU[DEMOS3D[s.demo]]), (view.x + 10, view.y + 8), (255, 220, 140), 16)
        text(surf, 'шаг X %.2f · Y %.2f · Z %.2f мм   |   куб %.0f × %.0f × %.0f мм' % (s.px, s.py, s.pz, 2 * rig.hx, 2 * rig.hy, (n - 1) * s.pz),
             (view.x + 10, view.y + 28), (170, 180, 200), 12)
        y_ = view.y + 44
        if hw or getattr(s, 'stretch', False):
            for sev, ln in rig.flags():
                text(surf, ('⚠ ' if sev == 'err' else '✓ ') + ln, (view.x + 10, y_), (255, 120, 100) if sev == 'err' else (140, 210, 150), 12); y_ += 15
        text(surf, T('hint_cube'), (view.x + 8, view.bottom - 20), (140, 146, 160), 11)
        surf.set_clip(None)

    # ------------------------------------------------------------------ true-scale rig (cube_rig.Rig) drawing
    def draw_hw(s, surf, Pm, rig):
        """electronics beside the cube at real mm: a tower of mono_electronics v15 boards (148.04 × 99.5) on 16 mm
        stand-offs (or one per layer height when the layer pitch ≥ 16 mm), each with its garland_breakout (60 × 145) for the
        wire grid; FFC board→breakout, four 16-way ribbon looms per layer up shared risers (= bundled), combs to the rails,
        JST-SH stacking cables, USB-C harness to the 5 V PSU. Boards are drawn semi-transparent."""
        from . import pcbtex
        show = s.app.views['system'].show; n = rig.n; bundle = show.get('bundle', True)
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        lod = 1 if n <= 8 else 2 if n <= 16 else 4
        def quad(cx, cy, z, w, h):
            return [Pm(cx + dx * w / 2, cy + dy * h / 2, z) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        def L(col, pts, w=1, on=surf):
            q = [Pm(*p) for p in pts]
            if all(q) and len(q) > 1: pygame.draw.lines(on, col, False, q, w)
        mask = tuple(pcbtex.MASK[:3]) + (120,)
        for k, (ty, zk) in enumerate(rig.units):
            for (cx_, ww, hh, key_, oc) in ((rig.bx, BOARD_W, BOARD_H, 'board_v15', (80, 180, 110)),) + (((rig.ax, GB_W, GB_H, 'garland', (180, 150, 80)),) if rig.wire else ()):
                q = quad(cx_, ty, zk, ww, hh)
                if not all(q): continue
                pygame.draw.polygon(ov, mask, q)
                if lod == 1:
                    for (px0, py0, pw, ph, colr) in pcbtex.parts(key_):                  # parts at their real place (board rotated 180°)
                        qq = quad(cx_ - px0, ty - py0, zk, pw, ph)
                        if all(qq): pygame.draw.polygon(ov, tuple(colr[:3]) + (150,), qq)
                pygame.draw.lines(surf, oc, True, q, 1)
            if k in (0, n - 1) and (k == 0 or rig.units[k][0] != rig.units[0][0] or True):
                q = Pm(rig.bx + BOARD_W / 2, ty + BOARD_H / 2, zk); q and text(surf, 'L%d' % k, (q[0] + 6, q[1] - 4 + (8 if k == 0 else -8)), (150, 200, 160), 9)
        surf.blit(ov, (0, 0))
        for k, r in enumerate(rig.cables):
            if show.get('ffc', True):
                if rig.wire:
                    L((120, 150, 220), r['ffc']['pts'], 4 if bundle else 2)
                    if not bundle: L((120, 150, 220), [rig.bpt(k, BOARD_CONN['J_COL']), rig.gpt(k, GB['J_COL'])], 2)
                else:
                    for fc in r['ffcs']: L((120, 150, 220) if fc['ok'] else (255, 90, 80), fc['pts'], 3 if bundle else 2)
            if show.get('led', True) and rig.wire:
                for lm in r['looms']:
                    col = (200, 120, 90) if lm['row'] else (110, 170, 220)
                    if not lm['ok']: col = (255, 70, 70)
                    if bundle: L(col, lm['pts'], 2)
                    else:
                        for i in range(0, 16, 4): L(col, [(p[0] + i * 0.6, p[1] + i * 0.6, p[2]) for p in lm['pts'][:-1]] + [lm['pts'][-1]], 1)
                    if k % lod == 0:                                                  # comb: anchor -> each wire end on the rail
                        ax_, ay_, az_ = lm['anc']
                        for i in range(0, 16, 1 if lod == 1 else 3):
                            j = lm['half'] * 16 + i
                            end = (rig.rx, (j - 15.5) * rig.py, az_) if lm['row'] else ((j - 15.5) * rig.px, -rig.ry, az_)
                            L(col if lm['comb_ok'] else (255, 70, 70), [lm['anc'], end], 1)
        if show.get('stack', True):
            for st in rig.stack: L((90, 220, 120) if st['ok'] else (255, 90, 80), st['pts'], 2)
        if show.get('power', True):                                                   # USB-C harness: one trunk per stack -> PSU
            ex = rig.bx + BOARD_W / 2 + 15; zs = {}
            for k, (ty, zk) in enumerate(rig.units):
                a = rig.bpt(k, BOARD_CONN['J_USB']); L((210, 210, 220), [a, (ex, a[1], zk)], 1); zs.setdefault(a[1], []).append(zk)
            for yy, z_ in zs.items(): L((210, 210, 220), [(ex, yy, max(z_)), (ex, yy, rig.floor), (rig.psu[0] - 45, rig.psu[1], rig.floor)], 3 if bundle else 1)
            q = [Pm(rig.psu[0] + dx * 45, rig.psu[1] + dy * 30, rig.floor) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            if all(q): pygame.draw.polygon(surf, (70, 70, 85), q); pygame.draw.lines(surf, (150, 150, 170), True, q, 1)
            c_ = Pm(*rig.psu, rig.floor); c_ and text(surf, 'БП 5 В', c_, (210, 210, 220), 9, center=True)

    def draw_ruler(s, surf, Pm, rig, hw):
        """mm ruler: a floor grid (10 mm minor / 50 mm / 100 mm labelled) under the cube (and the electronics when shown) and
        dimension lines for the grid, frame, layer stack and — with electronics on — boards, breakouts and cable lengths."""
        from .rulers import dim_line
        x0, x1 = -rig.hx - 40, (rig.psu[0] + 60 if hw else rig.hx + 40); y0, y1 = -rig.hy - 40, rig.hy + 40
        if hw: y0 = min(y0, rig.units[0][0] - 110 - 40 * (rig.ntw > 1)); y1 = max(y1, rig.units[-1][0] + 110)
        zf = rig.floor; st = 10 if (x1 - x0) < 500 else 50
        g0 = math.floor(x0 / st) * st
        v = g0
        while v <= x1:
            maj = abs(v % 100) < 1e-6
            a, b = Pm(v, y0, zf), Pm(v, y1, zf)
            if a and b: pygame.draw.line(surf, (70, 80, 100) if maj else (34, 38, 48), a, b, 1)
            if maj and a: text(surf, '%d' % v, (a[0] - 8, a[1] + 2), (150, 160, 180), 9)
            v += st
        v = math.floor(y0 / st) * st
        while v <= y1:
            maj = abs(v % 100) < 1e-6
            a, b = Pm(x0, v, zf), Pm(x1, v, zf)
            if a and b: pygame.draw.line(surf, (70, 80, 100) if maj else (34, 38, 48), a, b, 1)
            if maj and b: text(surf, '%d' % v, (b[0] + 3, b[1] - 5), (150, 160, 180), 9)
            v += st
        q = Pm(x0, y0, zf); q and text(surf, 'мм, сетка %d мм' % st, (q[0] - 10, q[1] + 12), (255, 220, 140), 10)
        Y = (255, 210, 120); zb, zt = rig.zl[0], rig.zl[-1]
        def D(a, b, lab, col=Y):
            a, b = Pm(*a), Pm(*b)
            if a and b: dim_line(surf, a, b, lab, col)
        D((-rig.lx, -rig.hy - 18, zb), (rig.lx, -rig.hy - 18, zb), 'LED %.0f мм (31 × %.2f)' % (31 * s.px, s.px))
        D((-rig.hx - 18, -rig.ly, zb), (-rig.hx - 18, rig.ly, zb), 'LED %.0f мм (31 × %.2f)' % (31 * s.py, s.py))
        D((-rig.hx, -rig.hy - 34, zb), (rig.hx, -rig.hy - 34, zb), ('рамка %.0f мм' if rig.wire else 'панель %.1f мм') % (2 * rig.hx), (200, 190, 150))
        D((-rig.hx - 10, -rig.hy - 10, zb), (-rig.hx - 10, -rig.hy - 10, zt), 'H %.0f мм (%d × %.2f)' % (zt - zb, rig.n - 1, s.pz))
        if hw:
            # tower dimensions on the FLOOR in front of the tower (one row, no stacking on the boards themselves)
            ty0 = min(u[0] for u in rig.units); yf = ty0 - (GB_H if rig.wire else BOARD_H) / 2 - 22
            D((rig.bx - BOARD_W / 2, yf, zf), (rig.bx + BOARD_W / 2, yf, zf), 'v15 %.2f × %.1f' % (BOARD_W, BOARD_H), (150, 220, 170))
            if rig.wire: D((rig.ax - GB_W / 2, yf - 16, zf), (rig.ax + GB_W / 2, yf - 16, zf), 'breakout %.0f × %.0f' % (GB_W, GB_H), (220, 190, 120))
            zs = [u[1] for u in rig.units]
            if max(zs) - min(zs) > 1:
                xo = rig.bx + BOARD_W / 2 + 25
                D((xo, yf, min(zs)), (xo, yf, max(zs)), 'стек %.0f мм' % (max(zs) - min(zs)), (150, 220, 170))
            # top-layer cable lengths: labelled where the loom meets the cube (away from the tower)
            r = rig.cables[-1]
            sel = ([r['looms'][0], r['looms'][2]] if rig.wire else r['ffcs'][:1])
            for c_ in sel:
                q = Pm(*c_['anc']) if 'anc' in c_ else Pm(*c_['pts'][-1])
                if q: text(surf, '%s %.0f → %d мм' % ('строки' if c_.get('row') else 'столбцы' if 'row' in c_ else 'FFC', c_['need'], c_['std']), (q[0] - 60, q[1] - 18), (255, 240, 160) if c_['ok'] else (255, 110, 100), 10)

    def draw_handles(s, surf, Pm, rig):
        """drag handles: grab the dot at the end of an axis and pull to stretch that pitch (mm)"""
        zb = rig.zl[0]; O = (-rig.lx, -rig.ly, zb)
        ends = {'x': (rig.lx, -rig.ly, zb), 'y': (-rig.lx, rig.ly, zb), 'z': (-rig.lx, -rig.ly, rig.zl[-1])}
        o = Pm(*O); s.handles = {}
        cols = {'x': (255, 110, 110), 'y': (120, 230, 130), 'z': (120, 160, 255)}
        for ax_, e in ends.items():
            q = Pm(*e)
            if not (o and q): continue
            fixed = ax_ in 'xy' and not rig.wire
            pygame.draw.line(surf, cols[ax_], o, q, 1)
            pygame.draw.circle(surf, (90, 90, 100) if fixed else cols[ax_], (int(q[0]), int(q[1])), 7 if s.hdrag == ax_ else 6, 0 if not fixed else 1)
            text(surf, '%s %.2f мм%s' % (ax_.upper(), getattr(s, 'p' + ax_), ' (PCB)' if fixed else ''), (q[0] + 9, q[1] - 7), cols[ax_], 11)
            if not fixed: s.handles[ax_] = (o, q)


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
        if n != s.N: s.N = n; s._grid(); s.kind == 'full_cube' and s.reset_pitch(z_only=True)
        y += 14
        kb = (W - 8) // 3
        for i, k in enumerate(('wire', 'lattice', 'full_cube')):
            if ui.button(surf, (x + i * (kb + 4), y, kb, 20), cube_rig.KINDS[k][1], on=s.kind == k, sz=10):
                if k != s.kind: s.kind = k; s.reset_pitch(); s.amb_key = s.ana_key = None
        y += 24
        # pitch per axis: numeric field (Enter) + −/+ ; drag handles in the view when «Тянуть» is on
        fw = 70
        for i, ax in enumerate('xyz'):
            xx = x + i * ((W - 8) // 3 + 4); cw = (W - 8) // 3
            fixed = ax != 'z' and s.kind != 'wire'
            text(surf, ax.upper(), (xx, y + 4), (255, 110, 110) if ax == 'x' else (120, 230, 130) if ax == 'y' else (120, 160, 255), 12)
            key = ('pitch', ax); cur = '%.2f' % getattr(s, 'p' + ax)
            txt = s.ptxt.get(ax, cur) if ui.focus == key else cur
            txt, ent = ui.field(surf, (xx + 12, y, cw - 52, 22), key, txt); s.ptxt[ax] = txt
            if ent:
                try: s.set_pitch(ax, float(txt.replace(',', '.')))
                except ValueError: pass
                ui.focus = None
            st = 0.5 if ax != 'z' or s.pz < 20 else 2.0
            if ui.button(surf, (xx + cw - 38, y, 18, 22), '−', sz=12) and not fixed: s.set_pitch(ax, getattr(s, 'p' + ax) - st)
            if ui.button(surf, (xx + cw - 18, y, 18, 22), '+', sz=12) and not fixed: s.set_pitch(ax, getattr(s, 'p' + ax) + st)
        y += 25
        tb3 = (W - 8) // 3
        if ui.button(surf, (x, y, tb3, 20), 'Тянуть шаг мышью', on=s.stretch, sz=10): s.stretch = not s.stretch
        if ui.button(surf, (x + tb3 + 4, y, tb3, 20), 'Линейка (мм)', on=s.show_ruler, sz=10): s.show_ruler = not s.show_ruler
        if ui.button(surf, (x + 2 * (tb3 + 4), y, tb3, 20), 'Шаг по умолчанию', sz=10): s.reset_pitch()
        y += 24
        qb = (W - 12) // 4
        for i, (k, lab) in enumerate((('front', 'Спереди'), ('top', 'Сверху'), ('iso', 'Изо'), ('reset', 'Сброс'))):
            if ui.button(surf, (x + i * (qb + 4), y, qb, 20), lab, sz=10):
                s.cam.reset() if k == 'reset' else s.cam.preset(k)
                if getattr(s, 'show_hw', False): s.fit_hw()
        y += 38
        sv = s.app.views['system'].w
        sv.brightness = int(ui.slider(surf, (x, y, bw, 8), T('brightness'), sv.brightness, 0, 255))
        sv.gamma = round(ui.slider(surf, (x + bw + 4, y, bw, 8), T('gamma'), sv.gamma, 1.0, 3.0, '%.2f'), 2); y += 14
        show = s.app.views['system'].show; tb = (W - 20) // 5; hw = getattr(s, 'show_hw', False)
        if ui.button(surf, (x, y, W - 16, 20), 'Электроника и кабели (реальный масштаб): ' + ('вкл' if hw else 'выкл'), on=hw, sz=10):
            s.show_hw = not hw; s.fit_hw() if s.show_hw else s.cam.reset()
        y += 24
        if hw:
            for i, (k, lab) in enumerate((('ffc', 'FFC'), ('stack', 'Стек'), ('power', 'Питание'), ('led', 'Гирлянды'), ('bundle', 'Жгуты'))):
                if ui.button(surf, (x + i * (tb + 4), y, tb, 20), lab, on=show.get(k, True), sz=9): show[k] = not show.get(k, True)
            y += 24
        if hw or s.stretch:
            for ln, ok in s.rig().summary():
                text(surf, ln, (x, y), (150, 200, 160) if ok else (255, 120, 100), 10); y += 13
            y += 3
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
