import json, sys
from PIL import Image, ImageDraw
D = json.load(open('fixed.json')); R = json.load(open('routes.json'))
x0, y0, x1, y1 = [float(v) for v in sys.argv[1:5]] if len(sys.argv) > 4 else (0, 0, 160, 160)
s = 1600 / max(x1 - x0, y1 - y0)
im = Image.new('RGB', (int((x1 - x0) * s), int((y1 - y0) * s)), 'black'); d = ImageDraw.Draw(im)
P = lambda x, y: ((x - x0) * s, (y - y0) * s)
col = {'F.Cu': (120, 40, 40), 'In1.Cu': (60, 60, 120), 'In2.Cu': (0, 200, 0), 'B.Cu': (60, 140, 255)}
for t in D['tracks']: d.line([P(t['x0'], t['y0']), P(t['x1'], t['y1'])], fill=col[t['layer']], width=max(1, int(t['w'] * s)))
for p in D['pads']:
    if 'B.Cu' in p['layers']: d.rectangle([P(p['bx0'], p['by0']), P(p['bx1'], p['by1'])], fill=(200, 200, 0))
for t in R['tracks']: d.line([P(t[0], t[1]), P(t[2], t[3])], fill=col[t[5]], width=max(1, int(t[4] * s)))
for v in D['vias']: x, y = P(v['x'], v['y']); d.ellipse([x - .225 * s, y - .225 * s, x + .225 * s, y + .225 * s], fill=(150, 150, 150))
for v in R['vias']: x, y = P(v[0], v[1]); d.ellipse([x - .225 * s, y - .225 * s, x + .225 * s, y + .225 * s], fill=(255, 255, 255))
im.save(sys.argv[5] if len(sys.argv) > 5 else '/tmp/routes.png')
