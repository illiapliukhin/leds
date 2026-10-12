#!/usr/bin/env python3
"""mono_panel_32x32_full: edge-to-edge 32x32 panel for seamless tiling (KiCad 10 pcbnew).
stage 'base'  : outline, LEDs, row buses (F.Cu), cathode stubs + vias, column lines (In1.Cu), FFCs + SMT standoffs (B.Cu)
                -> mono_panel_32x32_full.kicad_pcb + fixed.json (copper geometry for the router)
stage 'routes': add routes.json (from route_full.py, numpy maze router on In2.Cu/B.Cu) -> final board
Same nets/pinout/LED mapping as mono_panel_32x32 (Dn, n = 32(r-1)+c; pad2 = ROW_rr_ANODE, pad1 = COL_cc)."""
import json, math, os, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as M
H = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(H, '..', 'mono_panel_32x32', 'mono_panel_32x32.kicad_pcb')
OUT = os.path.join(H, 'mono_panel_32x32_full.kicad_pcb')

N, PITCH = 32, 5.0
SIZE = N * PITCH                     # 160 x 160, outline = 32 x pitch, LED centres at pitch/2 from the edge
XN = [PITCH / 2 + PITCH * c for c in range(N)]
YN = [PITCH / 2 + PITCH * r for r in range(N)]
BUS_DY, BUS_W = -0.775, 1.0          # row bus on the anode pad line
VIA_DY = 1.9                         # cathode via below the LED
VIA_D, VIA_DRILL = 0.45, 0.2
W_STUB, W_COL = 0.3, 0.3
JX_ROW, JX_COL, J_Y = 72.75, 107.75, 80.0      # FFC centres (rot 0, B.Cu, pins along x, cable exits south)
U_ID_XY, C_ID_XY = (91.0, 76.9), (91.0, 74.3)
STANDOFFS = [(20.0, 16.9), (140.0, 16.9), (20.0, 141.9), (140.0, 141.9)]
L = {'F.Cu': pcbnew.F_Cu, 'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu, 'B.Cu': pcbnew.B_Cu}

def board_base():
    src = pcbnew.LoadBoard(SRC)
    b = pcbnew.BOARD(); b.SetCopperLayerCount(4); b.GetDesignSettings().SetBoardThickness(M(1.6))
    nets = {}
    def net(n):
        if n not in nets:
            x = pcbnew.NETINFO_ITEM(b, n); b.Add(x); nets[n] = x
        return nets[n]
    for r in range(1, 33): net('ROW_%02d_ANODE' % r)
    for c in range(1, 33): net('COL_%02d' % c)
    def track(p0, p1, w, layer, n):
        t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(M(p0[0]), M(p0[1]))); t.SetEnd(VECTOR2I(M(p1[0]), M(p1[1])))
        t.SetWidth(M(w)); t.SetLayer(layer); t.SetNet(net(n)); b.Add(t)
    def via(p, n):
        v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(M(p[0]), M(p[1]))); v.SetDrill(M(VIA_DRILL))
        try: v.SetWidth(pcbnew.F_Cu, M(VIA_D))
        except TypeError: v.SetWidth(M(VIA_D))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(n)); b.Add(v)
    # outline (sharp corners: panels butt edge to edge)
    pts = [(0, 0), (SIZE, 0), (SIZE, SIZE), (0, SIZE)]
    for a, c in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(VECTOR2I(M(a[0]), M(a[1]))); s.SetEnd(VECTOR2I(M(c[0]), M(c[1])))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(M(0.05)); b.Add(s)
    led = src.FindFootprintByReference('D1')
    for r in range(N):
        rn = 'ROW_%02d_ANODE' % (r + 1)
        track((XN[0] - 0.4, YN[r] + BUS_DY), (XN[-1] + 0.4, YN[r] + BUS_DY), BUS_W, pcbnew.F_Cu, rn)
        for c in range(N):
            cn = 'COL_%02d' % (c + 1)
            f = pcbnew.FOOTPRINT(led); b.Add(f); f.SetReference('D%d' % (32 * r + c + 1)); f.SetOrientationDegrees(90)
            f.SetPosition(VECTOR2I(M(XN[c]), M(YN[r])))
            pa = next(p for p in f.Pads() if p.GetNumber() == '2'); pc = next(p for p in f.Pads() if p.GetNumber() == '1')
            if pc.GetPosition().y < pa.GetPosition().y: f.SetOrientationDegrees(-90)
            for p in f.Pads(): p.SetNet(net(rn if p.GetNumber() == '2' else cn))
            f.Reference().SetVisible(False)
            yc = next(p for p in f.Pads() if p.GetNumber() == '1').GetPosition().y / 1e6
            track((XN[c], yc), (XN[c], YN[r] + VIA_DY), W_STUB, pcbnew.F_Cu, cn)
            via((XN[c], YN[r] + VIA_DY), cn)
    for c in range(N):
        track((XN[c], YN[0] + VIA_DY), (XN[c], YN[-1] + VIA_DY), W_COL, pcbnew.In1_Cu, 'COL_%02d' % (c + 1))
    for ref, xj in (('J_ROW', JX_ROW), ('J_COL', JX_COL)):
        f = pcbnew.FOOTPRINT(src.FindFootprintByReference(ref)); b.Add(f)
        for a in (0, 180, 90, -90):
            f.SetOrientationDegrees(a); f.SetPosition(VECTOR2I(M(xj), M(J_Y)))
            p1 = next(p for p in f.Pads() if p.GetNumber() == '1'); p40 = next(p for p in f.Pads() if p.GetNumber() == '40')
            if p1.GetPosition().x < p40.GetPosition().x and p1.GetPosition().y > f.GetPosition().y: break
        f.Reference().SetVisible(False)
        spare = ({33: 'GND', 35: 'ID_SDA', 36: 'ID_SCL', 37: 'ID_3V3', 38: 'GND', 39: 'GND', 40: 'GND'} if ref == 'J_ROW'
                 else {33: 'GND', 38: 'GND', 40: 'GND'})          # LED_INTERFACE_STANDARD v1 s.3/7 (J_ROW 39 = ID_PRESENT_N -> GND)
        for p in f.Pads():
            if p.GetNumber().isdigit() and int(p.GetNumber()) <= 32:
                p.SetNet(net(('ROW_%02d_ANODE' if ref == 'J_ROW' else 'COL_%02d') % int(p.GetNumber())))
            elif p.GetNumber().isdigit() and int(p.GetNumber()) in spare:
                p.SetNet(net(spare[int(p.GetNumber())]))
    # panel ID EEPROM 24LC02BT-I/OT @0x50 (pin4 VCC, pin5 WP->GND, as garland_breakout) + 100 nF on ID_3V3, B.Cu
    FPL = os.path.join(os.environ.get('KICAD10_ROOT', '/workspace/.kicad10/squashfs-root'), 'usr/share/kicad/footprints')
    def fpl(lib, name, ref, x, y, val):
        f = pcbnew.FootprintLoad(os.path.join(FPL, lib + '.pretty'), name); f.SetReference(ref); f.SetValue(val)
        b.Add(f); f.SetPosition(VECTOR2I(M(x), M(y)))
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT); f.Value().SetVisible(False); f.Reference().SetVisible(False)
        return f
    u = fpl('Package_TO_SOT_SMD', 'SOT-23-5', 'U_ID', U_ID_XY[0], U_ID_XY[1], '24LC02BT-I/OT')
    if next(p for p in u.Pads() if p.GetNumber() == '1').GetPosition().x > u.GetPosition().x:
        u.SetOrientationDegrees(u.GetOrientationDegrees() + 180)          # I2C pins face the J_ROW side
    for p in u.Pads(): p.SetNet(net({'1': 'ID_SCL', '2': 'GND', '3': 'ID_SDA', '4': 'ID_3V3', '5': 'GND'}[p.GetNumber()]))
    c = fpl('Capacitor_SMD', 'C_0402_1005Metric', 'C_ID', C_ID_XY[0], C_ID_XY[1], '100n')
    for p in c.Pads(): p.SetNet(net('ID_3V3' if p.GetNumber() == '1' else 'GND'))
    # SMT standoffs (M2 internal thread, solder-on, no hole through the LED side)
    for i, (x, y) in enumerate(STANDOFFS):
        f = pcbnew.FOOTPRINT(b); f.SetReference('MH%d' % (i + 1)); f.SetValue('SMT_STANDOFF_M2')
        f.SetFPID(pcbnew.LIB_ID('', 'SMT_Standoff_M2_D4.2'))
        p = pcbnew.PAD(f); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(VECTOR2I(M(4.2), M(4.2))); p.SetNumber('1')
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.F_Paste); p.SetLayerSet(ls)
        f.Add(p); b.Add(f); f.SetPosition(VECTOR2I(M(x), M(y)))
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM if hasattr(pcbnew, 'FLIP_DIRECTION_TOP_BOTTOM') else False)
        f.Reference().SetVisible(False); f.Value().SetVisible(False)
        cy = pcbnew.PCB_SHAPE(f); cy.SetShape(pcbnew.SHAPE_T_CIRCLE); cy.SetCenter(VECTOR2I(M(x), M(y))); cy.SetEnd(VECTOR2I(M(x + 2.5), M(y)))
        cy.SetLayer(pcbnew.B_CrtYd); cy.SetWidth(M(0.05)); f.Add(cy)
    for (s, y) in (('mono_panel_32x32_full  5.0 mm pitch  edge-to-edge  4L 1.6 mm', 150.5), ('FFC: 2x 40P 0.5 mm TYPE B, pin 1 -> pin 1', 153.0)):
        t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(VECTOR2I(M(80), M(y))); t.SetLayer(pcbnew.B_SilkS)
        t.SetTextSize(VECTOR2I(M(1.0), M(1.0))); t.SetTextThickness(M(0.15)); t.SetMirrored(True); b.Add(t)
    return b

