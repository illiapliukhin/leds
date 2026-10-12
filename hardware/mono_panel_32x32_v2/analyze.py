"""Row-drop / IPC-2221 analysis from the routed board (python3.11, pcbnew).
Conservative model per row r (all 32 LEDs on, 10 mA each => I_row = 0.32 A):
  dV = I*(R_ffc + R_contacts) + I*R_fanout(series B.Cu route + vias) + I*R_bus_total/2 (distributed load fed at worst end)
Copper: 1 oz outer (35 um), rho(25C)=1.72e-8 Ohm*m, +20% for 60C / plating tolerance.  Via 0.3 mm drill, 25 um wall."""
import json, math, pcbnew
RHO = 1.72e-8 * 1.2; T = 35e-6
I = 0.32; R_FFC = 1.64 * 0.20; R_CONT = 2 * 0.03   # 200 mm 0.5 mm FFC conductor (Hirose spec) + 2 contacts x 30 mOhm max
VIA = RHO * 1.6e-3 / (math.pi * 0.3e-3 * 25e-6)
b = pcbnew.LoadBoard('mono_panel_32x32_v2.kicad_pcb')
rows = {}
for t in b.GetTracks():
    n = t.GetNetname()
    if not n.startswith('ROW_'): continue
    d = rows.setdefault(n, {'bus': 0.0, 'fan': 0.0, 'vias': 0, 'wmin': 9})
    if t.GetClass() == 'PCB_VIA': d['vias'] += 1; continue
    L = t.GetLength() / 1e6; w = t.GetWidth() / 1e6
    r = RHO * L / (w * T)
    if w >= 0.99e-3: d['bus'] += r
    else: d['fan'] += r; d['wmin'] = min(d['wmin'], w * 1e3)
out = {}
for n, d in sorted(rows.items()):
    dv = I * (R_FFC + R_CONT) + I * (d['fan'] + d['vias'] * VIA) + I * d['bus'] / 2
    out[n] = dict(R_fan_mohm=round(1e3 * d['fan'], 1), R_bus_mohm=round(1e3 * d['bus'], 1), vias=d['vias'], dV_mV=round(1e3 * dv, 1), board_only_mV=round(1e3 * (dv - I * (R_FFC + R_CONT)), 1))
w = max(out.items(), key=lambda kv: kv[1]['dV_mV'])
# IPC-2221 external: I = 0.048 dT^0.44 A^0.725 (A in mil^2), dT = 10C
def ipc(wmm, dT=10, ext=True): A = (wmm / 0.0254) * 1.378; return (0.048 if ext else 0.024) * dT ** 0.44 * A ** 0.725
res = dict(I_row_A=I, R_ffc_ohm=R_FFC, R_via_mohm=round(VIA * 1e3, 2), worst_row=w[0], worst=w[1], budget_mV=350,
           sink_headroom_V=round(4.24 - w[1]['dV_mV'] / 1e3 - I * 0.11 - 2.75, 2),
           ipc2221_10C={'0.3mm_ext_A': round(ipc(0.3), 2), '1.0mm_bus_ext_A': round(ipc(1.0), 2), '0.2mm_int_A': round(ipc(0.2, ext=False), 2)},
           I_row_rms_A=round(I / math.sqrt(32), 3), rows=out)
json.dump(res, open('docs/analysis.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, indent=1))
