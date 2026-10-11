#!/usr/bin/env python3
"""Generator for mono_panel_32x32_lattice: see-through 32x32 LED lattice panel for LED cubes.
Electrically/pin compatible with mono_panel_32x32 (same FH12-40S-0.5SH receptacles on B.Cu, same pinout,
LED Dn = ROW_r x COL_c with n = 32(r-1)+c, pad 2 = ROW_rr_ANODE, pad 1 = COL_cc).
Run with the KiCad 10 AppImage python:  source hardware/tools/kicad10_env.sh && python3.11 gen_lattice.py
Layer plan
  F.Cu : LED pads, row buses on the horizontal bars, row feeds in the side frames (twinned on B.Cu) and the
         south row band.
  B.Cu : column buses on the vertical bars, south column band + drops to J_COL, short row drops to J_ROW pads,
         side-frame twins of the row feeds, both FFC receptacles.
"""
import json, math, os, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as M

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'mono_panel_32x32', 'mono_panel_32x32.kicad_pcb')
OUT = os.path.join(HERE, 'mono_panel_32x32_lattice.kicad_pcb')
FPLIB = os.path.join(os.environ.get('KICAD10_ROOT', '/workspace/.kicad10/squashfs-root'), 'usr/share/kicad/footprints/MountingHole.pretty')

# ------------------------------------------------------------------ parameters (mm)
N = 32
PITCH = 5.2            # LED pitch, same voxel pitch in X/Y (and Z when stacked with 5.2 mm layer pitch)
BAR_H = 1.0            # horizontal (row) bar width
BAR_V = 1.3            # vertical (column) bar width: carries the 0603 LED (0.8 mm pad) + 0.25 edge clearance each side
R_CORNER = 0.5         # window corner radius (>= 1.0 mm router bit / 2)
EDGE_CLR = 0.25        # designed copper-to-routed-edge clearance (JLC min 0.20)
W_ROWBAR = 0.5         # row bus on the bar (F.Cu)
W_COLBAR = 0.4         # column bus on the bar (B.Cu)
W_FEED = 0.6           # row feed in side frames (F.Cu + B.Cu twin) and south band (F.Cu)
P_FEED = 0.85          # row feed pitch
W_DROP = 0.2           # B.Cu row drop at 0.5 mm connector pitch
W_COLBAND = 0.25       # column band + column drops (10 mA)
P_COLBAND = 0.5
VIA_D, VIA_DRILL = 0.5, 0.3   # JLC standard (no extra cost)
LED_VIA_DY = 2.6       # cathode via: mid-span of the vertical bar below the node
TOP_FRAME = 7.5
HOLE_ZONE = 7.0
X0, Y0 = 50.0, 40.0    # node (row1, col1)

WIN_W = PITCH - BAR_V  # 3.9
WIN_H = PITCH - BAR_H  # 4.2
XN = [X0 + PITCH * c for c in range(N)]
YN = [Y0 + PITCH * r for r in range(N)]
XC = (XN[0] + XN[-1]) / 2
LAT_L, LAT_R = XN[0] - BAR_V / 2 - WIN_W, XN[-1] + BAR_V / 2 + WIN_W       # inner edges of the frame
LAT_T, LAT_B = YN[0] - BAR_H / 2 - WIN_H, YN[-1] + BAR_H / 2 + WIN_H

# side frame feed columns: k = 0 innermost
XW = [LAT_L - EDGE_CLR - W_FEED / 2 - P_FEED * k for k in range(16)]
XE = [LAT_R + EDGE_CLR + W_FEED / 2 + P_FEED * k for k in range(16)]
EDGE_L = XW[-1] - W_FEED / 2 - EDGE_CLR
EDGE_R = XE[-1] + W_FEED / 2 + EDGE_CLR
EDGE_T = LAT_T - TOP_FRAME

# connectors (both rot 0 on B.Cu, cable exits south, pin 1 west)
XJ_ROW, XJ_COL = XC - 14.0, XC + 14.0
def pin_x(xj, p): return xj + 0.5 * (p - 20.5)

# south frame: column band, then row band
NL = sum(1 for c in range(1, 33) if XN[c - 1] < pin_x(XJ_COL, c))
NSLOT_C = max(NL, 32 - NL)
YCB_TOP = LAT_B + EDGE_CLR + W_COLBAND / 2 + 0.25
YCB_BOT = YCB_TOP + P_COLBAND * (NSLOT_C - 1)
YRB_TOP = YCB_BOT + 0.9
YRB = [YRB_TOP + P_FEED * k for k in range(16)]         # k = 0 top
EDGE_B = YRB[-1] + W_FEED / 2 + 0.3 + HOLE_ZONE
Y_CONN = YRB[-1] + 0.6 + 4.95                           # connector courtyard top just below the row band
EDGE_TAB = Y_CONN + 3.05 + 0.35
TAB_L, TAB_R = XJ_ROW - 15.5, XJ_COL + 15.5

