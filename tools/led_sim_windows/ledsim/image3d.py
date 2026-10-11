"""Image → 3D: turn a PNG/JPG into voxel content for an N×32×32 cube, and export LV3D animation files.

LV3D file (little-endian), played by the firmware layer-by-layer (board for layer k reads slice k of every frame):
  offset size  field
  0      4     magic  b'LV3D'
  4      1     version = 1
  5      1     N  layers (1..128)
  6      1     W  = 32 (columns)      7  1  H = 32 (rows)
  8      1     fps (1..120)           9  1  flags: bit0 = levels are linear (firmware applies its gamma-2.2 LUT)
  10     2     frame count F          12 4  reserved = 0
  16     F·N·H·W bytes: frame-major, then layer 0 (bottom) … N−1, then row 0 (top) … 31, then column 0 … 31;
               one byte per LED = 8-bit level (0..255) exactly as the BCM frame builder expects.
Size: 16 + F·N·1024 bytes (e.g. 8 layers × 120 frames = 983 056 bytes)."""
import math, struct
import numpy as np
import pygame

MODES = ['height', 'silhouette', 'bands', 'relief', 'particles', 'ambigram2', 'pseudo']
MODE_RU = {'height': 'Рельеф по яркости (карта высот)', 'silhouette': 'Силуэт (выдавливание)', 'bands': 'Срезы по полосам яркости',
           'relief': 'Вращающийся рельеф', 'particles': 'Частицы: сборка/взрыв', 'ambigram2': 'Амбиграмма из 2 картинок',
           'pseudo': 'Псевдо-глубина (яркость + края)'}

def load_gray(path, size=32):
    img = pygame.image.load(path)
    w, h = img.get_size(); k = size / max(w, h)
    sm = pygame.transform.smoothscale(img.convert_alpha() if pygame.display.get_init() and pygame.display.get_surface() else img, (max(1, int(w * k)), max(1, int(h * k))))
    rgb = pygame.surfarray.array3d(sm).transpose(1, 0, 2).astype(np.float32) / 255
    try: a = pygame.surfarray.array_alpha(sm).T.astype(np.float32) / 255
    except Exception: a = np.ones(rgb.shape[:2], np.float32)
    g = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) * a
    out = np.zeros((size, size), np.float32); oy, ox = (size - g.shape[0]) // 2, (size - g.shape[1]) // 2
    out[oy:oy + g.shape[0], ox:ox + g.shape[1]] = g
    return out

def demo_image():
    """built-in test picture when no file is loaded: radial face-ish gradient + ring"""
    y, x = np.mgrid[0:32, 0:32]; r = np.hypot(x - 15.5, y - 15.5)
    g = np.clip(1 - r / 15, 0, 1) ** 0.7
    g[(np.hypot(x - 10, y - 11) < 3) | (np.hypot(x - 21, y - 11) < 3)] = 0.05
    g[(r > 7) & (r < 9) & (y > 17)] = 1.0
    return g.astype(np.float32)

def preprocess(g, gamma=1.0, thr=0.5, dither=False, invert=False):
    g = np.clip(g, 0, 1)
    if invert: g = 1 - g
    g = g ** gamma
    if dither:                                                     # Floyd–Steinberg at cube resolution (binary)
        e = g.copy(); out = np.zeros_like(g)
        for r in range(32):
            for c in range(32):
                o = 1.0 if e[r, c] >= thr else 0.0; err = e[r, c] - o; out[r, c] = o
                if c + 1 < 32: e[r, c + 1] += err * 7 / 16
                if r + 1 < 32:
                    if c > 0: e[r + 1, c - 1] += err * 3 / 16
                    e[r + 1, c] += err * 5 / 16
                    if c + 1 < 32: e[r + 1, c + 1] += err * 1 / 16
        return out, out > 0.5
    return g, g >= thr

def blur(a, k=1):
    out = a.copy()
    for _ in range(k):
        out = (np.roll(out, 1, 0) + np.roll(out, -1, 0) + np.roll(out, 1, 1) + np.roll(out, -1, 1) + out * 4) / 8
    return out

