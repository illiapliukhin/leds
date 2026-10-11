"""Build-time exporter: .kicad_pcb (KiCad 6..10 s-expression) -> compact gzipped JSON for the PCB inspector.
Pure Python, no KiCad needed. Exports: outline, footprints (ref/value/pos/rot/side), pads (abs pos, size, shape,
layers, net, pin), tracks (segments + arcs as polylines, layer, width, net), vias, zone outlines (net, layer).
Usage: python export_pcb.py board.kicad_pcb out.json.gz "Title" """
import gzip, json, math, re, sys

TOK = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')

def parse(text):
    stack, cur = [], []
    for m in TOK.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append(cur); cur = []
        elif t == ')':
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t[1:-1].replace('\\"', '"') if t[0] == '"' else t)
    return cur[0]

def kids(n, name): return [c for c in n if isinstance(c, list) and c and c[0] == name]
def kid(n, name):
    for c in n:
        if isinstance(c, list) and c and c[0] == name: return c
def fl(v): return float(v)
LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']

def rot(x, y, deg):
    a = math.radians(-deg); c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c

def arc_pts(s, m, e, n=8):
    (x1, y1), (x2, y2), (x3, y3) = s, m, e
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9: return [s, e]
    ux = ((x1*x1+y1*y1)*(y2-y3)+(x2*x2+y2*y2)*(y3-y1)+(x3*x3+y3*y3)*(y1-y2))/d
    uy = ((x1*x1+y1*y1)*(x3-x2)+(x2*x2+y2*y2)*(x1-x3)+(x3*x3+y3*y3)*(x2-x1))/d
    r = math.hypot(x1-ux, y1-uy)
    a1, a2, a3 = (math.atan2(p[1]-uy, p[0]-ux) for p in (s, m, e))
    def norm(a): return (a + 2*math.pi) % (2*math.pi)
    sweep = norm(a3 - a1); ccw_mid = norm(a2 - a1) < sweep
    if not ccw_mid: sweep = sweep - 2*math.pi
    return [(ux + r*math.cos(a1 + sweep*i/n), uy + r*math.sin(a1 + sweep*i/n)) for i in range(n+1)]

def r3(v): return round(v, 3)

