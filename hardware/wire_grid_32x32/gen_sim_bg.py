#!/usr/bin/env python3
"""Background for the bring-up sim (--panel wire): 340 x 370 mm at 4 px/mm, dark bench, copper row wires, enamel column wires, breakout tab."""
from PIL import Image, ImageDraw
from params import *
K = 4; W, H = int(WIRE_LEN * K), int((WIRE_LEN + 30) * K)
im = Image.new('RGB', (W, H), (16, 18, 20)); d = ImageDraw.Draw(im)
for i in range(N):
    y = (RAIL_GAP + i * PITCH) * K; d.line([(0, y), (W, y)], fill=(170, 100, 50), width=2)
for i in range(N):
    x = (RAIL_GAP + i * PITCH) * K; d.line([(x, 0), (x, WIRE_LEN * K)], fill=(110, 60, 30), width=1)
d.rectangle([(0, WIRE_LEN * K), (W - 1, H - 1)], fill=(30, 70, 30))
im.save('renders/wire_sim_bg.png'); print('ok')
