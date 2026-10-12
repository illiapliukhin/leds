#!/usr/bin/env python3
"""mono_panel_32x32_v2: 32x32 single-colour panel, 2835 white LEDs (XL-2835UWC-02), 8.0 mm pitch, 256 x 256 mm, 4 layers.
KiCad 10 pcbnew generator (AppImage python3.11).  Stages:
  base   -> matrix + deterministic row bundle + parts; writes fixed.json for route_v2.py
  final  -> base + routes.json (filleted with arcs) + GND stitching + zones (filled) -> mono_panel_32x32_v2.kicad_pcb
Layers: F.Cu LEDs + 1.0 mm row buses (anode = row) | In1.Cu 32 column lines (cathode = column, via per LED)
        In2.Cu GND plane + column fan-out | B.Cu FFCs, ID EEPROM, row fan-out bundle, GND pour.
Nets: ROW_rr (LED anode, J_ROW pin rr), COL_cc (LED cathode, J_COL pin cc); Dn, n = 32(r-1)+c."""
import json, math, os, sys, uuid
import pcbnew
from pcbnew import VECTOR2I, FromMM as M
H = os.path.dirname(os.path.abspath(__file__))
NAME = 'mono_panel_32x32_v2'
OUT = os.path.join(H, NAME + '.kicad_pcb')
LIB = os.path.join(H, 'footprints', 'mono_panel_v2.pretty'); LIBN = 'mono_panel_v2'

