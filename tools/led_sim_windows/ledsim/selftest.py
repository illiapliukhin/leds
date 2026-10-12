"""Scripted screenshots of every view (LED_Simulator.exe --shots DIR, tests/shots.py)."""
import os
from .app import App

def run(out):
    os.makedirs(out, exist_ok=True)
    def P(n): return os.path.join(out, n)
    def fault(a):
        w = a.views['system'].w; w.panels[1].ffc = 'A'; w.panels[4].open_col = 9; w.set_power(w.boards[5], False)
    def pcbsel(a):
        v = a.views['boards']; p = v.pcb(); i = next(i for i, pd in enumerate(p.pads) if p.fps[pd[0]][0] == 'J_ROW1' and pd[1] == '5')
        v.lock = p.pads[i][9]; v.trace = v.do_trace(('pad', i))
    def panelsel(a): a.views['panels'].lock = a.views['boards'].trace['net']; a.views['panels'].cur = 0
    def big(a): a.views['system'].w.preset(10, 10); a.views['system'].fit(a.view); a.views['system'].apply_global()
    def cube(a): a.views['cube'].N = 16; a.views['cube']._grid(); a.views['cube'].demo = 0
    def cube2(a): a.views['cube'].demo = 3
    def stress(a): a.views['lab'].get().apply_preset('Стресс')
    def short(a): a.views['lab'].get().apply_preset('КЗ батареи')
    def surge(a): a.views['lab'].get().reset_damage(); a.views['lab'].get().apply_preset('Скачок 12 В на USB')
    def models(a): a.views['models'].report = __import__('ledsim.physcheck', fromlist=['run']).run()
    def test(a): a.views['test'].runner().start(list(a.views['system'].w.boards), 32)
    shots = [(100, 'lab', None, stress), (230, 'lab', P('10_lab_stress.png'), None), (232, 'lab', None, surge), (290, 'lab', P('11_lab_surge12V.png'), None),
             (292, 'lab', None, short), (340, 'lab', P('12_lab_batshort.png'), None), (342, 'models', None, models), (350, 'models', P('13_models.png'), None),
             (352, 'test', None, test), (900, 'test', P('14_test.png'), None)]
    old = [(240, None, P('01_system_3x2.png'), None), (300, None, None, fault), (560, None, P('02_faults.png'), None),
             (570, 'boards', None, pcbsel), (600, 'boards', P('03_pcb_board_v13.png'), None),
             (610, 'panels', None, panelsel), (640, 'panels', P('04_pcb_panel_full.png'), None),
             (650, 'cube', None, cube), (720, 'cube', P('05_cube_shapes.png'), None), (725, 'cube', None, cube2), (790, 'cube', P('06_cube_sphere.png'), None),
             (800, 'system', None, big), (1300, 'system', P('07_system_10x10.png'), None)]
    def amb(a):
        c = a.views['cube']; c.N = 16; c._grid(); c.demo = 0; c.show_hw = False; c.snap('w2'); c.cam.yaw, c.cam.pitch = c.READ['w2']; c.cam.goal = None; c.cam.dist = c.cam.dist_t = 8.0
    def hw(a):
        c = a.views['cube']; c.N = 8; c._grid(); c.demo = 7; c.show_hw = True; c.cam.reset(); c.cam.dist = c.cam.dist_t = 7.0; c.cam.pitch = 0.5
    def rul(a):
        sv = a.views['system']; sv._st(); sv.r_grid = True; sv.r_meas = 'armed'; sv.r_pts = [(0, 0), (320, 160)]
    shots += [(2400, 'cube', None, amb), (2460, 'cube', P('15_cube_ambigram_side.png'), None), (2462, 'cube', None, hw), (2540, 'cube', P('16_cube_electronics.png'), None),
              (2542, 'system', None, rul), (2600, 'system', P('17_system_rulers.png'), None)]
    shots += [(f + 1000, t, pth, act) for (f, t, pth, act) in old]
    App(shots=shots).run()

def run_old(out): pass
