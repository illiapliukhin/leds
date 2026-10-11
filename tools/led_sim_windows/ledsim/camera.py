"""Navigation: Nav2D mixin (smooth zoom to cursor, pan with inertia, fit, double-click focus, keys,
touchpad pinch/scroll) for the 2D views, and OrbitCam (turntable with inertia + damping, pan, zoom to
cursor, presets) for the cube view."""
import math
import pygame

def _mods(): return pygame.key.get_mods()
def _typing(app): return app.ui.focus is not None

class Nav2D:
    """Host must provide: self.app, self.zoom (px/mm), self.pan [x, y], fit(view), and optionally focus_at(wx, wy)."""
    ZMIN, ZMAX = 0.03, 400.0
    def nav_init(s):
        s._zt = None; s._anchor = None; s._vel = [0.0, 0.0]; s._drag = False; s._last_click = (0, (0, 0))
        s._rel = [0.0, 0.0]
    def w2s(s, x, y): return (s.pan[0] + x * s.zoom, s.pan[1] + y * s.zoom)
    def s2w(s, x, y): return ((x - s.pan[0]) / s.zoom, (y - s.pan[1]) / s.zoom)
    def zoom_at(s, factor, sx, sy):
        if s._zt is None: s._zt = s.zoom
        s._zt = max(s.ZMIN, min(s.ZMAX, s._zt * factor)); s._anchor = (sx, sy, *s.s2w(sx, sy))
    def nav_event(s, e, view):
        """returns True when the event was used for navigation"""
        if not hasattr(s, '_vel'): s.nav_init()
        if s.zoom is None: return False
        mp = pygame.mouse.get_pos()
        if e.type == pygame.MOUSEWHEEL and view.collidepoint(mp):
            px, py = getattr(e, 'precise_x', e.x), getattr(e, 'precise_y', e.y)
            if _mods() & pygame.KMOD_SHIFT: s._vel = [0, 0]; s.pan[0] += py * 40; return True
            if abs(px) > 0.01 and abs(py) < 0.01:                       # touchpad horizontal two-finger scroll
                s.pan[0] -= px * 30; return True
            s.zoom_at(1.2 ** py, *mp); return True
        if e.type == pygame.MULTIGESTURE:                               # touchpad / touch pinch + two-finger pan
            w, h = pygame.display.get_surface().get_size()
            if abs(e.pinched) > 1e-4: s.zoom_at(1 + e.pinched * 4, *mp)
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (2, 3) and view.collidepoint(e.pos):
            s._drag = True; s._vel = [0, 0]; return True
        if e.type == pygame.MOUSEBUTTONUP and e.button in (2, 3):
            s._drag = False; s._vel = list(s._rel); return True
        if e.type == pygame.MOUSEMOTION and s._drag:
            s.pan[0] += e.rel[0]; s.pan[1] += e.rel[1]; s._rel = [e.rel[0] * 60, e.rel[1] * 60]; return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos):
            t = pygame.time.get_ticks(); lt, lp = s._last_click; s._last_click = (t, e.pos)
            if t - lt < 350 and abs(lp[0] - e.pos[0]) + abs(lp[1] - e.pos[1]) < 8:
                wx, wy = s.s2w(*e.pos)
                if hasattr(s, 'focus_at') and s.focus_at(wx, wy): return True
                s.zoom_at(2.0, *e.pos); return True
        if e.type == pygame.KEYDOWN and not _typing(s.app):
            if e.key in (pygame.K_HOME, pygame.K_f): s.fit(view); s._zt = None; s._vel = [0, 0]; return True
            if e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS): s.zoom_at(1.25, *view.center); return True
            if e.key in (pygame.K_MINUS, pygame.K_KP_MINUS): s.zoom_at(0.8, *view.center); return True
        return False
    def nav_update(s, dt, view):
        if not hasattr(s, '_vel'): s.nav_init()
        if s.zoom is None: return
        if s._zt is not None and s._anchor:
            k = 1 - math.exp(-dt * 14)
            s.zoom += (s._zt - s.zoom) * k
            sx, sy, wx, wy = s._anchor; s.pan = [sx - wx * s.zoom, sy - wy * s.zoom]
            if abs(s._zt - s.zoom) < s.zoom * 1e-3: s.zoom = s._zt; s._zt = None
        if not s._drag and (abs(s._vel[0]) + abs(s._vel[1])) > 1:
            s.pan[0] += s._vel[0] * dt; s.pan[1] += s._vel[1] * dt
            d = math.exp(-dt * 6); s._vel = [s._vel[0] * d, s._vel[1] * d]
        if s._drag: s._rel = [s._rel[0] * 0.5, s._rel[1] * 0.5]
        if not _typing(s.app):
            k = pygame.key.get_pressed(); sp = 700 * dt
            if not (_mods() & pygame.KMOD_CTRL):
                if k[pygame.K_a] or k[pygame.K_LEFT]: s.pan[0] += sp
                if k[pygame.K_d] or k[pygame.K_RIGHT]: s.pan[0] -= sp
                if k[pygame.K_w] or k[pygame.K_UP]: s.pan[1] += sp
                if k[pygame.K_s] or k[pygame.K_DOWN]: s.pan[1] -= sp

