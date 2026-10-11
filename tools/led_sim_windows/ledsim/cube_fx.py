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


# ---------------------------------------------------------------- skeletal volume figures (walk / run / go-go)
# A figure is a set of capsules (bone segments with radii) + spheres, voxelised as a signed distance with a
# one-voxel anti-aliased edge: brightness = clip(0.5 − d/voxel, 0, 1). Body frame: f = forward, u = up, l = lateral.
# The figure stands along the panel's 32-LED rows (up = −y), so it fits a flat 32×32×8 lattice cube as well as a full cube.
VOX = 1 / 16.0

def _seg_dist(P, a, b):
    """distance from points P (..., 3) to segment a-b"""
    ab = b - a; t = np.clip(((P - a) @ ab) / max(1e-9, ab @ ab), 0, 1)
    return np.linalg.norm(P - a - t[..., None] * ab, axis=-1)

def _rot(a): c, s = math.cos(a), math.sin(a); return np.array([s, c])      # unit vector at angle a from "down" in the f-u plane

def _limb(root, a1, a2, L1, L2):
    """2-bone limb in the f-u plane: a1 = upper angle from straight down (forward +), a2 = lower bone's extra bend"""
    d1 = np.array([math.sin(a1), -math.cos(a1)]); d2 = np.array([math.sin(a1 + a2), -math.cos(a1 + a2)])
    j = root + d1 * L1; return j, j + d2 * L2

def _gait(t, hz, run):
    """smooth keyframe-like gait (Fourier-shaped cycle). Returns joints in (f, u, l) and segment list."""
    ph = 2 * math.pi * hz * t
    sw, kn, arm, el, lean, bob = (0.75, 1.5, 0.95, 1.4, 0.22, 0.06) if run else (0.42, 0.65, 0.42, 0.35, 0.03, 0.025)
    hip_u = -0.02 + bob * math.cos(2 * ph) - (0.06 if run else 0.0)
    segs = []
    H = np.array([0.0, hip_u])
    T = H + np.array([math.sin(lean), math.cos(lean)]) * 0.52                 # neck base
    for side, s in ((1, 0.0), (-1, math.pi)):
        p = ph + s
        a1 = sw * math.sin(p)
        a2 = -kn * max(0.0, math.sin(p + (1.9 if run else 1.6))) ** (1.0 if run else 1.4) - 0.05
        k, f = _limb(H, a1, a2, 0.42, 0.42)
        toe = f + np.array([0.11, -0.02])
        l = 0.09 * side
        segs += [((H, l), (k, l), 0.07), ((k, l), (f, l), 0.06), ((f, l), (toe, l), 0.045)]
        sh = T - np.array([math.sin(lean), math.cos(lean)]) * 0.06
        b1 = -arm * math.sin(p) + lean; b2 = el + (0.25 * math.sin(p) if run else 0.15 * (1 + math.sin(p)))
        e, w = _limb(sh, b1, b2, 0.29, 0.27)
        la = 0.2 * side
        segs += [((sh, la), (e, la), 0.05), ((e, la), (w, la), 0.042)]
    segs += [((H, 0.0), (T, 0.0), 0.11), ((T - np.array([0, 0.02]), -0.17), (T - np.array([0, 0.02]), 0.17), 0.06)]
    head = T + np.array([math.sin(lean) * 0.2, 0.2])
    return segs, [(head, 0.0, 0.12)], None

