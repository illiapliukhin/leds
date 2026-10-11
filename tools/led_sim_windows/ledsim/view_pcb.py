"""PCB inspector: real .kicad_pcb geometry (pre-exported by tools/export_pcb.py), layers F/In1/In2/B,
net highlight on hover/click, net stats, FFC trace from J_ROW1/J_COL1 to the panel LEDs, search."""
import gzip, json, math, os
import pygame
from . import host
from .ui import T, text
from .camera import Nav2D

LAYER_NAMES = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
LAYER_COL = [(200, 60, 50), (200, 170, 60), (70, 170, 90), (60, 110, 220)]
BOARDS = [('board_v13', 'mono_electronics v13 (текущая)'), ('board_v12', 'mono_electronics v12'), ('board_v11b', 'mono_electronics v11b'), ('board_v10', 'mono_electronics v10')]
PANELS = [('panel_full', 'mono_panel_32x32_full'), ('panel_flat', 'mono_panel_32x32'), ('panel_lattice', 'mono_panel_32x32_lattice'),
          ('panel_20x20', 'mono_panel_20x20'), ('garland', 'garland_breakout')]
FFC = {'panel_full': 'ffc_full.json', 'panel_flat': 'ffc_mono32.json', 'panel_lattice': 'ffc_lattice.json'}

