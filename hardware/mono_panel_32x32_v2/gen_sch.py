#!/usr/bin/env python3
"""Schematic for mono_panel_32x32_v2 (single A1 sheet): 32x32 LED matrix drawn as a real matrix (row wires on the
anodes, column wires on the cathodes), J_ROW / J_COL (FH12-40S, LED interface standard v1 pinout), panel ID EEPROM.
Symbols are copied verbatim from the KiCad 10 libraries into symbols/mono_panel_v2.kicad_sym (lib nickname mono_panel_v2),
UUIDs are deterministic (uuid5 of the reference) so gen_pcb.py links every footprint to its symbol path."""
import os, re, uuid, json
H = os.path.dirname(os.path.abspath(__file__)); NAME = 'mono_panel_32x32_v2'; LIBN = 'mono_panel_v2'
KS = '/workspace/.kicad10/AppDir/share/kicad/symbols'
SRC = {'LED': 'Device.kicad_symdir/LED', 'C': 'Device.kicad_symdir/C', 'Conn_01x40_MountingPin': 'Connector_Generic_MountingPin.kicad_symdir/Conn_01x40_MountingPin',
       'M24C02-WMN': 'Memory_EEPROM.kicad_symdir/M24C02-WMN', 'GND': 'power.kicad_symdir/GND', 'PWR_FLAG': 'power.kicad_symdir/PWR_FLAG'}
ROOT = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'mono_panel_v2/root'))
def U(s): return str(uuid.uuid5(uuid.NAMESPACE_DNS, 'mono_panel_v2/' + s))

def block(text, start):
    d = 0
    for j in range(start, len(text)):
        if text[j] == '(': d += 1
        elif text[j] == ')':
            d -= 1
            if d == 0: return text[start:j + 1]
def symbol_text(name):
    t = open(os.path.join(KS, SRC[name] + '.kicad_sym')).read()
    i = t.index('(symbol "%s"' % name); return block(t, i)
SYM = {k: symbol_text(k) for k in SRC}
def pins(name):
    out = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', SYM[name]):
        rest = SYM[name][m.end():m.end() + 600]
        num = re.search(r'\(number "([^"]+)"', rest).group(1)
        out.setdefault(num, []).append((float(m.group(1)), float(m.group(2))))
    return out
PINS = {k: pins(k) for k in SRC}
# project symbol library
lib = '(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "mono_panel_v2")\n\t(generator_version "10.0")\n' + '\n'.join('\t' + SYM[k] for k in SRC) + '\n)\n'
os.makedirs(os.path.join(H, 'symbols'), exist_ok=True)
open(os.path.join(H, 'symbols', LIBN + '.kicad_sym'), 'w').write(lib)
open(os.path.join(H, 'sym-lib-table'), 'w').write('(sym_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/symbols/%s.kicad_sym")(options "")(descr "mono_panel_32x32_v2 symbols (copied from KiCad 10 Device / Connector_Generic_MountingPin / Memory_EEPROM / power)"))\n)\n' % (LIBN, LIBN))

def g(v): return round(round(v / 1.27) * 1.27, 4)
items = []
FIELDS = {}
def pinpos(name, X, Y, rot, num):
    import math
    out = []
    for (x, y) in PINS[name][num]:
        a = math.radians(rot); xr = x * math.cos(a) - y * math.sin(a); yr = x * math.sin(a) + y * math.cos(a)
        out.append((round(X + xr, 4), round(Y - yr, 4)))
    return out
def prop(k, v, x, y, hide=False, size=1.27, rot=0):
    return '(property "%s" "%s" (at %.4f %.4f %d) (effects (font (size %.2f %.2f))%s))' % (k, v, x, y, rot, size, size, ' (hide yes)' if hide else '')
def place(name, ref, val, fp, X, Y, rot=0, fields=None, ref_off=(2.0, -1.5), hide_val=False, power=False, pinlist=None):
    fields = fields or {}
    ds = fields.pop('Datasheet', ''); de = fields.pop('Description', '')
    pl = pinlist or sorted(PINS[name].keys(), key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else 0, s))
    p = ['(symbol (lib_id "%s:%s") (at %.4f %.4f %d) (unit 1) (body_style 1) (exclude_from_sim no) (in_bom %s) (on_board %s) (in_pos_files %s) (dnp no)' % (
        LIBN, name, X, Y, rot, 'no' if power else 'yes', 'no' if power else 'yes', 'no' if power else 'yes'),
         '(uuid "%s")' % U(ref), prop('Reference', ref, X + ref_off[0], Y + ref_off[1], hide=power, size=1.0),
         prop('Value', val, X + ref_off[0], Y + ref_off[1] + 1.5, hide=hide_val, size=1.0), prop('Footprint', fp, X, Y, True),
         prop('Datasheet', ds, X, Y, True), prop('Description', de, X, Y, True)]
    for k, v in fields.items(): p.append(prop(k, v, X, Y, True))
    if not power: FIELDS[ref] = dict(fields, Datasheet=ds, Description=de)
    for num in pl: p.append('(pin "%s" (uuid "%s"))' % (num, U(ref + '/pin' + num)))
    p.append('(instances (project "%s" (path "/%s" (reference "%s") (unit 1))))' % (NAME, ROOT, ref))
    items.append(' '.join(p) + ')')
