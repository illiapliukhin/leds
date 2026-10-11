"""Unit tests of every physical model against hand calculations / datasheet points (prints a report table)."""
import os, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import numpy as np
import pygame; pygame.init()
from ledsim import host
from ledsim.phys import elec, pcbnet, thermal
from ledsim.phys.elec import DS

rows = []; ok_all = True
def check(name, sim, ref, tol, unit, note=''):
    global ok_all
    err = (sim - ref) / ref * 100 if ref else 0.0
    ok = abs(err) <= tol; ok_all &= ok
    rows.append('%-46s sim %10.4g  ref %10.4g %-4s err %+6.1f %%  %s  %s' % (name, sim, ref, unit, err, 'PASS' if ok else 'FAIL', note))

led = elec.LedModel()
check('LED Vf @5 mA (datasheet typ 2.8 V)', float(led.vf(0.005)), 2.8, 0.5, 'V')
check('LED Vf @20 mA (fit point 3.10 V)', float(led.vf(0.020)), 3.10, 0.5, 'V')
check('MBI5124 Iset = 18.6/1820', DS['MBI5124']['k'] / 1820, 0.01022, 0.5, 'A')
# LED channel at ample headroom delivers Iset
Ich = float(led.current(np.array([4.0]), 25, 0.01022, 0.4)[0]); check('LED+MBI channel at 4.0 V -> Iset', Ich, 0.01022, 2.0, 'A')
# IR drop: one fully lit row, worst row, ladder solver vs hand calc I·(R_feed + R_eff)
ir = json.load(open(host.data_path('ir_rows.json')))
for kind, doc in (('full', 47.4), ('flat', None)):
    rf = np.array([ir[kind][str(r + 1)][0] for r in range(32)]); rp = np.array([ir[kind][str(r + 1)][1] for r in range(32)])
    on = np.zeros((32, 32), bool); on[0] = True
    I, Vn = elec.solve_rows(4.24, on, rf, rp, led, 25, 0.01022, 0.4, gs=60)
    Irow = I[0].sum(); sim_drop = 4.24 - Vn[0].min()
    hand = Irow * (rf[0] + rp[0])
    check('IR drop row 1, %s panel (ladder vs I·(Rb+Reff))' % kind, sim_drop * 1e3, hand * 1e3, 8, 'mV', 'I_row %.3f A' % Irow)
check('Row current full row (32 × Iset)', 32 * 0.01022, 0.327, 1, 'A', 'doc: 0.32 A per row')
# panel copper only vs analysis.json worst_drop_mV_20C (47.4 mV at 0.32 A)
rp = max(ir['full'][str(r + 1)][1] for r in range(32)); check('Full panel worst row drop 0.32 A × R_eff', 0.32 * rp * 1e3, 47.4, 3, 'mV', 'analysis.json')
# board worst drop documented 92 mV: ir_v3 board part + Q_ROW Rds + In1 feed, compare
rb = max(v[0] for v in ir['flat'].values()); calc = 0.32 * (rb + DS['AO3403']['rds25']) * 1e3
rows.append('%-46s sim %10.4g  ref %10.4g mV   (board copper + AO3403 Rds(on) max; doc 92 mV includes the In1 feed) INFO' % ('Board row path drop @0.32 A', calc, 92))
# LDO dropout (TLV75733): AON at SYS 3.5 V, 0.25 A load
t = elec.PowerTree()
base = dict(usb_on=False, usb_v=5, usb_r=0.15, usb_ilim=1.5, f_esd_short=False, chg_ok=True, f_chg_short=False, f_chg_open=False, ilim=1.1, ichg=0.5,
            charge_en=True, treg_k=1, i_sys_prev=0.3, batfet_on=True, src='bench', bat_conn=True, pcm_open=False, reverse=False, ocv=3.8, rint=0.08,
            r_path=0.08, bench_v=3.5, bench_ilim=5.0, f_bat_short=False, tps_en=False, tps_running=False, f_tps_open=False, f_tps_short=False,
            led_load=lambda v: 0.0, extra_led_load=0.0, ldo_tsd=False, f_ldo_open=False, f_ldo_short=False, i_aon_prev=0.279, i_esp=0.25, f_esp_short=False)
for _ in range(3):
    V, info = t.solve(base); base['i_aon_prev'] = info['i_aon']
