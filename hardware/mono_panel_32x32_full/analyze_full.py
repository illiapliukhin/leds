#!/usr/bin/env python3
"""IR drop / current check for mono_panel_32x32_full (from routes.json + fixed.json). Writes analysis.json."""
import json, math, os
H = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(H, 'fixed.json'))); R = json.load(open(os.path.join(H, 'routes.json')))
RHO20, ALPHA, T_CU = 1.72e-8, 0.00393, 35e-6        # 1 oz on all four layers (order 1 oz inner)
I_LED, N = 0.010, 32
def r_per_mm(w_mm, temp=20): return RHO20 * (1 + ALPHA * (temp - 20)) * 1e-3 / (w_mm * 1e-3 * T_CU)
R_VIA = RHO20 * 1.6e-3 / (math.pi * 0.2e-3 * 25e-6)  # 0.2 mm drill, 25 um plating, 1.6 mm board
def ipc2152_dT(I, w_mm):                              # IPC-2152 external 1 oz chart fit (dT = (I/(0.048*A^0.44))^(1/0.44)... IPC-2221 form as check)
    A = w_mm / 0.0254 * 1.378                            # cross-section in mil^2 (1 oz = 1.378 mil)
    return (I / (0.048 * A ** 0.44)) ** (1 / 0.44)
out = {'rows': {}}
for temp in (20, 60):
    worst = 0
    for r in range(1, 33):
        net = 'ROW_%02d_ANODE' % r
        feed = sum(r_per_mm(t[4], temp) * math.hypot(t[2] - t[0], t[3] - t[1]) for t in R['tracks'] if t[6] == net)
        nv = sum(1 for v in R['vias'] if v[2] == net)
        xv = [v[0] for v in R['vias'] if v[2] == net][-1]
        xs = D['nodes_x']; rb = r_per_mm(D['bus_w'], temp)
        def drop_at(x):                                   # bus drop from feed point to LED at x (all 32 LEDs on, 10 mA each)
            d = 0; side = [xx for xx in xs if (xx - xv) * (x - xv) > 0]
            pts = sorted(side, key=lambda q: abs(q - xv)); prev = xv
            for k, q in enumerate(pts):
                if abs(q - xv) > abs(x - xv) + 1e-9: break
                d += I_LED * (len(pts) - k) * rb * abs(q - prev); prev = q
            return d
        bus = max(drop_at(x) for x in xs)
        tot = N * I_LED * (feed + nv * R_VIA) + bus
        worst = max(worst, tot)
        if temp == 20:
            out['rows'][net] = dict(feed_len_mm=round(sum(math.hypot(t[2] - t[0], t[3] - t[1]) for t in R['tracks'] if t[6] == net), 1),
                                    feed_mohm=round(feed * 1e3, 1), bus_drop_mV=round(bus * 1e3, 1), total_mV=round(tot * 1e3, 1))
    out['worst_drop_mV_%dC' % temp] = round(worst * 1e3, 1)
out['row_R_eff_ohm'] = {str(r): out['rows']['ROW_%02d_ANODE' % r]['total_mV'] / 1e3 / (N * I_LED) for r in range(1, 33)}
out['row_feed_width_mm'] = 0.3; out['bus_width_mm'] = D['bus_w']; out['via_mohm'] = round(R_VIA * 1e3, 2)
out['ipc2221_dT_0.3mm_0.32A_C'] = round(ipc2152_dT(0.32, 0.3), 1)
out['ipc2221_dT_bus_1.0mm_0.16A_C'] = round(ipc2152_dT(0.16, 1.0), 2)
col = [sum(math.hypot(t[2] - t[0], t[3] - t[1]) for t in R['tracks'] if t[6] == 'COL_%02d' % c) for c in range(1, 33)]
out['col_fan_len_mm_max'] = round(max(col), 1); out['n_route_vias'] = len(R['vias'])
json.dump(out, open(os.path.join(H, 'analysis.json'), 'w'), indent=1)
print({k: v for k, v in out.items() if k != 'rows'}); print('worst row', max(out['rows'].items(), key=lambda kv: kv[1]['total_mV']))
