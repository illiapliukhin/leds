"""Main window: tabs (Система / Платы / Панели / Куб), fixed-timestep loop at 60 fps."""
import os, sys, time
import pygame
from . import ui as U
from .ui import T, text
from .view_system import SystemView
from .view_pcb import PcbView
from .view_cube import CubeView
from .view_test import TestView
from .view_lab import LabView
from .view_models import ModelsView

SIDE_W = 400
TABS = ['system', 'test', 'lab', 'models', 'boards', 'panels', 'cube']
TAB_KEYS = {'system': 'tab_sys', 'boards': 'tab_boards', 'panels': 'tab_panels', 'cube': 'tab_cube', 'test': 'tab_test', 'lab': 'tab_lab', 'models': 'tab_models'}

class App:
    def __init__(s, size=(1600, 920), shots=None, lang='ru', tab='system', preset=None):
        pygame.init(); U.LANG[0] = lang
        flags = pygame.RESIZABLE
        s.screen = pygame.display.set_mode(size, flags)
        from . import _build as B; pygame.display.set_caption('%s — сборка %s, %s' % (T('title'), B.GIT_SHA, B.BUILD_TIME))
        s.ui = U.UI(); s.tab = tab; s.shots = shots or []
        s.layout()
        s.views = {'system': SystemView(s), 'boards': PcbView(s, 'boards'), 'panels': PcbView(s, 'panels'), 'cube': CubeView(s)}
        s.views['test'] = TestView(s); s.views['lab'] = LabView(s); s.views['models'] = ModelsView(s)
        if preset: c, r = preset; s.views['system'].w.preset(c, r)
        s.views['system'].fit(s.view); s.views['system'].apply_global()
        s.fps_meas = 60.0; s.dt = 1 / 60
    def layout(s):
        W, H = s.screen.get_size()
        s.view = pygame.Rect(0, 36, W - SIDE_W, H - 36 - 22); s.side = pygame.Rect(W - SIDE_W, 36, SIDE_W, H - 36 - 22); s.status = pygame.Rect(0, H - 22, W, 22)
    def ask_file(s, save):
        try:
            import tkinter as tk; from tkinter import filedialog
            r = tk.Tk(); r.withdraw()
            kw = dict(filetypes=[('JSON', '*.json')], defaultextension='.json')
            p = filedialog.asksaveasfilename(**kw) if save else filedialog.askopenfilename(**kw)
            r.destroy(); return p or None
        except Exception:
            return None
    def draw_status(s, sc):
        pygame.draw.rect(sc, (18, 20, 26), s.status); lab = s.views['lab'].get(); sp = lab.system_power()
        if not hasattr(s, '_ver'): from . import versions; s._ver = versions.short()
        vr = U.font(11).size(s._ver)[0]; text(sc, s._ver, (sc.get_width() - vr - 8, s.status.y + 5), (110, 116, 130), 11)
        if not getattr(lab, 'running', False):
            text(sc, 'Питание/тепло: модель остановлена — «Лаборатория» → «Запустить» (в фоне ничего не считается)', (8, s.status.y + 4), (150, 156, 170), 12); return
        if not sp: text(sc, 'Питание: модель ещё считает…', (8, s.status.y + 4), (150, 156, 170), 12); return
        b = s.views['lab'].board(); bp = lab.boards.get(b.id) if b else None
        t = 'СИСТЕМА %d плат: %.2f Вт · %.2f А при 5 В · LED %.2f Вт · потери %.2f Вт · энергия %.2f Вт·ч · БП ≥ %.0f Вт / %.1f А (текущий режим +25 %%)' % (
            sp['n'], sp['w'], sp['a5'], sp['p_led'], sp['loss'], sp['wh'], sp['psu_w'], sp['psu_a'])
        if bp is not None and hasattr(bp, 'pw'):
            pw = bp.pw
            t += '   |   %08X: %.2f Вт, USB %.2f А, БАТ %+.2f А, LED_4V1 %.2f А, AON %.0f мА, η %.0f %%' % (b.id, pw['total'], pw['usb_a'], pw['bat_a'], pw['i_led'], pw['i_aon'] * 1e3, pw['eff'] * 100)
        text(sc, t, (8, s.status.y + 4), (200, 220, 200), 12)
    def run(s):
        clock = pygame.time.Clock(); t_last = time.perf_counter(); frame = 0
        while True:
            ev = pygame.event.get()
            for e in ev:
                if e.type == pygame.QUIT: return
                if e.type == pygame.VIDEORESIZE: s.layout(); [setattr(v, 'surf_key', None) for v in s.views.values() if hasattr(v, 'surf_key')]
            s.ui.begin(ev)
            now = time.perf_counter(); dt = min(0.25, now - t_last); t_last = now
            s.fps_meas = 0.95 * s.fps_meas + 0.05 / max(dt, 1e-4)
            s.dt = dt
            if dt > 0.2: __import__('logging').warning('slow frame %.0f ms (tab %s, %d boards)', dt * 1000, s.tab, len(s.views['system'].w.boards))
            sv = s.views['system']; sv.tick(dt)
            tr = s.views['test'].runner()
            if not sv.w.paused and tr.running: s.views['test'].tick()   # tests only when started explicitly
            s.views['lab'].tick(dt)                                     # electrothermal model runs in every tab
            v = s.views[s.tab]
            sc = s.screen; sc.fill((24, 26, 32))
            # side panel + top bar first (they consume clicks), then the view gets the events
            pygame.draw.rect(sc, (30, 33, 40), s.side)
            v.panel(sc, s.ui, s.side)
            x = 8
            for t in TABS:
                if s.ui.button(sc, (x, 4, 100, 28), T(TAB_KEYS[t]), on=s.tab == t): s.tab = t
                x += 104
            if s.ui.button(sc, (x + 10, 4, 44, 28), T('lang')): U.LANG[0] = 'en' if U.LANG[0] == 'ru' else 'ru'
            text(sc, '%s   %.0f fps' % (T('title'), s.fps_meas), (x + 70, 11), (150, 156, 170), 13)
            for e in ev: v.event(e, s.view)
            v.draw(sc, s.view)
            s.draw_status(sc)
            pygame.display.flip()
            frame += 1
            if getattr(s, 'hook', None) and s.hook(s, frame, dt, time.perf_counter() - now) == 'quit': return
            for (fr, tab, path, act) in list(s.shots):
                if frame == fr:
                    if act: act(s)
                    if tab: s.tab = tab
                    if path: pygame.image.save(sc, path); print('shot', path, flush=True)
            if s.shots and frame > max(f for f, *_ in s.shots): return
            # idle when minimised / in the background: no need to burn a full core
            clock.tick(60 if getattr(s, 'hook', None) or (pygame.display.get_active() and pygame.key.get_focused()) else 12)

def main():
    a = sys.argv[1:]
    lang = 'en' if '--en' in a else 'ru'
    if '--autotest' in a:
        i = a.index('--autotest'); out = a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else None
        from . import autotest; sys.exit(autotest.run(out, headless='--headless' in a))
    if '--shots' in a:
        from . import selftest; selftest.run(a[a.index('--shots') + 1]); return
    import os, traceback, logging
    d = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'LED_Simulator'); os.makedirs(d, exist_ok=True)
    logging.basicConfig(filename=os.path.join(d, 'led_sim.log'), level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', force=True)
    logging.info('start %s', sys.argv)
    try: App(lang=lang).run()
    except Exception:
        logging.error('crash\n%s', traceback.format_exc()); raise
