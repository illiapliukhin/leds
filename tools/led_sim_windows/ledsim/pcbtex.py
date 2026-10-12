"""Pre-rendered PCB textures from the KiCad export (outline, solder mask, copper, pads, footprint bodies, silkscreen,
holes), cached per (board, side, px/mm) with a second cache per on-screen size/rotation (LOD)."""
import gzip, json, math
import pygame
from . import host

MASK = (22, 92, 48)            # KiCad default (no stackup colour set in the .kicad_pcb) = green solder mask
COPPER_UNDER_MASK = (36, 122, 62)
PAD = (205, 175, 90)           # ENIG / HASL finish (gold-ish)
SILK = (235, 235, 230)
from collections import OrderedDict
_data, _tex, _scaled = {}, OrderedDict(), OrderedDict()
_TEX_MB, _SCALED_MB = 48, 32                     # byte budgets (LRU): bounded RAM whatever the zoom history

def _nbytes(sf): return sf.get_width() * sf.get_height() * 4

def _put(cache, k, sf, budget_mb):
    cache[k] = sf; cache.move_to_end(k)
    while len(cache) > 1 and sum(_nbytes(v) for v in cache.values()) > budget_mb * 2**20: cache.popitem(last=False)
    return sf

def data(key):
    if key not in _data: _data[key] = json.load(gzip.open(host.data_path('pcb', key + '.json.gz'), 'rt', encoding='utf-8'))
    return _data[key]

def bbox(d):
    xs = [q[0] for seg in d['outline'] for q in seg]; ys = [q[1] for seg in d['outline'] for q in seg]
    return min(xs), min(ys), max(xs), max(ys)

def body_col(ref, val):
    v = (val or '').upper(); r = ref.rstrip('0123456789_')
    if 'ESP32' in v or 'WROOM' in v: return (190, 192, 196)          # metal RF can
    if r.startswith(('J', 'P', 'CN')): return (225, 215, 190)         # connector housings (beige/white)
    if r.startswith(('U', 'Q', 'IC')): return (28, 28, 30)            # IC / FET packages
    if r.startswith('C'): return (176, 140, 92)                       # MLCC
    if r.startswith('R'): return (30, 30, 32)                         # thick-film resistor (black top)
    if r.startswith(('D', 'LED')): return (240, 236, 210) if 'NCD' in v or r.startswith('LED') else (40, 40, 44)
    if r.startswith(('L', 'F')): return (60, 60, 64)
    if r.startswith(('SW', 'BT')): return (150, 150, 155)
    return (80, 80, 86)