def dump(b):
    out = {'pads': [], 'tracks': [], 'vias': [], 'size': SIZE, 'nodes_x': XN, 'nodes_y': YN, 'bus_dy': BUS_DY, 'bus_w': BUS_W}
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            out['pads'].append(dict(ref=f.GetReference(), n=p.GetNumber(), net=p.GetNetname(), x=p.GetPosition().x / 1e6, y=p.GetPosition().y / 1e6,
                                    bx0=bb.GetX() / 1e6, by0=bb.GetY() / 1e6, bx1=bb.GetRight() / 1e6, by1=bb.GetBottom() / 1e6,
                                    round=p.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE if hasattr(p, 'GetShape') else False,
                                    layers=[n for n, l in L.items() if p.IsOnLayer(l)]))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            out['vias'].append(dict(x=t.GetPosition().x / 1e6, y=t.GetPosition().y / 1e6, d=VIA_D, net=t.GetNetname()))
        else:
            out['tracks'].append(dict(x0=t.GetStart().x / 1e6, y0=t.GetStart().y / 1e6, x1=t.GetEnd().x / 1e6, y1=t.GetEnd().y / 1e6,
                                      w=t.GetWidth() / 1e6, layer=t.GetLayerName(), net=t.GetNetname()))
    json.dump(out, open(os.path.join(H, 'fixed.json'), 'w'))