def wire(a, b): items.append('(wire (pts (xy %.4f %.4f) (xy %.4f %.4f)) (stroke (width 0) (type default)) (uuid "%s"))' % (a[0], a[1], b[0], b[1], U('w%.4f,%.4f,%.4f,%.4f' % (a + b))))
def junction(a): items.append('(junction (at %.4f %.4f) (diameter 0) (color 0 0 0 0) (uuid "%s"))' % (a[0], a[1], U('j%.4f,%.4f' % a)))
def glabel(net, a, rot=180):
    just = 'right' if rot == 180 else 'left'
    items.append('(global_label "%s" (shape passive) (at %.4f %.4f %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s") (property "Intersheetrefs" "${INTERSHEET_REFS}" (at %.4f %.4f 0) (effects (font (size 1.27 1.27)) (hide yes))))' % (
        net, a[0], a[1], rot, just, U('gl' + net + '%.3f,%.3f' % a), a[0], a[1]))
def noconn(a): items.append('(no_connect (at %.4f %.4f) (uuid "%s"))' % (a[0], a[1], U('nc%.4f,%.4f' % a)))
def text(s, x, y, size=2.0):
    items.append('(text "%s" (exclude_from_sim no) (at %.4f %.4f 0) (effects (font (size %.2f %.2f)) (justify left bottom)) (uuid "%s"))' % (s, x, y, size, size, U('t' + s[:40] + str(x))))
gpwr = [0]
def gnd(a):
    gpwr[0] += 1; ref = '#PWR%03d' % gpwr[0]
    place('GND', ref, 'GND', '', a[0], a[1], 0, power=True)

FP_LED = LIBN + ':LED_2835_XL-2835UWC'; FP_FFC = LIBN + ':Hirose_FH12-40S-0.5SH_B'
# ---------------- LED matrix ----------------
X0, Y0, PX, PY = 40.64, 50.8, 10.16, 10.16
for r in range(32):
    xa_prev = None
    for c in range(32):
        X, Y = X0 + PX * c, Y0 + PY * r; ref = 'D%d' % (32 * r + c + 1)
        place('LED', ref, 'XL-2835UWC-02', FP_LED, X, Y, 90, fields={'LCSC': 'C2843876', 'MPN': 'XINGLIGHT XL-2835UWC-02',
              'Datasheet': 'https://www.lcsc.com/product-detail/C2843876.html', 'Description': '2835 white LED, row %d col %d' % (r + 1, c + 1)},
              ref_off=(1.5, 0.6), hide_val=True)
        a = pinpos('LED', X, Y, 90, '2')[0]; k = pinpos('LED', X, Y, 90, '1')[0]
        if xa_prev is None:
            st = (a[0] - 5.08, a[1]); wire(st, a); glabel('ROW_%02d' % (r + 1), st)
        else: wire(xa_prev, a)
        xa_prev = a
        kc = (k[0] + 2.54, k[1]); wire(k, kc)
        if r > 0: wire((kc[0], kc[1] - PY), kc)
        if 0 < r < 31: junction(kc)
        if r == 31:
            e = (kc[0], kc[1] + 5.08); wire(kc, e); glabel('COL_%02d' % (c + 1), e, 270)
text('LED matrix 32 x 32: XL-2835UWC-02 (LCSC C2843876), anode = row (AO3403 high side on the main board), cathode = column (MBI5124 sink, <= 10 mA)', X0 - 5, Y0 - 10, 2.0)
text('Dn, n = 32(r-1)+c   PCB: 8.0 mm pitch, LED centre (4 + 8(c-1), 4 + 8(r-1)) mm, 256 x 256 mm, edge-to-edge tiling', X0 - 5, Y0 - 6.5, 1.6)
# ---------------- connectors ----------------
def conn(ref, X, Y, kind):
    place('Conn_01x40_MountingPin', ref, 'FH12-40S-0.5SH(55)', FP_FFC, X, Y, 0, fields={'LCSC': 'C202114', 'MPN': 'Hirose FH12-40S-0.5SH(55)',
          'Description': '40P 0.5 mm FFC, bottom contact, B.Cu; LED interface standard v1 (%s)' % kind}, ref_off=(-2.5, -51.5))
    spare = ({33: 'GND', 35: 'ID_SDA', 36: 'ID_SCL', 37: 'ID_3V3', 38: 'GND', 39: 'GND', 40: 'GND'} if kind == 'J_ROW1'
             else {33: 'GND', 38: 'GND', 40: 'GND'})
    for nn in range(1, 41):
        p = pinpos('Conn_01x40_MountingPin', X, Y, 0, str(nn))[0]
        if nn <= 32: e = (p[0] - 5.08, p[1]); wire(p, e); glabel(('ROW_%02d' if kind == 'J_ROW1' else 'COL_%02d') % nn, e)
        elif nn in spare:
            e = (p[0] - 5.08, p[1]); wire(p, e)
            if spare[nn] == 'GND': glabel('GND', e)
            else: glabel(spare[nn], e)
        else: noconn(p)
    mp = pinpos('Conn_01x40_MountingPin', X, Y, 0, 'MP')[0]; e = (mp[0], mp[1] + 2.54); wire(mp, e); gnd(e)
