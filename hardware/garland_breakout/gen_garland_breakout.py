#!/usr/bin/env python3
"""Generate garland_breakout.kicad_pcb (run with KiCad 10 AppImage python3.11).

Layout (mm, board origin 0,0, 60 x 145, 2 layers, all SMD on B.Cu, THT IDC on F):
  * J_ROW / J_COL: Hirose FH12-40S-0.5SH on B.Cu, cable exits WEST, pin 1 north
    (footprint cloned from mono_panel_32x32 J_ROW -> breakout looks like a panel to
    the cable, so the standard Type-B pin1->pin1 cable is used).
  * Lines 1..32 of each FFC fan out (staircase, B.Cu) to a 1.27 mm bus, drop through
    a via to F.Cu, get a PESD5V0S1BL TVS (B.Cu, to B GND pour) and run on F.Cu into
    2x8 IDC box headers: header pin n == line n (ribbon conductor n == row/col n).
  * Spares 33..40 of J_ROW: GND / VLED_SENSE (test pad) / ID EEPROM (24LC02B) per
    hardware/common/LED_INTERFACE_STANDARD.md.
"""
import os, pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
FPL = os.path.join(os.environ.get('KICAD10_ROOT', '/workspace/.kicad10/squashfs-root'), 'usr/share/kicad/footprints')
PANEL = os.path.join(HERE, '../mono_panel_32x32/mono_panel_32x32.kicad_pcb')
OUT = os.path.join(HERE, 'garland_breakout.kicad_pcb')
mm = pcbnew.FromMM
W, H = 60.0, 145.0
b = pcbnew.BOARD()
b.SetCopperLayerCount(2)
nets = {}
def net(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
    return nets[n]
def V(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
def seg(p, q, w, layer=pcbnew.B_Cu, n='GND'):
    t = pcbnew.PCB_TRACK(b); t.SetStart(V(*p)); t.SetEnd(V(*q)); t.SetWidth(mm(w))
    t.SetLayer(layer); t.SetNet(net(n)); b.Add(t)
def path(pts, w, layer, n):
    for p, q in zip(pts, pts[1:]):
        if p != q: seg(p, q, w, layer, n)
def via(x, y, n):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(net(n)); b.Add(v)
def fp(lib, name, ref, x, y, rot=0, back=False, val=None, hide_ref=False):
    f = pcbnew.FootprintLoad(os.path.join(FPL, lib + '.pretty'), name)
    f.SetReference(ref); f.SetValue(val or name)
    f.SetPosition(V(x, y))
    b.Add(f)
    if back: f.Flip(V(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.Value().SetVisible(False)
    if hide_ref: f.Reference().SetVisible(False)
    return f
def pad(f, num):
    for p in f.Pads():
        if p.GetNumber() == str(num): return p
def pxy(p): q = p.GetPosition(); return (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))
def text(s, x, y, layer=pcbnew.F_SilkS, size=1.2, mirror=False, rot=0):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(V(size, size)); t.SetTextThickness(mm(0.18)); t.SetMirrored(mirror); t.SetTextAngleDegrees(rot); b.Add(t)

# outline
pts = [(0, 0), (W, 0), (W, H), (0, H)]
for p, q in zip(pts, pts[1:] + pts[:1]):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*p)); s.SetEnd(V(*q))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); b.Add(s)

panel = pcbnew.LoadBoard(PANEL)
src = panel.FindFootprintByReference('J_ROW')
P = 1.27; XV = 32.0; XHDR = 44.0
TVS = []

