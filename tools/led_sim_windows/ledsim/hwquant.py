"""Output stage shared by every effect, identical to firmware demo.c: gamma-aware spatio-temporal dithering to the
8-bit level (the scan engine then applies G[level] = round((level/255)^g*255) and 8-plane BCM at 960 Hz)."""
import numpy as np
DITH_N = 1024
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.int32)
_tab = {}

def tables(g):
    """port of demo.c dither_build(): per intensity index -> (low level, high level, fraction 0..255)"""
    t = _tab.get(g)
    if t is not None: return t
    G = np.minimum(255, (np.power(np.arange(256, dtype=np.float32) / 255.0, np.float32(g)) * 255.0 + 0.5).astype(np.int32))
    lo_ = np.zeros(DITH_N, np.uint8); hi_ = np.zeros(DITH_N, np.uint8); fr_ = np.zeros(DITH_N, np.uint8); lo = 0
    for k in range(DITH_N):
        D = np.float32(k / (DITH_N - 1)) ** np.float32(g) * 255.0
        while lo < 255 and G[lo + 1] <= D: lo += 1
        L = lo
        while L > 0 and G[L - 1] == G[L]: L -= 1
        hi = lo
        while hi < 255 and G[hi] == G[lo]: hi += 1
        fr = (D - G[lo]) / (G[hi] - G[lo]) if G[hi] > G[lo] else 0
        lo_[k] = 0 if G[lo] == 0 else L; hi_[k] = hi; fr_[k] = int(fr * 255 + 0.5)
    _tab[g] = t = (lo_, hi_, fr_); return t

def quantize(vol, frame, gamma=2.2):
    """vol [..., 32 rows, 32 cols] in 0..1 -> uint8 levels, dithered exactly like the firmware"""
    lo, hi, fr = tables(round(float(gamma), 3))
    k = np.clip((vol * (DITH_N - 1) + 0.5).astype(np.int32), 0, DITH_N - 1)
    H, W = vol.shape[-2:]
    thr = (np.tile(BAYER4, (H // 4 + 1, W // 4 + 1))[:H, :W] + (frame & 3) * 4 + ((frame >> 2) & 1) * 2) & 15
    out = np.where(fr[k] > thr * 16 + 8, hi[k], lo[k])
    return np.where(k > 0, out, 0).astype(np.uint8)