N, P = 32, 8.0
S = N * P                                   # 256.0, LED centres at P/2 from every edge -> seamless tiling
XC = [P / 2 + P * c for c in range(N)]
YR = [P / 2 + P * r for r in range(N)]
BUS_DY, BUS_W = -2.6, 1.0                   # row bus (F.Cu) 2.6 mm north of the LED centre
A_DX, K_DX = 1.35, -0.8                     # anode pad 2 / cathode pad 1 centres (footprint)
VIA_DX = -2.6                               # cathode via / In1 column line, west of the LED
VIA_D, VIA_DR = 0.6, 0.3                    # every via 0.6 / 0.3 mm (JLC standard, no small-via fee)
W_ASTUB, W_KSTUB, W_COL = 0.6, 0.4, 0.25
XL = [x + VIA_DX for x in XC]               # In1 column line x = 1.4 + 8c
YB = [y + BUS_DY for y in YR]               # row bus y = 1.4 + 8r
# connectors (B.Cu)
JR_X, JC_X, J_YC = 63.225, 175.225, 131.625   # J_ROW / J_COL centres (B.Cu); pads at x - 1.85 (0.125 grid), pin 1 north, cable exits east (front view) = west seen from the back
U_ID_XY, C_ID_XY = (53.4, 152.0), (53.4, 147.5)
CELL_FREE = (3.6, 1.4)                      # free spot of every cell (all layers): holes, fiducials
HOLES = [(3, 3), (27, 3), (3, 27), (27, 27), (15, 3), (15, 27)]      # (c, r) cells
FIDS = [(0, 0), (30, 0), (0, 31)]
LCSC = {'LED_2835_XL-2835UWC': 'C2843876', 'Hirose_FH12-40S-0.5SH_B': 'C202114', 'SOIC-8_3.9x4.9mm_P1.27mm': 'C7562', 'C_0402_1005Metric': 'C1525'}
SCHF = json.load(open(os.path.join(H, 'sch_fields.json')))['fields'] if os.path.exists(os.path.join(H, 'sch_fields.json')) else {}
L = {'F.Cu': pcbnew.F_Cu, 'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu, 'B.Cu': pcbnew.B_Cu}
ROW_FAN_W, ROW_W = 0.2, 0.6

def fillet_path(pts, r_want):
    """polyline -> list of ('seg', p0, p1) / ('arc', p0, pm, p1); every bend becomes a tangent arc (radius <= r_want,
    limited by half of each adjacent segment and by a 0.07 mm max deviation from the corner)."""
    out = []; cur = pts[0]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u = (b[0] - a[0], b[1] - a[1]); v = (c[0] - b[0], c[1] - b[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-9 or lv < 1e-9: continue
        u = (u[0] / lu, u[1] / lu); v = (v[0] / lv, v[1] / lv)
        cr = u[0] * v[1] - u[1] * v[0]; dt = max(-1, min(1, u[0] * v[0] + u[1] * v[1]))
        th = math.acos(dt)                                   # turning angle
        if th < 1e-3:
            out.append(('seg', cur, b)); cur = b; continue
        dev_cap = 0.07 / (1 / math.cos(th / 2) - 1) if th > 1e-3 else 1e9
        r = min(r_want, dev_cap)
        t = r * math.tan(th / 2)
        tmax = min(lu * (0.5 if i > 1 else 1.0), lv * (0.5 if i < len(pts) - 2 else 1.0))
        tmax = min(tmax, math.hypot(b[0] - cur[0], b[1] - cur[1]))
        if t > tmax: t = tmax; r = t / math.tan(th / 2)
        p0 = (b[0] - u[0] * t, b[1] - u[1] * t); p1 = (b[0] + v[0] * t, b[1] + v[1] * t)
        n = (-u[1], u[0]) if cr > 0 else (u[1], -u[0])       # toward the centre
        cc = (p0[0] + n[0] * r, p0[1] + n[1] * r)
        mdir = (b[0] - cc[0], b[1] - cc[1]); lm = math.hypot(*mdir)
        pm = (cc[0] + mdir[0] / lm * r, cc[1] + mdir[1] / lm * r)
        if math.hypot(p0[0] - cur[0], p0[1] - cur[1]) > 1e-6: out.append(('seg', cur, p0))
        out.append(('arc', p0, pm, p1)); cur = p1
    out.append(('seg', cur, pts[-1]))
    return out

class Board:
    def __init__(self):
        self.b = pcbnew.LoadBoard(os.path.join(H, 'template.kicad_pcb'))
        self.b.SetCopperLayerCount(4)
        self.nets = {}
        self.dump = {'pads': [], 'tracks': [], 'vias': [], 'holes': [], 'size': S}
    def net(self, n):
        if n not in self.nets:
            x = pcbnew.NETINFO_ITEM(self.b, n); self.b.Add(x); self.nets[n] = x
        return self.nets[n]
    def seg(self, p0, p1, w, layer, n):
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 1e-6: return
        t = pcbnew.PCB_TRACK(self.b); t.SetStart(VECTOR2I(M(p0[0]), M(p0[1]))); t.SetEnd(VECTOR2I(M(p1[0]), M(p1[1])))
        t.SetWidth(M(w)); t.SetLayer(L[layer]); t.SetNet(self.net(n)); self.b.Add(t)
        self.dump['tracks'].append(dict(x0=p0[0], y0=p0[1], x1=p1[0], y1=p1[1], w=w, layer=layer, net=n))
    def arc(self, p0, pm, p1, w, layer, n):
        a = pcbnew.PCB_ARC(self.b); a.SetStart(VECTOR2I(M(p0[0]), M(p0[1]))); a.SetMid(VECTOR2I(M(pm[0]), M(pm[1])))
        a.SetEnd(VECTOR2I(M(p1[0]), M(p1[1]))); a.SetWidth(M(w)); a.SetLayer(L[layer]); a.SetNet(self.net(n)); self.b.Add(a)
        for q0, q1 in ((p0, pm), (pm, p1)):
            self.dump['tracks'].append(dict(x0=q0[0], y0=q0[1], x1=q1[0], y1=q1[1], w=w, layer=layer, net=n))
    def path(self, pts, widths, layer, n, r=None):
        """pts polyline, widths per segment; bends filleted (arc width = narrower adjacent segment)."""
        if r is None: r = 3 * min(widths)
        # split into runs of equal width only at collinear points; fillet each bend with the narrower width
        items = fillet_path(pts, r)
        # assign width: find which original segment each item belongs to (by midpoint distance)
        def seg_w(p):
            best, bw = 1e9, widths[0]
            for (a, c), w in zip(zip(pts, pts[1:]), widths):
                dx, dy = c[0] - a[0], c[1] - a[1]; L2 = dx * dx + dy * dy or 1e-12
                tt = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
                d = math.hypot(a[0] + tt * dx - p[0], a[1] + tt * dy - p[1])
                if d < best - 1e-9 or (abs(d - best) < 1e-9 and w < bw): best, bw = d, w
            return bw
        for it in items:
            if it[0] == 'seg':
                m = ((it[1][0] + it[2][0]) / 2, (it[1][1] + it[2][1]) / 2); self.seg(it[1], it[2], seg_w(m), layer, n)
            else:
                self.arc(it[1], it[2], it[3], min(seg_w(it[1]), seg_w(it[3])), layer, n)
    def via(self, p, n, d=VIA_D, dr=VIA_DR):
        v = pcbnew.PCB_VIA(self.b); v.SetPosition(VECTOR2I(M(p[0]), M(p[1]))); v.SetDrill(M(dr))
        try: v.SetWidth(pcbnew.F_Cu, M(d))
        except TypeError: v.SetWidth(M(d))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(self.net(n)); self.b.Add(v)
        self.dump['vias'].append(dict(x=p[0], y=p[1], d=d, net=n))
    def fp(self, name, ref, val, x, y, rot=0, back=False, board_only=False):
        f = pcbnew.FootprintLoad(LIB, name); f.SetFPID(pcbnew.LIB_ID(LIBN, name))
        f.SetReference(ref); f.SetValue(val); self.b.Add(f)
        f.SetPosition(VECTOR2I(M(x), M(y))); f.SetOrientationDegrees(rot)
        if back: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if board_only: f.SetBoardOnly(True)
        else:
            f.SetPath(pcbnew.KIID_PATH('/' + str(uuid.uuid5(uuid.NAMESPACE_DNS, 'mono_panel_v2/' + ref))))
            for k, v in SCHF.get(ref, {}).items():
                if k == 'Datasheet': f.GetField(pcbnew.FIELD_T_DATASHEET).SetText(v) if hasattr(pcbnew, 'FIELD_T_DATASHEET') else f.SetField(k, v)
                elif k == 'Description': f.SetLibDescription(v) if False else f.SetField(k, v)
                else: f.SetField(k, v)
            for fld in f.GetFields():
                if fld.GetName() not in ('Reference', 'Value'): fld.SetVisible(False)
        f.Reference().SetVisible(False); f.Value().SetVisible(False)
        return f
    def pad_dump(self, f):
        for p in f.Pads():
            bb = p.GetBoundingBox()
            lay = [n for n, l in L.items() if p.IsOnLayer(l)]
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                self.dump['holes'].append(dict(x=p.GetPosition().x / 1e6, y=p.GetPosition().y / 1e6, r=p.GetDrillSize().x / 2e6)); continue
            self.dump['pads'].append(dict(ref=f.GetReference(), n=p.GetNumber(), net=p.GetNetname(),
                x=p.GetPosition().x / 1e6, y=p.GetPosition().y / 1e6, bx0=bb.GetX() / 1e6, by0=bb.GetY() / 1e6,
                bx1=bb.GetRight() / 1e6, by1=bb.GetBottom() / 1e6, layers=lay))
    def text(self, s, x, y, size=1.5, layer=pcbnew.B_SilkS):
        t = pcbnew.PCB_TEXT(self.b); t.SetText(s); t.SetPosition(VECTOR2I(M(x), M(y))); t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(M(size), M(size))); t.SetTextThickness(M(0.2)); t.SetMirrored(layer == pcbnew.B_SilkS); self.b.Add(t)

def build(stage):
    B = Board(); b = B.b
    for r in range(1, 33): B.net('ROW_%02d' % r)
    for c in range(1, 33): B.net('COL_%02d' % c)
    for n in ('GND', 'ID_SDA', 'ID_SCL', 'ID_3V3'): B.net(n)
    # outline: sharp corners, LED centres P/2 from every edge (seamless tiling)
    pts = [(0, 0), (S, 0), (S, S), (0, S)]
    for a, c in zip(pts, pts[1:] + pts[:1]):
        sh = pcbnew.PCB_SHAPE(b); sh.SetShape(pcbnew.SHAPE_T_SEGMENT); sh.SetStart(VECTOR2I(M(a[0]), M(a[1]))); sh.SetEnd(VECTOR2I(M(c[0]), M(c[1])))
        sh.SetLayer(pcbnew.Edge_Cuts); sh.SetWidth(M(0.05)); b.Add(sh)
    # LED matrix
    for r in range(N):
        rn = 'ROW_%02d' % (r + 1)
        B.seg((XC[0] + A_DX - 0.3, YB[r]), (XC[-1] + A_DX + 0.3, YB[r]), BUS_W, 'F.Cu', rn)
        for c in range(N):
            cn = 'COL_%02d' % (c + 1)
            f = B.fp('LED_2835_XL-2835UWC', 'D%d' % (32 * r + c + 1), 'XL-2835UWC-02', XC[c], YR[r])
            for p in f.Pads(): p.SetNet(B.net(rn if p.GetNumber() == '2' else cn))
            B.pad_dump(f)
            B.seg((XC[c] + A_DX, YR[r]), (XC[c] + A_DX, YB[r]), W_ASTUB, 'F.Cu', rn)
            B.seg((XC[c] + K_DX, YR[r]), (XL[c], YR[r]), W_KSTUB, 'F.Cu', cn)
            B.via((XL[c], YR[r]), cn)
    for c in range(N):
        B.seg((XL[c], YR[0]), (XL[c], YR[-1]), W_COL, 'In1.Cu', 'COL_%02d' % (c + 1))
    # connectors (B.Cu), LED interface standard v1: same FH12 on B.Cu, pins along y, pin 1 north, cable exits west seen from the back
    def ffc(ref, x, yc, kind):
        f = B.fp('Hirose_FH12-40S-0.5SH_B', ref, 'FH12-40S-0.5SH(55)', x, yc, rot=0, back=True)
        for a in (0, 90, 180, 270):
            f.SetOrientationDegrees(a)
            p1 = next(p for p in f.Pads() if p.GetNumber() == '1'); p40 = next(p for p in f.Pads() if p.GetNumber() == '40')
            if p1.GetPosition().y < p40.GetPosition().y and p1.GetPosition().x < f.GetPosition().x: break
        spare = ({33: 'GND', 35: 'ID_SDA', 36: 'ID_SCL', 37: 'ID_3V3', 38: 'GND', 39: 'GND', 40: 'GND'} if kind == 'ROW'
                 else {33: 'GND', 38: 'GND', 40: 'GND'})
        for p in f.Pads():
            n = p.GetNumber()
            if n.isdigit() and int(n) <= 32: p.SetNet(B.net(('ROW_%02d' if kind == 'ROW' else 'COL_%02d') % int(n)))
            elif n.isdigit() and int(n) in spare: p.SetNet(B.net(spare[int(n)]))
            elif n == 'MP': p.SetNet(B.net('GND'))
            elif n.isdigit(): p.SetNet(B.net('unconnected-(%s-Pin_%s-Pad%s)' % (ref, n, n)))
        return f
    jr = ffc('J_ROW1', JR_X, J_YC, 'ROW')
    jc = ffc('J_COL1', JC_X, J_YC, 'COL')
    for f in (jr, jc): B.pad_dump(f)
    info = {}
    u = B.fp('SOIC-8_3.9x4.9mm_P1.27mm', 'U_ID1', 'M24C02-WMN6TP', U_ID_XY[0], U_ID_XY[1], rot=0, back=True)
    for p in u.Pads(): p.SetNet(B.net({'1': 'GND', '2': 'GND', '3': 'GND', '4': 'GND', '5': 'ID_SDA', '6': 'ID_SCL', '7': 'GND', '8': 'ID_3V3'}[p.GetNumber()]))
    c = B.fp('C_0402_1005Metric', 'C_ID1', '100n', C_ID_XY[0], C_ID_XY[1], rot=0, back=True)
    for p in c.Pads(): p.SetNet(B.net('ID_3V3' if p.GetNumber() == '1' else 'GND'))
    for f in (u, c): B.pad_dump(f)
    for i, (cc, rr) in enumerate(HOLES):
        f = B.fp('MountingHole_2.2mm_M2_NPTH_Cell', 'MH%d' % (i + 1), 'MountingHole_M2', XC[cc] + CELL_FREE[0], YR[rr] + CELL_FREE[1], board_only=True)
        B.pad_dump(f)
    k = 0
    for back in (False, True):
        for (cc, rr) in FIDS:
            k += 1
            f = B.fp('Fiducial_1mm_Mask2mm', 'FID%d' % k, 'Fiducial', XC[cc] + CELL_FREE[0], YR[rr] + CELL_FREE[1], back=back, board_only=True)
            B.pad_dump(f)
    B.text('mono_panel_32x32_v2  32x32 XL-2835UWC-02  8.0 mm pitch  256x256  4L 1.6 mm JLC04161H-7628', 128, 238.4, 1.2)
    B.text('J_ROW / J_COL: FFC 40P 0.5 mm TYPE B, pin 1 -> pin 1, pin 1 north, cable exits west   ID 24C02 @0x50', 128, 240.6, 1.0)
    for f in b.GetFootprints():
        f.SetLocked(False)
    return B, info

if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'base'
    B, info = build(stage)
    if stage == 'base':
        B.dump['row_info'] = info; B.dump['XL'] = XL; B.dump['YR'] = YR; B.dump['YB'] = YB; B.dump['XC'] = XC
        json.dump(B.dump, open(os.path.join(H, 'fixed.json'), 'w'))
        pcbnew.SaveBoard(OUT, B.b); print('base saved; row info', len(info))
    else:
        import gen_final
        gen_final.finish(B, info)
        pcbnew.SaveBoard(OUT, B.b); print('final saved', OUT)
