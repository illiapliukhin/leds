"""Row voltage-drop budget per LED_INTERFACE_STANDARD §5 (design limit 0.35 V at I_ROW)."""
import json, math
from params import *
def r_wire(d_mm): return RHO_CU / (math.pi * (d_mm * 1e-3) ** 2 / 4)
R28 = 0.23; RFFC = 1.64; R_IDC = 0.010   # ohm/m 28 AWG ribbon, ohm/m FFC, ohm per IDC contact pair
LIMIT = 0.35
def budget(row_d=ROW_WIRE_D, lead=LEAD_RIBBON_M, opt='A'):
    net = r_wire(row_d) * WIRE_LEN * 1e-3 / 2          # spread load: far LED sees half the end-fed drop
    items = []
    if opt == 'A':
        items += [('FFC 0.5 мм, %.0f мм (v15 → breakout)' % (FFC_M * 1e3), RFFC * FFC_M),
                  ('плата breakout (медь)', 0.030), ('IDC 2×8 на breakout', R_IDC)]
    else:
        items += [('медь v15 до J_RH1 (+11 мВ по §6.1)', 0.011 / 0.32), ('IDC 2×20 1,27 на v15 + на бирке', 2 * R_IDC),
                  ('медь бирки', 0.010), ('IDC 2×8 бирка ← гребёнка', R_IDC)]
    items += [('шлейф 28 AWG %.2f м (подвод)' % lead, R28 * lead), ('гребёнка 28 AWG ≤ %.2f м' % FAN_MAX_M, R28 * FAN_MAX_M),
              ('пайка у рейки', 0.002), ('строка в сетке Ø%.2f мм, %.0f мм, ½' % (row_d, WIRE_LEN), net)]
    R = sum(r for _, r in items)
    return dict(option=opt, items=[(n, round(r * 1e3, 1), round(r * I_ROW * 1e3, 1)) for n, r in items],
                R_mohm=round(R * 1e3), drop_mV=round(R * I_ROW * 1e3), margin_mV=round((LIMIT - R * I_ROW) * 1e3),
                max_lead_m=round((LIMIT / I_ROW - (R - R28 * lead)) / R28, 2))
def wire_table():
    out = []
    for name, d in [('эмаль 0,30 мм', 0.30), ('эмаль 0,40 мм', 0.40), ('эмаль 0,50 мм (выбрано)', 0.50), ('24 AWG луж. (0,51 мм)', 0.511), ('луж. 0,80 мм', 0.80)]:
        r = r_wire(d)
        out.append((name, round(r, 3), round(r * WIRE_LEN * 1e-3 / 2 * I_ROW * 1e3, 1), round(r * WIRE_LEN * 1e-3 * I_ROW * 1e3, 1)))
    return out
def all_():
    col = r_wire(COL_WIRE_D) * WIRE_LEN * 1e-3 * I_LED
    return dict(A=budget(opt='A'), B=budget(opt='B'), wires=wire_table(), col_drop_mV=round(col * 1e3, 2),
                col_ohm_per_m=round(r_wire(COL_WIRE_D), 3), row_mohm_eeprom=budget(opt='A')['R_mohm'])
if __name__ == '__main__':
    d = all_(); json.dump(d, open('drop_calc.json', 'w'), indent=1, ensure_ascii=False); print(json.dumps(d, ensure_ascii=False, indent=1))