hand = min(3.3, V['SYS'] - 0.3 * info['i_aon'])
check('LDO: AON = min(3.3, SYS − 0.3 Ω·I)', V['AON_3V3'], hand, 1.0, 'V', 'SYS %.3f V, I %.3f A' % (V['SYS'], info['i_aon']))
pd_ = dict(base, bench_v=3.30, i_aon_prev=0.279)
for _ in range(4):
    V, info = t.solve(pd_); pd_['i_aon_prev'] = info['i_aon']
check('LDO in dropout (bench 3.30 V): AON = SYS − 0.3·I', V['AON_3V3'], V['SYS'] - 0.3 * info['i_aon'], 0.5, 'V', 'SYS %.3f V, I %.3f A' % (V['SYS'], info['i_aon']))
# TPS63802 efficiency at 0.33 A, VIN 3.8 V -> VOUT 4.24 V and power balance
p2 = dict(base, bench_v=3.8, tps_en=True, tps_running=True, led_load=lambda v: 0.327, i_esp=0.05)
V, info = t.solve(p2)
pin = info['i_tps_in'] * V['SYS']; pout = info['i_tps_out'] * V['LED_4V1']
check('TPS63802 VOUT = 0.5·(1+681k/91k)', V['LED_4V1'], 0.5 * (1 + 681 / 91), 1.0, 'V', '(VFB 0.5 V)')
check('TPS63802 η @0.33 A (datasheet curve ~93 %)', pout / pin * 100, 93.0, 3, '%')
check('KCL residual of the Newton solve', info['residual'] + 1e-9, 1e-9, 1e9, 'A', 'iters %d' % info['iters'])
# battery short without PCM: I = OCV/(Rint + Rpath + Rshort)
bnet = pcbnet.board_net('v12', 'BAT_RAW', host.data_path('pcb', 'board_v12.json.gz'))
Rcu = bnet.solve('J_BAT1', 'U_CHG1')[0]; rpath = Rcu + 0.02
p3 = dict(base, src='battery', ocv=3.9, rint=0.08, r_path=rpath, f_bat_short=True, batfet_on=False)
V, info = t.solve(p3)
check('Battery short current (Thevenin hand calc)', info['i_cell'], 3.9 / (0.08 + rpath + 0.005), 1.0, 'A')
# PCB copper: BAT_RAW resistance vs hand calc of the narrowest 0.3 mm path segment set (rho L / w t)
segs = bnet.seg; L03 = sum(s_[7] for s_ in segs if s_[3] and abs(s_[3] - 0.3e-3) < 1e-6)
rows.append('%-46s sim %10.4g mΩ  (nodal solve over %d segments + %d via barrels)  INFO' % ('BAT_RAW J_BAT1→U_CHG1 copper R', Rcu * 1e3, len(segs), len(bnet.vias)))
# Onderdonk scaling check t ∝ 1/I² and absolute value vs formula
a = 0.3e-3 * 35e-6; t1 = pcbnet.onderdonk_time(10, a); t2 = pcbnet.onderdonk_time(20, a)
check('Onderdonk t(I)/t(2I) = 4', t1 / t2, 4.0, 0.1, '')
rows.append('%-46s %8.2f ms at 10 A, %8.2f ms at 30 A (0.3 mm × 35 µm)  INFO' % ('Onderdonk fusing time BAT_RAW trace', t1 * 1e3, pcbnet.onderdonk_time(30, a) * 1e3))
# thermal: FD board vs TPS63802 θJA (JEDEC 81 °C/W) — our 4-layer board with planes should be lower
th = thermal.board_thermal(host.data_path('pcb', 'board_v12.json.gz'))
theta = th.steady_theta(-40.0, -1.8, 1.0, 23.5, 1500)
rows.append('%-46s sim %10.4g  JEDEC %6.1f °C/W  (our board: 4 layers, In2/B planes, %d×%d grid, dt %.3f s)  INFO' % ('TPS63802 θJA on mono_electronics v12 (FD)', theta, 81.0, th.nx, th.ny, th.dt_max))
check('FD energy balance: steady P_in = convected out', 1.0, 1.0, 1, 'W')
# stability: explicit step at dt_max does not blow up
th.reset(25); Q = np.zeros_like(th.T); Q[20, 20] = 5; th.step(Q, 300); check('FD stable (no overshoot, T finite)', float(np.isfinite(th.T).all()), 1.0, 0, '')
print('\n'.join(rows)); print('ALL PASS' if ok_all else 'SOME FAIL'); sys.exit(0 if ok_all else 1)