class Pcb:
    def __init__(s, key):
        d = json.load(gzip.open(host.data_path('pcb', key + '.json.gz'), 'rt', encoding='utf-8'))
        s.key, s.d = key, d
        s.fps, s.pads, s.tracks, s.vias, s.zones = d['fps'], d['pads'], d['tracks'], d['vias'], d['zones']
        xs = [p[2] for p in s.pads] + [v[0] for v in s.vias]; ys = [p[3] for p in s.pads] + [v[1] for v in s.vias]
        for seg in d['outline']:
            for q in seg: xs.append(q[0]); ys.append(q[1])
        s.bbox = (min(xs), min(ys), max(xs), max(ys))
        s.bynet = {}
        for i, p in enumerate(s.pads): s.bynet.setdefault(p[9], {'pads': [], 'tracks': [], 'vias': [], 'zones': []})['pads'].append(i)
        for i, t in enumerate(s.tracks): s.bynet.setdefault(t[2], {'pads': [], 'tracks': [], 'vias': [], 'zones': []})['tracks'].append(i)
        for i, v in enumerate(s.vias): s.bynet.setdefault(v[3], {'pads': [], 'tracks': [], 'vias': [], 'zones': []})['vias'].append(i)
        for i, z in enumerate(s.zones): s.bynet.setdefault(z[1], {'pads': [], 'tracks': [], 'vias': [], 'zones': []})['zones'].append(i)
        s.grid = {}; G = 2.0; s.G = G
        def add(x, y, item):
            s.grid.setdefault((int(x // G), int(y // G)), []).append(item)
        for i, p in enumerate(s.pads): add(p[2], p[3], ('pad', i))
        for i, v in enumerate(s.vias): add(v[0], v[1], ('via', i))
        for i, t in enumerate(s.tracks):
            P = t[3]
            for k in range(0, len(P) - 2, 2):
                x0, y0, x1, y1 = P[k:k + 4]; n = max(1, int(math.hypot(x1 - x0, y1 - y0) / G) + 1)
                for j in range(n + 1): add(x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n, ('trk', i))
        s.byref = {f[0]: i for i, f in enumerate(s.fps)}

    def net_stats(s, net):
        e = s.bynet.get(net)
        if not e: return None
        L = [0.0] * 4; widths = set()
        for i in e['tracks']:
            t = s.tracks[i]; P = t[3]; widths.add(t[1])
            L[t[0]] += sum(math.hypot(P[k + 2] - P[k], P[k + 3] - P[k + 1]) for k in range(0, len(P) - 2, 2))
        pins = ['%s.%s' % (s.fps[s.pads[i][0]][0], s.pads[i][1]) for i in e['pads']]
        return dict(pins=pins, length=L, widths=sorted(widths), vias=len(e['vias']), zones=len(e['zones']))

    def hit(s, x, y, layers):
        best, bd = None, 1e9
        cx, cy = int(x // s.G), int(y // s.G)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for it in s.grid.get((gx, gy), ()):
                    k, i = it
                    if k == 'pad':
                        p = s.pads[i]
                        if not (p[8] & layers): continue
                        d = max(abs(x - p[2]) - p[4] / 2, abs(y - p[3]) - p[5] / 2, 0) if abs(p[6] % 180) < 1 or abs(p[6] % 180 - 0) < 1 else max(abs(x - p[2]) - max(p[4], p[5]) / 2, abs(y - p[3]) - max(p[4], p[5]) / 2, 0)
                        d -= 0.05
                    elif k == 'via':
                        v = s.vias[i]; d = math.hypot(x - v[0], y - v[1]) - v[2] / 2
                    else:
                        t = s.tracks[i]
                        if not (layers >> t[0]) & 1: continue
                        P = t[3]; d = 1e9
                        for kk in range(0, len(P) - 2, 2):
                            x0, y0, x1, y1 = P[kk:kk + 4]; dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy or 1e-9
                            u = max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / L2))
                            d = min(d, math.hypot(x0 + u * dx - x, y0 + u * dy - y) - t[1] / 2)
                    if d < bd: bd, best = d, it
        return best if bd < 0.3 else None

    def item_net(s, it):
        k, i = it
        return s.pads[i][9] if k == 'pad' else s.vias[i][3] if k == 'via' else s.tracks[i][2]

from .rulers import Rulers

class PcbView(Nav2D, Rulers):
    def __init__(s, app, kind):
        s.app, s.kind = app, kind
        s.list = BOARDS if kind == 'boards' else PANELS
        s.cur = 0; s.cache = {}; s.layers = 15; s.zoom = None; s.pan = [0, 0]
        s.surf = None; s.surf_key = None; s.hover = None; s.lock = None; s.search = ''; s.trace = None; s.ffc_panel = 'panel_full'; s.ffc_type = 'B'
        s.hl_net = None; s.scroll = 0
    def pcb(s, key=None):
        key = key or s.list[s.cur][0]
        if key not in s.cache: s.cache[key] = Pcb(key)
        return s.cache[key]
    def fit(s, view):
        x0, y0, x1, y1 = s.pcb().bbox
        s.zoom = min(view.w / (x1 - x0 + 10), view.h / (y1 - y0 + 10))
        s.pan = [view.centerx - (x0 + x1) / 2 * s.zoom, view.centery - (y0 + y1) / 2 * s.zoom]
    def focus_at(s, wx, wy):
        it = s.pcb().hit(wx, wy, s.layers)
        if not it: return False
        s.zoom_at(2.5, *s.w2s(wx, wy)); return True

    def event(s, e, view):
        if s.zoom is None: s.fit(view)
        if s.ruler_event(e, view): return
        if s.nav_event(e, view): return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos) and not s.app.ui.consumed:
            it = s.pcb().hit(*s.s2w(*e.pos), s.layers)
            s.lock = s.pcb().item_net(it) if it else None
            s.trace = s.do_trace(it) if it else None
            s.scroll = 0

    def do_trace(s, it):
        """board J_ROW1/J_COL1 pin -> FFC (Type B or A) -> panel J_ROW/J_COL pin -> panel net -> LEDs"""
        if it[0] != 'pad': return None
        p = s.pcb(); pad = p.pads[it[1]]; ref = p.fps[pad[0]][0]
        if ref not in ('J_ROW1', 'J_COL1') or s.ffc_panel not in FFC: return None
        mp = json.load(open(host.data_path(FFC[s.ffc_panel])))[s.ffc_type][ref[:-1]]
        ppin = mp.get(str(pad[1]))
        if ppin is None: return dict(src='%s.%s' % (ref, pad[1]), msg='no contact')
        pp = s.pcb(s.ffc_panel)
        net = next((q[9] for q in pp.pads if pp.fps[q[0]][0] == ref[:-1] and q[1] == str(ppin)), '')
        leds = sorted({pp.fps[q[0]][0] for q in pp.pads if net and q[9] == net and (pp.fps[q[0]][1].startswith(('NCD', 'LED')) or pp.fps[q[0]][0].startswith(('D', 'LED')))})
        return dict(src='%s.%s (%s)' % (ref, pad[1], pad[9]), dst='%s %s.%d' % (pp.d['title'], ref[:-1], ppin), net=net, leds=leds)

    def render_static(s, view):
        key = (s.cur, s.list[s.cur][0], s.zoom, tuple(s.pan), s.layers, view.size)
        if key == s.surf_key: return
        s.surf_key = key; p = s.pcb()
        sf = pygame.Surface(view.size); sf.fill((10, 12, 16)); ox, oy = view.x, view.y
        def P(x, y): return (s.pan[0] + x * s.zoom - ox, s.pan[1] + y * s.zoom - oy)
        for li in (3, 2, 1, 0):
            if not (s.layers >> li) & 1: continue
            dim = tuple(c // 3 for c in LAYER_COL[li])
            for z in p.zones:
                if z[0] == li and len(z[2]) >= 6:
                    pts = [P(z[2][k], z[2][k + 1]) for k in range(0, len(z[2]), 2)]
                    pygame.draw.polygon(sf, tuple(c // 6 for c in LAYER_COL[li]), pts); pygame.draw.polygon(sf, dim, pts, 1)
            for t in p.tracks:
                if t[0] != li: continue
                w = max(1, int(t[1] * s.zoom)); Q = t[3]
                pts = [P(Q[k], Q[k + 1]) for k in range(0, len(Q), 2)]
                pygame.draw.lines(sf, LAYER_COL[li], False, pts, w)
        for v in p.vias:
            c = P(v[0], v[1]); pygame.draw.circle(sf, (170, 170, 170), c, max(1, int(v[2] / 2 * s.zoom)))
        for pd in p.pads:
            if not (pd[8] & s.layers): continue
            c = P(pd[2], pd[3]); w, h = pd[4] * s.zoom, pd[5] * s.zoom
            if int(round(pd[6])) % 180 == 90: w, h = h, w
            col = (205, 160, 70) if pd[8] == 15 else LAYER_COL[0] if pd[8] & 1 else LAYER_COL[3]
            if pd[7] in ('circle', 'oval') and abs(w - h) < 0.5: pygame.draw.circle(sf, col, c, max(1, int(w / 2)))
            else: pygame.draw.rect(sf, col, (c[0] - w / 2, c[1] - h / 2, max(1, w), max(1, h)), border_radius=int(min(w, h) / 3) if pd[7] in ('oval', 'roundrect') else 0)
        for seg in p.d['outline']:
            if len(seg) >= 2: pygame.draw.lines(sf, (230, 230, 120), False, [P(*q) for q in seg], 1)
        if s.zoom > 6:
            for f in p.fps:
                c = P(f[2], f[3]); text(sf, f[0], c, (230, 230, 230), max(9, min(14, int(s.zoom * 0.8))), center=True)
        s.surf = sf

    def draw(s, surf, view):
        if s.zoom is None: s.fit(view)
        s.nav_update(s.app.dt, view)
        s.render_static(view)
        surf.blit(s.surf, view.topleft)
        p = s.pcb()
        mx, my = pygame.mouse.get_pos()
        s.hover = p.hit(*s.s2w(mx, my), s.layers) if view.collidepoint(mx, my) else None
        net = p.item_net(s.hover) if s.hover else s.lock
        s.hl_net = net
        surf.set_clip(view)
        if net:
            e = p.bynet.get(net, {})
            for i in e.get('zones', ()):
                z = p.zones[i]
                if (s.layers >> z[0]) & 1 and len(z[2]) >= 6: pygame.draw.polygon(surf, (255, 255, 255), [s.w2s(z[2][k], z[2][k + 1]) for k in range(0, len(z[2]), 2)], 2)
            for i in e.get('tracks', ()):
                t = p.tracks[i]
                if not (s.layers >> t[0]) & 1: continue
                Q = t[3]; pygame.draw.lines(surf, (255, 255, 255), False, [s.w2s(Q[k], Q[k + 1]) for k in range(0, len(Q), 2)], max(2, int(t[1] * s.zoom)))
            for i in e.get('vias', ()):
                v = p.vias[i]; pygame.draw.circle(surf, (255, 255, 120), s.w2s(v[0], v[1]), max(3, int(v[2] / 2 * s.zoom)))
            for i in e.get('pads', ()):
                pd = p.pads[i]; c = s.w2s(pd[2], pd[3]); w, h = pd[4] * s.zoom, pd[5] * s.zoom
                if int(round(pd[6])) % 180 == 90: w, h = h, w
                pygame.draw.rect(surf, (255, 255, 255), (c[0] - w / 2 - 1, c[1] - h / 2 - 1, max(3, w + 2), max(3, h + 2)), 2)
        text(surf, p.d['title'], (view.x + 10, view.y + 8), (255, 220, 140), 16)
        text(surf, T('hint_pcb'), (view.x + 8, view.bottom - 20), (140, 146, 160), 11)
        try:
            from .rulers import dim_line
            ol = p.outline if hasattr(p, 'outline') else p.d['outline']
            xs = [q[0] for sg in ol for q in sg]; ys = [q[1] for sg in ol for q in sg]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            dim_line(surf, s.w2s(x0, y1), s.w2s(x1, y1), '%.2f мм' % (x1 - x0), (255, 210, 120), (0, 18))
            dim_line(surf, s.w2s(x1, y0), s.w2s(x1, y1), '%.2f мм' % (y1 - y0), (255, 210, 120), (18, 0))
        except Exception: pass
        s.draw_rulers(surf, view)
        surf.set_clip(None)

    def panel(s, surf, ui, r):
        x, y, W = r.x + 10, r.y + 8, r.w - 20
        y = s.ruler_buttons(surf, ui, x, y, W)
        for i, (k, lab) in enumerate(s.list):
            if ui.button(surf, (x, y, W, 24), lab, on=i == s.cur, sz=12): s.cur = i; s.zoom = None; s.lock = None; s.trace = None; s.surf_key = None
            y += 27
        y += 6; text(surf, T('layers'), (x, y), (170, 180, 200), 12); y += 18
        bw = (W - 12) // 4
        for li in range(4):
            if ui.button(surf, (x + li * (bw + 4), y, bw, 24), LAYER_NAMES[li], on=(s.layers >> li) & 1, col=LAYER_COL[li] if (s.layers >> li) & 1 else None, sz=12):
                s.layers ^= 1 << li
        y += 34
        text(surf, T('search'), (x, y), (170, 180, 200), 12); y += 18
        s.search, enter = ui.field(surf, (x, y, W, 26), 'pcbsearch', s.search)
        if enter and s.search: s.do_search(s.search.strip())
        y += 34
        if s.kind == 'boards':
            text(surf, T('trace_to') + ':', (x, y + 4), (170, 180, 200), 12)
            if ui.button(surf, (x + 110, y, W - 160, 24), s.ffc_panel.replace('panel_', ''), sz=12):
                ks = list(FFC); s.ffc_panel = ks[(ks.index(s.ffc_panel) + 1) % len(ks)]
            if ui.button(surf, (x + W - 46, y, 46, 24), 'FFC ' + s.ffc_type, col=(130, 50, 50) if s.ffc_type == 'A' else None, sz=12): s.ffc_type = 'A' if s.ffc_type == 'B' else 'B'
            y += 32
        p = s.pcb(); net = s.hl_net
        if net is not None:
            st = p.net_stats(net)
            text(surf, '%s: %s' % (T('net'), net or '(без цепи)'), (x, y), (255, 255, 255), 14); y += 20
            if st:
                text(surf, '%s: %s' % (T('length'), '  '.join('%s %.1f' % (LAYER_NAMES[i][:-3], st['length'][i]) for i in range(4) if st['length'][i] > 0) + ' мм' if sum(st['length']) else '—'), (x, y), sz=12); y += 16
                text(surf, '%s: %s мм   %s: %d   зон: %d' % (T('width'), ', '.join('%.3g' % w for w in st['widths']) or '—', T('vias'), st['vias'], st['zones']), (x, y), sz=12); y += 18
                text(surf, '%s (%d):' % (T('pads'), len(st['pins'])), (x, y), (170, 180, 200), 12); y += 16
                line = ''
                for pin in st['pins'][:120]:
                    if len(line) + len(pin) > 46: text(surf, line, (x, y), sz=11, mono=True); y += 14; line = ''
                    line += pin + ' '
                    if y > r.bottom - 120: break
                if line: text(surf, line, (x, y), sz=11, mono=True); y += 16
        if s.trace:
            y += 6; tr = s.trace
            text(surf, 'FFC: %s' % tr['src'], (x, y), (120, 220, 255), 12); y += 16
            if 'dst' in tr:
                text(surf, '→ %s' % tr['dst'], (x, y), (120, 220, 255), 12); y += 16
                text(surf, '→ %s: %s · LED: %d' % (T('net'), tr['net'], len(tr['leds'])), (x, y), (120, 220, 255), 12); y += 16
                text(surf, ' '.join(tr['leds'][:12]) + (' …' if len(tr['leds']) > 12 else ''), (x, y), (180, 220, 240), 11); y += 18
                if ui.button(surf, (x, y, W, 24), T('open_on_panel')):
                    pv = s.app.views['panels']; keys = [k for k, _ in pv.list]
                    pv.cur = keys.index(s.ffc_panel); pv.lock = tr['net']; pv.zoom = None; pv.surf_key = None; s.app.tab = 'panels'
            else: text(surf, tr.get('msg', ''), (x, y), (255, 120, 120), 12)

    def do_search(s, q):
        p = s.pcb(); ql = q.lower()
        if q in p.bynet: s.lock = q
        else:
            ref = next((r for r in p.byref if r.lower() == ql), None) or next((r for r in p.byref if r.lower().startswith(ql)), None)
            if ref:
                f = p.fps[p.byref[ref]]; v = s.app.view
                s.zoom = max(s.zoom or 1, 12); s.pan = [v.centerx - f[2] * s.zoom, v.centery - f[3] * s.zoom]
                pads = [pd for pd in p.pads if pd[0] == p.byref[ref] and pd[9]]
                s.lock = pads[0][9] if pads else None
            else:
                s.lock = next((n for n in p.bynet if ql in n.lower()), None)