def _gogo(t):
    """go-go dancer facing the viewer (f = depth): hip sway, alternating arm pumps, knee bends, flared dress"""
    bpm = 128; ph = 2 * math.pi * bpm / 60 / 2 * t                          # one sway cycle = 2 beats
    sway = 0.11 * math.sin(ph); bounce = 0.035 * abs(math.sin(ph))
    segs = []
    # here the f-u plane is the FRONT plane: "f" is the lateral screen axis, l is depth
    H = np.array([sway, -0.05 - bounce])
    tilt = -0.25 * math.sin(ph)                                               # torso leans against the hips
    T = H + np.array([math.sin(tilt), math.cos(tilt)]) * 0.5
    for side in (1, -1):
        kb = 0.25 + 0.25 * max(0.0, math.sin(ph * side))                      # the leg on the sway side straightens
        hp = H + np.array([0.08 * side, 0]); foot = np.array([0.13 * side, -0.88])
        mid = (hp + foot) / 2 + np.array([0, 0]); knee = mid + np.array([0, 0]) ; knee = mid + np.array([0.0, 0.0])
        knee = mid + np.array([0.0, 0.0]); knee[0] += 0.0
        kneeF = kb * 0.25                                                     # knee comes forward (depth)
        segs += [((hp, 0.0), (knee, kneeF), 0.06), ((knee, kneeF), (foot, 0.0), 0.05), ((foot, 0.0), (foot + np.array([0, -0.02]), 0.1), 0.04)]
        # arms: alternate "pump up" / "down by the hip" with a twist of the wrist
        a = ph * 2 + (0 if side > 0 else math.pi)
        up = 0.5 + 0.5 * math.sin(a)
        sh = T + np.array([0.17 * side, -0.05])
        e = sh + np.array([0.18 * side, -0.12 + 0.3 * up])
        w = e + np.array([(0.05 - 0.12 * up) * side, -0.18 + 0.48 * up])
        segs += [((sh, 0.0), (e, 0.05 * up), 0.045), ((e, 0.05 * up), (w, 0.0), 0.038)]
    segs += [((H, 0.0), (T, 0.0), 0.085), ((T + np.array([-0.17, -0.05]), 0.0), (T + np.array([0.17, -0.05]), 0.0), 0.05)]
    head = T + np.array([0.04 * math.sin(ph + 0.6), 0.2])
    sph = [(head, 0.0, 0.11), (head + np.array([0, 0.06]), -0.08, 0.08)]   # head + hair bun
    # dress: cone shell from the waist down, axis swings with the hips, hem flares with the sway speed
    waist = H + np.array([0, 0.17]); ax = np.array([0.35 * math.sin(ph - 0.5), -1.0]); ax /= np.linalg.norm(ax)
    flare = 0.36 + 0.08 * abs(math.cos(ph))
    return segs, sph, (waist, ax, 0.42, 0.1, flare, ph)

def figure(kind, x, y, z, t):
    """voxelised figure. kind: 'walk' | 'run' | 'gogo'"""
    zext = float(np.abs(z).max()) if z.size else 1.0
    ls = min(1.0, max(0.35, zext / 0.3))                                     # lateral/depth squeeze for a flat 8-layer cube
    if kind == 'gogo':
        segs, sph, dress = _gogo(t); spin = 0.35 * math.sin(2 * math.pi * 0.1 * t)
    else:
        segs, sph, dress = _gait(t, 1.0 if kind == 'walk' else 1.5, kind == 'run'); spin = 0.0
    # tall cube (layers span the height): stand upright along the layer axis (up = +z: the renderer maps world-up to +z);
    # flat lattice slab (32×32×N, N small): lie in the 32×32 plane (up = −y) with depth squeezed into the layers
    if zext >= 0.6: F, U, Lz = x, z, y
    else: F, U, Lz = x, -y, z / ls
    if spin: F, Lz = F * math.cos(spin) - Lz * math.sin(spin), F * math.sin(spin) + Lz * math.cos(spin)
    # narrow band: only voxels inside the figure's bounding box are evaluated (≈ 10 % of a 32³ cube)
    pts = [np.array([a[0], a[1], la]) for (a, la), _, _ in segs] + [np.array([b[0], b[1], lb]) for _, (b, lb), _ in segs] + [np.array([c[0], c[1], l]) for c, l, _ in sph]
    lo = np.min(pts, 0) - 0.2; hi = np.max(pts, 0) + 0.2
    if dress is not None: lo = np.minimum(lo, [-0.62, -0.45, -0.5]); hi = np.maximum(hi, [0.62, 0.3, 0.5])
    sel = np.flatnonzero((F >= lo[0]) & (F <= hi[0]) & (U >= lo[1]) & (U <= hi[1]) & (Lz >= lo[2]) & (Lz <= hi[2]))
    P = np.stack([F.ravel()[sel], U.ravel()[sel], Lz.ravel()[sel]], -1)
    d = np.full(len(sel), 9.0)
    for (a, la), (b, lb), r in segs:
        d = np.minimum(d, _seg_dist(P, np.array([a[0], a[1], la]), np.array([b[0], b[1], lb])) - r * 1.3)   # ×1.3: limbs ≥ 2 voxels thick
    for c, l, r in sph:
        d = np.minimum(d, np.linalg.norm(P - np.array([c[0], c[1], l]), axis=-1) - r)
    vs = np.clip(0.5 - d / VOX, 0, 1)
    if dress is not None:
        W, ax, L, r0, r1, ph = dress; A = np.array([ax[0], ax[1], 0.0])
        q = P - np.array([W[0], W[1], 0.0]); h = q @ A
        rad = np.linalg.norm(q - h[..., None] * A, axis=-1)
        ang = np.arctan2(q[..., 2], q[..., 0])
        R = r0 + (r1 - r0) * np.clip(h / L, 0, 1) * (1 + 0.18 * np.sin(3 * ang + ph * 2))   # pleats ripple
        dd = np.maximum(np.abs(rad - R) - 0.025, np.maximum(-h, h - L))
        vs = np.maximum(vs, np.clip(0.5 - dd / VOX, 0, 1) * 0.85)
    v = np.zeros(x.size, np.float32); v[sel] = vs
    return v.reshape(x.shape)