def block(kind, YhA, ffc_ref, spare_nets):
    YhB = YhA + 30.0
    t = [YhA + i * P for i in range(16)] + [YhB + i * P for i in range(16)]
    s32 = t[31] + 1.0; s1 = s32 - 31 * 0.5
    f = pcbnew.FOOTPRINT(src); f.SetReference(ffc_ref); f.SetValue('FH12-40S-0.5SH')
    f.SetPosition(V(6.0, s1 + 9.75)); b.Add(f)
    f.Reference().SetVisible(False)
    for i in range(40):
        n = f'{kind}_{i+1:02d}' if i < 32 else spare_nets[i - 32]
        pad(f, i + 1).SetNet(net(n))
    for p in f.Pads():
        if p.GetNumber() == 'MP': p.SetNet(net('GND'))
    px = pxy(pad(f, 1))[0]
    wv = 0.25
    wh = 0.4 if kind == 'ROW' else 0.25
    for i in range(32):
        n = f'{kind}_{i+1:02d}'; sy = pxy(pad(f, i + 1))[1]
        xt = 10.0 + i * 0.6   # line 1 most displaced -> turns first
        path([(px, sy), (xt, sy)], 0.2, pcbnew.B_Cu, n)
        path([(xt, sy), (xt, t[i])], wv, pcbnew.B_Cu, n)
        path([(xt, t[i]), (XV, t[i])], wh, pcbnew.B_Cu, n)
        via(XV, t[i], n)
        d = fp('Diode_SMD', 'D_0402_1005Metric', f'D_{kind[0]}{i+1:02d}', 34.0, t[i], 0, True, 'PESD5V0S1BL', True)
        p1, p2 = pad(d, 1), pad(d, 2)
        if pxy(p1)[0] > pxy(p2)[0]:
            d.SetOrientationDegrees(180)
        p1.SetNet(net(n)); p2.SetNet(net('GND'))
        seg((XV, t[i]), pxy(p1), 0.3, pcbnew.B_Cu, n)
        # F.Cu to IDC header
        k = i % 16; hdr_y = (YhA if i < 16 else YhB) + (k // 2) * 2.54
        if k % 2 == 0:
            path([(XV, t[i]), (XHDR, t[i])], wh if kind == 'ROW' else 0.25, pcbnew.F_Cu, n)
        else:
            path([(XV, t[i]), (XHDR + 2.54, t[i]), (XHDR + 2.54, hdr_y)], 0.3 if kind == 'ROW' else 0.25, pcbnew.F_Cu, n)
    for h, Yh in ((1, YhA), (2, YhB)):
        ref = f'J_{kind[0]}{h}'
        j = fp('Connector_IDC', 'IDC-Header_2x08_P2.54mm_Vertical', ref, XHDR, Yh, 0, False,
               f'IDC 2x8 {kind}S {16*(h-1)+1}-{16*h}')
        for q in range(16): pad(j, q + 1).SetNet(net(f'{kind}_{16*(h-1)+q+1:02d}'))
        j.Reference().SetVisible(False)
        text(f'{ref}  {kind}S {16*(h-1)+1}-{16*h}  pin1=^', 52.6, Yh + 9.0, size=1.0, rot=90)
    text(f'J_{kind} FFC TYPE B  PIN1 ^', 13.0, s1 - 4.0, pcbnew.B_SilkS, 1.0, True)
    return f, s32

ROW_SP = ['GND', 'VLED_SENSE', 'ID_SDA', 'ID_SCL', 'ID_3V3', 'GND', 'GND', 'GND']   # 39 = ID_PRESENT_N tied GND here
COL_SP = ['GND', 'COL_RSV_34', 'COL_RSV_35', 'COL_RSV_36', 'COL_RSV_37', 'GND', 'COL_RSV_39', 'GND']
fr, s32r = block('ROW', 8.0, 'J_ROW', ROW_SP)
fc, s32c = block('COL', 74.0, 'J_COL', COL_SP)

# ---- ROW spares: staircase DOWN, all at 1.27 pitch below the row bus
px = pxy(pad(fr, 33))[0]
T = [s32r + 0.5 + 0.8 + k * P for k in range(8)]
for k in range(8):
    sy = pxy(pad(fr, 33 + k))[1]; n = ROW_SP[k]
    xt = 9.0 + (7 - k) * 0.6
    path([(px, sy), (xt, sy), (xt, T[k])], 0.2, pcbnew.B_Cu, n)
    if n == 'GND':
        path([(xt, T[k]), (15.5, T[k])], 0.25, pcbnew.B_Cu, n); via(15.5, T[k], 'GND')
tp = fp('TestPoint', 'TestPoint_Pad_D1.5mm', 'TP_VSENSE', 18.5, T[1], 0, True, 'VLED_SENSE', True)
pad(tp, 1).SetNet(net('VLED_SENSE'))
path([(9.0 + 6 * 0.6, T[1]), (18.5, T[1])], 0.25, pcbnew.B_Cu, 'VLED_SENSE')
ux, uy = 22.0, (T[2] + T[3]) / 2
u = None
for rot in (0, 90, 180, 270):
    if u: b.Remove(u)
    u = fp('Package_TO_SOT_SMD', 'SOT-23-5', 'U_ID', ux, uy, rot, True, '24LC02BT-I/OT', True)
    xy = {q: pxy(pad(u, q)) for q in range(1, 6)}
    if xy[1][0] < ux and xy[3][0] < ux and xy[3][1] < xy[1][1]: break
print('U_ID rot', rot, xy)
for q, n in {1: 'ID_SCL', 2: 'GND', 3: 'ID_SDA', 4: 'ID_3V3', 5: 'GND'}.items(): pad(u, q).SetNet(net(n))
x35 = 9.0 + 5 * 0.6; x36 = 9.0 + 4 * 0.6; x37 = 9.0 + 3 * 0.6
path([(x35, T[2]), (20.0, T[2]), xy[3]], 0.2, pcbnew.B_Cu, 'ID_SDA')
path([(x36, T[3]), (20.0, T[3]), xy[1]], 0.2, pcbnew.B_Cu, 'ID_SCL')
path([xy[2], (ux, uy)], 0.25, pcbnew.B_Cu, 'GND'); via(ux, uy, 'GND')
path([xy[5], (ux, uy)], 0.25, pcbnew.B_Cu, 'GND')
xr = xy[4][0] + 1.5
path([(x37, T[4]), (xr, T[4]), (xr, xy[4][1]), xy[4]], 0.25, pcbnew.B_Cu, 'ID_3V3')
c = fp('Capacitor_SMD', 'C_0402_1005Metric', 'C_ID', xr + 1.6, T[4], 0, True, '100n', True)
c1, c2 = pad(c, 1), pad(c, 2)
if pxy(c1)[0] > pxy(c2)[0]: c.SetOrientationDegrees(180)
c1.SetNet(net('ID_3V3')); c2.SetNet(net('GND'))
seg((xr, T[4]), pxy(c1), 0.25, pcbnew.B_Cu, 'ID_3V3')
g = pxy(c2); seg(g, (g[0] + 1.0, g[1]), 0.25, pcbnew.B_Cu, 'GND'); via(g[0] + 1.0, g[1], 'GND')
text('U_ID 24C02 @0x50  TP=VSENSE', 24.0, 70.0, pcbnew.B_SilkS, 1.0, True)

# ---- COL spares: GND pins 33, 38, 40 joined at x=5.6, via east
pc = {k: pxy(pad(fc, k)) for k in (33, 38, 40)}
for k in (33, 38, 40): seg(pc[k], (5.6, pc[k][1]), 0.2, pcbnew.B_Cu, 'GND')
seg((5.6, pc[33][1]), (5.6, pc[40][1]), 0.2, pcbnew.B_Cu, 'GND')
seg((5.6, pc[40][1]), (10.5, pc[40][1]), 0.25, pcbnew.B_Cu, 'GND'); via(10.5, pc[40][1], 'GND')

# ---- injection / earth terminal, mounting holes, stitching
ji = fp('TerminalBlock_Phoenix', 'TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal', 'J_INJ', 30.0, 136.0, 0, False, 'VINJ/GND (DNP)')
pad(ji, 1).SetNet(net('GND')); pad(ji, 2).SetNet(net('VINJ'))
text('J_INJ 1=GND 2=VINJ', 17.0, 136.0, size=1.0)
for i, (x, y) in enumerate([(4.5, 4.5), (55.5, 4.5), (4.5, 140.5), (55.5, 140.5)]):
    m = fp('MountingHole', 'MountingHole_3.2mm_M3_Pad_Via', f'H{i+1}', x, y, 0, False, 'M3 GND', True)
    for p in m.Pads(): p.SetNet(net('GND'))
for y in range(12, 135, 6): via(56.5, y, 'GND')
for y in (64.0, 68.0, 70.5):
    for x in (36.0, 40.0, 50.0): via(x, y, 'GND')
for x in (2.0,):
    for y in list(range(10, 38, 4)) + list(range(76, 104, 4)): via(x, y, 'GND')
text('GARLAND BREAKOUT v1', 24.0, 72.2, pcbnew.B_SilkS, 1.0, True)
text('illiapliukhin/leds', 30.0, 140.0, pcbnew.B_SilkS, 1.0, True)

# ---- GND pours both layers
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(net('GND'))
    o = z.Outline(); o.NewOutline()
    for x, y in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]: o.Append(mm(x), mm(y))
    z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.3))
    b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.SetFileName(OUT)
pcbnew.SaveBoard(OUT, b)
print('saved', OUT)
