"""Scripted screenshots of every view (used on Linux/Wine to verify the build)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ledsim.app import App
out = sys.argv[1] if len(sys.argv) > 1 else 'shots'
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
shots = [(240, None, P('01_system_3x2.png'), None), (300, None, None, fault), (560, None, P('02_faults.png'), None),
         (570, 'boards', None, pcbsel), (600, 'boards', P('03_pcb_board_v12.png'), None),
         (610, 'panels', None, panelsel), (640, 'panels', P('04_pcb_panel_full.png'), None),
         (650, 'cube', None, cube), (720, 'cube', P('05_cube_shapes.png'), None), (725, 'cube', None, cube2), (790, 'cube', P('06_cube_sphere.png'), None),
         (800, 'system', None, big), (1300, 'system', P('07_system_10x10.png'), None)]
App(shots=shots).run()
