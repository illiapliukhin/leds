"""System view: layout canvas + live stack state + controls."""
import json, math, os
import numpy as np
import pygame
from . import host, stack_model
from .ui import T, text, font
from .world import World, PANELS, BOARD_W, BOARD_H, rotv, panel_data
from .stack_model import LEAD, FOLLOW, STATE_NAMES

SIDES = 'NESW'
LED_RGB = np.array([255, 246, 228], np.float32)
ROLE_COL = {LEAD: (255, 196, 60), FOLLOW: (90, 210, 120), stack_model.WAIT: (120, 170, 255), stack_model.ELECT: (200, 120, 255),
            stack_model.DISCOVER: (255, 120, 80), stack_model.OFF: (110, 110, 110)}

def layout_dir():
    d = os.path.join(os.path.expanduser('~'), 'Documents', 'LED_Simulator')
    os.makedirs(d, exist_ok=True); return d

class SystemView:
    def __init__(s, app):
        s.app = app; s.w = World(); s.w.preset(3, 2)
        s.zoom = 1.2; s.pan = [260, 200]; s.sel = None; s.drag = None; s.wire = None; s.kind = 'full'
        s.snap = 10.0; s.demo_i = 0; s.fps = 60; s.speed = 1.0; s.acc = 0.0; s.msg = ''; s.msg_t = 0
        s.masks = {}; s.scroll = 0; s.show_topo = True; s.load_ms = 0.0

    # ------------------------------------------------ coords
    def w2s(s, x, y): return (s.pan[0] + x * s.zoom, s.pan[1] + y * s.zoom)
    def s2w(s, x, y): return ((x - s.pan[0]) / s.zoom, (y - s.pan[1]) / s.zoom)
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
    def ffc_handle(s, p): return p.x, p.y + p.size * 0.32
    def cable_at(s, wx, wy):
        r = max(5, 8 / s.zoom)
        for c in s.w.cables:
            ax, ay = c.a.port_pos(c.as_); bx, by = c.b.port_pos(c.bs)
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if math.hypot(wx - mx, wy - my) < r * 1.6: return c
            dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy or 1
            t = max(0, min(1, ((wx - ax) * dx + (wy - ay) * dy) / L2))
            if math.hypot(ax + t * dx - wx, ay + t * dy - wy) < r * 0.6: return c

    # ------------------------------------------------ events
    def event(s, e, view):
        if e.type == pygame.MOUSEWHEEL and view.collidepoint(pygame.mouse.get_pos()):
            mx, my = pygame.mouse.get_pos(); wx, wy = s.s2w(mx, my)
            s.zoom = max(0.05, min(30, s.zoom * (1.15 ** e.y))); s.pan = [mx - wx * s.zoom, my - wy * s.zoom]
        elif e.type == pygame.MOUSEMOTION and (e.buttons[2] or e.buttons[1]):
            s.pan[0] += e.rel[0]; s.pan[1] += e.rel[1]
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos) and not s.app.ui.consumed:
            wx, wy = s.s2w(*e.pos)
            pt = s.port_at(wx, wy)
            if pt: s.wire = ('port', pt); return
            for p in reversed(s.w.panels):
                hx, hy = s.ffc_handle(p)
                if math.hypot(wx - hx, wy - hy) < max(6, 9 / s.zoom): s.wire = ('ffc', p); s.sel = p; return
            c = s.cable_at(wx, wy)
            if c:
                c.plugged = not c.plugged; s.w.dirty(); s.sel = c
                s.note(T('plug') if c.plugged else T('unplug')); return
            o = s.board_at(wx, wy) or s.panel_at(wx, wy)
            s.sel = o
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
            nx, ny = round((wx - ox) / s.snap) * s.snap, round((wy - oy) / s.snap) * s.snap
            for p in carry: p.x, p.y = nx, ny
            o.x, o.y = nx, ny
        elif e.type == pygame.KEYDOWN and s.app.ui.focus is None:
            if e.key == pygame.K_SPACE: s.w.paused = not s.w.paused
            elif e.key == pygame.K_r and s.sel is not None and hasattr(s.sel, 'rot'):
                s.sel.rot = (s.sel.rot + 1) & 3
                if hasattr(s.sel, 'node'):
                    for p in s.w.panels:
                        if p.board is s.sel and abs(p.x - s.sel.x) < 1 and abs(p.y - s.sel.y) < 1: p.rot = s.sel.rot
                s.w.dirty()
            elif e.key == pygame.K_DELETE: s.delete_sel()
    def delete_sel(s):
        o = s.sel
        if o is None: return
        if hasattr(o, 'node'): s.w.remove_board(o)
        elif hasattr(o, 'kind'): s.w.remove_panel(o)
        else: s.w.remove_cable(o)
        s.sel = None

    # ------------------------------------------------ time
    def tick(s, dt):
        if s.w.paused: return
        s.acc += dt * 1000 * s.speed
        n = int(s.acc); s.acc -= n
        n = min(n, 100)
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
            if p.board:
                bx, by = s.w2s(p.board.x, p.board.y)
                if abs(bx - hx) + abs(by - hy) > 4: pygame.draw.line(surf, col, (hx, hy), (bx, by), 2)
            if p.open_col >= 0 or p.ffc == 'A':
                text(surf, ('FFC A ' if p.ffc == 'A' else '') + ('col %d open' % (p.open_col + 1) if p.open_col >= 0 else ''), (r.x + 4, r.bottom - 16), (255, 100, 100), 11)

    def draw_board(s, surf, b):
        n = b.node; hw, hh = (BOARD_W, BOARD_H) if b.rot % 2 == 0 else (BOARD_H, BOARD_W)
        x, y = s.w2s(b.x - hw / 2, b.y - hh / 2); r = pygame.Rect(x, y, hw * s.zoom, hh * s.zoom)
        if not r.colliderect(surf.get_rect()): return
        col = ROLE_COL.get(n.state if b.powered else stack_model.OFF)
        k = (r.size, b.powered)
        if len(s.masks) > 300: s.masks.clear()
        if k not in s.masks:
            ov = pygame.Surface(r.size, pygame.SRCALPHA); ov.fill((20, 60, 30, 70) if b.powered else (60, 20, 20, 90)); s.masks[k] = ov
        surf.blit(s.masks[k], r.topleft)
        pygame.draw.rect(surf, (255, 255, 255) if b is s.sel else col, r, 2 if b is s.sel else 1)
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

    def draw(s, surf, view):
        surf.set_clip(view); surf.fill((14, 15, 19), view)
        g = 160 * s.zoom
        if g > 20:
            x0, y0 = s.w2s(0, 0); x = x0 % g + view.x; 
            while x < view.right: pygame.draw.line(surf, (24, 26, 32), (x, view.y), (x, view.bottom)); x += g
            y = y0 % g + view.y
            while y < view.bottom: pygame.draw.line(surf, (24, 26, 32), (view.x, y), (view.right, y)); y += g
        for p in s.w.panels: s.draw_panel(surf, p)
        for b in s.w.boards: s.draw_board(surf, b)
        for c in s.w.cables:
            a = s.w2s(*c.a.port_pos(c.as_)); bb = s.w2s(*c.b.port_pos(c.bs))
            col = ((255, 80, 80) if c.type == 'A' else (90, 220, 120)) if c.plugged else (110, 110, 110)
            if c.plugged: pygame.draw.line(surf, col, a, bb, 3 if c is s.sel else 2)
            else:
                m = ((a[0] + bb[0]) / 2, (a[1] + bb[1]) / 2)
                pygame.draw.line(surf, col, a, (a[0] * 0.6 + m[0] * 0.4, a[1] * 0.6 + m[1] * 0.4), 2)
                pygame.draw.line(surf, col, bb, (bb[0] * 0.6 + m[0] * 0.4, bb[1] * 0.6 + m[1] * 0.4), 2)
            m = ((a[0] + bb[0]) / 2, (a[1] + bb[1]) / 2)
            pygame.draw.circle(surf, col, (int(m[0]), int(m[1])), 5 if c is s.sel else 4, 0 if c.plugged else 1)
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
                y += 30
            else:
                text(surf, '%s: %s.%s — %s.%s' % (T('selected'), '%08X' % o.a.id, SIDES[o.as_], '%08X' % o.b.id, SIDES[o.bs]), (x, y), (255, 220, 140), 12); y += 20
                if ui.button(surf, (x, y, hb, 24), T('unplug') if o.plugged else T('plug')): o.plugged = not o.plugged; s.w.dirty()
                if ui.button(surf, (x + hb + 4, y, hb, 24), T('cable_a') if o.type == 'A' else T('cable_b'), col=(130, 50, 50) if o.type == 'A' else None): o.type = 'B' if o.type == 'A' else 'A'; s.w.dirty()
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
