"""ctypes bridge to led_host (the real firmware sources compiled for the host: host/led_host.c)."""
import ctypes, os, sys
import numpy as np

def base_dir():
    if getattr(sys, '_MEIPASS', None): return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def data_path(*p): return os.path.join(base_dir(), 'data', *p)

def _load():
    names = ['led_host.dll'] if os.name == 'nt' else ['libledhost.so']
    for d in (base_dir(), os.path.join(base_dir(), 'host'), os.path.join(base_dir(), 'build')):
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p): return ctypes.CDLL(p)
    raise SystemExit('led_host library not found (build host/led_host.c first: see README)')

L = _load()
U8P = ctypes.POINTER(ctypes.c_uint8)
L.sim_demo_name.restype = ctypes.c_char_p
L.sim_canvas_name.restype = ctypes.c_char_p
L.sim_demo_render.argtypes = [ctypes.c_int, ctypes.c_uint32, U8P]
L.sim_render_tile.argtypes = [ctypes.c_int] * 7 + [ctypes.c_uint32, U8P]
L.sim_duty_lut.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.POINTER(ctypes.c_float)]
L.sim_compute_grid.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                               ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
L.sim_crc8.argtypes = [U8P, ctypes.c_int]
L.sim_demo_for_frame.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_int]

DEMOS = [L.sim_demo_name(i).decode() for i in range(1, L.sim_demo_count())]      # demo.c (single panel)
CANVAS = [L.sim_canvas_name(i).decode() for i in range(L.sim_canvas_count())]   # stack.c (shared canvas)
CANVAS_SECS = [L.sim_canvas_secs(i) for i in range(len(CANVAS))]
MAXB = 16                                                                        # stack.c MAXB

def demo_frame(mode, t):
    a = np.zeros(1024, np.uint8); L.sim_demo_render(mode, t & 0xFFFFFFFF, a.ctypes.data_as(U8P)); return a.reshape(32, 32)

def tile(x, y, rot, W, H, demo, fps, f):
    a = np.zeros(1024, np.uint8); L.sim_render_tile(x, y, rot, W, H, demo, fps, f & 0xFFFFFFFF, a.ctypes.data_as(U8P)); return a.reshape(32, 32)

def demo_for_frame(demo, f, fps): return L.sim_demo_for_frame(demo, f & 0xFFFFFFFF, fps)

_lut = {}
def duty_lut(br, gamma):
    k = (int(br), round(float(gamma), 2))
    if k not in _lut:
        a = (ctypes.c_float * 256)(); L.sim_duty_lut(k[0], k[1], a); _lut[k] = np.array(a, np.float32)
        if len(_lut) > 64: _lut.pop(next(iter(_lut)))
    return _lut[k]

def compute_grid(leader, ids, edges):
    """stack.c compute_grid(); ids <= MAXB. edges = [(a, as, b, bs)]. -> ({id: (placed,x,y,rot)}, W, H)"""
    n = len(ids); ia = (ctypes.c_uint32 * n)(*ids)
    flat = [v for e in edges for v in e] or [0]
    ea = (ctypes.c_uint32 * len(flat))(*flat); out = (ctypes.c_int * (4 * n))(); wh = (ctypes.c_int * 2)()
    L.sim_compute_grid(leader, n, ia, len(edges), ea, out, wh)
    return {ids[i]: tuple(out[4 * i:4 * i + 4]) for i in range(n)}, wh[0], wh[1]

def crc8(b):
    a = (ctypes.c_uint8 * len(b))(*b); return L.sim_crc8(a, len(b))
