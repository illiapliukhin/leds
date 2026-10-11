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
from .world import FFC_LENGTHS, JST_LENGTHS, lead_lengths

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
        s.zoom = 1.2; s.pan = [260, 200]; s.sel = None; s.drag = None; s.wire = None; s.menu = None; s.kind = 'full'
        s.snap = 10.0; s.demo_i = 0; s.fps = 60; s.speed = 1.0; s.acc = 0.0; s.msg = ''; s.msg_t = 0
        s.masks = {}; s.ropes = Ropes(); s.rope_idx = {}; s.scroll = 0; s.show_topo = True; s.load_ms = 0.0
        s.show = {'ffc': True, 'stack': True, 'power': True, 'led': True, 'bundle': True, 'panels': True, 'boards': True}; s.bundle_sel = None; s.board_alpha = 0.35; s.xray = False; s.checks = []; s.check_t = 0

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
    SNAP_MM = 10.0
    def snap_port(s, wx, wy, exclude=None):
        """nearest FREE compatible stacking port within ~10 mm (or 10 px when zoomed out)"""
        best, bd = None, max(s.SNAP_MM, 10 / s.zoom)
        for b in s.w.boards:
            if b is exclude: continue
            for side in range(4):
                if s.w.cable_at(b, side): continue
                px, py = b.port_pos(side); d = math.hypot(wx - px, wy - py)
                if d < bd: best, bd = (b, side), d
        return best
    def snap_board(s, wx, wy):
        """FFC end: snaps to a board's J_ROW1/J_COL1 within ~10 mm, or anywhere over a board"""
        for b in s.w.boards:
            for nm in ('J_ROW', 'J_COL'):
                q = b.conn_pos(nm)
                if math.hypot(wx - q[0], wy - q[1]) < max(s.SNAP_MM, 10 / s.zoom): return b
        return s.board_at(wx, wy)
    def cable_menu(s, c, pos):
        s.menu = (c, pos)
    def menu_event(s, e):
        if not getattr(s, 'menu', None): return False
        c, (mx, my) = s.menu
        if e.type == pygame.MOUSEBUTTONDOWN:
            items = s.menu_items(c)
            for i, (lab, fn) in enumerate(items):
                if pygame.Rect(mx, my + i * 22, 170, 22).collidepoint(e.pos): fn(); break
            s.menu = None; return True
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE: s.menu = None; return True
        return False
    def menu_items(s, c):
        if hasattr(c, 'kind'):                                         # a panel's FFC
            p = c; out = []
            if p.board is not None: out.append(('Отключить FFC', lambda: (setattr(p, '_last_board', p.board), setattr(p, 'board', None), s.w.dirty())))
            elif getattr(p, '_last_board', None) in s.w.boards: out.append(('Подключить FFC', lambda: (setattr(p, 'board', p._last_board), s.w.dirty())))
            out.append(('Удалить FFC', lambda: (setattr(p, 'board', None), setattr(p, '_last_board', None), s.w.dirty())))
            return out
        return [('Отключить' if c.plugged else 'Подключить', lambda: (setattr(c, 'plugged', not c.plugged), s.w.dirty())),
                ('Удалить кабель', lambda: (s.w.remove_cable(c), setattr(s, 'sel', None)))]
    def ffc_at(s, wx, wy):
        r = max(4, 14 / s.zoom)
        for p in s.w.panels:
            for k in (('F', id(p)), ('f', id(p), 'J_ROW'), ('f', id(p), 'J_COL')):
                i = s.rope_idx.get(k)
                if i is not None and np.hypot(s.ropes.pts(i)[:, 0] - wx, s.ropes.pts(i)[:, 1] - wy).min() < r: return p
        return None
    def cable_at(s, wx, wy):
        r = max(3, 14 / s.zoom)                                       # ~14 px grab radius along the drawn rope
        for c in s.w.cables:
            i = s.rope_idx.get(('c', id(c)))
            if i is None: continue
            P = s.ropes.pts(i)
            d = np.hypot(P[:, 0] - wx, P[:, 1] - wy).min()
            if d < r: return c
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
        if s.menu_event(e): return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3 and view.collidepoint(e.pos):
            wx, wy = s.s2w(*e.pos); o = s.cable_at(wx, wy) or (s.ffc_at(wx, wy) if s.show['ffc'] else None)
            if o is not None: s.sel = o; s.cable_menu(o, e.pos); return
        if s.ruler_event(e, view): return
        if s.nav_event(e, view): return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos) and not s.app.ui.consumed:
            wx, wy = s.s2w(*e.pos)
            pt = s.port_at(wx, wy)
            if pt:
                c0 = s.w.cable_at(*pt) or next((c for c in s.w.cables if (c.a, c.as_) == pt or (c.b, c.bs) == pt), None)
                if c0 is not None:                                     # grab the cable END at this port (drag = move it, click = toggle)
                    far = (c0.b, c0.bs) if (c0.a, c0.as_) == pt else (c0.a, c0.as_)
                    s.wire = ('end', c0, far, pt, e.pos); return
                s.wire = ('port', pt, e.pos); return
            for p in reversed(s.w.panels):
                hx, hy = s.ffc_handle(p)
                if math.hypot(wx - hx, wy - hy) < max(6, 12 / s.zoom): s.wire = ('ffc', p, e.pos); s.sel = p; return
            for p in s.w.panels:
                i = s.rope_idx.get(('F', id(p)))
                if i is not None and s.show['ffc'] and any(math.hypot(wx - x, wy - y) < max(12, 14 / s.zoom) for x, y in s.ropes.pts(i)):
                    s.bundle_sel = p; s.sel = p; return
            c = s.cable_at(wx, wy)
            if c and not (s.panel_at(wx, wy) or s.board_at(wx, wy)):
                # a click on a cable body only SELECTS it (it used to toggle it: cables lie over boards/panels with a 14 px
                # hit band, so clicking/dragging a panel silently unplugged the stack cable -> "panels lose connection").
                # Unplug/plug: click its connector, right-click menu, or Delete/U.
                s.sel = c; s.note('Кабель выбран: ПКМ — меню, U — отключить/подключить'); return
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
                moved = math.hypot(e.pos[0] - s.wire[-1][0], e.pos[1] - s.wire[-1][1]) > 4 if s.wire[0] in ('port', 'end') else True
                if s.wire[0] == 'end':
                    c0, far, near = s.wire[1], s.wire[2], s.wire[3]
                    if not moved:
                        c0.plugged = not c0.plugged; s.w.dirty(); s.sel = c0; s.note(T('plug') if c0.plugged else T('unplug'))
                        s.w.cause = 'клик по разъёму %08X.%s (пользователь)' % (s.wire[3][0].id, SIDES[s.wire[3][1]])
                    else:
                        tgt = s.snap_port(wx, wy, exclude=far[0])
                        if tgt:
                            s.w.remove_cable(c0); nc = s.w.connect(far[0], far[1], tgt[0], tgt[1], c0.type)
                            if nc: nc.length = c0.length; s.sel = nc; s.note(T('plug'))
                        else: s.note('Кабель не перенесён: рядом нет свободного порта — остаётся подключённым')   # was: silently unplugged
                elif s.wire[0] == 'port':
                    pt = s.snap_port(wx, wy, exclude=s.wire[1][0])
                    if pt and moved: s.w.connect(s.wire[1][0], s.wire[1][1], pt[0], pt[1])
                elif s.wire[0] == 'ffc':
                    b = s.snap_board(wx, wy); p = s.wire[1]
                    if math.hypot(e.pos[0] - s.wire[2][0], e.pos[1] - s.wire[2][1]) <= 4:      # click on the panel connector = toggle
                        if p.board is not None: p._last_board = p.board; p.board = None; s.note(T('unplug')); s.w.cause = 'клик по разъёму FFC панели (пользователь)'
                        elif getattr(p, '_last_board', None) in s.w.boards: p.board = p._last_board; s.note(T('plug'))
                        s.w.dirty()
                    elif b:
                        for q in s.w.panels:
                            if q.board is b: q.board = None
                        p.board = b; s.w.dirty()
                s.wire = None
            if s.drag: s.w.dirty()
            s.drag = None
        elif e.type == pygame.MOUSEMOTION and s.drag:
            o, ox, oy, carry = s.drag; wx, wy = s.s2w(*e.pos)
            t = s.place(o, wx - ox, wy - oy)
            if t: o.tx, o.ty = t
        elif e.type == pygame.KEYDOWN and s.app.ui.focus is None:
            if e.key == pygame.K_SPACE: s.w.paused = not s.w.paused
            elif e.key == pygame.K_u and s.sel is not None and hasattr(s.sel, 'plugged'):
                s.sel.plugged = not s.sel.plugged; s.w.dirty(); s.w.cause = 'клавиша U (пользователь)'; s.note(T('plug') if s.sel.plugged else T('unplug'))
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
        # cables never unplug on their own: over-length is shown in red (tcol) + a one-shot note; unplug only by the user
        if s.drag is None: return
        for c in s.w.cables:
            i = s.rope_idx.get(('c', id(c)))
            if i is not None and c.plugged and ten[i] > 1.0 and not getattr(c, '_warned', False):
                c._warned = True; s.note('Кабель %08X.%s длиннее не станет: нужно %.0f > %d мм (красный)' % (c.a.id, SIDES[c.as_], ten[i] * c.length, c.length))
            elif i is not None and ten[i] <= 1.0: c._warned = False
        for p in s.w.panels:
            i = s.rope_idx.get(('f', id(p), 'J_ROW')); j = s.rope_idx.get(('f', id(p), 'J_COL'))
            if i is None: i = j = s.rope_idx.get(('F', id(p)))
            if p.board is not None and i is not None and max(ten[i], ten[j]) > 1.0 and not getattr(p, '_warned', False):
                p._warned = True; s.note('FFC %d мм не хватает: нужно %.0f мм (красный)' % (p.ffc_len, max(ten[i], ten[j]) * p.ffc_len))
            elif i is not None and max(ten[i], ten[j]) <= 1.0: p._warned = False
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
                    pygame.draw.polygon(ov, tuple(int(c * shade) for c in col) + (110 if k[0] == 'F' else 150,), q)
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
        if k in s.masks: s.masks[k] = s.masks.pop(k)                     # LRU order
        else:
            while len(s.masks) >= 4: s.masks.pop(next(iter(s.masks)))         # each is a (32k)² surface: keep 4
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
        pygame.draw.rect(surf, (18, 20, 18) if p.kind not in ('lattice', 'wire') else (12, 14, 12), r)
        if p.kind == 'wire' and size > 40:                             # wire grid: no PCB, row (Cu) + column (enamel) wires
            pd0 = panel_data('wire'); pt = (pd0['hi'][0] - pd0['lo'][0]) / 31
            for i in range(32):
                o = (pd0['lo'][0] + i * pt) * s.zoom
                pygame.draw.line(surf, (150, 85, 40), (x, y + o), (x + size, y + o)); pygame.draw.line(surf, (95, 55, 30), (x + o, y), (x + o, y + size))
        elif size > 220:                                                 # real panel PCB under the LEDs
            from . import pcbtex
            surf.blit(pcbtex.scaled({'full': 'panel_full', 'flat': 'panel_flat', 'lattice': 'panel_lattice'}[p.kind], r.size, p.rot), r.topleft)
        elif p.kind == 'lattice' and size > 60:
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
        k = int(round(aw / 32))                                            # whole-pixel LED cells: no second rescale pass
        if k >= 3:
            if k > 40: k = int(pitch * s.zoom)
            big = pygame.transform.scale(small, (32 * k, 32 * k))
            big.blit(s.dot_mask(min(k, 40)) if k <= 40 else pygame.transform.scale(s.dot_mask(40), (32 * k, 32 * k)), (0, 0), special_flags=pygame.BLEND_MULT)
            # glow composited into the LED layer off-screen, then ONE additive blit to the screen (was two)
            gs = pygame.transform.smoothscale(small, (16, 16)); gs.fill((95, 95, 95), special_flags=pygame.BLEND_MULT)
            big.blit(pygame.transform.smoothscale(gs, big.get_size()), (0, 0), special_flags=pygame.BLEND_ADD)
            surf.blit(big, (ax, ay), special_flags=pygame.BLEND_ADD)
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
        if (not behind or s.xray) and r.w > 40:                       # the real PCB: mask, copper, pads, parts, silkscreen
            from . import pcbtex
            tex = pcbtex.scaled('board_v15', r.size, b.rot, b.mirror, 'B' if b.mirror else 'F')
            if behind: tex = tex.copy(); tex.set_alpha(150)
            surf.blit(tex, r.topleft)
            if not b.powered: surf.blit(s.masks[k], r.topleft)
        else: surf.blit(s.masks[k], r.topleft)
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
        # draw order: LED panels on top; boards as a semi-transparent layer (opacity slider, default 35 %)
        if s.show.get('panels', True):
            for p in s.w.panels: s.draw_panel(surf, p)
        if s.show.get('boards', True):
            if s.board_alpha >= 0.99:
                for b in s.w.boards: s.draw_board(surf, b)
            else:
                # dirty-rect cache: the translucent board layer is only redrawn when the camera, a board, the selection
                # or the opacity changed; and only the boards' bounding box is blended onto the screen
                key = (pygame.time.get_ticks() // 250, surf.get_size(), tuple(view), s.zoom, s.w2s(0, 0), id(s.sel), int(255 * s.board_alpha), getattr(s, 'xray', None),
                       tuple((id(b), b.x, b.y, b.rot, getattr(b, 'mirror', 0), b.powered, b.node.state) for b in s.w.boards))
                if getattr(s, '_blayer', None) is None or s._blayer.get_size() != surf.get_size(): s._blayer = pygame.Surface(surf.get_size(), pygame.SRCALPHA); s._bkey = None
                L = s._blayer
                if key != getattr(s, '_bkey', None):
                    L.fill((0, 0, 0, 0)); L.set_clip(view)
                    for b in s.w.boards: s.draw_board(L, b)
                    L.set_clip(None); L.set_alpha(int(255 * s.board_alpha)); s._bkey = key
                    br = L.get_bounding_rect(); s._brect = br.clip(view)
                if s._brect.w and s._brect.h: surf.blit(L, s._brect.topleft, s._brect)
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
            if s.wire[0] == 'port': st = s.w2s(*s.wire[1][0].port_pos(s.wire[1][1]))
            elif s.wire[0] == 'end': st = s.w2s(*s.wire[2][0].port_pos(s.wire[2][1]))
            else: st = s.w2s(*s.ffc_handle(s.wire[1]))
            mp = pygame.mouse.get_pos(); wx, wy = s.s2w(*mp)
            if s.wire[0] == 'ffc':
                b = s.snap_board(wx, wy)
                if b:
                    for nm in ('J_ROW', 'J_COL'):
                        q = s.w2s(*b.conn_pos(nm)); pygame.draw.circle(surf, (120, 255, 160), (int(q[0]), int(q[1])), max(8, int(10 * s.zoom)), 2)
            else:
                tgt = s.snap_port(wx, wy, exclude=(s.wire[1] if s.wire[0] == 'port' else s.wire[2])[0])
                if tgt:
                    q = s.w2s(*tgt[0].port_pos(tgt[1])); mp = q
                    pygame.draw.circle(surf, (120, 255, 160), (int(q[0]), int(q[1])), max(8, int(s.SNAP_MM * s.zoom)), 2)
            pygame.draw.line(surf, (255, 255, 255), st, mp, 2)
        if getattr(s, 'menu', None):
            c, (mx, my) = s.menu; mpos = pygame.mouse.get_pos()
            for i, (lab, fn) in enumerate(s.menu_items(c)):
                rr = pygame.Rect(mx, my + i * 22, 170, 22)
                pygame.draw.rect(surf, (60, 70, 95) if rr.collidepoint(mpos) else (36, 40, 52), rr); pygame.draw.rect(surf, (90, 100, 130), rr, 1)
                text(surf, lab, (rr.x + 8, rr.y + 4), (230, 230, 240), 12)
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
        for i, (k, lab) in enumerate((('ffc', 'FFC'), ('stack', 'Кабели'), ('power', 'Питание'))):
            if ui.button(surf, (x + i * (tb + 4), y, tb, 22), lab, on=s.show[k], sz=10): s.show[k] = not s.show[k]
        cats = ('ffc', 'stack', 'power', 'led'); allon = all(s.show[k] for k in cats)
        if ui.button(surf, (x + 3 * (tb + 4), y, tb, 22), 'Все', on=allon, sz=10):
            for k in cats: s.show[k] = not allon
        if ui.button(surf, (x + 4 * (tb + 4), y, tb, 22), 'Рентген', on=s.xray, sz=10): s.xray = not s.xray
        y += 26
        for i, (k, lab) in enumerate((('panels', 'LED-панели'), ('boards', 'Платы'))):
            if ui.button(surf, (x + i * (W // 2 + 2), y, W // 2 - 2, 22), lab, on=s.show[k], sz=10): s.show[k] = not s.show[k]
        y += 40
        s.board_alpha = round(ui.slider(surf, (x, y, W, 8), 'Непрозрачность плат', s.board_alpha, 0.05, 1.0, '%.2f'), 2); y += 16
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
                text(surf, 'шлейф, мм:' if o.kind == 'wire' else 'FFC, мм:', (x, y + 4), sz=12)
                for i, L in enumerate(lead_lengths(o.kind)):
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
