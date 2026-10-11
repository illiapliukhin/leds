"""mm rulers along the view edges (follow zoom/pan), optional mm grid and a two-click measuring tool, for every
Nav2D view (world units = mm). Keys: G grid, M measure, Esc cancel."""
import math
import pygame
from .ui import text

STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]

class Rulers:
    def rulers_init(s): s.r_grid = False; s.r_meas = None; s.r_pts = []
    def _st(s):
        if not hasattr(s, 'r_grid'): s.rulers_init()
    def ruler_buttons(s, surf, ui, x, y, W):
        s._st(); hb = (W - 4) // 2
        if ui.button(surf, (x, y, hb, 22), 'Сетка мм (G)', on=s.r_grid, sz=10): s.r_grid = not s.r_grid
        if ui.button(surf, (x + hb + 4, y, hb, 22), 'Линейка: 2 клика (M)', on=s.r_meas is not None, sz=10): s.r_meas = None if s.r_meas is not None else 'armed'; s.r_pts = []
        return y + 26
    def ruler_event(s, e, view):
        s._st()
        if e.type == pygame.KEYDOWN and s.app.ui.focus is None:
            if e.key == pygame.K_g: s.r_grid = not s.r_grid; return True
            if e.key == pygame.K_m: s.r_meas = None if s.r_meas is not None else 'armed'; s.r_pts = []; return True
            if e.key == pygame.K_ESCAPE and s.r_meas is not None: s.r_meas = None; s.r_pts = []; return True
        if s.r_meas is not None and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos) and not s.app.ui.consumed:
            if len(s.r_pts) >= 2: s.r_pts = []
            s.r_pts.append(s.s2w(*e.pos)); return True
        return False
    def step_for(s, px_min=60):
        return next((st for st in STEPS if st * s.zoom >= px_min), STEPS[-1])
    def draw_rulers(s, surf, view):
        s._st(); z = s.zoom; st = s.step_for(); minor = st / 5 if str(st)[0] in '125' else st / 2
        x0w, y0w = s.s2w(view.x, view.y); x1w, y1w = s.s2w(view.right, view.bottom)
        if s.r_grid:
            g = s.step_for(18)
            k = math.floor(x0w / g)
            while k * g <= x1w:
                X = s.w2s(k * g, 0)[0]; c = (40, 46, 58) if abs(k * g / st - round(k * g / st)) < 1e-6 else (26, 29, 36)
                pygame.draw.line(surf, c, (X, view.y), (X, view.bottom)); k += 1
            k = math.floor(y0w / g)
            while k * g <= y1w:
                Y = s.w2s(0, k * g)[1]; c = (40, 46, 58) if abs(k * g / st - round(k * g / st)) < 1e-6 else (26, 29, 36)
                pygame.draw.line(surf, c, (view.x, Y), (view.right, Y)); k += 1
        bar = 18
        pygame.draw.rect(surf, (22, 24, 30), (view.x, view.y, view.w, bar)); pygame.draw.rect(surf, (22, 24, 30), (view.x, view.y, bar, view.h))
        for axis in (0, 1):
            lo, hi = (x0w, x1w) if axis == 0 else (y0w, y1w)
            k = math.floor(lo / minor)
            while k * minor <= hi:
                v = k * minor; major = abs(v / st - round(v / st)) < 1e-6
                if axis == 0:
                    X = s.w2s(v, 0)[0]
                    if X > view.x + bar:
                        pygame.draw.line(surf, (150, 156, 170), (X, view.y + (4 if major else 11)), (X, view.y + bar))
                        if major: text(surf, ('%g' % v), (X + 2, view.y + 1), (170, 176, 190), 9)
                else:
                    Y = s.w2s(0, v)[1]
                    if Y > view.y + bar:
                        pygame.draw.line(surf, (150, 156, 170), (view.x + (4 if major else 11), Y), (view.x + bar, Y))
                        if major: text(surf, ('%g' % v), (view.x + 1, Y + 1), (170, 176, 190), 9)
                k += 1
        text(surf, 'мм', (view.x + 2, view.y + 3), (255, 220, 140), 9)
        mx, my = pygame.mouse.get_pos()
        if view.collidepoint(mx, my):
            wx, wy = s.s2w(mx, my)
            pygame.draw.line(surf, (255, 200, 80), (mx, view.y), (mx, view.y + bar), 1); pygame.draw.line(surf, (255, 200, 80), (view.x, my), (view.x + bar, my), 1)
            text(surf, 'x %.1f  y %.1f мм' % (wx, wy), (view.right - 150, view.y + 2), (255, 220, 140), 10)
        # measuring tool
        if s.r_meas is not None:
            pts = list(s.r_pts) + ([s.s2w(mx, my)] if len(s.r_pts) == 1 else [])
            for p in s.r_pts: q = s.w2s(*p); pygame.draw.circle(surf, (255, 230, 80), (int(q[0]), int(q[1])), 4)
            if len(pts) == 2:
                a, b = s.w2s(*pts[0]), s.w2s(*pts[1]); pygame.draw.line(surf, (255, 230, 80), a, b, 2)
                d = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
                text(surf, '%.2f мм  (Δx %.2f, Δy %.2f)' % (d, pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]), ((a[0] + b[0]) / 2 + 8, (a[1] + b[1]) / 2 - 16), (255, 240, 150), 13)
            elif not s.r_pts: text(surf, 'Линейка: кликните первую точку (Esc — выход)', (view.x + 26, view.y + 22), (255, 230, 80), 12)

def dim_line(surf, a, b, label, col=(200, 205, 120), off=(0, 0)):
    """dimension line between screen points a, b with end ticks and a centred label"""
    a = (a[0] + off[0], a[1] + off[1]); b = (b[0] + off[0], b[1] + off[1])
    pygame.draw.line(surf, col, a, b, 1)
    dx, dy = b[0] - a[0], b[1] - a[1]; ln = math.hypot(dx, dy) or 1; nx, ny = -dy / ln * 5, dx / ln * 5
    for p in (a, b): pygame.draw.line(surf, col, (p[0] - nx, p[1] - ny), (p[0] + nx, p[1] + ny), 1)
    text(surf, label, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 7), col, 10, center=True)
