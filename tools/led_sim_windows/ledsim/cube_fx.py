"""Volumetric effects for the cube. Every generator returns a float volume V[layer, row, col] in 0..1 for an
N×32×32 stack (layer 0 = bottom). Hardware model: each layer is one board + panel refreshed at the stack frame rate
(60 fps, FRAME_SYNC-locked), 8-bit BCM per LED, ≤ MAXB 128 boards per stack; every board renders its own slice from
(shared time, demo id, params), so nothing streams over RS-485."""
import math
import numpy as np
import pygame

_font = {}
def text_mask(word, w, h, stretch=False):
    """word rasterised to a w×h boolean mask (row 0 = top), bold sans fitted to the box."""
    word = word or ' '
    if not pygame.font.get_init(): pygame.font.init()
    sz = max(6, int(h * 1.35))
    if sz not in _font: _font[sz] = pygame.font.SysFont('dejavusans,arial', sz, bold=True)
    s = _font[sz].render(word, True, (255, 255, 255), (0, 0, 0))
    a = pygame.surfarray.array_red(s).T.astype(np.float32) / 255
    ys, xs = np.nonzero(a > 0.3)
    if len(xs): a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    srf = pygame.surfarray.make_surface((np.repeat(a.T[..., None], 3, 2) * 255).astype(np.uint8))
    hh, ww = a.shape; k = min(w / ww, h / hh)
    nw, nh = max(1, int(round(ww * k))), max(1, int(round(hh * k)))
    if stretch: nw, nh = w, h                                  # fill the box: every row/column carries ink (ambigram needs it)
    srf = pygame.transform.smoothscale(srf, (nw, nh))
    m = pygame.surfarray.array_red(srf).T.astype(np.float32) / 255
    out = np.zeros((h, w), np.float32); oy, ox = (h - nh) // 2, (w - nw) // 2
    out[oy:oy + nh, ox:ox + nw] = m
    return out > 0.45

def ambigram(words, n):
    """intersection of extruded silhouettes: word0 seen from the front (x, layer), word1 from the side (y, layer),
    word2 from the top (x, y). Returns the bool volume and a per-view coverage report (fraction of each word's
    pixels whose line of sight hits at least one voxel = how well it reads)."""
    A = text_mask(words[0], 32, n, True)[::-1]                    # [layer, x], top row = top layer
    B = text_mask(words[1], 32, n, True)[::-1]                    # [layer, y]; side reading camera (yaw −90°) has screen-right = +y
    C = text_mask(words[2], 32, 32, True)[::-1] if len(words) > 2 and words[2] else np.ones((32, 32), bool)   # [y, x]
    V = A[:, None, :] & B[:, :, None] & C[None, :, :]
    def cov(proj, m): return float((proj & m).sum()) / max(1, m.sum())
    rep = (cov(V.any(1), A), cov(V.any(2), B), cov(V.any(0), C) if len(words) > 2 and words[2] else 1.0)
    return V.astype(np.float32), rep

def anamorphic(img_mask, n, yaw=0.62, pitch=0.42, zpitch=1.0, seed=3):
    """voxels scattered in depth along each lit pixel's line of sight for one camera direction (same projection as
    the cube view): from that angle the projection is the image, from anywhere else it is a random cloud."""
    rng = np.random.default_rng(seed); V = np.zeros((n, 32, 32), np.float32)
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    d = np.array([sy * cp, sp, cy * cp]); right = np.array([cy, 0.0, -sy]); down = np.array([-sy * sp, cp, -cy * sp])   # (X, Y, Z)
    ys, xs = np.nonzero(img_mask)
    for (r, c) in zip(ys, xs):
        for _try in range(30):
            p = right * (c - 15.5) / 16 * 0.9 + down * (r - 15.5) / 16 * 0.9 + d * rng.uniform(-1.4, 1.4)
            xi = int(round(p[0] * 16 + 15.5)); yi = int(round(p[2] * 16 + 15.5)); zi = int(round(-p[1] * 16 / zpitch + (n - 1) / 2))
            if 0 <= xi < 32 and 0 <= yi < 32 and 0 <= zi < n: V[zi, yi, xi] = 1.0; break
    return V