def export(path, title):
    root = parse(open(path, encoding='utf-8').read())
    nets = {}
    for n in kids(root, 'net'):
        if len(n) >= 3: nets[n[1]] = n[2]
    def netname(node):
        nn = kid(node, 'net')
        if not nn: return ''
        if len(nn) >= 3: return nn[2]
        return nets.get(nn[1], nn[1]) if len(nn) == 2 and nn[1].isdigit() else (nn[1] if len(nn) == 2 else '')
    out = {'title': title, 'outline': [], 'fps': [], 'pads': [], 'tracks': [], 'vias': [], 'zones': []}
    for g in kids(root, 'gr_line') + kids(root, 'gr_arc') + kids(root, 'gr_rect') + kids(root, 'gr_circle') + kids(root, 'gr_poly'):
        ly = kid(g, 'layer')
        if not ly or ly[1] != 'Edge.Cuts': continue
        if g[0] == 'gr_line':
            s, e = kid(g, 'start'), kid(g, 'end'); out['outline'].append([[fl(s[1]), fl(s[2])], [fl(e[1]), fl(e[2])]])
        elif g[0] == 'gr_arc' and kid(g, 'mid'):
            s, m, e = kid(g, 'start'), kid(g, 'mid'), kid(g, 'end')
            out['outline'].append([list(p) for p in arc_pts((fl(s[1]), fl(s[2])), (fl(m[1]), fl(m[2])), (fl(e[1]), fl(e[2])))])
        elif g[0] == 'gr_rect':
            s, e = kid(g, 'start'), kid(g, 'end'); x1, y1, x2, y2 = fl(s[1]), fl(s[2]), fl(e[1]), fl(e[2])
            out['outline'].append([[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]])
        elif g[0] == 'gr_circle':
            c, e = kid(g, 'center'), kid(g, 'end'); cx, cy = fl(c[1]), fl(c[2]); r = math.hypot(fl(e[1]) - cx, fl(e[2]) - cy)
            out['outline'].append([[cx + r*math.cos(k*math.pi/16), cy + r*math.sin(k*math.pi/16)] for k in range(33)])
        elif g[0] == 'gr_poly':
            pts = kid(g, 'pts'); P = [[fl(p[1]), fl(p[2])] for p in kids(pts, 'xy')]
            out['outline'].append(P + P[:1])
    for fp in kids(root, 'footprint') + kids(root, 'module'):
        at = kid(fp, 'at'); fx, fy = fl(at[1]), fl(at[2]); fr = fl(at[3]) if len(at) > 3 else 0
        side = 'B' if (kid(fp, 'layer') or ['', 'F.Cu'])[1].startswith('B') else 'F'
        ref, val = '', ''
        for p in kids(fp, 'property'):
            if p[1] == 'Reference': ref = p[2]
            if p[1] == 'Value': val = p[2]
        for t in kids(fp, 'fp_text'):
            if t[1] == 'reference': ref = t[2]
            if t[1] == 'value': val = t[2]
        fi = len(out['fps']); out['fps'].append([ref, val, r3(fx), r3(fy), fr, side])
        for pd in kids(fp, 'pad'):
            pa = kid(pd, 'at'); px, py = fl(pa[1]), fl(pa[2]); pr = fl(pa[3]) if len(pa) > 3 else fr
            dx, dy = rot(px, py, fr); sz = kid(pd, 'size')
            lys = kid(pd, 'layers') or ['layers']
            L = 0
            for l in lys[1:]:
                if l in ('*.Cu', 'F&B.Cu'): L |= 15 if l == '*.Cu' else 9
                elif l in LAYERS: L |= 1 << LAYERS.index(l)
            if not L: continue
            out['pads'].append([fi, pd[1], r3(fx + dx), r3(fy + dy), r3(fl(sz[1])), r3(fl(sz[2])), pr, pd[3] if len(pd) > 3 else 'rect', L, netname(pd)])
    for tr in kids(root, 'segment') + kids(root, 'arc'):
        ly = kid(tr, 'layer')[1]
        if ly not in LAYERS: continue
        s, e = kid(tr, 'start'), kid(tr, 'end')
        S, E = (fl(s[1]), fl(s[2])), (fl(e[1]), fl(e[2]))
        pts = arc_pts(S, (fl(kid(tr, 'mid')[1]), fl(kid(tr, 'mid')[2])), E, 6) if tr[0] == 'arc' else [S, E]
        out['tracks'].append([LAYERS.index(ly), r3(fl(kid(tr, 'width')[1])), netname(tr), [r3(c) for p in pts for c in p]])
    for v in kids(root, 'via'):
        a = kid(v, 'at'); out['vias'].append([r3(fl(a[1])), r3(fl(a[2])), r3(fl(kid(v, 'size')[1])), netname(v)])
    for z in kids(root, 'zone'):
        nm = netname(z) or (kid(z, 'net_name') or ['', ''])[1]
        lyn = kid(z, 'layer'); lys = [lyn[1]] if lyn else (kid(z, 'layers') or ['x'])[1:]
        poly = kid(z, 'polygon')
        if not poly: continue
        P = [r3(c) for p in kids(kid(poly, 'pts'), 'xy') for c in (fl(p[1]), fl(p[2]))]
        for l in lys:
            if l in LAYERS: out['zones'].append([LAYERS.index(l), nm, P])
    return out

if __name__ == '__main__':
    d = export(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else sys.argv[1])
    with gzip.open(sys.argv[2], 'wt', encoding='utf-8') as f: json.dump(d, f, separators=(',', ':'))
    print(sys.argv[2], {k: len(v) for k, v in d.items() if isinstance(v, list)})