CX = 419.1
conn('J_ROW1', CX, 120.65, 'J_ROW1'); conn('J_COL1', CX + 60.96, 120.65, 'J_COL1')
text('J_ROW / J_COL: Hirose FH12-40S-0.5SH on B.Cu, pin 1 north, cable exits west seen from the back; 40-way 0.5 mm FFC TYPE B, pin 1 -> pin 1', CX - 30, 62, 1.6)
text('J_ROW 33/38/40 GND, 39 ID_PRESENT_N = GND, 34 VLED_SENSE NC, 35/36 ID_SDA/ID_SCL, 37 ID_3V3;  J_COL 33/38/40 GND, 34-37/39 EXP NC', CX - 30, 65.5, 1.6)
# ---------------- ID EEPROM ----------------
UX, UY = 444.5, 215.9
place('M24C02-WMN', 'U_ID1', 'M24C02-WMN6TP', LIBN + ':SOIC-8_3.9x4.9mm_P1.27mm', UX, UY, 0, fields={'LCSC': 'C7562', 'MPN': 'ST M24C02-WMN6TP',
      'Description': 'panel ID EEPROM 2 kbit I2C, address 0x50 (E2..E0 = 0), WC = GND (writable)'}, ref_off=(3.0, -9.0))
for num, net in (('1', 'GND'), ('2', 'GND'), ('3', 'GND'), ('7', 'GND'), ('5', 'ID_SDA'), ('6', 'ID_SCL')):
    p = pinpos('M24C02-WMN', UX, UY, 0, num)[0]; d = -5.08 if p[0] < UX else 5.08
    e = (p[0] + d, p[1]); wire(p, e); glabel(net, e, 180 if d < 0 else 0)
p8 = pinpos('M24C02-WMN', UX, UY, 0, '8')[0]; e8 = (p8[0], p8[1] - 5.08); wire(p8, e8); glabel('ID_3V3', e8, 90)
p4 = pinpos('M24C02-WMN', UX, UY, 0, '4')[0]; e4 = (p4[0], p4[1] + 2.54); wire(p4, e4); gnd(e4)
CXc, CYc = 469.9, 215.9
place('C', 'C_ID1', '100n', LIBN + ':C_0402_1005Metric', CXc, CYc, 0, fields={'LCSC': 'C1525', 'MPN': 'Samsung CL05B104KO5NNNC',
      'Description': '100 nF 16 V X7R 0402, ID_3V3 decoupling'}, ref_off=(2.0, -1.0))
c1 = pinpos('C', CXc, CYc, 0, '1')[0]; c2 = pinpos('C', CXc, CYc, 0, '2')[0]
e = (c1[0], c1[1] - 2.54); wire(c1, e); glabel('ID_3V3', e, 90); e = (c2[0], c2[1] + 2.54); wire(c2, e); gnd(e)
# power flags: GND and ID_3V3 come from the main board through the FFC (passive connector pins)
for i, net in enumerate(('GND', 'ID_3V3')):
    X, Y = 495.3 + 15.24 * i, 205.74
    place('PWR_FLAG', '#FLG%02d' % (i + 1), 'PWR_FLAG', '', X, Y, 0, power=True)
    e = (X, Y + 5.08); wire((X, Y), e)
    if net == 'GND': gnd(e)
    else: glabel(net, e, 270)
text('Panel ID (LED_INTERFACE_STANDARD s.4): 24C02-class at 0x50, ID_3V3 from main-board AON_3V3 via 100 R, no pull-ups on the panel', 420, 195, 1.6)
text('Mounting holes MH1-6 (M2 NPTH 2.2) and fiducials FID1-6 are board-only footprints (not in the schematic).', 420, 250, 1.6)
# ---------------- write ----------------
syms = '\n'.join('    ' + SYM[k].replace('(symbol "%s"' % k, '(symbol "%s:%s"' % (LIBN, k), 1) for k in SRC)
doc = '''(kicad_sch
  (version 20250114)
  (generator "eeschema")
  (generator_version "10.0")
  (uuid "%s")
  (paper "A1")
  (title_block (title "mono_panel_32x32_v2 - 32x32 2835 white LED panel, 8.0 mm pitch") (date "2026-10-12") (rev "v2.0")
    (comment 1 "LED interface standard v1 (hardware/common/LED_INTERFACE_STANDARD.md), mono_electronics v15")
    (comment 2 "generated by gen_sch.py; PCB by gen_pcb.py + route_v2.py"))
  (lib_symbols
%s
  )
  %s
  (sheet_instances (path "/" (page "1")))
)
''' % (ROOT, syms, '\n  '.join(items))
open(os.path.join(H, NAME + '.kicad_sch'), 'w').write(doc)
json.dump({'root': ROOT, 'fields': FIELDS}, open(os.path.join(H, 'sch_fields.json'), 'w'))
print('schematic items', len(items))
