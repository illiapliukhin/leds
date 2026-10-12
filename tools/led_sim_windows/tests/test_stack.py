"""Headless regression: presets converge (one leader per group, all placed, no overlaps, canvas size),
unplug/replug, Type A stack cable split, C/Python compute_grid agree, frame lock."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ledsim.world import World
from ledsim.stack_model import LEAD, FOLLOW, compute_grid_py
from ledsim import host

from ledsim import stack_model
PROF = sys.argv[1] if len(sys.argv) > 1 else 'hw+fix'; stack_model.set_profile(PROF); print('timing profile', PROF)
K = 800 if PROF == 'sim' else 60
def settle(w, ms=None): w.step(max(ms or 0, 4000 + len(w.boards) * K))
def check(w, expect_groups, canvas=None, tag=''):
    gs = w.groups(); ok = len(gs) == expect_groups
    for g in gs:
        leads = [b for b in g if b.node.state == LEAD]
        ok &= len(leads) == 1 and leads[0].id == min(b.id for b in g)
        ok &= all(b.node.me[0] for b in g)
        ok &= len({(b.node.me[1], b.node.me[2]) for b in g}) == len(g)
        if canvas and len(g) > 1: ok &= '%dx%d' % (g[0].node.W * 32, g[0].node.H * 32) == canvas
        fr = [b.node.frame for b in g]; ok &= max(fr) - min(fr) <= 1
    print('%-28s %s  groups=%d %s' % (tag, 'PASS' if ok else 'FAIL', len(gs), [('%dx%d' % (g[0].node.W * 32, g[0].node.H * 32), len(g)) for g in gs]))
    return ok

res = []
for (c, r, cv) in [(1, 1, '32x32'), (3, 2, '96x64'), (6, 1, '192x32'), (2, 2, '64x64')]:
    w = World(); w.preset(c, r); t = time.time(); settle(w); res.append(check(w, 1, cv, 'preset %dx%d (%.1fs wall)' % (c, r, time.time() - t)))
w = World(); w.preset(3, 2); settle(w)
b = w.boards[0]; w.set_power(b, False); settle(w, 3000); res.append(check(w, 1, None, 'unplug board 0 of 3x2'))
w.set_power(b, True); settle(w, 4000); res.append(check(w, 1, '96x64', 'replug board 0'))
c = w.cables[0]; c.plugged = False; w.dirty(); settle(w, 3000); res.append(check(w, 1, '96x64', 'unplug one cable (ring)'))
w = World(); w.preset(6, 1); settle(w); w.cables[2].type = 'A'; w.dirty(); settle(w, 4000); res.append(check(w, 2, None, 'Type A stack cable 6x1'))
w = World(); w.preset(10, 10); t = time.time(); settle(w, 12000); res.append(check(w, 1, '320x320', '10x10 MAXB=%d' % __import__('ledsim.host', fromlist=['MAXB']).MAXB + '  (%.1fs wall)' % (time.time() - t)))
# C vs Python compute_grid
w = World(); w.preset(4, 4); settle(w); L = [b for b in w.boards if b.node.state == LEAD][0].node
a = host.compute_grid(L.id, L.members, L.edges); p = compute_grid_py(L.id, L.members, L.edges)
eq = a[1:] == p[1:] and all(tuple(a[0][k]) == tuple(p[0][k]) for k in a[0]); print('compute_grid C == Python   ', 'PASS' if eq else 'FAIL'); res.append(eq)
print('crc8(01 02 03) = 0x%02X' % host.crc8([1, 2, 3]))
print('ALL PASS' if all(res) else 'SOME FAIL'); sys.exit(0 if all(res) else 1)