def build():
    src = pcbnew.LoadBoard(SRC)
    b = pcbnew.BOARD()
    ds = b.GetDesignSettings()
    b.SetCopperLayerCount(2)
    ds.SetBoardThickness(M(0.8))
    nets = {}
    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
        return nets[name]
    for r in range(1, 33): net('ROW_%02d_ANODE' % r)
    for c in range(1, 33): net('COL_%02d' % c)

    def track(p0, p1, w, layer, n):
        t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(M(p0[0]), M(p0[1]))); t.SetEnd(VECTOR2I(M(p1[0]), M(p1[1])))
        t.SetWidth(M(w)); t.SetLayer(layer); t.SetNet(net(n)); b.Add(t)
    def poly(pts, w, layer, n):
        for a, c in zip(pts, pts[1:]):
            if a != c: track(a, c, w, layer, n)
    def via(p, n):
        v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(M(p[0]), M(p[1]))); v.SetDrill(M(VIA_DRILL))
        try: v.SetWidth(pcbnew.F_Cu, M(VIA_D))
        except TypeError: v.SetWidth(M(VIA_D))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(n)); b.Add(v)
    def seg(p0, p1, layer=pcbnew.Edge_Cuts):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(VECTOR2I(M(p0[0]), M(p0[1])))
        s.SetEnd(VECTOR2I(M(p1[0]), M(p1[1]))); s.SetLayer(layer); s.SetWidth(M(0.1)); b.Add(s)
    def arc(c, r, a0, a1, layer=pcbnew.Edge_Cuts):
        pts = [(c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a))) for a in (a0, (a0 + a1) / 2, a1)]
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(*[VECTOR2I(M(x), M(y)) for x, y in pts]); s.SetLayer(layer); s.SetWidth(M(0.1)); b.Add(s)
    def rrect(x0, y0, x1, y1, r):
        seg((x0 + r, y0), (x1 - r, y0)); seg((x1, y0 + r), (x1, y1 - r)); seg((x1 - r, y1), (x0 + r, y1)); seg((x0, y1 - r), (x0, y0 + r))
        arc((x1 - r, y0 + r), r, -90, 0); arc((x1 - r, y1 - r), r, 0, 90); arc((x0 + r, y1 - r), r, 90, 180); arc((x0 + r, y0 + r), r, 180, 270)

    # ---------------- outline: frame + south connector tab (outer corners R 1.0, tab fillets R 1.0)
    R = 1.0
    pts = [(EDGE_L, EDGE_T), (EDGE_R, EDGE_T), (EDGE_R, EDGE_B), (TAB_R, EDGE_B), (TAB_R, EDGE_TAB), (TAB_L, EDGE_TAB), (TAB_L, EDGE_B), (EDGE_L, EDGE_B)]
    # convex/concave flags for fillets (clockwise on screen)
    def fillet_outline(P):
        n = len(P); segs = []
        for i in range(n):
            a, p, c = P[i - 1], P[i], P[(i + 1) % n]
            d0 = ((p[0] - a[0]), (p[1] - a[1])); d1 = ((c[0] - p[0]), (c[1] - p[1]))
            l0 = math.hypot(*d0); l1 = math.hypot(*d1); u0 = (d0[0] / l0, d0[1] / l0); u1 = (d1[0] / l1, d1[1] / l1)
            s0 = (p[0] - u0[0] * R, p[1] - u0[1] * R); s1 = (p[0] + u1[0] * R, p[1] + u1[1] * R)
            cen = (s0[0] + u1[0] * R, s0[1] + u1[1] * R)
            segs.append((s0, s1, cen))
        for i in range(n):
            s0, s1, cen = segs[i]
            a0 = math.degrees(math.atan2(s0[1] - cen[1], s0[0] - cen[0])); a1 = math.degrees(math.atan2(s1[1] - cen[1], s1[0] - cen[0]))
            mid_a = a0 + ((a1 - a0 + 180) % 360 - 180) / 2
            m = (cen[0] + R * math.cos(math.radians(mid_a)), cen[1] + R * math.sin(math.radians(mid_a)))
            sh = pcbnew.PCB_SHAPE(b); sh.SetShape(pcbnew.SHAPE_T_ARC); sh.SetArcGeometry(VECTOR2I(M(s0[0]), M(s0[1])), VECTOR2I(M(m[0]), M(m[1])), VECTOR2I(M(s1[0]), M(s1[1])))
            sh.SetLayer(pcbnew.Edge_Cuts); sh.SetWidth(M(0.1)); b.Add(sh)
            seg(s1, segs[(i + 1) % n][0])
    fillet_outline(pts)

    # ---------------- windows: 33 x 33 (outer ring opens into the frame too)
    xs = [XN[0] - PITCH] + XN; ys = [YN[0] - PITCH] + YN
    nwin = 0
    for x in xs:
        for y in ys:
            rrect(x + BAR_V / 2, y + BAR_H / 2, x + PITCH - BAR_V / 2, y + PITCH - BAR_H / 2, R_CORNER); nwin += 1

    # ---------------- LEDs (copied footprint NCD0603W1), anode pad on the node, cathode 1.55 mm south
    led_src = src.FindFootprintByReference('D1')
    for r in range(N):
        for c in range(N):
            f = pcbnew.FOOTPRINT(led_src); b.Add(f)
            f.SetReference('D%d' % (32 * r + c + 1)); f.SetOrientationDegrees(90)
            f.SetPosition(VECTOR2I(M(XN[c]), M(YN[r])))
            pa = next(p for p in f.Pads() if p.GetNumber() == '2'); pc = next(p for p in f.Pads() if p.GetNumber() == '1')
            if pc.GetPosition().y < pa.GetPosition().y:
                f.SetOrientationDegrees(-90)
            pa = next(p for p in f.Pads() if p.GetNumber() == '2')
            off = f.GetPosition() - pa.GetPosition()
            f.SetPosition(VECTOR2I(M(XN[c]), M(YN[r])) + off)
            for p in f.Pads():
                p.SetNet(net('ROW_%02d_ANODE' % (r + 1) if p.GetNumber() == '2' else 'COL_%02d' % (c + 1)))
            f.Reference().SetVisible(False)
            ycat = next(p for p in f.Pads() if p.GetNumber() == '1').GetPosition().y / 1e6
            poly([(XN[c], ycat), (XN[c], YN[r] + LED_VIA_DY)], 0.4, pcbnew.F_Cu, 'COL_%02d' % (c + 1))
            via((XN[c], YN[r] + LED_VIA_DY), 'COL_%02d' % (c + 1))

    # ---------------- connectors
    for ref, xj in (('J_ROW', XJ_ROW), ('J_COL', XJ_COL)):
        f = pcbnew.FOOTPRINT(src.FindFootprintByReference(ref)); b.Add(f)
        f.SetOrientationDegrees(0); f.SetPosition(VECTOR2I(M(xj), M(Y_CONN)))
        p1 = next(p for p in f.Pads() if p.GetNumber() == '1'); p40 = next(p for p in f.Pads() if p.GetNumber() == '40')
        if not (p1.GetPosition().x < p40.GetPosition().x and p1.GetPosition().y > f.GetPosition().y):
            for a in (180, 90, -90):
                f.SetOrientationDegrees(a)
                p1 = next(p for p in f.Pads() if p.GetNumber() == '1'); p40 = next(p for p in f.Pads() if p.GetNumber() == '40')
                if p1.GetPosition().x < p40.GetPosition().x and p1.GetPosition().y > f.GetPosition().y: break
        f.Reference().SetVisible(False)
        for p in f.Pads():
            if p.GetNumber().isdigit() and int(p.GetNumber()) <= 32:
                p.SetNet(net(('ROW_%02d_ANODE' if ref == 'J_ROW' else 'COL_%02d') % int(p.GetNumber())))
    J = {ref: b.FindFootprintByReference(ref) for ref in ('J_ROW', 'J_COL')}
    def padxy(ref, n):
        p = next(p for p in J[ref].Pads() if p.GetNumber() == str(n)); return p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
    assert abs(padxy('J_ROW', 1)[0] - pin_x(XJ_ROW, 1)) < 1e-3, padxy('J_ROW', 1)

    # ---------------- rows
    feed = {}
    for r in range(1, 33):
        n = 'ROW_%02d_ANODE' % r; y = YN[r - 1]
        px, py = padxy('J_ROW', r)
        if r <= 16:   # west frame: row 1 outermost (k=15) -> bottom slot; planar without crossings
            k = 16 - r; bar = [(XN[-1], y), (XN[0], y)]; xf = XW[k]
        else:         # east frame: row 17 outermost (k=15) -> bottom slot
            k = 32 - r; bar = [(XN[0], y), (XN[-1], y)]; xf = XE[k]
        ys = YRB[k]
        poly(bar, W_ROWBAR, pcbnew.F_Cu, n)
        path = [bar[-1], (xf, y), (xf, ys), (px, ys)]
        poly(path, W_FEED, pcbnew.F_Cu, n)
        poly([(xf, y), (xf, ys)], W_FEED, pcbnew.B_Cu, n)        # B.Cu twin in the side frame
        via((xf, y), n); via((xf, ys), n)
        via((px, ys), n)
        poly([(px, ys), (px, py)], W_DROP, pcbnew.B_Cu, n)
        feed[r] = dict(bar=abs(bar[0][0] - bar[1][0]), stub=abs(bar[-1][0] - xf), side=abs(ys - y), band=abs(xf - px), drop=abs(py - ys))
    # ---------------- columns
    for c in range(1, 33):
        n = 'COL_%02d' % c; x = XN[c - 1]; px, py = padxy('J_COL', c)
        s = (c - 1) if x < px else (32 - c)
        ys = YCB_BOT - P_COLBAND * s
        poly([(x, YN[0] + LED_VIA_DY), (x, YN[-1])], W_COLBAR, pcbnew.B_Cu, n)
        poly([(x, YN[-1]), (x, ys), (px, ys), (px, py)], W_COLBAND, pcbnew.B_Cu, n)

    # ---------------- mounting / alignment holes
    def hole(name, x, y, ref):
        f = pcbnew.FootprintLoad(FPLIB, name); f.SetReference(ref); f.SetPosition(VECTOR2I(M(x), M(y))); b.Add(f)
        f.Reference().SetVisible(False); f.Value().SetVisible(False)
    hc = 3.75
    for i, (x, y) in enumerate([(EDGE_L + hc, EDGE_T + hc), (EDGE_R - hc, EDGE_T + hc), (EDGE_L + hc, EDGE_B - hc), (EDGE_R - hc, EDGE_B - hc)]):
        hole('MountingHole_2.7mm_M2.5', x, y, 'H%d' % (i + 1))
    for i, (x, y) in enumerate([(XC - 50, EDGE_T + hc), (XC + 50, EDGE_T + hc), (XC - 50, EDGE_B - hc), (XC + 50, EDGE_B - hc)]):
        hole('MountingHole_2.2mm_M2', x, y, 'H%d' % (i + 5))

    # ---------------- text
    def text(s, x, y, layer, h=1.2, mirror=False):
        t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(VECTOR2I(M(x), M(y))); t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(M(h), M(h))); t.SetTextThickness(M(0.18)); t.SetMirrored(mirror); b.Add(t)
    text('mono_panel_32x32_lattice  32x32 @5.2mm  FR4 0.8mm 2L', XC, EDGE_T + 2.4, pcbnew.F_SilkS)
    text('LED cube layer - rows F.Cu / cols B.Cu - FFC TYPE B', XC, EDGE_T + 5.0, pcbnew.F_SilkS)
    for ref, xj in (('J_ROW', XJ_ROW), ('J_COL', XJ_COL)):
        text('%s  PIN1 >' % ref, xj - 6, Y_CONN - 6.2, pcbnew.B_SilkS, 1.0, True)
    text('FFC: 2x 40P 0.5mm TYPE B', XC - 72, EDGE_B - 3.75, pcbnew.B_SilkS, 1.0, True)

    pcbnew.SaveBoard(OUT, b)
    geo = dict(edge=[EDGE_L, EDGE_T, EDGE_R, EDGE_TAB], edge_b=EDGE_B, tab=[TAB_L, TAB_R], lattice=[LAT_L, LAT_T, LAT_R, LAT_B],
               nodes_x=XN, nodes_y=YN, pitch=PITCH, bar_h=BAR_H, bar_v=BAR_V, win=[WIN_W, WIN_H], r_corner=R_CORNER, n_windows=nwin,
               widths=dict(rowbar=W_ROWBAR, colbar=W_COLBAR, feed=W_FEED, drop=W_DROP, colband=W_COLBAND), feed=feed)
    json.dump(geo, open(os.path.join(HERE, 'lattice_geometry.json'), 'w'), indent=1)
    print('board %.1f x %.1f mm (tab to %.1f), windows %d, col slots %d' % (EDGE_R - EDGE_L, EDGE_TAB - EDGE_T, EDGE_TAB, nwin, NSLOT_C))

if __name__ == '__main__':
    build()
