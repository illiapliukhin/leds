#!/usr/bin/env python3
"""3D model of the wire grid: STEP + GLB (cadquery) and PNG renders (matplotlib). Coordinates mm, LED faces +Z.
Row r (1..32) wire along X at y = (32-r)*P, column c along Y at x = (c-1)*P; columns on top of rows."""
import math, sys, numpy as np, cadquery as cq
from params import *
FULL = '--sub' not in sys.argv and not globals().get('SUB')
n = N if FULL else 4
P = PITCH; zr = ROW_WIRE_D / 2; zc = ROW_WIRE_D + COL_WIRE_D / 2
L0 = -RAIL_GAP; L1 = SPAN + RAIL_GAP
def cyl(d, p0, axis, L):
    return cq.Solid.makeCylinder(d / 2, L, cq.Vector(*p0), cq.Vector(*axis))
def led(x, y):
    # anode pad on row at (x+1.1, y), cathode on column at (x, y+1.1): body on the diagonal, top at z ~ 1.1
    b = cq.Solid.makeBox(1.6, 0.8, 0.6, cq.Vector(-0.8, -0.4, 0)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), -45)
    return b.translate(cq.Vector(x + 0.55, y + 0.55, ROW_WIRE_D + 0.05))
def lens(x, y):
    return cq.Solid.makeBox(1.0, 0.5, 0.05, cq.Vector(-0.5, -0.25, 0)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), -45).translate(cq.Vector(x + 0.55, y + 0.55, ROW_WIRE_D + 0.65))
def rowy(r): return (n - 1 - r) * P
rows = [cyl(ROW_WIRE_D, (L0 - 20, rowy(r), zr), (1, 0, 0), (L1 - L0) + 20) for r in range(n)]
cols = [cyl(COL_WIRE_D, (c * P, L0 - 20, zc), (0, 1, 0), (L1 - L0) + 20) for c in range((n))]
span = P * (n - 1)
leds = [led(c * P, rowy(r)) for r in range(n) for c in range(n)]
lenses = [lens(c * P, rowy(r)) for r in range(n) for c in range(n)]
kapton = [cq.Solid.makeBox(1.5, 1.5, 0.05, cq.Vector(c * P - 0.75, rowy(r) - 0.75, ROW_WIRE_D)) for r in range(n) for c in range(n)]
W = span + 2 * RAIL_GAP
fr = (cq.Workplane('XY').box(W + 2 * FRAME_W, W + 2 * FRAME_W, 6).faces('>Z').workplane().rect(W, W).cutThruAll()
      .translate((span / 2, span / 2, -4)).val())
rails = [cq.Solid.makeBox(8, W, 1.6, cq.Vector(L0 - 8, L0, -1.6)), cq.Solid.makeBox(8, W, 1.6, cq.Vector(L1, L0, -1.6)),
         cq.Solid.makeBox(W, 8, 1.6, cq.Vector(L0, L0 - 8, -1.6)), cq.Solid.makeBox(W, 8, 1.6, cq.Vector(L0, L1, -1.6))]
# tag board WG_TAG at the lower-left corner, behind the frame, with 2x 2x20 1.27 box headers and 4x 2x8 headers
tx, ty = L0 - FRAME_W - 70, L0 - FRAME_W - 50
tag = [cq.Solid.makeBox(60, 40, 1.6, cq.Vector(tx, ty, -10))]
hdr = [cq.Solid.makeBox(31.75, 6, 4.9, cq.Vector(tx + 4, ty + 4 + k * 10, -8.4)) for k in range(2)] + \
      [cq.Solid.makeBox(25.4 * 0.8, 8.8, 9, cq.Vector(tx + 2 + k * 14.5, ty + 26, -8.4)) for k in range(0)] + \
      [cq.Solid.makeBox(9, 25, 9, cq.Vector(tx + 40 + k * 10, ty + 2, -8.4)) for k in range(2)]
ueep = [cq.Solid.makeBox(3, 1.6, 1.1, cq.Vector(tx + 40, ty + 32, -8.4))]
ribbons = []
for k, yy in enumerate([rowy(int(n * 0.25)), rowy(int(n * 0.75))]):
    ribbons.append(cq.Solid.makeBox(abs(L0 - 8 - (tx + 50)) + 1, 20.3 if FULL else 4, 0.9, cq.Vector(tx + 50, yy - 10, -3)))
PARTS = []
asm = cq.Assembly(name='wire_grid_32x32')
def add(name, solids, rgb):
    PARTS.append((name, solids, rgb)); asm.add(cq.Workplane().add(cq.Compound.makeCompound(solids)), name=name, color=cq.Color(*rgb))
add('row_wires_0p5_enamel', rows, (0.80, 0.45, 0.20)); add('col_wires_0p25_enamel', cols, (0.55, 0.30, 0.12))
add('leds_NCD0603W1', leds, (0.97, 0.95, 0.85)); add('led_emitters', lenses, (1.0, 0.85, 0.2))
add('kapton_crossings', kapton, (0.9, 0.55, 0.1)); add('frame', [fr], (0.85, 0.78, 0.6)); add('rails_fr4', rails, (0.2, 0.45, 0.2))
add('tag_WG_TAG', tag, (0.1, 0.4, 0.1)); add('tag_headers', hdr + ueep, (0.1, 0.1, 0.1)); add('fan_ribbons', ribbons, (0.6, 0.6, 0.65))
if __name__ == '__main__':
  stem = 'wire_grid_32x32' if FULL else 'out/wire_grid_detail'
  asm.save(stem + '.step'); asm.save(stem + '.glb')
  print('saved', stem)