def render(key, ppmm=8.0, side='F'):
    k = (key, ppmm, side)
    if k in _tex: _tex.move_to_end(k); return _tex[k]
    d = data(key); x0, y0, x1, y1 = bbox(d); W, H = int((x1 - x0) * ppmm) + 2, int((y1 - y0) * ppmm) + 2
    sf = pygame.Surface((W, H), pygame.SRCALPHA); sf.fill((0, 0, 0, 0))
    P = lambda x, y: ((x - x0) * ppmm, (y - y0) * ppmm)
    segs = d['outline']
    if len(segs) <= 8: pygame.draw.rect(sf, MASK + (255,), (0, 0, W, H))
    else:                                                               # lattice: draw the outline cut paths filled per closed loop
        pygame.draw.rect(sf, MASK + (255,), (0, 0, W, H))
        for seg in segs:
            if len(seg) > 3: pygame.draw.polygon(sf, (0, 0, 0, 0), [P(*q) for q in seg])
    cu = 0 if side == 'F' else 3
    for t in d['tracks']:
        if t[0] != cu: continue
        q = t[3]; pts = [P(q[i], q[i + 1]) for i in range(0, len(q), 2)]
        pygame.draw.lines(sf, COPPER_UNDER_MASK, False, pts, max(1, int(t[1] * ppmm)))
    for v in d['vias']:
        pygame.draw.circle(sf, COPPER_UNDER_MASK, P(v[0], v[1]), max(1, v[2] * ppmm / 2))
    fp_box = {}
    for g in d.get('gfx', []):
        if g[0] in ((1, 2) if side == 'F' else (4, 5)):
            q = g[3]; b = fp_box.setdefault((g[1], g[0]), [1e9, 1e9, -1e9, -1e9])
            for i in range(0, len(q), 2): b[0] = min(b[0], q[i]); b[1] = min(b[1], q[i + 1]); b[2] = max(b[2], q[i]); b[3] = max(b[3], q[i + 1])
    lb = 1 if side == 'F' else 8
    for p in d['pads']:
        if not (p[8] & lb): continue
        w, h, a = p[4] * ppmm, p[5] * ppmm, math.radians(-p[6])
        if p[7] == 'circle': pygame.draw.circle(sf, PAD, P(p[2], p[3]), max(1, w / 2)); continue
        c, s_ = math.cos(a), math.sin(a); cx, cy = P(p[2], p[3])
        pygame.draw.polygon(sf, PAD, [(cx + dx * c - dy * s_, cy + dx * s_ + dy * c) for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))])
    fside = 'F' if side == 'F' else 'B'
    for i, f in enumerate(d['fps']):
        if f[5] != fside: continue
        b = fp_box.get((i, 1 if side == 'F' else 4))                     # fab layer = package body
        if b is None or b[2] - b[0] > 60: continue
        col = body_col(f[0], f[1]); (ax, ay), (bx, by) = P(b[0], b[1]), P(b[2], b[3])
        r = pygame.Rect(ax, ay, max(1, bx - ax), max(1, by - ay))
        pygame.draw.rect(sf, col, r, border_radius=max(0, int(min(r.w, r.h) * 0.08)))
        pygame.draw.rect(sf, tuple(min(255, c + 30) for c in col), r, 1)
    for g in d.get('gfx', []):
        if g[0] != (0 if side == 'F' else 3): continue
        q = g[3]; pts = [P(q[i], q[i + 1]) for i in range(0, len(q), 2)]
        if len(pts) > 1: pygame.draw.lines(sf, SILK, False, pts, max(1, int(g[2] * ppmm)))
    for h in d.get('holes', []):
        pygame.draw.circle(sf, (10, 10, 12, 255), P(h[0], h[1]), max(1, h[2] * ppmm / 2))
        if h[3]: pygame.draw.circle(sf, (200, 200, 200), P(h[0], h[1]), h[2] * ppmm / 2 + 1, 1)
    if ppmm >= 6:
        from .ui import font
        fn = font(max(7, int(ppmm * 0.9)))
        for i, f in enumerate(d['fps']):
            if f[5] != fside or not f[0] or f[0].startswith(('LED', 'D')) and len(d['fps']) > 500: continue
            t = fn.render(f[0], True, SILK); x, y = P(f[2], f[3])
            if t.get_width() < 60 * ppmm: sf.blit(t, (x - t.get_width() / 2, y - t.get_height() / 2 - ppmm * 1.2))
    return _put(_tex, k, sf, _TEX_MB)

def scaled(key, size, rot=0, mirror=False, side='F'):
    """board texture fitted to an on-screen size (w, h) after rotation; cached (LOD: 4/8/16 px/mm sources)"""
    k = (key, size, rot & 3, mirror, side)
    if k in _scaled: _scaled.move_to_end(k); return _scaled[k]
    ppmm_need = max(size) / 160.0
    src = render(key, next(q for q in (2.0, 4.0, 8.0, 99) if q >= ppmm_need * 0.9) if ppmm_need < 8 else 8.0, side)
    if mirror: src = pygame.transform.flip(src, True, False)
    if rot & 3: src = pygame.transform.rotate(src, -90 * (rot & 3))
    out = pygame.transform.scale(src, (max(1, int(size[0])), max(1, int(size[1]))))
    return _put(_scaled, k, out, _SCALED_MB)

_parts = {}
def parts(key):
    """[(cx, cy, w, h, colour)] package bodies (fab layer bbox) in mm relative to the board centre — for 3D views"""
    if key in _parts: return _parts[key]
    d = data(key); x0, y0, x1, y1 = bbox(d); mx, my = (x0 + x1) / 2, (y0 + y1) / 2; bx = {}
    for g in d.get('gfx', []):
        if g[0] != 1: continue
        q = g[3]; b = bx.setdefault(g[1], [1e9, 1e9, -1e9, -1e9])
        for i in range(0, len(q), 2): b[0] = min(b[0], q[i]); b[1] = min(b[1], q[i + 1]); b[2] = max(b[2], q[i]); b[3] = max(b[3], q[i + 1])
    out = []
    for i, b in bx.items():
        f = d['fps'][i]
        if f[5] == 'F' and b[2] - b[0] < 60: out.append(((b[0] + b[2]) / 2 - mx, (b[1] + b[3]) / 2 - my, b[2] - b[0], b[3] - b[1], body_col(f[0], f[1])))
    _parts[key] = out; return out