class OrbitCam:
    """Turntable orbit camera: yaw/pitch with angular inertia + damping, target pan, dolly zoom toward the cursor."""
    PRESETS = {'front': (0.0, 0.0), 'top': (0.0, 1.5), 'iso': (0.785, 0.615)}
    def __init__(s): s.reset()
    def reset(s):
        s.yaw, s.pitch, s.dist = 0.6, 0.45, 2.6; s.target = [0.0, 0.0, 0.0]; s.wy = s.wp = 0.0
        s.goal = None; s.drag = None; s.dist_t = s.dist; s._last_click = 0; s.tele = False; s.R = None
    def matrix(s):
        """world→camera rotation: free trackball matrix if set (middle-drag), else turntable yaw/pitch"""
        if getattr(s, 'R', None) is not None: return s.R
        cy, sy, cp, sp = math.cos(s.yaw), math.sin(s.yaw), math.cos(s.pitch), math.sin(s.pitch)
        import numpy as _np
        return _np.array([[cy, 0.0, -sy], [-sy * sp, cp, -cy * sp], [sy * cp, sp, cy * cp]])
    def trackball(s, dx, dy):
        """free rotation about the screen axes (no gimbal lock): left-multiply the incremental rotation"""
        import numpy as _np
        R = s.matrix().copy(); a, b = dx * 0.008, dy * 0.008
        ry = _np.array([[math.cos(a), 0, -math.sin(a)], [0, 1, 0], [math.sin(a), 0, math.cos(a)]])
        rx = _np.array([[1, 0, 0], [0, math.cos(b), math.sin(b)], [0, -math.sin(b), math.cos(b)]])
        R = rx @ ry @ R; u, _, vt = _np.linalg.svd(R); s.R = u @ vt                     # re-orthonormalise
    def preset(s, name): s.R = None; s.goal = s.PRESETS[name] + (2.6,); s.target = [0.0, 0.0, 0.0]; s.tele = False
    def basis(s):
        if getattr(s, 'R', None) is not None: return tuple(s.R[0]), tuple(-s.R[1])
        cy, sy, cp, sp = math.cos(s.yaw), math.sin(s.yaw), math.cos(s.pitch), math.sin(s.pitch)
        right = (cy, 0.0, -sy); up = (-sy * sp, cp, -cy * sp)
        return right, up
    def event(s, e, view, app):
        if e.type == pygame.MOUSEBUTTONDOWN and view.collidepoint(e.pos) and not app.ui.consumed:
            if e.button == 1:
                t = pygame.time.get_ticks()
                if t - s._last_click < 350: s.target = [0.0, 0.0, 0.0]; s.dist_t = 1.9; s._last_click = 0; return
                s._last_click = t; s.drag = 'orbit'; s.wy = s.wp = 0; s.goal = None; s.R = None
            elif e.button == 2: s.drag = 'track'; s.wy = s.wp = 0; s.goal = None
            elif e.button == 3: s.drag = 'pan'
        elif e.type == pygame.MOUSEBUTTONUP: s.drag = None
        elif e.type == pygame.MOUSEMOTION and s.drag == 'orbit':
            s.wy = e.rel[0] * 0.6; s.wp = e.rel[1] * 0.6
            s.yaw += e.rel[0] * 0.01; s.pitch = max(-1.55, min(1.55, s.pitch + e.rel[1] * 0.01))
        elif e.type == pygame.MOUSEMOTION and s.drag == 'track': s.trackball(e.rel[0], e.rel[1])
        elif e.type == pygame.MOUSEMOTION and s.drag == 'pan':
            r, u = s.basis(); k = s.dist * 0.0012
            for i in range(3): s.target[i] -= (r[i] * e.rel[0] - u[i] * e.rel[1]) * k
        elif e.type == pygame.MOUSEWHEEL and view.collidepoint(pygame.mouse.get_pos()):
            f = 0.88 ** getattr(e, 'precise_y', e.y); nd = max(0.9, min(10, s.dist_t * f))
            mx, my = pygame.mouse.get_pos(); ox, oy = (mx - view.centerx) / (min(view.w, view.h) * 0.45), (my - view.centery) / (min(view.w, view.h) * 0.45)
            r, u = s.basis(); mv = (s.dist_t - nd)                     # dolly toward the point under the cursor
            for i in range(3): s.target[i] += (r[i] * ox + u[i] * oy) * mv * 0.5
            s.dist_t = nd
        elif e.type == pygame.MULTIGESTURE and abs(e.pinched) > 1e-4: s.dist_t = max(0.9, min(10, s.dist_t * (1 - e.pinched * 4)))
        elif e.type == pygame.KEYDOWN and app.ui.focus is None:
            if e.key in (pygame.K_HOME, pygame.K_r): s.reset()
            elif e.key == pygame.K_1: s.preset('front')
            elif e.key == pygame.K_2: s.preset('top')
            elif e.key == pygame.K_3: s.preset('iso')
    def update(s, dt, app):
        if s.drag != 'orbit' and (abs(s.wy) + abs(s.wp)) > 1e-3:
            s.yaw += s.wy * dt; s.pitch = max(-1.55, min(1.55, s.pitch + s.wp * dt))
            d = math.exp(-dt * 3.5); s.wy *= d; s.wp *= d
        if app.ui.focus is None:
            k = pygame.key.get_pressed()
            if k[pygame.K_a] or k[pygame.K_LEFT]: s.yaw -= 1.6 * dt
            if k[pygame.K_d] or k[pygame.K_RIGHT]: s.yaw += 1.6 * dt
            if k[pygame.K_w] or k[pygame.K_UP]: s.pitch = min(1.55, s.pitch + 1.2 * dt)
            if k[pygame.K_s] or k[pygame.K_DOWN]: s.pitch = max(-1.55, s.pitch - 1.2 * dt)
            if k[pygame.K_q]: s.dist_t = min(10, s.dist_t * (1 + dt))
            if k[pygame.K_e]: s.dist_t = max(0.9, s.dist_t * (1 - dt))
        if s.goal:
            gy, gp, gd = s.goal; k = 1 - math.exp(-dt * 6)
            dy = (gy - s.yaw + math.pi) % (2 * math.pi) - math.pi
            s.yaw += dy * k; s.pitch += (gp - s.pitch) * k; s.dist_t = gd
            if abs(dy) + abs(gp - s.pitch) < 1e-3: s.goal = None
        s.dist += (s.dist_t - s.dist) * (1 - math.exp(-dt * 10))
