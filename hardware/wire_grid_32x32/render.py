#!/usr/bin/env python3
"""PNG renders: close-up (4x4 nodes, tessellated cadquery solids) + full-grid overview (lines/markers, lit pattern)."""
import sys, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.argv.append('--sub')
import gen_3d as g
from params import *
def tris(solid):
    v, t = solid.tessellate(0.05, 0.3); v = np.array([[p.x, p.y, p.z] for p in v]); return v[np.array(t)]
def closeup(fn, elev, azim, lim):
    fig = plt.figure(figsize=(10, 8), dpi=120); ax = fig.add_subplot(111, projection='3d'); ax.set_proj_type('persp', 0.6)
    light = np.array([0.3, -0.4, 1.0]); light /= np.linalg.norm(light)
    for name, solids, rgb in g.PARTS:
        if name in ('frame', 'rails_fr4', 'tag_WG_TAG', 'tag_headers', 'fan_ribbons'): continue
        import cadquery as cq
        box = cq.Solid.makeBox(lim[0][1] - lim[0][0], lim[1][1] - lim[1][0], 20, cq.Vector(lim[0][0], lim[1][0], -10))
        cl = [s.intersect(box) for s in solids]; cl = [c for c in cl if c.Volume() > 1e-6]
        if not cl: continue
        T = np.concatenate([tris(c) for c in cl])
        nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        sh = 0.45 + 0.55 * np.abs(nrm @ light)
        ax.add_collection3d(Poly3DCollection(T, facecolors=np.clip(np.array(rgb)[None] * sh[:, None], 0, 1), linewidths=0, alpha=0.45 if name.startswith('kapton') else 1.0))
    ax.set_xlim(*lim[0]); ax.set_ylim(*lim[1]); ax.set_zlim(-2, 2 + (lim[0][1] - lim[0][0]) * 0.15)
    ax.set_box_aspect((lim[0][1] - lim[0][0], lim[1][1] - lim[1][0], 4 + (lim[0][1] - lim[0][0]) * 0.15)); ax.view_init(elev, azim); ax.set_axis_off()
    ax.set_title('wire_grid_32x32 — узел: строка Ø%.2f, столбец Ø%.2f, %s, каптон на кресте' % (ROW_WIRE_D, COL_WIRE_D, LED), fontsize=10)
    fig.savefig(fn, bbox_inches='tight', facecolor='white'); plt.close(fig)
def overview(fn):
    fig = plt.figure(figsize=(11, 9), dpi=120); ax = fig.add_subplot(111, projection='3d')
    L0, L1 = -RAIL_GAP, SPAN + RAIL_GAP
    for i in range(N):
        y = i * PITCH; ax.plot([L0 - 20, L1 + 5], [y, y], [0, 0], color='#c87533', lw=0.8)
        ax.plot([y, y], [L0 - 20, L1 + 5], [0.6, 0.6], color='#7a4020', lw=0.4)
    yy, xx = np.mgrid[0:N, 0:N]; r = N - 1 - yy
    on = ((xx - 15.5) ** 2 + (r - 15.5) ** 2 < 14 ** 2) & ((xx + r) % 4 < 2)
    ax.scatter(xx * PITCH + 0.5, yy * PITCH + 0.5, 1.2, c=np.where(on.ravel(), '#ffe680', '#f4f0e0'), s=np.where(on.ravel(), 14, 3), edgecolors='none', depthshade=False)
    W = L1 - L0 + 2 * FRAME_W; o = L0 - FRAME_W
    for a, b in [((o, o), (o + W, o)), ((o + W, o), (o + W, o + W)), ((o + W, o + W), (o, o + W)), ((o, o + W), (o, o))]:
        ax.plot([a[0], b[0]], [a[1], b[1]], [-4, -4], color='#b09060', lw=6)
    tx, ty = L0 - FRAME_W - 70, L0 - FRAME_W - 50
    ax.plot([tx, tx + 60, tx + 60, tx, tx], [ty, ty, ty + 40, ty + 40, ty], [-10] * 5, color='#1a6a1a', lw=3)
    ax.text(tx, ty - 12, -10, 'WG_TAG / → breakout или v15', fontsize=8)
    for yv in (23.5 * PITCH, 7.5 * PITCH): ax.plot([L0 - 8, tx + 50], [yv, ty + 30], [-3, -10], color='gray', lw=3, alpha=0.7)
    for xv in (7.5 * PITCH, 23.5 * PITCH): ax.plot([xv, tx + 55], [L0 - 8, ty + 20], [-3, -10], color='gray', lw=3, alpha=0.7)
    ax.set_box_aspect((1, 1, 0.12)); ax.view_init(38, -62); ax.set_axis_off(); ax.set_zlim(-12, 30)
    ax.set_title('wire_grid_32x32: 1024 × %s, шаг %.0f мм, окно %.0f мм (тестовый узор)' % (LED, PITCH, SPAN + 2 * RAIL_GAP), fontsize=11)
    fig.savefig(fn, bbox_inches='tight', facecolor='white'); plt.close(fig)
closeup('renders/node_closeup_iso.png', 35, -55, ((-4, 14), (-4, 14)))
closeup('renders/node_closeup_top.png', 89, -90, ((-3, 13), (-3, 13)))
overview('renders/grid_overview.png')
print('ok')
