#!/usr/bin/env python3
"""Open area, row IR drop (IPC-2152 / resistive), JLC cutout checks -> analysis.json + printed summary."""
import json, math, os
H = os.path.dirname(os.path.abspath(__file__)); g = json.load(open(os.path.join(H, 'lattice_geometry.json')))
RHO20, ALPHA, T_CU = 1.724e-8, 0.00393, 35e-6         # 1 oz = 35 um
def rmm(w, tC=20): return RHO20 * (1 + ALPHA * (tC - 20)) / (w * 1e-3 * T_CU) * 1e-3   # ohm per mm
ww, wh = g['win']; r = g['r_corner']; nwin = g['n_windows']
a_win = ww * wh - (4 - math.pi) * r * r
L, T, Rr, B = g['lattice']; a_lat = (Rr - L) * (B - T)
p = g['pitch']; a_cell = p * p
EL, ET, ER, ETAB = g['edge']; EB = g['edge_b']; TL, TR = g['tab']
a_board = (ER - EL) * (EB - ET) + (TR - TL) * (ETAB - EB) - (4 - math.pi) * 1.0 ** 2 * 4
open_cell = a_win / a_cell; open_lat = nwin * a_win / a_lat; open_board = nwin * a_win / a_board
I_LED, NLED = 0.0102, 32
w = g['widths']
def row_drop(f, tC):
    # feed (full row current) + bar with 32 equal taps at 5.2 mm, fed from one end; worst LED = far end
    Rf = (f['stub'] * rmm(w['feed'], tC) + f['side'] * rmm(w['feed'], tC) / 2 + f['band'] * rmm(w['feed'], tC) + f['drop'] * rmm(w['drop'], tC))
    vf = I_LED * NLED * Rf
    # bar: first LED sits at the bar end node; segment k (between LED k and k+1) carries (32-k-1) LEDs
    vb = sum((NLED - k - 1) * I_LED * p * rmm(w['rowbar'], tC) for k in range(NLED - 1))
    return vf, vb
res = {}
for tC in (20, 60):
    rows = {r: row_drop(f, tC) for r, f in g['feed'].items()}
    worst = max(rows, key=lambda k: sum(rows[k]))
    res[tC] = dict(worst_row=int(worst), feed_mV=rows[worst][0] * 1e3, bar_mV=rows[worst][1] * 1e3, total_mV=sum(rows[worst]) * 1e3,
                   best_total_mV=min(sum(v) for v in rows.values()) * 1e3)
# IPC-2152 (external, 1 oz, still air, 10 C rise) via the IPC-2221 fit (IPC-2152 external charts are more generous)
def ipc_width_mm(I, dT=10, k=0.048):
    A = (I / (k * dT ** 0.44)) ** (1 / 0.725)   # mil^2
    return A / (1.378) * 0.0254
out = dict(open_area=dict(per_cell_pct=100 * open_cell, lattice_pct=100 * open_lat, whole_board_pct=100 * open_board,
                          window_mm=[ww, wh], window_area_mm2=a_win, windows=nwin, lattice_mm2=a_lat, board_mm2=a_board),
           bars=dict(horizontal_row_bar_mm=g['bar_h'], vertical_col_bar_mm=g['bar_v'], copper=w),
           ipc=dict(I_row_A=I_LED * NLED, min_width_10C_mm=ipc_width_mm(I_LED * NLED), rowbar_R_per_166mm_ohm=166 * rmm(w['rowbar'])),
           ir_drop=res,
           jlc_cutouts=dict(min_window_width_mm=min(ww, wh), jlc_min_npth_slot_mm=1.0, corner_radius_mm=r, router_bit_mm=1.0,
                            copper_to_routed_edge_mm=0.25, jlc_min_copper_edge_mm=0.2, min_bar_mm=min(g['bar_h'], g['bar_v']),
                            route_length_m=nwin * (2 * (ww + wh) - (8 - 2 * math.pi) * r) / 1000,
                            route_density_m_per_m2=nwin * (2 * (ww + wh) - (8 - 2 * math.pi) * r) / 1000 / (a_board * 1e-6)),
           row_R_eff_ohm={r: sum(row_drop(f, 20)) / (I_LED * NLED) for r, f in g['feed'].items()},
           board_mm=[ER - EL, ETAB - ET])
json.dump(out, open(os.path.join(H, 'analysis.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
