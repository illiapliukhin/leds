"""Main window: tabs (Система / Платы / Панели / Куб), fixed-timestep loop at 60 fps."""
import os, sys, time
import pygame
from . import ui as U
from .ui import T, text
from .view_system import SystemView
from .view_pcb import PcbView
from .view_cube import CubeView
from .view_test import TestView

SIDE_W = 400
TABS = ['system', 'test', 'boards', 'panels', 'cube']
TAB_KEYS = {'system': 'tab_sys', 'boards': 'tab_boards', 'panels': 'tab_panels', 'cube': 'tab_cube', 'test': 'tab_test'}

class App:
    def __init__(s, size=(1600, 920), shots=None, lang='ru', tab='system', preset=None):
        pygame.init(); U.LANG[0] = lang
        flags = pygame.RESIZABLE
        s.screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption(T('title'))
        s.ui = U.UI(); s.tab = tab; s.shots = shots or []
        s.layout()
        s.views = {'system': SystemView(s), 'boards': PcbView(s, 'boards'), 'panels': PcbView(s, 'panels'), 'cube': CubeView(s)}
        s.views['test'] = TestView(s)
        if preset: c, r = preset; s.views['system'].w.preset(c, r)
        s.views['system'].fit(s.view); s.views['system'].apply_global()
        s.fps_meas = 60.0; s.dt = 1 / 60
    def layout(s):
        W, H = s.screen.get_size()
        s.view = pygame.Rect(0, 36, W - SIDE_W, H - 36); s.side = pygame.Rect(W - SIDE_W, 36, SIDE_W, H - 36)
    def ask_file(s, save):
        try:
            import tkinter as tk; from tkinter import filedialog
            r = tk.Tk(); r.withdraw()
            kw = dict(filetypes=[('JSON', '*.json')], defaultextension='.json')
            p = filedialog.asksaveasfilename(**kw) if save else filedialog.askopenfilename(**kw)
            r.destroy(); return p or None
        except Exception:
            return None
    def run(s):
        clock = pygame.time.Clock(); t_last = time.perf_counter(); frame = 0
        while True:
            ev = pygame.event.get()
            for e in ev:
                if e.type == pygame.QUIT: return
                if e.type == pygame.VIDEORESIZE: s.layout(); [setattr(v, 'surf_key', None) for v in s.views.values() if hasattr(v, 'surf_key')]
            s.ui.begin(ev)
            now = time.perf_counter(); dt = min(0.1, now - t_last); t_last = now
            s.fps_meas = 0.95 * s.fps_meas + 0.05 / max(dt, 1e-4)
            s.dt = dt
            sv = s.views['system']; sv.tick(dt)
            if not sv.w.paused: s.views['test'].tick()                 # the stack keeps running in every tab
            v = s.views[s.tab]
            sc = s.screen; sc.fill((24, 26, 32))
            # side panel + top bar first (they consume clicks), then the view gets the events
            pygame.draw.rect(sc, (30, 33, 40), s.side)
            v.panel(sc, s.ui, s.side)
            x = 8
            for t in TABS:
                if s.ui.button(sc, (x, 4, 106, 28), T(TAB_KEYS[t]), on=s.tab == t): s.tab = t
                x += 112
            if s.ui.button(sc, (x + 10, 4, 44, 28), T('lang')): U.LANG[0] = 'en' if U.LANG[0] == 'ru' else 'ru'
            text(sc, '%s   %.0f fps' % (T('title'), s.fps_meas), (x + 70, 11), (150, 156, 170), 13)
            for e in ev: v.event(e, s.view)
            v.draw(sc, s.view)
            pygame.display.flip()
            frame += 1
            for (fr, tab, path, act) in list(s.shots):
                if frame == fr:
                    if act: act(s)
                    if tab: s.tab = tab
                    if path: pygame.image.save(sc, path); print('shot', path, flush=True)
            if s.shots and frame > max(f for f, *_ in s.shots): return
            clock.tick(60)

def main():
    a = sys.argv[1:]
    lang = 'en' if '--en' in a else 'ru'
    if '--shots' in a:
        from . import selftest; selftest.run(a[a.index('--shots') + 1]); return
    App(lang=lang).run()
