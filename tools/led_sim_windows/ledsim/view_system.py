"""System view: layout canvas + live stack state + controls."""
import json, math, os
import numpy as np
import pygame
from . import host, stack_model
from .ui import T, text, font
from .world import World, PANELS, BOARD_W, BOARD_H, rotv, panel_data
from .stack_model import LEAD, FOLLOW, STATE_NAMES
from .camera import Nav2D
from .physics import Ropes
from .world import FFC_LENGTHS, JST_LENGTHS

SIDES = 'NESW'
LED_RGB = np.array([255, 246, 228], np.float32)
ROLE_COL = {LEAD: (255, 196, 60), FOLLOW: (90, 210, 120), stack_model.WAIT: (120, 170, 255), stack_model.ELECT: (200, 120, 255),
            stack_model.DISCOVER: (255, 120, 80), stack_model.OFF: (110, 110, 110)}

def layout_dir():
    d = os.path.join(os.path.expanduser('~'), 'Documents', 'LED_Simulator')
    os.makedirs(d, exist_ok=True); return d

from .rulers import Rulers, dim_line

class SystemView(Nav2D, Rulers):
    def __init__(s, app):
        s.app = app; s.w = World(); s.w.preset(3, 2)
        s.zoom = 1.2; s.pan = [260, 200]; s.sel = None; s.drag = None; s.wire = None; s.kind = 'full'
        s.snap = 10.0; s.demo_i = 0; s.fps = 60; s.speed = 1.0; s.acc = 0.0; s.msg = ''; s.msg_t = 0
        s.masks = {}; s.ropes = Ropes(); s.rope_idx = {}; s.scroll = 0; s.show_topo = True; s.load_ms = 0.0
        s.show = {'ffc': True, 'stack': True, 'power': True, 'led': True, 'bundle': True}; s.bundle_sel = None; s.xray = False; s.checks = []; s.check_t = 0

    # ------------------------------------------------ coords
    def focus_at(s, wx, wy):
        o = s.board_at(wx, wy) or s.panel_at(wx, wy)
        if not o: return False
        v = s.app.view; size = getattr(o, 'size', 170) * 1.6
        s._zt = min(v.w, v.h) / size; s._anchor = None
        s.zoom = s._zt; s._zt = None; s.pan = [v.centerx - o.x * s.zoom, v.centery - o.y * s.zoom]; return True
    def fit(s, rect):
        bs = s.w.boards + s.w.panels
        if not bs: return
        xs = [o.x for o in bs]; ys = [o.y for o in bs]
        x0, x1, y0, y1 = min(xs) - 120, max(xs) + 120, min(ys) - 120, max(ys) + 120
        s.zoom = min(rect.w / (x1 - x0), rect.h / (y1 - y0)); s.pan = [rect.x + rect.w / 2 - (x0 + x1) / 2 * s.zoom, rect.y + rect.h / 2 - (y0 + y1) / 2 * s.zoom]
    def note(s, m): s.msg = m; s.msg_t = pygame.time.get_ticks()

    # ------------------------------------------------ demo list
    def demo_items(s):
        it = [(T('cycle'), 'c', -1)]
        it += [('%s: %s' % (T('canvas'), n), 'c', i) for i, n in enumerate(host.CANVAS)]
        it += [('%s: %s' % (T('panel'), n), 'p', i + 1) for i, n in enumerate(host.DEMOS)]
        return it
    def apply_demo(s):
        lab, kind, v = s.demo_items()[s.demo_i]
        targets = [s.w.comps().get(s.sel.id, [s.sel])] if hasattr(s.sel, 'node') else s.w.groups()
        for g in targets:
            for b in g:
                b.pdemo = v if kind == 'p' else 0
                b.node.demo = v if kind == 'c' else b.node.demo     # stack_set_demo on the leader; followers get it via T_TIME
                if kind == 'c' and b.node.state == LEAD: b.node.demo = v
        if not hasattr(s.sel, 'node'): s.global_demo = (kind, v)

    # ------------------------------------------------ hit tests
    def board_at(s, wx, wy):
        for b in reversed(s.w.boards):
            hw, hh = (BOARD_W / 2, BOARD_H / 2) if b.rot % 2 == 0 else (BOARD_H / 2, BOARD_W / 2)
            if abs(wx - b.x) < hw and abs(wy - b.y) < hh: return b
    def panel_at(s, wx, wy):
        for p in reversed(s.w.panels):
            if abs(wx - p.x) < p.size / 2 and abs(wy - p.y) < p.size / 2: return p
    def port_at(s, wx, wy):
        r = max(6, 10 / s.zoom)
        for b in s.w.boards:
            for side in range(4):
                px, py = b.port_pos(side)
                if math.hypot(wx - px, wy - py) < r: return b, side
    def ffc_handle(s, p): return p.conn_pos('J_ROW')
    def cable_at(s, wx, wy):
        r = max(5, 8 / s.zoom)
        for c in s.w.cables:
            ax, ay = c.a.port_pos(c.as_); bx, by = c.b.port_pos(c.bs)
            i = s.rope_idx.get(('c', id(c)))
            mx, my = s.ropes.pts(i)[len(s.ropes.pts(i)) // 2] if i is not None else ((ax + bx) / 2, (ay + by) / 2)
            if not c.plugged and i is not None: bx, by = s.ropes.pts(i)[-1]
            if math.hypot(wx - mx, wy - my) < r * 1.6: return c
            dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy or 1
            t = max(0, min(1, ((wx - ax) * dx + (wy - ay) * dy) / L2))
            if math.hypot(ax + t * dx - wx, ay + t * dy - wy) < r * 0.6: return c

    # ------------------------------------------------ events
    def event(s, e, view):
        if s.ruler_event(e, view): return
        if s.nav_event(e, view): return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos) and not s.app.ui.consumed:
            wx, wy = s.s2w(*e.pos)
            pt = s.port_at(wx, wy)
            if pt: s.wire = ('port', pt); return
            for p in reversed(s.w.panels):
                hx, hy = s.ffc_handle(p)
                if math.hypot(wx - hx, wy - hy) < max(6, 9 / s.zoom): s.wire = ('ffc', p); s.sel = p; return
            for p in s.w.panels:
                i = s.rope_idx.get(('F', id(p)))
                if i is not None and s.show['ffc'] and any(math.hypot(wx - x, wy - y) < max(12, 14 / s.zoom) for x, y in s.ropes.pts(i)):
                    s.bundle_sel = p; s.sel = p; return
            c = s.cable_at(wx, wy)
            if c:
                c.plugged = not c.plugged; s.w.dirty(); s.sel = c
                s.note(T('plug') if c.plugged else T('unplug')); return
            o = s.board_at(wx, wy) if s.xray else None
            o = o or s.panel_at(wx, wy) or s.board_at(wx, wy)
            s.sel = o
            if o is not None and hasattr(o, 'node') and o.mount is not None and o.mount in s.w.panels and not s.xray: o = o.mount
            dro = o.mount if (o is not None and hasattr(o, 'node') and o.mount in s.w.panels) else o
            if dro is not o: o = dro
            if o: s.drag = (o, wx - o.x, wy - o.y, [p for p in s.w.panels if p.board is o and abs(p.x - o.x) < 1 and abs(p.y - o.y) < 1] if hasattr(o, 'node') else [])
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if s.wire:
                wx, wy = s.s2w(*e.pos)
                if s.wire[0] == 'port':
                    pt = s.port_at(wx, wy)
                    if pt and pt[0] is not s.wire[1][0]:
                        s.w.connect(s.wire[1][0], s.wire[1][1], pt[0], pt[1])
                else:
                    b = s.board_at(wx, wy)
                    if b:
                        for p in s.w.panels:
                            if p.board is b: p.board = None
                        s.wire[1].board = b
                s.wire = None
            if s.drag: s.w.dirty()
            s.drag = None
        elif e.type == pygame.MOUSEMOTION and s.drag:
            o, ox, oy, carry = s.drag; wx, wy = s.s2w(*e.pos)
            t = s.place(o, wx - ox, wy - oy)
            if t: o.tx, o.ty = t
        elif e.type == pygame.KEYDOWN and s.app.ui.focus is None:
            if e.key == pygame.K_SPACE: s.w.paused = not s.w.paused
            elif e.key == pygame.K_r and s.sel is not None and hasattr(s.sel, 'rot'):
                s.sel.rot = (s.sel.rot + 1) & 3
                if hasattr(s.sel, 'kind') and s.sel.board is not None and s.sel.board.mount is s.sel: s.sel.board.rot = s.sel.rot
                if hasattr(s.sel, 'node') and s.sel.mount is not None: s.sel.mount.rot = s.sel.rot
                if hasattr(s.sel, 'node'):
                    for p in s.w.panels:
                        if p.board is s.sel and abs(p.x - s.sel.x) < 1 and abs(p.y - s.sel.y) < 1: p.rot = s.sel.rot
                s.w.dirty()
            elif e.key == pygame.K_DELETE: s.delete_sel()
    # ------------------------------------------------ placement physics: grid snap, magnetic edges, no overlap
    def extent(s, o):
        if hasattr(o, 'node'): return (BOARD_W / 2, BOARD_H / 2) if o.rot % 2 == 0 else (BOARD_H / 2, BOARD_W / 2)
        return (o.size / 2, o.size / 2)
    def overlaps(s, o, x, y):
        hx, hy = s.extent(o)
        for q in (s.w.boards if hasattr(o, 'node') else s.w.panels):
            if q is o or (hasattr(q, 'node') and q.mount is not None): continue
            qx, qy = s.extent(q); X, Y = getattr(q, 'tx', q.x), getattr(q, 'ty', q.y)
            if abs(x - X) < hx + qx - 0.5 and abs(y - Y) < hy + qy - 0.5: return q
    def place(s, o, x, y):
        isb = hasattr(o, 'node')
        P = 160.0 if isb else o.size
        if isb:
            pp = [p for p in s.w.panels if p.board is o]
            if pp: P = pp[0].size
        best, bd = None, 30.0                                       # magnetic: one pitch from a neighbour
        for q in (s.w.boards if isb else s.w.panels):
            if q is o: continue
            for dx, dy in ((P, 0), (-P, 0), (0, P), (0, -P)):
                cx, cy = q.x + dx, q.y + dy; d = math.hypot(x - cx, y - cy)
                if d < bd: bd, best = d, (cx, cy)
        if best: x, y = best
        else: x, y = round(x / s.snap) * s.snap, round(y / s.snap) * s.snap
        q = s.overlaps(o, x, y)
        if q:                                                       # slide out along the shallower axis
            hx, hy = s.extent(o); qx, qy = s.extent(q)
            px_ = hx + qx - abs(x - q.x); py_ = hy + qy - abs(y - q.y)
            if px_ < py_: x += px_ * (1 if x >= q.x else -1)
            else: y += py_ * (1 if y >= q.y else -1)
            if s.overlaps(o, x, y): return None
        return x, y
    def move_smooth(s, dt):
        k = 1 - math.exp(-dt * 18)
        for o in s.w.boards + s.w.panels:
            if not hasattr(o, 'tx'): continue
            ox, oy = o.x, o.y
            o.x += (o.tx - o.x) * k; o.y += (o.ty - o.y) * k
            if abs(o.tx - o.x) + abs(o.ty - o.y) < 0.05: o.x, o.y = o.tx, o.ty; del o.tx; del o.ty
            if hasattr(o, 'kind') and o.board is not None and o.board.mount is o:
                o.board.x, o.board.y = o.x, o.y; s.w.dirty()                 # board rides behind its panel
            if hasattr(o, 'node'):
                for p in s.w.panels:
                    if p.board is o and abs(p.x - ox) < 1 and abs(p.y - oy) < 1 and not hasattr(p, 'tx'): p.x, p.y = o.x, o.y
                s.w.dirty()

    # ------------------------------------------------ cables as ropes
    def rope_specs(s):
        sp = {}
        for c in s.w.cables:
            sp[('c', id(c))] = (c.a.port_pos(c.as_), c.b.port_pos(c.bs) if c.plugged else None, c.length)
        for p in s.w.panels:
            if p.board is not None and p.board.mount is not p and p.board in s.w.boards and s.ffc_merged(p):
                a = s.mid(p.board.conn_pos('J_ROW'), p.board.conn_pos('J_COL')); b = s.mid(p.conn_pos('J_ROW'), p.conn_pos('J_COL'))
                sp[('F', id(p))] = (a, b, p.ffc_len); continue
            for n in ('J_ROW', 'J_COL'):
                if p.board is not None and p.board.mount is p: continue                # mounted: FFC folded flat in the 8 mm gap (drawn straight)
                if p.board is not None and p.board in s.w.boards: sp[('f', id(p), n)] = (p.board.conn_pos(n), p.conn_pos(n), p.ffc_len)
                else: sp[('f', id(p), n)] = (p.conn_pos(n), None, p.ffc_len)
        return sp
    MERGE_MM = 60.0          # both connector pairs closer than this -> the two 40P FFCs share one route (drawn as one ribbon)
    @staticmethod
    def mid(a, b): return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    def ffc_merged(s, p):
        if not s.show.get('bundle', True) or p.board is None: return False
        b = p.board; d = lambda f: math.hypot(f('J_ROW')[0] - f('J_COL')[0], f('J_ROW')[1] - f('J_COL')[1])
        return d(b.conn_pos) <= s.MERGE_MM and d(p.conn_pos) <= s.MERGE_MM
    def bundle_nets(s, p):
        """member conductors of a merged FFC: board J_ROW1/J_COL1 pin -> net (from the board .kicad_pcb export)"""
        out = []
        try:
            pc = s.app.views['boards'].pcb()
            for ref in ('J_ROW1', 'J_COL1'):
                pads = sorted(((int(q[1]) if str(q[1]).isdigit() else 0, q[9]) for q in pc.pads if pc.fps[q[0]][0] == ref), key=lambda t: t[0])
                out.append((ref, pads))
        except Exception: pass
        return out
    def physics(s, dt):
        s.move_smooth(dt)
        s.ropes.sync(s.rope_specs()); s.rope_idx = {k: i for i, k in enumerate(s.ropes.keys)}
        s.ropes.step(dt)
        ten = s.ropes.tension()
        if s.drag is None: return                                    # only a user drag can over-stretch
        for c in s.w.cables:
            i = s.rope_idx.get(('c', id(c)))
            if i is not None and c.plugged and ten[i] > 1.12:
                c.plugged = False; s.w.dirty(); s.note('Кабель %08X.%s перерастянут (%.0f > %d мм) — отключён' % (c.a.id, SIDES[c.as_], ten[i] * c.length, c.length))
        for p in s.w.panels:
            i = s.rope_idx.get(('f', id(p), 'J_ROW')); j = s.rope_idx.get(('f', id(p), 'J_COL'))
            if i is None: i = j = s.rope_idx.get(('F', id(p)))
            if p.board is not None and i is not None and max(ten[i], ten[j]) > 1.12:
                s.note('FFC перерастянут (%.0f > %d мм) — панель отключена' % (max(ten[i], ten[j]) * p.ffc_len, p.ffc_len)); p.board = None
    def tcol(s, t, base):
        if t > 1.0: return (255, 60, 60)
        if t > 0.92: return (255, 200, 60)
        return base
    def draw_ropes(s, surf):
        ten = s.ropes.tension()
        ov = None
        # stacking cables between the same two boards -> one harness (trunk = mean path), fanning out near the ports
        groups = {}
        for c in s.w.cables:
            if ('c', id(c)) in s.rope_idx and c.plugged and s.show.get('bundle', True): groups.setdefault(frozenset((c.a.id, c.b.id)), []).append(c)
        bundled = set()
        for g in groups.values():
            if len(g) < 2 or not s.show['stack']: continue
            Ps = [s.ropes.pts(s.rope_idx[('c', id(c))]) for c in g]; n = min(len(P) for P in Ps)
            if any(c.a.id != g[0].a.id for c in g): Ps = [P if c.a.id == g[0].a.id else P[::-1] for P, c in zip(Ps, g)]
            tr = [(sum(P[j][0] for P in Ps) / len(Ps), sum(P[j][1] for P in Ps) / len(Ps)) for j in range(n)]
            j0, j1 = max(1, n // 6), n - 1 - max(1, n // 6)
            trunk = [s.w2s(*q) for q in tr[j0:j1 + 1]]
            w = max(3, int((1.6 + 0.9 * len(g)) * s.zoom))
            pygame.draw.lines(surf, (20, 20, 20), False, trunk, w + 2); pygame.draw.lines(surf, (70, 190, 110), False, trunk, w)
            for P, c in zip(Ps, g):
                bundled.add(('c', id(c))); col = (255, 80, 80) if c.type == 'A' else (90, 220, 120)
                pygame.draw.lines(surf, col, False, [s.w2s(*q) for q in P[:j0 + 1]] , max(2, int(1.4 * s.zoom)))
                pygame.draw.lines(surf, col, False, [s.w2s(*q) for q in P[j1:]], max(2, int(1.4 * s.zoom)))
            m = trunk[len(trunk) // 2]
            if s.zoom > 0.5: text(surf, 'жгут: %d кабеля' % len(g), (m[0] + 6, m[1] - 6), (170, 220, 180), 10)
        for k, i in s.rope_idx.items():
            P = s.ropes.pts(i); pts = [s.w2s(x, y) for x, y in P]
            if (k[0] == 'c' and not s.show['stack']) or (k[0] in 'fF' and not s.show['ffc']): continue
            if k[0] == 'c' and k in bundled: continue
            if k[0] == 'c':
                c = next((c for c in s.w.cables if id(c) == k[1]), None)
                if c is None: continue
                base = ((255, 80, 80) if c.type == 'A' else (90, 220, 120)) if c.plugged else (120, 120, 120)
                col = s.tcol(ten[i], base) if c.plugged else base
                w = max(2, int(1.6 * s.zoom)) if c is not s.sel else max(3, int(2.4 * s.zoom))
                pygame.draw.lines(surf, (20, 20, 20), False, pts, w + 2); pygame.draw.lines(surf, col, False, pts, w)
                m = pts[len(pts) // 2]; pygame.draw.circle(surf, col, (int(m[0]), int(m[1])), 5 if c is s.sel else 4, 0 if c.plugged else 1)
                if s.zoom > 0.6: text(surf, '%d мм' % c.length, (m[0] + 6, m[1] - 6), (170, 175, 185), 10)
            else:
                p = next((p for p in s.w.panels if id(p) == k[1]), None)
                if p is None: continue
                if ov is None: ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                twist = math.pi if p.ffc == 'A' else 0.0
                half = 10.5 * s.zoom                                   # 40P x 0.5 mm ribbon ~ 21 mm wide
                if k[0] == 'F':                                        # two 40P ribbons laid side by side = one 42 mm band
                    half = 21.5 * s.zoom
                    for nm in ('J_ROW', 'J_COL'):                      # fan-outs: band end -> each real connector
                        pygame.draw.line(ov, (120, 150, 200, 170), pts[0], s.w2s(*p.board.conn_pos(nm)), max(2, int(8 * s.zoom)))
                        pygame.draw.line(ov, (120, 150, 200, 170), pts[-1], s.w2s(*p.conn_pos(nm)), max(2, int(8 * s.zoom)))
                    if p is s.sel or getattr(s, 'bundle_sel', None) is p:
                        pygame.draw.lines(surf, (255, 230, 120), False, pts, max(2, int(2 * s.zoom)))
                n = len(P); col = s.tcol(ten[i], (120, 150, 200)) if p.board else (110, 110, 120)
                L, R = [], []
                for j in range(n):
                    a = P[max(j - 1, 0)]; b = P[min(j + 1, n - 1)]
                    dx, dy = b[0] - a[0], b[1] - a[1]; ln = math.hypot(dx, dy) or 1
                    nx, ny = -dy / ln, dx / ln
                    f = math.cos(twist * j / (n - 1)); w = half * max(0.12, abs(f))
                    x, y = pts[j]; L.append((x + nx * w * (1 if f >= 0 else -1), y + ny * w * (1 if f >= 0 else -1))); R.append((x - nx * w * (1 if f >= 0 else -1), y - ny * w * (1 if f >= 0 else -1)))
                for j in range(n - 1):
                    q = [L[j], L[j + 1], R[j + 1], R[j]]
                    shade = 0.65 + 0.35 * abs(math.cos(twist * (j + 0.5) / (n - 1)))
                    pygame.draw.polygon(ov, tuple(int(c * shade) for c in col) + (150,), q)
                pygame.draw.lines(ov, (230, 70, 70, 220), False, L, max(1, int(s.zoom * 0.8)))    # pin-1 stripe
                if k[0] == 'F' and s.zoom > 0.6: text(surf, 'FFC J_ROW+J_COL (2×40P) %s %d мм' % (p.ffc, p.ffc_len), (pts[n // 2][0] + 8, pts[n // 2][1]), (170, 190, 230), 10)
                if k[0] == 'f' and s.zoom > 1.5 and k[2] == 'J_ROW': text(surf, 'FFC %s %d мм' % (p.ffc, p.ffc_len), (pts[n // 2][0] + 8, pts[n // 2][1]), (170, 190, 230), 10)
        if s.show['ffc']:
            for p in s.w.panels:
                b = p.board
                if b is None or b.mount is not p: continue
                if ov is None: ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                need = s.w.ffc_need(p); col = (120, 150, 200, 120 if s.xray else 40) if need <= p.ffc_len else (255, 70, 70, 160)
                for n in ('J_ROW', 'J_COL'):
                    a = s.w2s(*b.conn_pos(n)); c = s.w2s(*p.conn_pos(n)); dx, dy = c[0] - a[0], c[1] - a[1]; ln = math.hypot(dx, dy) or 1
                    nx, ny = -dy / ln * 10.5 * s.zoom, dx / ln * 10.5 * s.zoom
                    pygame.draw.polygon(ov, col, [(a[0] + nx, a[1] + ny), (c[0] + nx, c[1] + ny), (c[0] - nx, c[1] - ny), (a[0] - nx, a[1] - ny)])
                    if s.zoom > 1.5 and n == 'J_ROW': text(surf, 'FFC %s %d мм (нужно %.0f)' % (p.ffc, p.ffc_len, need), ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2 - 18), (170, 190, 230), 10)
        if ov: surf.blit(ov, (0, 0))

    def delete_sel(s):
        o = s.sel
        if o is None: return
        if hasattr(o, 'node'): s.w.remove_board(o)
        elif hasattr(o, 'kind'): s.w.remove_panel(o)
        else: s.w.remove_cable(o)
        s.sel = None

    # ------------------------------------------------ time
    def tick(s, dt):
        s.physics(dt)
        if s.w.paused: return
        s.acc += dt * 1000 * s.speed
        n = int(s.acc); s.acc -= n
        n = min(n, 250)          # keep sim time locked to wall clock down to ~4 fps (was 100 -> boards visibly slowed/stalled below 10 fps)
        import time; t0 = time.perf_counter()
        if n: s.w.step(n)
        s.load_ms = 0.9 * s.load_ms + 0.1 * (time.perf_counter() - t0) * 1000
        s.w.update_panels()

    # ------------------------------------------------ drawing
    def dot_mask(s, k):
        if k not in s.masks:
            m = pygame.Surface((k, k)); m.fill((0, 0, 0))
            if k >= 4:
                for rr in range(k):
                    for cc in range(k):
                        d = math.hypot(rr + 0.5 - k / 2, cc + 0.5 - k / 2) / (k * 0.42)
                        v = max(0.0, min(1.0, 1.25 - d)) ** 0.8; m.set_at((cc, rr), (int(255 * v),) * 3)
            else: m.fill((255, 255, 255))
            s.masks[k] = pygame.transform.scale(m, (k, k))
            big = pygame.Surface((32 * k, 32 * k))
            for rr in range(32):
                for cc in range(32): big.blit(s.masks[k], (cc * k, rr * k))
            s.masks[k] = big
        return s.masks[k]

    def draw_panel(s, surf, p):
        pd = panel_data(p.kind); size = p.size * s.zoom
        x, y = s.w2s(p.x - p.size / 2, p.y - p.size / 2)
        r = pygame.Rect(x, y, size, size)
        if not r.colliderect(surf.get_rect()): return
        pygame.draw.rect(surf, (18, 20, 18) if p.kind != 'lattice' else (12, 14, 12), r)
        if p.kind == 'lattice' and size > 60:
            for i in range(33):
                pygame.draw.line(surf, (34, 40, 30), (x + i * size / 32, y), (x + i * size / 32, y + size))
                pygame.draw.line(surf, (34, 40, 30), (x, y + i * size / 32), (x + size, y + i * size / 32))
        img = p.duty.reshape(32, 32)
        img = np.rot90(img, -p.rot)
        rgb = (np.clip(img, 0, 1)[..., None] ** (1 / 2.2) * LED_RGB).astype(np.uint8)   # duty -> display (sRGB)
        small = pygame.surfarray.make_surface(np.ascontiguousarray(rgb.transpose(1, 0, 2)))
        lo, hi = pd['lo'], pd['hi']; pitch = (hi[0] - lo[0]) / 31
        ax, ay = s.w2s(p.x - p.size / 2 + lo[0] - pitch / 2, p.y - p.size / 2 + lo[1] - pitch / 2)
        aw = 32 * pitch * s.zoom
        k = int(pitch * s.zoom)
        if k >= 3:
            big = pygame.transform.scale(small, (32 * k, 32 * k))
            big.blit(s.dot_mask(min(k, 40)) if k <= 40 else pygame.transform.scale(s.dot_mask(40), (32 * k, 32 * k)), (0, 0), special_flags=pygame.BLEND_MULT)
            big = pygame.transform.scale(big, (int(aw), int(aw))) if abs(32 * k - aw) > 1 else big
            surf.blit(big, (ax, ay), special_flags=pygame.BLEND_ADD)
            gs = pygame.transform.smoothscale(small, (16, 16)); gs.fill((95, 95, 95), special_flags=pygame.BLEND_MULT)
            glow = pygame.transform.smoothscale(gs, (int(aw * 1.06), int(aw * 1.06)))
            surf.blit(glow, (ax - aw * 0.03, ay - aw * 0.03), special_flags=pygame.BLEND_ADD)
        else:
            surf.blit(pygame.transform.smoothscale(small, (max(1, int(aw)), max(1, int(aw)))), (ax, ay))
        sel = p is s.sel
        pygame.draw.rect(surf, (255, 255, 255) if sel else (60, 66, 60), r, 2 if sel else 1)
        if size > 50:
            hx, hy = s.w2s(*s.ffc_handle(p))
            col = (255, 80, 80) if p.ffc == 'A' else (90, 200, 255) if p.board else (140, 140, 140)
            pygame.draw.rect(surf, col, (hx - 5, hy - 5, 10, 10))
            if p.open_col >= 0 or p.ffc == 'A':
                text(surf, ('FFC A ' if p.ffc == 'A' else '') + ('col %d open' % (p.open_col + 1) if p.open_col >= 0 else ''), (r.x + 4, r.bottom - 16), (255, 100, 100), 11)

    def draw_board(s, surf, b):
        n = b.node; hw, hh = (BOARD_W, BOARD_H) if b.rot % 2 == 0 else (BOARD_H, BOARD_W)
        x, y = s.w2s(b.x - hw / 2, b.y - hh / 2); r = pygame.Rect(x, y, hw * s.zoom, hh * s.zoom)
        if not r.colliderect(surf.get_rect()): return
        col = ROLE_COL.get(n.state if b.powered else stack_model.OFF)
        k = (r.size, b.powered)
        if len(s.masks) > 300: s.masks.clear()
        behind = b.mount is not None and b.mount in s.w.panels
        k = (r.size, b.powered, behind, s.xray)
        if k not in s.masks:
            a = (150 if s.xray else 22) if behind else 70
            ov = pygame.Surface(r.size, pygame.SRCALPHA); ov.fill((20, 70, 40, a) if b.powered else (70, 20, 20, a)); s.masks[k] = ov
        surf.blit(s.masks[k], r.topleft)
        if behind and s.xray and s.zoom > 0.6:
            for nm, cc in (('J_ROW', (120, 150, 220)), ('J_COL', (120, 150, 220)), ('J_USB', (210, 210, 220)), ('J_BAT', (220, 90, 90))):
                q = s.w2s(*b.conn_pos(nm)); pygame.draw.rect(surf, cc, (q[0] - 4, q[1] - 4, 8, 8), 1)
                if s.zoom > 1.4: text(surf, nm + '1', (q[0] + 5, q[1] - 5), cc, 9)
        pygame.draw.rect(surf, (255, 255, 255) if b is s.sel else col, r, 2 if b is s.sel else 1)
        if behind and not s.xray and b is not s.sel:
            for side in range(4):
                px, py = s.w2s(*b.port_pos(side)); pygame.draw.circle(surf, (150, 150, 160), (int(px), int(py)), 3)
            return
        for side in range(4):
            px, py = s.w2s(*b.port_pos(side)); s.w.comps(); c = s.w._cmap.get((b.id, side))
            pc = (90, 220, 120) if c and c.plugged and c.type == 'B' else (255, 80, 80) if c else (150, 150, 160)
            if n.pres_out[side]: pc = (255, 255, 120)
            pygame.draw.circle(surf, pc, (int(px), int(py)), max(3, int(4 * min(2, s.zoom))))
            if s.zoom > 1.0: text(surf, SIDES[side], (px + 4, py - 14), (170, 170, 180), 10)
        if r.w > 70:
            inf = s.w.board_info(b)
            text(surf, inf['id'], (r.x + 4, r.y + 3), col, 12 if r.w > 140 else 10, mono=True)
            if r.w > 110:
                text(surf, '%s  %s' % (inf['state'], inf['pos']), (r.x + 4, r.y + 18), (220, 220, 220), 11)
                if r.w > 150: text(surf, '%d fps  skew %.1f µs  Δf %d' % (inf['fps'], inf['skew'], inf['dframe']), (r.x + 4, r.y + 32), (180, 190, 200), 10)

    def draw_dims(surf_s, surf):
        s = surf_s
        if s.zoom < 0.35: return
        for p in s.w.panels:
            h = p.size / 2; a = s.w2s(p.x - h, p.y + h); b = s.w2s(p.x + h, p.y + h)
            pd = panel_data(p.kind); pitch = (pd['hi'][0] - pd['lo'][0]) / 31
            if s.zoom > 0.6: dim_line(surf, a, b, '%g×%g мм · шаг LED %.2f мм' % (p.size, p.size, pitch), (150, 200, 150), (0, -10))
        if s.xray or s.zoom > 1.6:
            for b in s.w.boards:
                hw, hh = (BOARD_W / 2, BOARD_H / 2) if b.rot % 2 == 0 else (BOARD_H / 2, BOARD_W / 2)
                dim_line(surf, s.w2s(b.x - hw, b.y - hh), s.w2s(b.x + hw, b.y - hh), '%g×%g мм' % (BOARD_W, BOARD_H), (140, 200, 160), (0, 10))
        objs = s.w.panels or s.w.boards
        if objs:
            ex = [(o.x - (o.size / 2 if hasattr(o, 'kind') else BOARD_W / 2), o.y - (o.size / 2 if hasattr(o, 'kind') else BOARD_H / 2),
                   o.x + (o.size / 2 if hasattr(o, 'kind') else BOARD_W / 2), o.y + (o.size / 2 if hasattr(o, 'kind') else BOARD_H / 2)) for o in objs]
            x0, y0, x1, y1 = min(e[0] for e in ex), min(e[1] for e in ex), max(e[2] for e in ex), max(e[3] for e in ex)
            dim_line(surf, s.w2s(x0, y1), s.w2s(x1, y1), 'сборка %.0f × %.0f мм' % (x1 - x0, y1 - y0), (255, 210, 120), (0, 22))
            dim_line(surf, s.w2s(x1, y0), s.w2s(x1, y1), '%.0f мм' % (y1 - y0), (255, 210, 120), (22, 0))
    def draw_power(s, surf):
        lab = getattr(s.w, 'lab', None); p = lab.p if lab else {'usb_on': True, 'src': 'battery'}
        for b in s.w.boards:
            if p.get('usb_on'):
                ux, uy = b.conn_pos('J_USB'); out = -1 if not b.mirror else 1
                d = [0, 1, 0, -1][b.world_dir(3)], [-1, 0, 1, 0][b.world_dir(3)]           # USB-C sits on the W edge
                a = s.w2s(ux, uy); e = s.w2s(ux + d[0] * 25, uy + d[1] * 25)
                pygame.draw.line(surf, (30, 30, 30), a, e, max(3, int(3.5 * s.zoom))); pygame.draw.line(surf, (200, 200, 210), a, e, max(1, int(2.2 * s.zoom)))
                if s.zoom > 1.0: text(surf, 'USB-C', (e[0] + 3, e[1] - 6), (200, 200, 210), 10)
            if p.get('src') in ('battery', 'bench'):
                bx, by = b.conn_pos('J_BAT'); a = s.w2s(bx, by)
                d = [0, 1, 0, -1][b.world_dir(3)], [-1, 0, 1, 0][b.world_dir(3)]
                cpos = (bx + d[0] * 12 + (0 if d[0] else 0), by + d[1] * 12 + 22)
                e = s.w2s(*cpos)
                pygame.draw.line(surf, (200, 60, 60), a, e, max(1, int(1.2 * s.zoom))); pygame.draw.line(surf, (40, 40, 40), (a[0] + 2, a[1]), (e[0] + 2, e[1]), max(1, int(1.2 * s.zoom)))
                w_, h_ = 18 * s.zoom, 30 * s.zoom
                pygame.draw.rect(surf, (60, 70, 90) if p.get('src') == 'battery' else (90, 70, 40), (e[0] - w_ / 2, e[1], w_, h_), border_radius=3)
                if s.zoom > 1.0: text(surf, 'JST PH' if p.get('src') == 'battery' else 'БП', (e[0] - w_ / 2, e[1] + h_ + 2), (180, 180, 190), 9)
    def draw(s, surf, view):
        s.nav_update(s.app.dt, view)
        surf.set_clip(view); surf.fill((14, 15, 19), view)
        g = 160 * s.zoom
        if g > 20:
            x0, y0 = s.w2s(0, 0); x = x0 % g + view.x; 
            while x < view.right: pygame.draw.line(surf, (24, 26, 32), (x, view.y), (x, view.bottom)); x += g
            y = y0 % g + view.y
            while y < view.bottom: pygame.draw.line(surf, (24, 26, 32), (view.x, y), (view.right, y)); y += g
        for p in s.w.panels: s.draw_panel(surf, p)
        for b in s.w.boards: s.draw_board(surf, b)
        s.draw_ropes(surf)
        if s.show['power']: s.draw_power(surf)
        now = pygame.time.get_ticks()
        if now - s.check_t > 300: s.checks = s.w.checks(); s.check_t = now
        for lvl, msg, (cx, cy) in s.checks:
            q = s.w2s(cx, cy); pygame.draw.line(surf, (255, 60, 60), (q[0] - 7, q[1] - 7), (q[0] + 7, q[1] + 7), 3); pygame.draw.line(surf, (255, 60, 60), (q[0] - 7, q[1] + 7), (q[0] + 7, q[1] - 7), 3)
        if s.checks: text(surf, '⚠ %d физически невозможных соединений — см. панель справа' % len(s.checks), (view.x + 10, view.y + 30), (255, 90, 90), 13)
        if s.w.mirror_mount: text(surf, 'Платы обращены к панели обратной стороной: вид спереди зеркален (E↔W) — прошивка не знает об этом, холст зеркалится', (view.x + 10, view.y + 48), (255, 200, 80), 12)
        if s.show_topo:                              # discovered topology (leader's edges)
            bm = {b.id: b for b in s.w.boards}
            for b in s.w.boards:
                if b.node.state != LEAD: continue
                for (a, as_, bid, bs) in b.node.edges:
                    if a in bm and bid in bm:
                        pa, pb = s.w2s(*bm[a].port_pos(as_)), s.w2s(*bm[bid].port_pos(bs))
                        pygame.draw.line(surf, (255, 200, 60), pa, pb, 1)
        if s.wire:
            st = s.w2s(*(s.wire[1][0].port_pos(s.wire[1][1]) if s.wire[0] == 'port' else s.ffc_handle(s.wire[1])))
            pygame.draw.line(surf, (255, 255, 255), st, pygame.mouse.get_pos(), 2)
        s.draw_dims(surf)
        s.draw_rulers(surf, view)
        text(surf, T('hint_sys'), (view.x + 8, view.bottom - 20), (140, 146, 160), 11)
        if s.w.paused: text(surf, T('pause').upper(), (view.x + 10, view.y + 8), (255, 200, 60), 18)
        if s.msg and pygame.time.get_ticks() - s.msg_t < 2500: text(surf, s.msg, (view.centerx, view.y + 20), (255, 230, 150), 16, center=True)
        surf.set_clip(None)

    # ------------------------------------------------ side panel
    def panel(s, surf, ui, r):
        x, y, W = r.x + 10, r.y + 8, r.w - 20
        bw = (W - 8) // 3
        if ui.button(surf, (x, y, bw, 26), T('add_board')):
            cx, cy = s.s2w(s.app.view.centerx, s.app.view.centery); b = s.w.add_board(round(cx / 10) * 10, round(cy / 10) * 10); s.sel = b
        if ui.button(surf, (x + bw + 4, y, bw, 26), T('add_panel')):
            cx, cy = s.s2w(s.app.view.centerx, s.app.view.centery); s.sel = s.w.add_panel(s.kind, round(cx / 10) * 10, round(cy / 10) * 10)
        if ui.button(surf, (x + 2 * bw + 8, y, bw, 26), s.kind):
            ks = list(PANELS); s.kind = ks[(ks.index(s.kind) + 1) % len(ks)]
        y += 30
        if ui.button(surf, (x, y, bw, 26), T('autocable')): s.note('+%d' % s.w.auto_connect())
        if ui.button(surf, (x + bw + 4, y, bw, 26), T('autopanel')): s.w.auto_panels(s.kind)
        if ui.button(surf, (x + 2 * bw + 8, y, bw, 26), T('delete')): s.delete_sel()
        y += 32; text(surf, T('presets'), (x, y + 5), sz=12)
        px = x + 70
        for lab, c, rr in [('1×1', 1, 1), ('3×2', 3, 2), ('6×1', 6, 1), ('2×2', 2, 2), ('10×10', 10, 10)]:
            if ui.button(surf, (px, y, 52, 24), lab, sz=12):
                s.w.preset(c, rr, s.kind); s.sel = None; s.fit(s.app.view); s.apply_global()
            px += 56
        y += 30
        tb = (W - 16) // 5
        for i, (k, lab) in enumerate((('ffc', 'FFC'), ('stack', 'Стек'), ('power', 'Питание'))):
            if ui.button(surf, (x + i * (tb + 4), y, tb, 22), lab, on=s.show[k], sz=10): s.show[k] = not s.show[k]
        cats = ('ffc', 'stack', 'power', 'led'); allon = all(s.show[k] for k in cats)
        if ui.button(surf, (x + 3 * (tb + 4), y, tb, 22), 'Все', on=allon, sz=10):
            for k in cats: s.show[k] = not allon
        if ui.button(surf, (x + 4 * (tb + 4), y, tb, 22), 'Рентген', on=s.xray, sz=10): s.xray = not s.xray
        y += 26
        if ui.button(surf, (x, y, W, 22), 'Объединять параллельные кабели в жгуты/ленты: ' + ('да' if s.show['bundle'] else 'нет'), on=s.show['bundle'], sz=10):
            s.show['bundle'] = not s.show['bundle']; s.bundle_sel = None
        y += 26
        bp = s.bundle_sel if (s.bundle_sel in s.w.panels and ('F', id(s.bundle_sel)) in s.rope_idx) else None
        if bp is not None:
            text(surf, 'Лента FFC J_ROW+J_COL → панель (%s): проводники' % bp.kind, (x, y), (255, 230, 120), 11); y += 14
            for ref, pads in s.bundle_nets(bp):
                nets = [n for _, n in pads if n]; uniq = []
                [uniq.append(n) for n in nets if n not in uniq]
                line = '%s (%d конт.): %s' % (ref, len(pads), ', '.join(uniq))
                for k0 in range(0, min(len(line), 3 * 70), 70): text(surf, line[k0:k0 + 70], (x, y), (200, 200, 170), 9); y += 11
            y += 4
        if ui.button(surf, (x, y, W, 22), 'Плата к панели: ' + ('обратной стороной (зеркально)' if s.w.mirror_mount else 'компонентами (F.Cu)'), on=s.w.mirror_mount, sz=10):
            s.w.mirror_mount = not s.w.mirror_mount; n = max(1, len(s.w.boards)); c = int(round(n ** 0.5))
            cols = sorted({round(b.x) for b in s.w.boards}); rows = sorted({round(b.y) for b in s.w.boards})
            s.w.preset(max(1, len(cols)), max(1, len(rows)), s.kind); s.fit(s.app.view); s.apply_global()
        y += 26
        y = s.ruler_buttons(surf, ui, x, y, W)
        for lvl, msg, _ in s.checks[:3]: text(surf, msg[:64], (x, y), (255, 110, 110), 10); y += 13
        hb = (W - 4) // 2
        if ui.button(surf, (x, y, hb, 26), T('save')): s.save()
        if ui.button(surf, (x + hb + 4, y, hb, 26), T('load')): s.load()
        y += 34
        # demo
        items = s.demo_items(); s.demo_i %= len(items)
        text(surf, '%s (%s)' % (T('demo'), T('group_sel') if hasattr(s.sel, 'node') else T('group_all')), (x, y), (170, 180, 200), 12); y += 18
        if ui.button(surf, (x, y, 28, 26), '◀'): s.demo_i = (s.demo_i - 1) % len(items); s.apply_demo()
        ui.button(surf, (x + 32, y, W - 64, 26), items[s.demo_i][0], on=True)
        if ui.button(surf, (x + W - 28, y, 28, 26), '▶'): s.demo_i = (s.demo_i + 1) % len(items); s.apply_demo()
        y += 48
        s.w.brightness = int(ui.slider(surf, (x, y, W, 10), T('brightness'), s.w.brightness, 0, 255)); y += 34
        s.w.gamma = round(ui.slider(surf, (x, y, W, 10), T('gamma'), s.w.gamma, 1.0, 3.0, '%.2f'), 2); y += 34
        f = int(ui.slider(surf, (x, y, W, 10), T('fps'), s.fps, 10, 60))
        if f != s.fps:
            s.fps = f
            for b in s.w.boards:
                if b.node.state == LEAD: b.node.fps = f; b.node.lead_sync(True)    # stack_set_fps on leaders
        y += 34
        s.speed = round(ui.slider(surf, (x, y, W, 10), T('speed'), s.speed, 0.05, 2.0, '%.2f×'), 2); y += 22
        if ui.button(surf, (x, y, hb, 24), T('run') if s.w.paused else T('pause'), on=s.w.paused): s.w.paused = not s.w.paused
        if ui.button(surf, (x + hb + 4, y, hb, 24), 'MAXB %d' % s.w.maxb): s.w.maxb = 256 if s.w.maxb == 16 else 16
        y += 28
        if ui.button(surf, (x, y, W, 24), '%s: %s' % (T('timing'), stack_model.PROFILE)):
            ks = list(stack_model.PROFILES); stack_model.set_profile(ks[(ks.index(stack_model.PROFILE) + 1) % len(ks)])
        y += 32
        # selection
        o = s.sel
        if o is not None and (o in s.w.boards or o in s.w.panels or o in s.w.cables):
            if hasattr(o, 'node'):
                inf = s.w.board_info(o)
                text(surf, '%s: %s' % (T('selected'), inf['id']), (x, y), (255, 220, 140), 13); y += 18
                for k in ('state', 'leader', 'pos', 'canvas', 'members'):
                    text(surf, '%s: %s' % (k, inf[k]), (x, y), sz=12); y += 15
                text(surf, 'fps %d  skew %.2f µs  Δкадр %d  rx %d  tx %d B' % (inf['fps'], inf['skew'], inf['dframe'], o.node.rx_ok, o.node.tx_bytes), (x, y), sz=12); y += 18
                if ui.button(surf, (x, y, hb, 24), T('power_on') if not o.powered else T('power_off'), col=(120, 50, 50) if o.powered else None): s.w.set_power(o, not o.powered)
                if ui.button(surf, (x + hb + 4, y, hb, 24), T('rotate')): o.rot = (o.rot + 1) & 3; s.w.dirty()
                y += 28
                for ln in list(o.node.log)[-5:]: text(surf, ln[:52], (x, y), (150, 160, 175), 10, mono=True); y += 13
            elif hasattr(o, 'kind'):
                text(surf, '%s: %s' % (T('selected'), PANELS[o.kind][2]), (x, y), (255, 220, 140), 12); y += 20
                if ui.button(surf, (x, y, W, 24), T('ffc_a') if o.ffc == 'A' else T('ffc_b'), col=(130, 50, 50) if o.ffc == 'A' else None): o.ffc = 'B' if o.ffc == 'A' else 'A'
                y += 28
                text(surf, '%s: %s' % (T('open_col'), o.open_col + 1 if o.open_col >= 0 else T('none')), (x, y + 4), sz=12)
                if ui.button(surf, (x + W - 90, y, 28, 22), '−'): o.open_col = max(-1, o.open_col - 1)
                if ui.button(surf, (x + W - 58, y, 28, 22), '+'): o.open_col = min(31, o.open_col + 1)
                if ui.button(surf, (x + W - 26, y, 26, 22), '×'): o.open_col = -1
                y += 28
                if ui.button(surf, (x, y, hb, 24), T('connect_near')):
                    if s.w.boards: o.board = min(s.w.boards, key=lambda b: math.hypot(b.x - o.x, b.y - o.y))
                if ui.button(surf, (x + hb + 4, y, hb, 24), T('disconnect_ffc')): o.board = None
                y += 28
                text(surf, 'FFC, мм:', (x, y + 4), sz=12)
                for i, L in enumerate(FFC_LENGTHS):
                    if ui.button(surf, (x + 70 + i * 52, y, 48, 22), str(L), on=o.ffc_len == L, sz=11): o.ffc_len = L
                y += 30
            else:
                text(surf, '%s: %s.%s — %s.%s' % (T('selected'), '%08X' % o.a.id, SIDES[o.as_], '%08X' % o.b.id, SIDES[o.bs]), (x, y), (255, 220, 140), 12); y += 20
                if ui.button(surf, (x, y, hb, 24), T('unplug') if o.plugged else T('plug')): o.plugged = not o.plugged; s.w.dirty()
                if ui.button(surf, (x + hb + 4, y, hb, 24), T('cable_a') if o.type == 'A' else T('cable_b'), col=(130, 50, 50) if o.type == 'A' else None): o.type = 'B' if o.type == 'A' else 'A'; s.w.dirty()
                y += 28
                text(surf, 'JST-SH, мм:', (x, y + 4), sz=12)
                for i, L in enumerate(JST_LENGTHS):
                    if ui.button(surf, (x + 80 + i * 46, y, 42, 22), str(L), on=o.length == L, sz=11): o.length = L
                y += 30
        # groups
        y += 4; text(surf, T('groups'), (x, y), (170, 180, 200), 13); y += 18
        gs = s.w.groups()
        for g in gs[:6]:
            ld = [b for b in g if b.node.state == LEAD]
            n0 = (ld[0] if ld else g[0]).node
            text(surf, '%s %s · %d %s · %s %dx%d · %s' % (T('leader'), '%08X' % ld[0].id if ld else '—', len(g), T('members'), T('canvas_size'), n0.W * 32, n0.H * 32,
                 (host.CANVAS[n0.demo] if 0 <= n0.demo < len(host.CANVAS) else 'cycle')), (x, y), (255, 210, 120) if ld else (200, 120, 120), 11); y += 15
        if len(gs) > 6: text(surf, '… +%d' % (len(gs) - 6), (x, y), sz=11); y += 15
        y += 6; text(surf, '%s: %d   bus %d B   step %.1f ms   t=%.1f s' % (T('boards'), len(s.w.boards), s.w.bus_bytes, s.load_ms, s.w.now / 1000), (x, y), (150, 160, 175), 11); y += 16
        rows = sorted(s.w.boards, key=lambda b: b.id)
        maxrows = max(0, (r.bottom - y - 8) // 13)
        for b in rows[:maxrows]:
            inf = s.w.board_info(b)
            text(surf, '%s %-8s %-14s %2d fps %4.1fµs' % (inf['id'], inf['state'][:8], inf['pos'][:14], inf['fps'], inf['skew']), (x, y),
                 ROLE_COL.get(b.node.state if b.powered else 0), 10, mono=True); y += 13

    def apply_global(s):
        s.sel_backup = s.sel; s.sel = None; s.apply_demo(); s.sel = s.sel_backup

    def save(s):
        p = s.app.ask_file(True) or os.path.join(layout_dir(), 'layout.json')
        json.dump(s.w.to_json(), open(p, 'w'), indent=1); s.note('%s: %s' % (T('saved'), p))
    def load(s):
        p = s.app.ask_file(False) or os.path.join(layout_dir(), 'layout.json')
        if os.path.exists(p): s.w.from_json(json.load(open(p))); s.sel = None; s.fit(s.app.view); s.note('%s: %s' % (T('loaded'), p))