def add_routes(b):
    R = json.load(open(os.path.join(H, 'routes.json')))
    nets = {b.GetNetInfo().GetNetItem(i).GetNetname(): b.GetNetInfo().GetNetItem(i) for i in range(b.GetNetCount())}
    for t in R['tracks']:
        x = pcbnew.PCB_TRACK(b); x.SetStart(VECTOR2I(M(t[0]), M(t[1]))); x.SetEnd(VECTOR2I(M(t[2]), M(t[3])))
        x.SetWidth(M(t[4])); x.SetLayer(L[t[5]]); x.SetNet(nets[t[6]]); b.Add(x)
    for v in R['vias']:
        x = pcbnew.PCB_VIA(b); x.SetPosition(VECTOR2I(M(v[0]), M(v[1]))); x.SetDrill(M(VIA_DRILL))
        try: x.SetWidth(pcbnew.F_Cu, M(VIA_D))
        except TypeError: x.SetWidth(M(VIA_D))
        x.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); x.SetNet(nets[v[2]]); b.Add(x)

if __name__ == '__main__':
    b = board_base()
    if len(sys.argv) > 1 and sys.argv[1] == 'routes':
        add_routes(b)
    else:
        dump(b)
    pcbnew.SaveBoard(OUT, b)
    print('saved', OUT)