class FX:
    def __init__(s): s.reset(8)
    def reset(s, n):
        s.n = n; rng = np.random.default_rng(1)
        s.life = rng.random((n, 32, 32)) < 0.18; s.life_t = 0.0
        s.parts = np.zeros((0, 7), np.float32); s.fw_t = 0.0
        s.snake = [(n // 2, 16, 16)]; s.snake_dir = (0, 0, 1); s.food = (n // 2, 8, 8); s.snake_t = 0.0
    # ---- individual effects (x,y,z normalized -1..1, z = layer axis scaled)
    def life3d(s, t, dt):
        s.life_t += dt
        if s.life_t > 0.25:
            s.life_t = 0; L = s.life.astype(np.int8); nb = np.zeros_like(L)
            for dz in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dz or dy or dx: nb += np.roll(np.roll(np.roll(L, dz, 0), dy, 1), dx, 2)
            s.life = (s.life & (nb >= 5) & (nb <= 7)) | (~s.life & (nb == 6))       # Bays' rule 5766
            if s.life.sum() < 20 or s.life.sum() > s.life.size * 0.6:
                s.life = np.random.default_rng(int(t * 10)).random(s.life.shape) < 0.18
        return s.life.astype(np.float32)
    def fireworks(s, t, dt):
        n = s.n; s.fw_t -= dt
        if s.fw_t <= 0:
            s.fw_t = 0.9 + np.random.rand() * 0.6
            c = np.array([np.random.uniform(8, 24), np.random.uniform(8, 24), np.random.uniform(n * 0.5, n - 1)])
            k = 60; v = np.random.normal(size=(k, 3)); v /= np.linalg.norm(v, axis=1)[:, None]; v *= np.random.uniform(6, 12, (k, 1))
            v[:, 2] *= n / 32 * 1.5
            P = np.c_[np.tile(c, (k, 1)), v, np.ones(k)].astype(np.float32)
            s.parts = np.r_[s.parts, P]
        P = s.parts
        if len(P):
            P[:, 0:3] += P[:, 3:6] * dt; P[:, 5] -= 9.0 * n / 32 * dt; P[:, 3:6] *= 0.985; P[:, 6] -= dt * 0.7
            s.parts = P = P[P[:, 6] > 0]
        V = np.zeros((n, 32, 32), np.float32)
        for x, y, z, *_r, life in P:
            xi, yi, zi = int(x), int(y), int(z)
            if 0 <= xi < 32 and 0 <= yi < 32 and 0 <= zi < n: V[zi, yi, xi] = max(V[zi, yi, xi], min(1, life * 1.4))
        return V
    def snake3d(s, t, dt):
        n = s.n; s.snake_t += dt
        while s.snake_t > 0.06:
            s.snake_t -= 0.06
            h = s.snake[-1]; f = s.food
            dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
            body = set(s.snake)
            def ok(p): return 0 <= p[0] < n and 0 <= p[1] < 32 and 0 <= p[2] < 32 and p not in body
            best = sorted(dirs, key=lambda d: sum(abs(h[i] + d[i] - f[i]) for i in range(3)) + (0.5 if d != s.snake_dir else 0))
            nxt = next(((h[0] + d[0], h[1] + d[1], h[2] + d[2]) for d in best if ok((h[0] + d[0], h[1] + d[1], h[2] + d[2]))), None)
            if nxt is None: s.snake = [(n // 2, 16, 16)]; continue
            s.snake_dir = (nxt[0] - h[0], nxt[1] - h[1], nxt[2] - h[2]); s.snake.append(nxt)
            if nxt == f:
                r = np.random.default_rng(len(s.snake)); s.food = (int(r.integers(n)), int(r.integers(32)), int(r.integers(32)))
            elif len(s.snake) > 6 + 0: s.snake.pop(0) if len(s.snake) > 40 or np.random.rand() < 0.9 else None
        V = np.zeros((n, 32, 32), np.float32)
        for i, (z, y, x) in enumerate(s.snake): V[z, y, x] = 0.35 + 0.65 * i / max(1, len(s.snake) - 1)
        if math.sin(t * 12) > 0: V[s.food] = 1.0
        return V
    @staticmethod
    def heart(x, y, z, t):
        k = 1 + 0.12 * max(0, math.sin(t * 6.0)) ** 8 * 3                       # heartbeat
        X, Y, Z = x / 0.75 * k, -z / 0.75 * k, y / 0.75 * k
        f = (X * X + 9 / 4 * Z * Z + Y * Y - 1) ** 3 - X * X * Y ** 3 - 9 / 80 * Z * Z * Y ** 3
        return np.clip(1 - np.abs(f) * 6, 0, 1) * 0.9 + (f < 0) * 0.02
    @staticmethod
    def ripples(x, y, z, t):
        out = np.zeros_like(x)
        for (cx, cy, ph) in ((-0.4, -0.3, 0.0), (0.45, 0.35, 1.7)):
            r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            out += 0.35 * np.sin(r * 9 - t * 4 + ph) * np.exp(-r * 1.2)
        return np.clip(1 - np.abs(z - out) * 6, 0, 1)
    @staticmethod
    def plasma(x, y, z, t):
        v = np.sin(x * 3 + t) + np.sin(y * 3.3 - t * 1.3) + np.sin(z * 3.7 + t * 0.7) + np.sin(np.sqrt(x * x + y * y + z * z) * 5 - t * 2)
        return np.clip((np.sin(v * 1.6) * 0.5 + 0.5) ** 2.2, 0, 1)
    @staticmethod
    def dna(x, y, z, t):
        a = z * 4.2 + t * 1.6; R = 0.55
        out = np.zeros_like(x)
        for ph in (0, math.pi):
            cx, cy = R * np.cos(a + ph), R * np.sin(a + ph)
            out = np.maximum(out, np.clip(1 - np.sqrt((x - cx) ** 2 + (y - cy) ** 2) * 7, 0, 1))
        # base-pair rungs every ~quarter turn
        rung = (np.abs(np.sin(z * 4.2 * 2)) < 0.25)
        px, py = np.cos(a), np.sin(a); d = np.abs(x * py - y * px)
        out = np.maximum(out, rung * (np.sqrt(x * x + y * y) < R) * np.clip(1 - d * 12, 0, 1) * 0.55)
        return out
    @staticmethod
    def text_sweep(word, x, y, z, t, n):
        m = text_mask(word, 32, 32).astype(np.float32)                    # rotating extruded word (top view source)
        a = t * 0.9; ca, sa = math.cos(a), math.sin(a)
        u = x * ca - y * sa; w = x * sa + y * ca                                # rotate about the layer axis
        col = np.clip(((u + 1) * 16).astype(int), 0, 31); lay = np.clip(((z / max(np.abs(z).max(), 1e-6) + 1) * 16).astype(int), 0, 31)
        thick = np.abs(w) < 0.18
        return m[31 - lay, col] * thick * ((np.abs(u) <= 1))


# ---------------------------------------------------------------- anatomical volume figures (walk / run / go-go)
# Bodies are smooth signed-distance fields: ellipsoids (head, chest, waist, pelvis, hands, feet) and tapered capsules
# (neck, limbs), blended with a polynomial smooth-min so joints read as one organic surface, then voxelised with a
# one-voxel anti-aliased edge (brightness = clip(0.5 − d/voxel)). Pose = forward kinematics from mocap-like keyframes
# (cyclic Catmull-Rom). Secondary motion (hair, ponytail, skirt hem) is a damped spring system integrated per frame.
# Body frame: x = right, y = up, z = forward (towards the viewer for the dancer). Units: cube half-size = 1.
VOX = 1 / 16.0

def _smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)

def _ell(P, c, r):
    """ellipsoid SDF (first-order bound, good near the surface): r = (rx, ry, rz)"""
    q = (P - c) / r; k = np.linalg.norm(q, axis=-1)
    return (k - 1) * min(r)

def _cone(P, a, b, ra, rb):
    """tapered capsule a→b with radii ra→rb"""
    ab = b - a; L2 = max(1e-9, ab @ ab); t = np.clip(((P - a) @ ab) / L2, 0, 1)
    return np.linalg.norm(P - a - t[..., None] * ab, axis=-1) - (ra + (rb - ra) * t)

def _catmull(keys, u):
    """cyclic Catmull-Rom through equally spaced keyframes, u in [0, 1)"""
    n = len(keys); f = (u % 1.0) * n; i = int(f); t = f - i
    p0, p1, p2, p3 = (np.asarray(keys[(i + k) % n], float) for k in (-1, 0, 1, 2))
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)

def _dir(flex, abd, side):
    """limb direction from flexion (forward +) and abduction (outward +) angles, rad"""
    return np.array([side * math.sin(abd) * math.cos(flex), -math.cos(flex) * math.cos(abd), math.sin(flex) * math.cos(abd)])

def _yaw(v, a):
    c, s_ = math.cos(a), math.sin(a); return np.array([v[0] * c + v[2] * s_, v[1], -v[0] * s_ + v[2] * c])

def _roll(v, a):
    c, s_ = math.cos(a), math.sin(a); return np.array([v[0] * c - v[1] * s_, v[0] * s_ + v[1] * c, v[2]])

# go-go: 8 beats (one 2-bar phrase at 128 BPM ≈ 3.75 s). Channels (degrees / units):
#  px  py  pyaw proll tyaw tside  shLa shLf elL  shRa shRf elR  hLf kL  hRf kR  hLa hRa  head
GOGO_KEYS = [
    # 1-2: twist down (knees bent, pelvis twists, chest counter-twists, bent arms pump)
    [0.00, -0.06,  35, 0,  -25,  0,   35, 50, 95,   35, 20, 95,   25, 45, 10, 35,  8, 8,   0],
    [0.00, -0.03, -35, 0,   25,  0,   35, 20, 95,   35, 50, 95,   10, 35, 25, 45,  8, 8,   0],
    # 3-4: side step right + hip sway, right arm waves over the head
    [0.10, -0.02,  10, 9,   -5, -9,   40, 10, 60,  165, 10, 25,    5, 15, 20, 35,  6, 16, -10],
    [0.14,  0.00, -10, -9,   5,  9,   30, 10, 70,  170, 20, 10,   18, 30,  5, 10,  4, 20,  10],
    # 5-6: twist again, both hands framing the face
    [0.04, -0.06,  30, 0,  -22,  0,   60, 80, 120,  60, 80, 120,  25, 45, 10, 35,  8, 8,   0],
    [-0.04,-0.03, -30, 0,   22,  0,   60, 80, 120,  60, 80, 120,  10, 35, 25, 45,  8, 8,   0],
    # 7-8: side step left, left arm waves over the head
    [-0.10,-0.02, -10, -9,   5,  9,  165, 10, 25,   40, 10, 60,   20, 35,  5, 15, 16, 6,  10],
    [-0.14, 0.00,  10, 9,   -5, -9,  170, 20, 10,   30, 10, 70,    5, 10, 18, 30, 20, 4, -10],
]

class Figure:
    def __init__(s, kind):
        s.kind = kind; s.t_prev = None
        s.hair = None; s.hem = np.zeros(16); s.hem_v = np.zeros(16); s.hem_c = np.zeros(2); s.hem_cv = np.zeros(2); s.yaw_prev = 0.0

    # ------------------------------------------------ poses
    def pose(s, t):
        d = math.radians
        if s.kind == 'gogo':
            beat = 128 / 60.0; u = (t * beat / 8.0) % 1.0
            k = _catmull(GOGO_KEYS, u)
            px, py, pyaw, proll, tyaw, tside, shLa, shLf, elL, shRa, shRf, elR, hLf, kL, hRf, kR, hLa, hRa, hd = k
            wrist = 0.5 * math.sin(2 * math.pi * beat * t)                      # wrists flick on every beat
            return dict(px=px, py=py, pz=0.0, pyaw=d(pyaw), proll=d(proll), tyaw=d(tyaw), tside=d(tside), lean=d(4),
                        arms=[(d(shLa), d(shLf), d(elL), wrist), (d(shRa), d(shRf), d(elR), -wrist)],
                        legs=[(d(hLf), d(kL), d(hLa)), (d(hRf), d(kR), d(hRa))], head=d(hd), female=True)
        run = s.kind == 'run'; hz = 1.5 if run else 1.0; ph = 2 * math.pi * hz * t
        # gait channels shaped like mocap curves (hip flexion leads, knee double-hump on walk, big knee drive on run)
        def leg(p):
            hip = (d(42) * math.sin(p) + d(8)) if run else (d(24) * math.sin(p) + d(4))
            sw = max(0.0, math.sin(p + 1.75))                                   # swing phase
            knee = (d(25) + d(95) * sw ** 1.2) if run else (d(6) + d(55) * sw ** 1.6 + d(12) * max(0.0, math.sin(2 * p - 0.6)) * (1 - sw))
            return (hip, knee, d(3))
        def arm(p):
            return (d(6), -(d(55) if run else d(22)) * math.sin(p) + (d(10) if run else d(4)), d(95) + d(10) * math.sin(p) if run else d(14) + d(10) * (1 + math.sin(p)), 0.0)
        bob = (0.05 if run else 0.022) * math.cos(2 * ph)
        return dict(px=0.0, py=bob - (0.05 if run else 0.0), pz=0.0, pyaw=d(9 if run else 6) * math.sin(ph), proll=d(3) * math.sin(ph),
                    tyaw=-d(14 if run else 8) * math.sin(ph), tside=0.0, lean=d(14 if run else 3),
                    arms=[arm(ph), arm(ph + math.pi)], legs=[leg(ph + math.pi), leg(ph)], head=0.0, female=False)

    # ------------------------------------------------ skeleton + primitives
    def build(s, t, dt):
        q = s.pose(t); S = 1.08; fem = q['female']
        P0 = np.array([q['px'], 0.05 * S + q['py'], q['pz']])
        def pel(v): return P0 + _yaw(_roll(np.asarray(v, float) * S, q['proll']), q['pyaw'])
        def tor(v):
            v = np.asarray(v, float) * S
            v = np.array([v[0], v[1] * math.cos(q['lean']) - v[2] * math.sin(q['lean']), v[1] * math.sin(q['lean']) + v[2] * math.cos(q['lean'])])
            return P0 + _yaw(_roll(_roll(v, q['tside']), q['proll']), q['pyaw'] + q['tyaw'])
        E, C = [], []                                                          # ellipsoids (c, r), cones (a, b, ra, rb)
        # torso: pelvis, waist, ribcage, bust/chest, shoulders
        E += [(pel([0, 0.0, 0]), np.array([0.165 if fem else 0.15, 0.11, 0.11]) * S),
              (tor([0, 0.16, 0]), np.array([0.105 if fem else 0.13, 0.11, 0.085]) * S),
              (tor([0, 0.32, 0]), np.array([0.15 if fem else 0.175, 0.13, 0.10]) * S)]
        if fem: E += [(tor([sx * 0.065, 0.33, 0.07]), np.array([0.06, 0.055, 0.05]) * S) for sx in (-1, 1)]
        neck = tor([0, 0.46, 0]); head_c = tor([0, 0.60, 0.01]) + np.array([0.0, 0.0, 0.0])
        head_c = head_c + _yaw(np.array([math.sin(q['head']) * 0.04, 0, 0]), q['pyaw'] + q['tyaw'])
        C += [(tor([0, 0.40, 0]), neck, 0.045 * S, 0.04 * S)]
        E += [(head_c, np.array([0.085, 0.115, 0.10]) * S),                    # skull
              (head_c + _yaw(np.array([0, -0.07, 0.035]) * S, q['pyaw'] + q['tyaw']), np.array([0.06, 0.05, 0.065]) * S)]   # jaw
        # arms
        for (abd, flex, el, wr), side in zip(q['arms'], (-1, 1)):
            sh = tor([side * 0.17, 0.41, 0]); E.append((sh, np.array([0.055, 0.05, 0.05]) * S))   # deltoid
            ua = _yaw(_roll(_dir(flex, abd, side), q['tside'] + q['proll']), q['pyaw'] + q['tyaw'])
            el_ = sh + ua * 0.28 * S
            fa = _yaw(_roll(_dir(flex + el * math.cos(abd), abd + el * math.sin(abd) * 0.3, side), q['tside'] + q['proll']), q['pyaw'] + q['tyaw'])
            wr_ = el_ + fa * 0.25 * S
            hd = _yaw(_roll(_dir(flex + el + wr, abd, side), q['tside']), q['pyaw'] + q['tyaw'])
            C += [(sh, el_, 0.048 * S, 0.036 * S), (el_, wr_, 0.036 * S, 0.026 * S)]
            E.append((wr_ + hd * 0.05 * S, np.array([0.03, 0.055, 0.03]) * S))   # hand
        # legs
        feet = []
        for (hf, kn, ha), side in zip(q['legs'], (-1, 1)):
            hp = pel([side * 0.09, -0.04, 0])
            th = _yaw(_roll(_dir(hf, ha, side), q['proll']), q['pyaw']); kn_ = hp + th * 0.43 * S
            sh_ = _yaw(_roll(_dir(hf - kn, ha * 0.6, side), q['proll']), q['pyaw']); an = kn_ + sh_ * 0.42 * S
            fwd = _yaw(np.array([0, 0, 1.0]), q['pyaw'])
            C += [(hp, kn_, (0.085 if fem else 0.08) * S, 0.052 * S), (kn_, an, 0.05 * S, 0.034 * S)]
            E.append((kn_ + fwd * 0.01, np.array([0.05, 0.05, 0.05]) * S))     # knee
            if fem: C.append((kn_ - sh_ * 0.06 * S, an, 0.056 * S, 0.044 * S))  # go-go boot shaft up to the knee
            E.append((an + fwd * 0.065 * S - np.array([0, 0.03, 0]) * S, np.array([0.045, 0.035, 0.11]) * S))   # foot / boot
            feet.append(an)
        # hair: cap + long hair that swings (spring chain); ponytail for the dancer
        hair_E = [(head_c + np.array([0, 0.025, -0.012]) * S, np.array([0.098, 0.12, 0.112]) * S)]
        if fem:
            root = head_c + _yaw(np.array([0, 0.02, -0.09]) * S, q['pyaw'] + q['tyaw'])
            s.step_hair(root, dt)
            for i in range(len(s.hair) - 1):
                C.append((s.hair[i], s.hair[i + 1], (0.07 - 0.012 * i) * S, (0.058 - 0.012 * i) * S))
        E += hair_E
        skirt = None
        if fem:
            waist = tor([0, 0.10, 0]); s.step_skirt(waist, q, dt); skirt = (waist, q)
        return E, C, skirt

    def step_hair(s, root, dt):
        n = 5; seg = 0.085
        if s.hair is None: s.hair = [root - np.array([0, i * seg, 0.0]) for i in range(n)]; s.hair_p = [h.copy() for h in s.hair]
        dt = min(max(dt, 1e-3), 0.05)
        new = [root.copy()]
        for i in range(1, n):
            p, pp = s.hair[i], s.hair_p[i]
            v = (p - pp) * 0.9                                                  # damping
            new.append(p + v + np.array([0, -4.0, 0]) * dt * dt)                # gravity
        for _ in range(4):                                                      # length constraints + head collision
            for i in range(1, n):
                d_ = new[i] - new[i - 1]; L = np.linalg.norm(d_) or 1
                new[i] = new[i - 1] + d_ * (seg / L)
                off = new[i] - (root + np.array([0, -0.02, 0.09])); r = np.linalg.norm(off)
                if r < 0.13: new[i] = new[i] + off / max(r, 1e-6) * (0.13 - r)
        s.hair_p = s.hair; s.hair = new

    def step_skirt(s, waist, q, dt):
        """hem: 16 radial springs. Twist angular velocity flares the hem (centripetal), hip acceleration makes the
        hem centre lag (inertia), each pleat has its own damped spring -> secondary motion / wave around the hem"""
        dt = min(max(dt, 1e-3), 0.05); yaw = q['pyaw']
        w = (yaw - s.yaw_prev) / dt; s.yaw_prev = yaw
        ang = np.linspace(0, 2 * math.pi, 16, endpoint=False)
        target = 0.05 * min(w * w, 30.0) / 30.0 * 2.2 + 0.025 * np.sin(ang * 2 + yaw * 3)
        acc = 70.0 * (target - s.hem) - 7.0 * s.hem_v
        acc += 6.0 * (np.roll(s.hem, 1) + np.roll(s.hem, -1) - 2 * s.hem)       # fabric couples neighbouring pleats
        s.hem_v += acc * dt; s.hem += s.hem_v * dt
        c = np.array([waist[0], waist[2]])
        if not hasattr(s, 'hem_cp'): s.hem_cp = c.copy(); s.hem_c = c.copy()
        a = 40.0 * (c - s.hem_c) - 6.0 * s.hem_cv
        s.hem_cv += a * dt; s.hem_c += s.hem_cv * dt

    # ------------------------------------------------ voxelise
    def volume(s, x, y, z, t, dt):
        E, C, skirt = s.build(t, dt)
        zext = float(np.abs(z).max()) if z.size else 1.0
        if s.kind == 'gogo': X, Y, Z = x, z, -y                                   # faces the front panel (−y)
        else: X, Y, Z = -y, z, x                                                 # side view: walks towards +x
        if zext < 0.6:                                                           # flat 32×32×N lattice slab: lie in the panel plane
            sq = min(1.0, max(0.35, zext / 0.3))
            X, Y, Z = (x, -y, z / sq) if s.kind == 'gogo' else (z / sq, -y, x)
        pts = [c for c, _ in E] + [a for a, *_ in C] + [b for _, b, *_ in C]
        lo = np.min(pts, 0) - 0.16; hi = np.max(pts, 0) + 0.16
        if skirt is not None: lo = np.minimum(lo, skirt[0] - [0.5, 0.5, 0.5]); hi = np.maximum(hi, skirt[0] + [0.5, 0.05, 0.5])
        sel = np.flatnonzero((X >= lo[0]) & (X <= hi[0]) & (Y >= lo[1]) & (Y <= hi[1]) & (Z >= lo[2]) & (Z <= hi[2]))
        P = np.stack([X.ravel()[sel], Y.ravel()[sel], Z.ravel()[sel]], -1).astype(np.float32)
        d = np.full(len(sel), 9.0, np.float32); k = 0.035
        for c, r in E: d = _smin(d, _ell(P, c, r), k)
        for a, b, ra, rb in C: d = _smin(d, _cone(P, a, b, ra, rb), k)
        v = np.clip(0.5 - d / VOX, 0, 1)
        if skirt is not None:
            W, q = skirt; L = 0.36
            h = np.clip((W[1] - P[:, 1]) / L, -1, 2)
            cx = W[0] + (s.hem_c[0] - W[0]) * np.clip(h, 0, 1) ** 1.5 * 1.6 + (s.hem_c[0] - W[0]) * 0
            cz = W[2] + (s.hem_c[1] - W[2]) * np.clip(h, 0, 1) ** 1.5 * 1.6
            th = np.arctan2(P[:, 2] - cz, P[:, 0] - cx)
            hem = np.interp((th - q['pyaw']) % (2 * math.pi), np.linspace(0, 2 * math.pi, 17), np.r_[s.hem, s.hem[:1]])
            R = 0.13 + (0.21 + hem) * np.clip(h, 0, 1) ** 0.85 + 0.012 * np.sin(th * 10 - q['pyaw'] * 4) * np.clip(h, 0, 1)
            rad = np.hypot(P[:, 0] - cx, P[:, 2] - cz)
            dd = np.maximum(np.abs(rad - R) - 0.022, np.maximum(-h * L, (h - 1) * L))
            v = np.maximum(v, np.clip(0.5 - dd / VOX, 0, 1) * 0.9)
        out = np.zeros(x.size, np.float32); out[sel] = v
        return out.reshape(x.shape)

def figure(kind, x, y, z, t, dt=1 / 60, _cache={}):
    f = _cache.get(kind)
    if f is None: f = _cache[kind] = Figure(kind)
    return f.volume(x, y, z, t, dt)