def pseudo_depth(g):
    """no-ML depth guess: smooth luminance (bright = near) + inside-of-shape distance + edge emphasis (Sobel)."""
    gx = np.roll(g, -1, 1) - np.roll(g, 1, 1); gy = np.roll(g, -1, 0) - np.roll(g, 1, 0)
    edge = np.clip(np.hypot(gx, gy) * 2, 0, 1)
    mask = g > 0.12; dist = mask.astype(np.float32)
    for _ in range(8): dist = np.where(mask, np.minimum(dist + 1, blur(dist, 1) + 1), 0)  # crude distance-inside
    dist = dist / max(dist.max(), 1)
    d = 0.5 * blur(g, 3) + 0.35 * dist + 0.15 * edge
    return np.clip(d / max(d.max(), 1e-6), 0, 1)

def volume(mode, g, mask, n, t, g2=None, mask2=None, fill=False):
    V = np.zeros((n, 32, 32), np.float32)
    if mode in ('height', 'pseudo', 'relief'):
        h = pseudo_depth(g) if mode == 'pseudo' else g
        top = np.round(h * (n - 1)).astype(int)
        L = np.arange(n)[:, None, None]
        V = (((L <= top[None]) if fill else (L == top[None])) & (h[None] > 0.04)).astype(np.float32) * (0.4 + 0.6 * h[None])
        if mode == 'relief':                                       # rotate the relief about the layer axis
            a = t * 0.8; ca, sa = math.cos(a), math.sin(a)
            yy, xx = np.mgrid[0:32, 0:32] - 15.5
            sx = np.clip(np.round(xx * ca - yy * sa + 15.5), 0, 31).astype(int); sy = np.clip(np.round(xx * sa + yy * ca + 15.5), 0, 31).astype(int)
            inside = (np.abs(xx * ca - yy * sa) < 16) & (np.abs(xx * sa + yy * ca) < 16)
            V = V[:, sy, sx] * inside[None]
        return V
    if mode == 'silhouette':
        return np.repeat(mask[None].astype(np.float32), n, 0)
    if mode == 'bands':
        b = np.clip((g * n).astype(int), 0, n - 1)
        for k in range(n): V[k] = ((b == k) & (g > 0.04)) * 1.0
        return V
    if mode == 'particles':
        tgt = np.argwhere(volume('height', g, mask, n, 0) > 0)              # target voxels (layer, row, col)
        if not len(tgt): return V
        rng = np.random.default_rng(7); start = rng.uniform([0, 0, 0], [n - 1, 31, 31], (len(tgt), 3))
        ph = (t % 6.0) / 6.0                                              # 0..0.4 assemble, 0.4..0.6 hold, 0.6..1 explode
        if ph < 0.4: k = 1 - (1 - ph / 0.4) ** 3; P = start * (1 - k) + tgt * k
        elif ph < 0.6: P = tgt.astype(np.float32)
        else:
            k = (ph - 0.6) / 0.4; c = np.array([(n - 1) / 2, 15.5, 15.5]); d = tgt - c + rng.normal(0, 0.5, tgt.shape)
            P = tgt + d * k * 2.5
        P = np.round(P).astype(int); ok = (P[:, 0] >= 0) & (P[:, 0] < n) & (P[:, 1] >= 0) & (P[:, 1] < 32) & (P[:, 2] >= 0) & (P[:, 2] < 32)
        V[P[ok, 0], P[ok, 1], P[ok, 2]] = 1.0
        return V
    if mode == 'ambigram2':
        A = squeeze(mask, n)[::-1]; B = squeeze(mask2 if mask2 is not None else mask.T, n)[::-1][:, ::-1]
        return (A[:, None, :] & B[:, :, None]).astype(np.float32)
    return V

def squeeze(mask, n):
    """32×32 mask → n×32 (rows resampled to the layer count)"""
    rows = np.clip((np.arange(n) + 0.5) * 32 / n, 0, 31).astype(int)
    return mask[rows]

def export_lv3d(path, frames, fps):
    frames = [np.clip(f * 255 + 0.5, 0, 255).astype(np.uint8) for f in frames]
    n = frames[0].shape[0]
    with open(path, 'wb') as f:
        f.write(b'LV3D' + struct.pack('<BBBBBBHI', 1, n, 32, 32, int(fps), 1, len(frames), 0))
        for fr in frames: f.write(fr.tobytes())
    return 16 + len(frames) * n * 1024

def read_lv3d(path):
    with open(path, 'rb') as f: b = f.read()
    assert b[:4] == b'LV3D'
    ver, n, w, h, fps, flags, F, _ = struct.unpack('<BBBBBBHI', b[4:16])
    data = np.frombuffer(b, np.uint8, offset=16).reshape(F, n, h, w)
    return dict(version=ver, n=n, fps=fps, flags=flags, frames=data)
