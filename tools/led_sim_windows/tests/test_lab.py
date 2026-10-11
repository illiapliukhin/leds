"""Scenario runs of the Лаборатория presets on one board (headless): prints the lab log."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame; pygame.init()
from ledsim.world import World
from ledsim.phys.lab import Lab
for preset, secs in (('Норма', 4), ('Стресс', 6), ('Жара', 6), ('Скачок 12 В на USB', 2), ('КЗ батареи', 2), ('Разряд', 6)):
    w = World(); w.preset(1, 1); w.step(1500); lab = Lab(w); lab.sel = w.boards[0]
    lab.apply_preset(preset); lab.p['time_k'] = 60
    t0 = time.time()
    for k in range(int(secs * 10)):
        w.step(10); w.update_panels(); lab.tick(0.1)
    sm = lab.summary(w.boards[0])
    print('==== %s (%.1fs wall): rails %s' % (preset, time.time() - t0, {k: round(v, 3) for k, v in sm['rails'].items()}))
    print('     hot %s %.1f °C, panel %.1f °C, cell %.1f °C, I_cell %.2f A, failed %s, first limit %s, dead %s' % (sm['hot'][0], sm['hot'][1], sm['t_panel'], sm['t_cell'], sm['i_cell'], sm['failed'], sm['first'], sm['dead']))
    for e in lab.events:
        if e['level'] != 'DEBUG': print('    %7.3f %-5s %s' % (e['t'], e['level'], e['msg']))
