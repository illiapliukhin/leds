/* Generative patterns, 8-bit grey (see patterns.h). Coordinates are canvas pixels (one LED = one stitch). */
#include "patterns.h"
#include <math.h>
#include <stdlib.h>

static inline float clampf(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
static inline float smooth(float e0, float e1, float x) { float t = clampf((x - e0) / (e1 - e0)); return t * t * (3 - 2 * t); }
static inline uint32_t hash2(int x, int y) { uint32_t h = (uint32_t)x * 374761393u + (uint32_t)y * 668265263u; h = (h ^ (h >> 13)) * 1274126177u; return h ^ (h >> 16); }
static inline float hashf(int x, int y) { return (hash2(x, y) & 0xFFFF) / 65535.0f; }

/* ---------------------------------------------------------------- vyshyvanka
 * Cross-stitch ornaments on a 16x16 rapport, mirrored 8-fold. Thread "colours" are brightness levels:
 * red thread = 1.0, black thread = 0.42, linen = 0.035 with a weave texture. */
#define RED 1.0f
#define BLK 0.42f
static float motif(int m, int dx, int dy, int u, int v)      /* dx,dy = 0..7 from the rapport centre */
{
    int ax = dx > dy ? dx : dy, ay = dx > dy ? dy : dx;        /* 8-fold fold */
    switch (m) {
    case 0: {   /* Alatyr: eight-pointed star of rhombus petals + centre cross */
        if (ax + ay <= 1) return RED;
        if (ay == 0 && ax <= 6) return BLK;                     /* straight arms */
        if (ax - ay <= 1 && ax + ay <= 9 && ax >= 2) return RED; /* diagonal petals */
        if (ax + ay == 7 && ay >= 1 && ax - ay >= 3) return BLK; /* petal outlines */
        if (ax == 7 && ay == 7) return RED;                     /* corner stitches join rapports */
        return 0;
    }
    case 1: {   /* nested rhombuses */
        int r = dx + dy;
        if (r == 0) return RED;
        if (r % 4 == 2) return RED;
        if (r % 4 == 0 && r <= 12) return BLK;
        return 0;
    }
    case 2: {   /* oblique crosses in a lattice */
        if (dx == dy && dx <= 5) return RED;
        if ((dx == 0 && dy == 7) || (dy == 0 && dx == 7)) return RED;
        if (abs(dx - dy) == 7 - 0) return BLK;
        if ((dx == 3 && dy == 0) || (dy == 3 && dx == 0) || (dx == 0 && dy == 0)) return BLK;
        if (dx + dy == 7 && (dx == 2 || dy == 2)) return BLK;
        return 0;
    }
    default: {  /* tree of life: trunk, paired branches, berries, roots (mirrored in x only) */
        int cx = abs(u - 7) + (u > 7 ? -1 : 0);                 /* 0..7 from the trunk, symmetric pair */
        if (cx == 0 && v >= 2 && v <= 14) return BLK;
        if (v >= 3 && v <= 12 && cx >= 1 && cx <= 5 && (v + cx) % 4 == 0 && cx <= (13 - v) / 2 + 2) return RED;
        if (cx == 0 && v == 1) return RED;                      /* crown */
        if (v == 14 && cx <= 3 && cx >= 1) return BLK;          /* roots */
        if (v == 15 && (cx == 2 || cx == 4)) return RED;
        if ((cx == 5 && v == 4) || (cx == 6 && v == 8) || (cx == 4 && v == 1)) return RED; /* berries */
        return 0;
    }
    }
}

static float vysh(int X, int Y, int W, int H, float t)
{
    const float T = 14.0f;                                       /* seconds per motif */
    int k = (int)floorf(t / T);
    float ph = t / T - k;                                        /* 0..1 inside a motif */
    int m = k % 4;
    /* zigzag borders (top + bottom 4 rows) stay, the field changes */
    int bh = H >= 64 ? 5 : 3;
    float linen = 0.035f + 0.012f * (((X + Y) & 1) ? 1 : -1) + 0.008f * hashf(X, Y);
    float pulse = 0.82f + 0.18f * sinf(t * 1.7f - (X + Y) * 0.16f);
    if (Y < bh || Y >= H - bh) {
        int yy = Y < bh ? Y : H - 1 - Y;
        int z = abs(((X + (int)(t * 2.0f)) % 8) - 4);              /* slowly running zigzag */
        float v = (yy == 0) ? BLK * 0.6f : (z == yy || z == yy - 1) ? RED : (yy == bh - 1 && (X & 1)) ? BLK : 0;
        float on = smooth(0.0f, 0.04f, t / 6.0f - (float)abs(X - W / 2) / W);   /* first reveal from the centre */
        return v > 0 ? linen + (v * pulse - linen) * on : linen;
    }
    int fy = Y - bh, fh = H - 2 * bh;
    int R = 16;
    int ox = (W % R) / 2, oy = (fh % R) / 2;
    int u = ((X - ox) % R + R) % R, v = ((fy - oy) % R + R) % R;
    int dx = u < 8 ? 7 - u : u - 8, dy = v < 8 ? 7 - v : v - 8;
    float val = motif(m, dx, dy, u, v);
    if (val <= 0) return linen;
    /* stitch-by-stitch reveal: from each rapport centre outward, jittered per stitch, then unpick in reverse */
    int tx = (X - ox) / R, ty = (fy - oy) / R;
    float order = ((dx > dy ? dx : dy) + 0.4f * (dx + dy)) / 10.0f * 0.55f + 0.12f * hashf(X, Y) + 0.05f * ((tx + ty) & 3);
    float rin = smooth(order, order + 0.05f, ph * 1.6f);
    float rout = 1.0f - smooth(order, order + 0.05f, (ph - 0.86f) * 7.0f);
    float a = rin * rout;
    /* alternate rapports swap thread colours, a glowing pulse runs through the red thread */
    if (((tx + ty) & 1) && m != 3) val = (val == RED) ? BLK : RED;
    float glow = (val == RED) ? pulse : 1.0f;
    float sparkle = (rin < 0.999f && rin > 0.02f) ? 0.35f * (1 - rin) : 0;   /* needle flash on the newest stitch */
    float out = linen + (val * glow - linen) * a + sparkle;
    return clampf(out);
}

/* ---------------------------------------------------------------- aurora / flow */
static float aurora(int X, int Y, int W, int H, float t)
{
    float s = 32.0f / H;
    float x = X * s, y = Y * s;                                  /* 32-unit-tall space */
    float v = 0;
    for (int i = 0; i < 3; i++) {
        float fi = (float)i;
        float yc = 9.0f + 7.0f * fi + 3.2f * sinf(x * (0.13f + 0.03f * fi) + t * (0.45f + 0.12f * fi) + fi * 2.1f)
                 + 1.6f * sinf(x * 0.31f - t * (0.7f - 0.1f * fi));
        float wdt = 2.2f + 1.1f * sinf(x * 0.07f + t * 0.3f + fi);
        float d = (y - yc) / wdt;
        float curtain = expf(-d * d);
        float tail = (y < yc) ? expf(-(yc - y) / (6.0f + 2.0f * fi)) * 0.35f : 0;   /* rays above the band */
        float rays = 0.65f + 0.35f * sinf(x * 1.3f + 2.0f * sinf(t * 0.5f + x * 0.2f) + fi);
        float br = 0.55f + 0.45f * sinf(t * 0.37f + fi * 1.9f + x * 0.05f);
        v += (curtain + tail) * rays * br * (0.75f - 0.15f * fi);
    }
    /* slow flow-field shimmer + faint twinkling stars in the dark */
    v += 0.06f * (0.5f + 0.5f * sinf(x * 0.21f + y * 0.17f + t * 0.9f) * sinf(y * 0.23f - t * 0.6f));
    if ((hash2(X, Y) & 63) == 0) v += 0.18f * (0.5f + 0.5f * sinf(t * 2.3f + hashf(Y, X) * 40.0f));
    return clampf(v * 0.92f);
}

/* ---------------------------------------------------------------- kinetic geometry */
static float kin_seg(int seg, float x, float y, float cx, float cy, float t)
{
    switch (seg & 3) {
    case 0: {   /* rotating moire: two ring sets on orbiting centres */
        float ax = cx + 7 * cosf(t * 0.6f), ay = cy + 5 * sinf(t * 0.8f);
        float bx = cx - 7 * cosf(t * 0.5f), by = cy - 5 * sinf(t * 0.7f);
        float r1 = sqrtf((x - ax) * (x - ax) + (y - ay) * (y - ay)), r2 = sqrtf((x - bx) * (x - bx) + (y - by) * (y - by));
        float m = sinf(r1 * 1.15f - t * 2.0f) * sinf(r2 * 1.15f + t * 1.4f);
        return 0.5f + 0.5f * m;
    }
    case 1: {   /* tunnel */
        float dx = x - cx - 3 * sinf(t * 0.7f), dy = y - cy - 2 * cosf(t * 0.5f);
        float r = sqrtf(dx * dx + dy * dy) + 0.6f, a = atan2f(dy, dx);
        float z = 22.0f / r + t * 2.2f;
        float c = sinf(z * 3.14159f) * sinf(a * 6.0f + t * 0.8f + z * 0.5f);
        float fog = smooth(0.0f, 6.0f, r);
        return clampf((0.5f + 0.5f * c) * fog + 0.15f * (1 - fog) * (0.5f + 0.5f * sinf(t * 3)));
    }
    case 2: {   /* Lissajous ribbon with a fading trail */
        float best = 1e9f, bk = 0;
        for (int k = 0; k < 22; k++) {
            float tk = t - k * 0.055f;
            float px = cx + (cx - 3) * sinf(tk * 1.3f + 0.5f), py = cy + (cy - 3) * sinf(tk * 1.7f);
            float d = (x - px) * (x - px) + (y - py) * (y - py);
            float w = d * (1.0f + k * 0.12f);
            if (w < best) { best = w; bk = k; }
        }
        float g = expf(-best * 0.35f) * (1.0f - bk / 26.0f);
        float bg = 0.05f * (0.5f + 0.5f * sinf(x * 0.5f + y * 0.5f - t));
        return clampf(g + bg);
    }
    default: {  /* ripples: three sources interfering */
        float v = 0;
        for (int i = 0; i < 3; i++) {
            float sx = cx + (cx * 0.7f) * cosf(t * 0.23f + i * 2.094f), sy = cy + (cy * 0.6f) * sinf(t * 0.31f + i * 2.094f);
            float d = sqrtf((x - sx) * (x - sx) + (y - sy) * (y - sy));
            v += sinf(d * 0.9f - t * 3.2f) / (1.0f + d * 0.06f);
        }
        return clampf(0.5f + 0.28f * v);
    }
    }
}

static float kinetic(int X, int Y, int W, int H, float t)
{
    float s = 32.0f / H;
    float x = X * s, y = Y * s, cx = W * s * 0.5f, cy = 16.0f;
    const float SEG = 18.0f, FADE = 1.6f;
    int k = (int)floorf(t / SEG);
    float ph = t - k * SEG;
    float a = kin_seg(k, x, y, cx, cy, t);
    if (ph > SEG - FADE) {
        float b = kin_seg(k + 1, x, y, cx, cy, t);
        float w = smooth(SEG - FADE, SEG, ph);
        a = a * (1 - w) + b * w;
    }
    return a;
}

float pattern_px(int pat, int X, int Y, int W, int H, float t)
{
    switch (pat) {
    case PAT_VYSH:    return vysh(X, Y, W, H, t);
    case PAT_AURORA:  return aurora(X, Y, W, H, t);
    case PAT_KINETIC: return kinetic(X, Y, W, H, t);
    default:          return 0;
    }
}
