"""Лаборатория: per-board electrothermal state. Each lab tick: LED matrix solve -> power-tree Newton solve ->
part dissipations -> FD board thermal step (time-compressed) -> physical failure criteria -> consequences.
Boards are processed round-robin (the selected one every tick) so 100+ boards stay real-time."""
import gzip, json, math, random
import numpy as np
from .. import host
from . import elec, thermal, pcbnet
from .elec import DS

BOARD_PCB = 'board_v13.json.gz'          # v13: eFuse U_OVP1 + TVS D_VBUS1 on USB, F_BAT1 + Q_BAT1 in the battery path
PART_REFS = ['U_LED_PWR1', 'U_LDO1', 'U_CHG1', 'U_ESD1', 'U1', 'U_LED1', 'U_LED2', 'J_BAT1', 'L_LED1', 'U_GAUGE1', 'U_485', 'Q_ROW01', 'Q_ROW16', 'Q_ROW17', 'Q_ROW32', 'U_OVP1', 'D_VBUS1', 'F_BAT1', 'Q_BAT1']
PART_PSI = {'U_LED_PWR1': 23.5, 'U_LDO1': 40.0, 'U_CHG1': 25.0, 'U_ESD1': 80.0, 'U1': 10.0, 'U_LED1': 30.0, 'U_LED2': 30.0, 'J_BAT1': 60.0,
            'L_LED1': 30.0, 'U_GAUGE1': 40.0, 'U_485': 40.0, 'U_OVP1': 15.0, 'D_VBUS1': 60.0, 'F_BAT1': 80.0, 'Q_BAT1': 60.0}           # ΨJB °C/W: TPS63802 from datasheet, others = assumption
PRESETS = {
 'Норма':  dict(src='battery', usb_on=True, usb_v=5.0, usb_ilim=1.5, ambient=25.0, esp_mode='active', full_white=False, rext=1820.0, soc=0.8, pcm=True, faults={}),
 'Стресс': dict(src='battery', usb_on=True, usb_v=5.0, usb_ilim=3.0, ambient=45.0, esp_mode='wifi_tx', full_white=True, brightness=255, rext=1820.0, soc=0.3, pcm=True, faults={}),
 'Жара':   dict(src='battery', usb_on=True, usb_v=5.0, usb_ilim=3.0, ambient=70.0, esp_mode='wifi_tx', full_white=True, brightness=255, rext=1820.0, soc=0.5, pcm=True, faults={}),
 'Скачок 12 В на USB': dict(src='battery', usb_on=True, usb_v=5.0, usb_ilim=3.0, ambient=25.0, esp_mode='active', full_white=False, soc=0.8, pcm=True,
                            faults={'surge': ('VBUS', 12.0, 50.0)}),
 'КЗ батареи': dict(src='battery', usb_on=False, ambient=25.0, esp_mode='active', soc=0.9, pcm=False, faults={'bat_short': True}),
 'Разряд': dict(src='battery', usb_on=False, ambient=25.0, esp_mode='wifi_rx', full_white=True, brightness=200, soc=0.12, pcm=True, faults={}),
}

def default_params():
    return dict(src='battery', cap_mah=2000.0, rint25=0.080, soc=0.8, t_cell=25.0, pcm=True, bench_v=3.8, bench_ilim=2.0,
                usb_on=True, usb_v=5.0, usb_ilim=1.5, usb_r=0.15, ambient=25.0, esp_mode='active', rext=1820.0, full_white=False,
                time_k=20.0, ffc_mm=100.0)

class Part:
    def __init__(s, ref, x, y): s.ref, s.x, s.y = ref, x, y; s.P = 0.0; s.Tj = 25.0; s.state = 'ok'; s.mode = ''; s.prot = ''

class BoardPhys:
    def __init__(s, lab, b):
        s.b = b; s.lab = lab; s.tree = elec.PowerTree(); s.th = None
        s.parts = {r: Part(r, *lab.part_pos[r]) for r in PART_REFS}
        s.soc = lab.p['soc']; s.t_cell = lab.p['ambient']; s.gauge = s.soc; s.T_panel = lab.p['ambient']
        s.rails = {}; s.info = {}; s.led_I = np.zeros((32, 32)); s.led_dead = np.zeros((32, 32), bool); s.led_dmg = np.zeros((32, 32))
        s.factor = np.ones((32, 32)); s.fires = []; s.flags = dict(chg_tshut=False, tps_otp=False, ldo_tsd=False, pcm_open=False, batfet_off=False, bod=False)
        s.trace_dmg = {}; s.dead = None; s.first_limit = None; s.i_sys_prev = 0.1; s.i_aon_prev = 0.08; s.surge_left = 0.0; s.surge = None
        s.t = 0.0; s.next_log = 0.0
    def thermal(s):
        if s.th is None:
            base = thermal.board_thermal(host.data_path('pcb', BOARD_PCB))
            s.th = thermal.BoardThermal.__new__(thermal.BoardThermal); s.th.__dict__.update(base.__dict__); s.th.T = np.full_like(base.T, s.lab.p['ambient']); s.th.Ta = s.lab.p['ambient']
        return s.th

class Lab:
    def __init__(s, world):
        s.w = world; s.p = default_params(); s.faults = {}; s.boards = {}; s.events = []; s.rr = 0; s.sel = None
        pcb = json.load(gzip.open(host.data_path('pcb', BOARD_PCB), 'rt', encoding='utf-8'))
        xs = [q[0] for sg in pcb['outline'] for q in sg]; ys = [q[1] for sg in pcb['outline'] for q in sg]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        F = {f[0]: f for f in pcb['fps']}
        s.part_pos = {r: (F[r][2] - cx, F[r][3] - cy) for r in PART_REFS}
        s.pcb = pcb
        # battery path copper from the v13 layout: J_BAT1 -BAT_PACK- F_BAT1 -BAT_FUSE- Q_BAT1 -BAT_RAW- U_CHG1
        s.bat_paths = []; s.r_bat_cu = 0.0
        for net, a, b_ in (('BAT_PACK', 'J_BAT1', 'F_BAT1'), ('BAT_FUSE', 'F_BAT1', 'Q_BAT1'), ('BAT_RAW', 'Q_BAT1', 'U_CHG1')):
            nm = pcbnet.board_net('v13', net, host.data_path('pcb', BOARD_PCB)); r = nm.solve(a, b_)
            if r: s.bat_paths.append((net, nm, r[1])); s.r_bat_cu += r[0]
        s.bat_net, s.bat_seg_I = (s.bat_paths[-1][1], s.bat_paths[-1][2]) if s.bat_paths else (None, [])
        s.r_path = s.r_bat_cu + 2 * DS['PicoBlade']['r_contact'] + DS['F466_2A']['r'] + DS['AO3401A']['rds']
        s.ir = json.load(open(host.data_path('ir_rows.json')))
        s.led = elec.LedModel()
    def apply_preset(s, name):
        pr = dict(PRESETS[name]); s.faults = dict(pr.pop('faults', {}))
        br = pr.pop('brightness', None)
        if br is not None: s.w.brightness = br
        s.p.update(pr)
        for bp in s.boards.values():
            bp.soc = s.p['soc']; bp.gauge = s.p['soc']
        if 'surge' in s.faults: s.trigger_surge(*s.faults['surge'])
        s.log(None, 'INFO', 'Пресет «%s»' % name)
    def reset_damage(s):
        s.boards = {}; s.log(None, 'INFO', 'Все платы заменены новыми (сброс повреждений)')
        for b in s.w.boards:
            if getattr(b, 'phys_dead', None): b.phys_dead = None; s.w.set_power(b, True)
    def trigger_surge(s, target, v, ms):
        for bp in s.boards.values(): bp.surge = (target, v); bp.surge_left = ms / 1000.0
        s.pending_surge = (target, v, ms)
        s.log(None, 'WARN', 'Импульс %s = %.1f В, %.0f мс' % (target, v, ms))
    def once(s, b, bp, key, level, msg):
        """log an event once per board until re-armed (prevents TSHUT/recovery spam)"""
        seen = bp.__dict__.setdefault('_once', set())
        if key in seen: return
        seen.add(key); s.log(b, level, msg)
    def log(s, b, level, msg):
        s.events.append({'t': s.w.now / 1000.0, 'board': '%08X' % b.id if b else '--------', 'level': level, 'test': 'lab', 'msg': msg})
        if len(s.events) > 20000: s.events = s.events[-15000:]

    # -------------------------------------------------------------- one board
    def bp(s, b):
        if b.id not in s.boards:
            s.boards[b.id] = BoardPhys(s, b)
            ps = getattr(s, 'pending_surge', None)
            if ps: s.boards[b.id].surge = ps[:2]; s.boards[b.id].surge_left = ps[2] / 1000
        return s.boards[b.id]

    def tick(s, dt_real, budget=6):
        boards = s.w.boards
        if not boards: return
        todo = []; s.frame = getattr(s, 'frame', 0) + 1
        # the electrothermal state changes on 0.1 s+ time scales: selected board at 10 Hz, one background board on
        # the other frames, so the model costs <~4 ms/frame on a 4-core laptop CPU (was ~11 ms every frame -> 100 % core)
        if s.frame % 6 == 0:
            if s.sel in boards: todo.append(s.sel)
            n = 0
        else: n = 1 if s.frame % 2 else 0
        import time as _t; t0 = _t.perf_counter()
        for b in todo + [None] * n:
            if b is None:
                if _t.perf_counter() - t0 > 0.004: break
                s.rr = (s.rr + 1) % len(boards); b = boards[s.rr]
                if b is s.sel: continue
            bp = s.bp(b)
            last = getattr(bp, 'last_real', None); import time as _t; now = _t.perf_counter(); bp.last_real = now
            dt = min(1.0, (now - last) if last else dt_real)
            s.step_board(b, bp, dt)

    def duty(s, b):
        lut = host.duty_lut(s.w.brightness, s.w.gamma)
        if s.p['full_white']: return np.full((32, 32), float(lut[255]))
        src = b.override if getattr(b, 'override', None) is not None else b.tile
        return lut[src].astype(float)

    def step_board(s, b, bp, dt):
        p, f = s.p, s.faults; P = bp.parts
        dt_th = dt * p['time_k']                                       # thermal / battery time
        surge = None
        if bp.surge_left > 0:
            surge = bp.surge; dt_e = min(bp.surge_left, 0.005); bp.surge_left -= dt_e
        else: dt_e = None
        panel = next((q for q in s.w.panels if q.board is b), None)
        kind = panel.kind if panel else 'full'
        ir = s.ir[kind]
        T_led = bp.T_panel
        # ---- LED matrix (rows ladder) at the current LED_4V1
        iset = DS['MBI5124']['k'] / p['rext']
        d = s.duty(b) if (panel and b.powered) else np.zeros((32, 32))
        on = (d > 0) & ~bp.led_dead
        if P['U_LED1'].state != 'ok' or P['U_LED2'].state != 'ok': on[:] = False
        V_led = bp.rails.get('LED_4V1', 4.24)
        r_ffc = 0.0016 * (panel.ffc_len if panel else 100) * 2                 # FFC: ~0.16 Ω/100 mm per conductor (arch doc), row + share of GND
        rds = DS['AO3403']['rds25'] * (1 + DS['AO3403']['rds_tc'] * (P['Q_ROW01'].Tj - 25))
        r_feed = np.array([ir[str(r + 1)][0] + rds + r_ffc for r in range(32)])
        r_panel = np.array([ir[str(r + 1)][1] for r in range(32)])
        sc = [f['short_col']] if f.get('short_col', -1) is not None and f.get('short_col', -1) >= 0 else None
        I, Vn = elec.solve_rows(V_led, on, r_feed, r_panel, s.led, T_led, iset, DS['MBI5124']['vknee'], sc, I0=bp.led_I if bp.led_I.any() else None)
        sr = f.get('short_row', -1)
        if sr is not None and sr >= 0: I[sr] = 0.0
        bp.led_I = I
        i_led_avg = float((I * np.where(sc is not None, 1.0, 1.0) * np.maximum(d, (I > iset * 1.5).astype(float))).sum() / 32)
        extra = f.get('extra_load', 0.0)
        if sr is not None and sr >= 0:
            extra += min(V_led / (rds + ir[str(sr + 1)][0] + 1e-3), 5.0) / 32      # shorted row: one row slot in 32 into a dead short
        # ---- power tree
        usb_v = p['usb_v']; bench_v = p['bench_v']; ocv_scale = 1.0
        if surge and surge[0] == 'VBUS': usb_v = surge[1]
        if surge and surge[0] == 'BAT_dip': bench_v = surge[1]
        if surge and surge[0] == 'VBUS_dip': usb_v = surge[1]
        rint = elec.r_int(p['rint25'], bp.t_cell)
        ocv = elec.ocv(bp.soc)
        if surge and surge[0] == 'BAT': ocv = surge[1]
        treg_k = 1.0 if P['U_CHG1'].Tj < DS['BQ25185']['treg'] else max(0.0, 1 - (P['U_CHG1'].Tj - DS['BQ25185']['treg']) / 50)
        # ---- USB-C front end (v13): adapter/surge Thevenin -> SMF12A TVS on VBUS_CONN -> eFuse
        tv = DS['SMF12A']; rd = (tv['vc'] - tv['vbr']) / tv['ipp']
        src_ilim = 50.0 if surge and surge[0] == 'VBUS' else p['usb_ilim']       # a surge source is not current limited
        if P['D_VBUS1'].state == 'short': vconn = 0.0; i_tvs = 0.0
        elif usb_v > tv['vbr']:
            i_tvs = min((usb_v - tv['vbr']) / (p['usb_r'] + rd), src_ilim); vconn = tv['vbr'] + i_tvs * rd
        else: vconn, i_tvs = usb_v, 0.0
        if not (p['usb_on'] and b.powered): vconn, i_tvs = 0.0, 0.0
        bp.vconn, bp.i_tvs, bp.usb_src = vconn, i_tvs, usb_v
        pp = dict(vconn=vconn, efuse=P['U_OVP1'].state, efuse_otp=bp.flags.get('efuse_otp', False), fuse_open=P['F_BAT1'].state == 'open', q_bat=P['Q_BAT1'].state,
                  usb_on=p['usb_on'] and b.powered, usb_v=usb_v, usb_r=p['usb_r'], usb_ilim=p['usb_ilim'],
                  f_esd_short=P['U_ESD1'].state == 'short', chg_ok=P['U_CHG1'].state == 'ok' and not bp.flags['chg_tshut'],
                  f_chg_short=P['U_CHG1'].state == 'short', f_chg_open=P['U_CHG1'].state == 'open',
                  ilim=DS['BQ25185']['ilim_max'], ichg=0.5, i_in_prev=bp.info.get('i_in', 0.3) if bp.info else 0.3, charge_en=True, treg_k=treg_k, i_sys_prev=bp.i_sys_prev,
                  batfet_on=not bp.flags['batfet_off'] and P['U_CHG1'].state == 'ok' and not bp.flags['chg_tshut'],
                  src=p['src'], bat_conn=b.powered and bp.dead is None or p['src'] != 'none', pcm_open=bp.flags['pcm_open'] or bp.flags.get('trace_fused', False),
                  reverse=f.get('reverse', False), ocv=ocv, rint=rint, r_path=s.r_path, bench_v=bench_v, bench_ilim=p['bench_ilim'],
                  f_bat_short=f.get('bat_short', False) and not bp.flags.get('trace_fused') and P['F_BAT1'].state == 'ok',
                  tps_en=b.powered and not bp.flags['tps_otp'], tps_running=V_led > 1, f_tps_open=P['U_LED_PWR1'].state == 'open', f_tps_short=P['U_LED_PWR1'].state == 'short',
                  led_load=lambda v: i_led_avg * max(0.0, min(1.0, v / max(V_led, 0.5))), extra_led_load=extra,
                  ldo_tsd=bp.flags['ldo_tsd'], f_ldo_open=P['U_LDO1'].state == 'open', f_ldo_short=P['U_LDO1'].state == 'short', i_aon_prev=bp.i_aon_prev,
                  i_esp=0.0 if P['U1'].state != 'ok' else DS['ESP32S3']['modes'][p['esp_mode']], f_esp_short=P['U1'].state == 'short')
        if p['src'] == 'battery' and not p['pcm'] is False: pass
        bp.pp = pp
        V, info = bp.tree.solve(pp)
        if not info.get('nonconv') and s.fast(b, bp, V, info, dt_e or dt_th):          # a part opened/shorted within this step
            pp.update(efuse=P['U_OVP1'].state, fuse_open=P['F_BAT1'].state == 'open', pcm_open=bp.flags['pcm_open'] or bp.flags.get('trace_fused', False),
                      f_bat_short=pp['f_bat_short'] and P['F_BAT1'].state == 'ok', vconn=bp.vconn)
            V, info = bp.tree.solve(pp)
        bp.rails = V; bp.info = info
        bp.i_sys_prev = info['i_tps_in'] + info['i_ldo']; bp.i_aon_prev = info['i_aon']
        i_cell = info['i_cell']
        # ---- dissipation per part
        Vs, Vb, Va, Vl, Vo = V['SYS'], V['VBUS'], V['BAT'], V['LED_4V1'], V['AON_3V3']
        P['U_ESD1'].P = info['i_esd'] * max(Vb, 0)
        P['U_CHG1'].P = max(0, Vb - Vs) * info['i_in'] + max(0, Vs - Va) * info['i_chg'] + info['i_batfet'] ** 2 * 0.05
        eta = info.get('tps_eta', 0.9); pout = max(0, info['i_tps_out']) * Vl
        P['L_LED1'].P = (info['i_tps_in'] ** 2) * 0.040                             # DFE201612E-R47M DCR ≈ 40 mΩ (assumption)
        P['U_LED_PWR1'].P = max(0, pout * (1 / eta - 1) - P['L_LED1'].P) if P['U_LED_PWR1'].state == 'ok' else (Vs ** 2 / 0.03 if P['U_LED_PWR1'].state == 'short' else 0.0)
        P['U_LDO1'].P = max(0, Vs - Vo) * info['i_ldo']
        P['U1'].P = Vo * pp['i_esp']
        ch = Vn - s.led.vf(np.maximum(I, 1e-9), T_led)                                 # MBI5124 channel Vds
        p_mbi = float((np.maximum(ch, 0) * I * np.maximum(d, 0)).sum() / 32)
        P['U_LED1'].P = p_mbi / 2 + DS['MBI5124']['idd'] * 3.3; P['U_LED2'].P = p_mbi / 2 + DS['MBI5124']['idd'] * 3.3
        P['J_BAT1'].P = i_cell ** 2 * 2 * DS['PicoBlade']['r_contact']
        P['U_GAUGE1'].P = 0.0001; P['U_485'].P = 0.003
        P['D_VBUS1'].P = bp.vconn * bp.i_tvs if P['D_VBUS1'].state == 'ok' else 0.0
        P['U_OVP1'].P = max(0.0, bp.vconn - Vb) * info['i_usb'] if P['U_OVP1'].state == 'ok' else (info['i_usb'] ** 2 * 0.05 if P['U_OVP1'].state == 'short' else 0.0)
        P['F_BAT1'].P = i_cell ** 2 * DS['F466_2A']['r'] if P['F_BAT1'].state == 'ok' else 0.0
        P['Q_BAT1'].P = i_cell ** 2 * DS['AO3401A']['rds'] if P['Q_BAT1'].state == 'ok' else 0.0
        for q in P.values():                                                       # destroyed parts dissipate nothing more
            if q.state == 'open': q.P = 0.0
        rowI = (I * np.maximum(d, 0)).sum(1)
        for r in (1, 16, 17, 32):
            P['Q_ROW%02d' % r].P = (I[r - 1].sum() ** 2) * rds / 32
        # ---- thermal FD (board) with the part powers in their cells
        th = bp.thermal(); th.Ta = p['ambient']
        Q = np.zeros_like(th.T)
        for part in P.values():
            i, j = th.cell(part.x, part.y); Q[i, j] += min(part.P, 30.0)          # >30 W in one part destroys it within ms anyway
        th.step(Q, dt_th)
        dte = dt_e if dt_e else dt_th
        for part in P.values():
            i, j = th.cell(part.x, part.y)
            psi = PART_PSI.get(part.ref, 60.0 if part.ref.startswith('Q_') else 40.0)
            tau = 0.02 if part.ref == 'U_ESD1' else 0.5                     # die/package thermal time constant (assumption)
            if part.ref == 'U_ESD1': psi = DS['USBLC6']['theta_ja']
            tss = th.T[i, j] + part.P * psi                                  # junction = local board cell + P·ΨJB
            part.Tj += (tss - part.Tj) * (1 - math.exp(-dte / tau))
            if part.Tj >= 400.0:                                             # package decomposition / charring: no higher "TJ"
                part.Tj = 400.0
                if not getattr(part, 'charred', False):
                    was = part.state; part.state = 'short' if (was == 'short' and part.ref == 'D_VBUS1') else 'open'; part.charred = True; part.P = 0.0
                    s.log(b, 'FAIL', '%s: ≥ 400 °C — корпус разрушен/обуглен (компаунд разлагается), цепь разорвана%s' % (part.ref, ' (был КЗ)' if was == 'short' else ''))
                    bp.fires.append(dict(x=part.x, y=part.y, t0=s.w.now, fire=False, ref=part.ref))
        # ---- panel / LED temperature (lumped: panel area, both faces)
        p_led = float((s.led.vf(np.maximum(I, 1e-9), T_led) * I * np.maximum(d, 0)).sum() / 32)
        A = (panel.size if panel else 160) ** 2 * 1e-6
        Gp = 2 * A * (thermal.H_CONV + 6.0); Cp = A * 1.6e-3 * thermal.RC_FR4
        bp.T_panel += dt_th * (p_led - Gp * (bp.T_panel - p['ambient'])) / Cp
        # ---- battery: SOC, cell temperature (C ≈ 0.9 J/gK·45 g, θ 20 K/W - assumption)
        if p['src'] == 'battery' and not pp['pcm_open']:
            bp.soc = min(1.0, max(0.0, bp.soc - i_cell * dt_th / 3600 / (p['cap_mah'] / 1000)))
            bp.t_cell += dt_th * (i_cell ** 2 * rint - (bp.t_cell - p['ambient']) / 20.0) / 40.0
        bp.gauge += (bp.soc - bp.gauge) * (1 - math.exp(-dt_th / 60)) + (0.002 * i_cell * random.uniform(-1, 1))
        # ---- display factor (real LED behaviour): luminous ∝ I^0.95 (assumption), −0.3 %/°C (assumption)
        lum = np.where(on | (I > 0), (I / iset) ** 0.95, 0.0) * (1 - 0.003 * (T_led + 8 * (I > 0) - 25))
        ghost = np.vstack([np.zeros((1, 32)), lum[:-1]]) * 0.004                       # row-switch ghosting (assumption 0.4 %)
        bp.factor = np.clip(np.where(bp.led_dead, 0, lum + ghost), 0, 4)
        if Vl < 2.7 or P['U_LED_PWR1'].state != 'ok': bp.factor[:] = 0
        b.phys_factor = bp.factor
        # ---- power accounting (from the solved operating point)
        p_usb = info['i_usb'] * Vb; p_cell = i_cell * Va                         # + = into the board
        p_in = p_usb + max(p_cell, 0.0); p_store = max(-p_cell, 0.0)              # charging power stored in the cell
        p_esp = Vo * pp['i_esp']; p_ledp = p_led
        p_loss = sum(q.P for q in P.values()) + info['i_in'] * 0 + (I.sum(1) ** 2 * r_feed).sum() / 32
        bp.pw = dict(total=p_in, usb_w=p_usb, usb_a=info['i_usb'], bat_w=p_cell, bat_a=i_cell, i_led=info['i_tps_out'], i_aon=info['i_aon'],
                     i_sys=info['i_tps_in'] + info['i_ldo'] + info['i_chg'], p_led=p_ledp, p_esp=p_esp, p_loss=max(0.0, p_in - p_store - p_ledp - p_esp),
                     p_store=p_store, eff=(p_ledp + p_esp + p_store) / p_in if p_in > 1e-3 else 0.0)
        bp.e_wh = getattr(bp, 'e_wh', 0.0) + p_in * dt_th / 3600
        bp.hist = getattr(bp, 'hist', [])
        bp.hist.append((bp.t, p_in, info['i_usb'], i_cell, bp.T_panel, max(q.Tj for q in P.values())))
        if len(bp.hist) > 600: del bp.hist[:100]
        bp.t += dt_th
        if info.get('nonconv'):
            s.once(b, bp, 'nonconv', 'DEBUG', 'решатель не сошёлся (невязка %.1e) — шаг пропущен, оставлена прежняя рабочая точка; проверки отказов не применялись' % info['residual'])
        else:
            bp.__dict__.setdefault('_once', set()).discard('nonconv')
            s.check(b, bp, V, info, I, d, dt_th, dt_e, panel, i_cell)
        if bp.t >= bp.next_log and b is s.sel:
            bp.next_log = bp.t + 10.0
            hot = max(P.values(), key=lambda q: q.Tj)
            s.log(b, 'DEBUG', 't=%.0f с: SYS %.2f В, LED %.2f В, AON %.2f В, BAT %.2f В, Iяч %.2f А; горячее всего %s %.1f °C; панель %.1f °C; ячейка %.1f °C' %
                  (bp.t, Vs, Vl, Vo, Va, i_cell, hot.ref, hot.Tj, bp.T_panel, bp.t_cell))

    # -------------------------------------------------------------- physical criteria
    def fast(s, b, bp, V, info, dts):
        """electrical events faster than a step (µs–ms): TVS energy, eFuse abs max, cell PCM / fuse / copper race.
        Evaluated on the solved point BEFORE heating, so the step's dissipation uses the post-event circuit."""
        P = bp.parts; p = s.p; changed = False
        # ---- v13 USB front end: TVS energy, eFuse abs max / OVC clamp
        vc = bp.vconn; dt_e = dts; dt = dts
        if vc > DS['TPS259531']['vin_abs'] and P['U_OVP1'].state == 'ok':
            s.fail(b, bp, 'U_OVP1', 'short', 'VBUS_CONN %.1f В > abs max 20 В (TVS SMF12A не удержал: источник %.1f В, R %.2f Ом)' % (vc, bp.usb_src, p['usb_r']))
            s.log(b, 'INFO', 'Последствие: eFuse пробит накоротко — VBUS = VBUS_CONN; дальше защищает только BQ25185 VIN_OVP 18.5 В (abs max 25 В).'); changed = True
        ptv = vc * bp.i_tvs if P['D_VBUS1'].state == 'ok' else 0.0
        if ptv > DS['SMF12A']['p_cont'] and P['D_VBUS1'].state == 'ok':
            t_allow = 1e-3 * (DS['SMF12A']['ppk'] / ptv) ** 2                 # PPK ∝ t^-1/2 (10/1000 µs rating curve, assumption-level)
            bp.trace_dmg['tvs'] = bp.trace_dmg.get('tvs', 0) + (dt_e or dt) / t_allow
            if bp.trace_dmg['tvs'] >= 1:
                s.fail(b, bp, 'D_VBUS1', 'short', 'TVS SMF12A: %.0f Вт дольше допустимого (%.3g мс по кривой PPK)' % (ptv, t_allow * 1e3))
                s.log(b, 'INFO', 'Последствие: VBUS_CONN закорочен TVS, адаптер уходит в ограничение тока; плата питается от батареи.')
                bp.vconn, bp.i_tvs = 0.0, 0.0; changed = True
        if info['i_batfet'] > DS['BQ25185']['batocp'] and not bp.flags['batfet_off']:
            bp.flags['batfet_off'] = True; s.log(b, 'WARN', 'BQ25185 BATOCP: ток BAT→SYS %.1f А > 3 А — BATFET выключен (защита)' % info['i_batfet'])
        # battery protection (PCM) / UVLO / OVP
        # ---- battery path: F_BAT1 (I²t / time-current curve) races the copper (Onderdonk) — whichever is faster opens first
        ia = abs(info['i_cell'])
        if ia > DS['F466_2A']['i_n'] * 1.1 and P['F_BAT1'].state == 'ok':
            r_ = ia / DS['F466_2A']['i_n']
            if r_ >= 3: t_open = DS['F466_2A']['i2t'] / ia ** 2                         # adiabatic: nominal melting I²t
            elif r_ >= 2: t_open = 5.0 * (0.2 / 5.0) ** (r_ - 2)                           # 200 % ≤ 5 s, 300 % ≤ 0.2 s (datasheet points)
            else: t_open = 5.0 * (1.0 / (r_ - 1)) ** 4                                    # < 200 %: long (assumption)
            t_left_f = (1 - bp.trace_dmg.get('fuse', 0)) * t_open
            worst = None
            for net, nm, fr in s.bat_paths:
                for k, frac in enumerate(fr):
                    sg = nm.seg[k]
                    if sg[3] is None: continue
                    tf = pcbnet.onderdonk_time(ia * abs(frac), sg[3] * sg[4], max(25, p['ambient']))
                    if worst is None or tf < worst[0]: worst = (tf, sg, net)
            t_left_c = (1 - bp.trace_dmg.get('bat_trace', 0)) * worst[0] if worst else float('inf')
            if p['src'] == 'battery' and p['pcm'] and ia > 4.0 and not bp.flags['pcm_open'] and 5e-4 < min(t_left_f, t_left_c):
                bp.flags['pcm_open'] = True; changed = True                       # cell PCM short-circuit delay ~0.2–1 ms (assumption 0.5 ms) beats fuse/copper
                s.log(b, 'WARN', 'Защита ячейки (PCM): КЗ %.1f А — отключение за ~0.5 мс (раньше предохранителя: %.1f мс), без повреждений' % (ia, t_left_f * 1e3))
                return changed
            if t_left_f <= dts and t_left_f <= t_left_c:
                bp.trace_dmg['fuse'] = 1.0
                if worst: bp.trace_dmg['bat_trace'] = bp.trace_dmg.get('bat_trace', 0) + t_left_f / worst[0]
                s.fail(b, bp, 'F_BAT1', 'open', 'предохранитель 0466002 2 А: %.1f А, сработал за %.2f мс (I²t %.3f А²с); медь (худший участок %s %.2f мм) успела бы расплавиться только за %.0f мс' %
                       (ia, t_left_f * 1e3, DS['F466_2A']['i2t'], worst[2] if worst else '-', (worst[1][3] * 1e3) if worst else 0, (worst[0] * 1e3) if worst else 0))
                s.log(b, 'INFO', 'Защита сработала штатно: батарея отключена предохранителем, дорожки целы, возгорания нет.'); changed = True
            else:
                bp.trace_dmg['fuse'] = bp.trace_dmg.get('fuse', 0) + dts / t_open
                if worst:
                    bp.trace_dmg['bat_trace'] = bp.trace_dmg.get('bat_trace', 0) + dts / worst[0]
                    if bp.trace_dmg['bat_trace'] >= 1 and not bp.flags.get('trace_fused'):
                        bp.flags['trace_fused'] = True
                        changed = True
                        s.fail(b, bp, 'F_BAT1', 'open', 'дорожка %s %.2f мм расплавилась раньше предохранителя (%.1f А)' % (worst[2], worst[1][3] * 1e3, ia), fire=not p['pcm'])
        return changed

    def fail(s, b, bp, ref, mode, cause, fire=False, xy=None):
        part = bp.parts.get(ref)
        if part is not None:
            if part.state != 'ok': return
            part.state = mode
            if ref == 'U_ESD1': part.P = 0.0
        x, y = xy if xy else (part.x, part.y)
        bp.fires.append(dict(x=x, y=y, t0=s.w.now, fire=fire, ref=ref))
        s.log(b, 'FAIL', '%s: %s → отказ (%s)%s' % (ref, cause, {'short': 'КЗ', 'open': 'обрыв'}.get(mode, mode),
              ' — ВОЗМОЖНО ВОЗГОРАНИЕ' if fire else ' — гибель компонента, без открытого огня'))
    def limit(s, b, bp, what):
        if bp.first_limit is None:
            bp.first_limit = (bp.t, what); s.log(b, 'WARN', 'Первым достигнут предел: %s (t=%.0f с)' % (what, bp.t))

    def check(s, b, bp, V, info, I, d, dt, dt_e, panel, i_cell):
        P = bp.parts; f = s.faults; p = s.p
        Vb, Vs, Va, Vo = V['VBUS'], V['SYS'], V['BAT'], V['AON_3V3']
        if P['U_ESD1'].state == 'ok' and P['U_ESD1'].Tj > DS['USBLC6']['tj_fail']:
            s.fail(b, bp, 'U_ESD1', 'short', 'VBUS %.1f В > VBR 6 В, ток фиксации %.2f А, %.1f Вт → TJ > %.0f °C' % (Vb, info['i_esd'], P['U_ESD1'].P, DS['USBLC6']['tj_fail']))
            s.log(b, 'INFO', 'Последствие: VBUS закорочен, адаптер в ограничении тока; плата работает от батареи. Энергия ограничена адаптером — возгорания нет.')
        if Vb > DS['BQ25185']['vin_abs']: s.fail(b, bp, 'U_CHG1', 'short', 'VIN %.1f В > abs max 25 В' % Vb)
        elif Vb > DS['BQ25185']['vin_ovp'] and P['U_CHG1'].state == 'ok': s.limit(b, bp, 'BQ25185 VIN_OVP (%.1f В) — вход отключён, защита' % Vb)
        for ref, lim in (('U_LED_PWR1', DS['TPS63802']['vin_abs']), ('U_LDO1', DS['TLV75733']['vin_abs'])):
            if Vs > lim and P[ref].state == 'ok':
                s.fail(b, bp, ref, 'short', 'Vin %.1f В > abs max %.1f В' % (Vs, lim))
        if Vo > DS['ESP32S3']['vdd_abs'] and P['U1'].state == 'ok':
            s.fail(b, bp, 'U1', 'short', 'VDD %.2f В > abs max 3.6 В' % Vo)
        if f.get('reverse') and P['Q_BAT1'].state == 'ok': s.once(b, bp, 'rev', 'INFO', 'Обратная полярность ячейки: Q_BAT1 AO3401A закрыт (VGS обратного знака), ток не течёт — плата защищена')
        if Va < -0.3 and P['U_CHG1'].state == 'ok':
            s.fail(b, bp, 'U_CHG1', 'short', 'обратная полярность: BAT %.2f В < −0.3 В, ток через внутренние диоды %.1f А' % (Va, abs(i_cell)))
            s.fail(b, bp, 'U_GAUGE1', 'short', 'обратная полярность на CELL')
        # thermal protections (recoverable) and limits
        def prot(flag, tj, on_t, off_t, name, msg_on, ref=None):
            if ref and P[ref].state != 'ok': return                           # a destroyed part has no working protection
            if tj > on_t and not bp.flags.get(flag):
                bp.flags[flag] = True; n = bp.flags.get(flag + '_n', 0) + 1; bp.flags[flag + '_n'] = n
                if n == 1: s.log(b, 'WARN', msg_on % tj); s.limit(b, bp, name)
                elif n == 2: s.log(b, 'WARN', '%s: защита циклит (авто-повтор/остывание) — дальнейшие срабатывания не логируются' % name)
            elif bp.flags.get(flag) and tj < off_t:
                bp.flags[flag] = False
                if bp.flags.get(flag + '_n', 0) == 1: s.log(b, 'INFO', '%s: остыл до %.0f °C, работа возобновлена' % (name, tj))
        tj = min(P['U_CHG1'].Tj, 400.0)
        if tj > DS['BQ25185']['treg']: s.limit(b, bp, 'BQ25185 TREG 100 °C — ток заряда снижается')
        prot('chg_tshut', tj, DS['BQ25185']['tshut'], DS['BQ25185']['tshut_rec'], 'BQ25185 TSHUT', 'BQ25185 TSHUT %.0f °C: заряд и SYS выключены (защита)', 'U_CHG1')
        prot('tps_otp', P['U_LED_PWR1'].Tj, DS['TPS63802']['tj_abs'], 130, 'TPS63802 OTP', 'TPS63802 перегрев %.0f °C: защита от перегрева, LED_4V1 выключен', 'U_LED_PWR1')
        if info.get('i_tps_out', 0) >= info.get('tps_iol', 9) * 0.97: s.limit(b, bp, 'TPS63802 ограничение тока %.2f А' % info['tps_iol'])
        prot('ldo_tsd', P['U_LDO1'].Tj, DS['TLV75733']['tsd'], 145, 'TLV75733 TSD', 'TLV75733 TSD %.0f °C: AON выключен', 'U_LDO1')
        if getattr(bp, 'vconn', 0) > DS['TPS259531']['vovc'] + 0.2 and P['U_OVP1'].state == 'ok': s.once(b, bp, 'ovc', 'WARN', 'U_OVP1 TPS259531: VBUS_CONN %.1f В > 5.7 В — OVC-клампа держит VBUS ≤ 5.7 В (защита работает)' % bp.vconn)
        prot('efuse_otp', P['U_OVP1'].Tj, DS['TPS259531']['tsd'], 130, 'TPS259531 OTP', 'U_OVP1 eFuse перегрев %.0f °C (клампа рассеивает (VBUS_CONN−5.7 В)·I): выход выключен, авто-повтор', 'U_OVP1')
        if p['src'] == 'battery':
            if p['pcm'] and abs(i_cell) > 4.0 and not bp.flags['pcm_open'] and P['F_BAT1'].state == 'ok':
                bp.flags['pcm_open'] = True; s.log(b, 'WARN', 'Защита ячейки (PCM): ток %.1f А > 4 А — ячейка отключена, без повреждений' % abs(i_cell))
            if 0 < Va < 3.0 and not bp.flags.get('buvlo') and not bp.flags['pcm_open'] and P['F_BAT1'].state == 'ok': bp.flags['buvlo'] = True; s.log(b, 'WARN', 'BQ25185 BUVLO: BAT %.2f В < 3.0 В — разряд остановлен' % Va); s.limit(b, bp, 'BUVLO батареи')
            if bp.t_cell > 60: s.limit(b, bp, 'ячейка > 60 °C (предел разряда Li-ion)')
            if bp.t_cell > 130 and not bp.flags.get('runaway'):
                bp.flags['runaway'] = True; s.fail(b, bp, 'J_BAT1', 'open', 'ячейка %.0f °C > 130 °C (плавление сепаратора, тепловой разгон)' % bp.t_cell, fire=True)
        if p['src'] == 'bench' and Va > 4.6: s.limit(b, bp, 'VBAT %.2f В > 4.6 В (абс. макс. заряда)' % Va)
        if abs(i_cell) > DS['PicoBlade']['i_contact'] * 3: s.limit(b, bp, 'J_BAT1 ток %.1f А > 1 А/контакт' % abs(i_cell))
        # LED: overdrive criterion (peak > IFP 50 mA accumulates damage; PD 72 mW average) -> open
        iset_over = I > DS['NCD0603W1']['ifp']
        if iset_over.any():
            bp.led_dmg += np.where(iset_over, (I / DS['NCD0603W1']['ifp'] - 1) * dt * 0.5, 0)
            newdead = (bp.led_dmg >= 1) & ~bp.led_dead
            if newdead.any():
                bp.led_dead |= newdead
                rr, cc = np.nonzero(newdead)
                s.log(b, 'FAIL', 'LED: %d шт. перегорели (обрыв): пиковый ток до %.0f мА > IFP 50 мА; например строка %d столбец %d' % (len(rr), I.max() * 1e3, rr[0] + 1, cc[0] + 1))
                if panel is not None:
                    pd_ = __import__('ledsim.world', fromlist=['panel_data']).panel_data(panel.kind)
                    bp.fires.append(dict(panel=panel, led=int(rr[0] * 32 + cc[0]), t0=s.w.now, fire=False, ref='LED'))
        # brown-out
        if Vo < DS['ESP32S3']['bod'] and b.powered and not bp.flags['bod'] and P['U1'].state == 'ok':
            bp.flags['bod'] = True; s.log(b, 'WARN', 'ESP32-S3 brown-out: AON %.2f В < %.1f В → сброс' % (Vo, DS['ESP32S3']['bod'])); b.node.reset()
        elif Vo > DS['ESP32S3']['bod'] + 0.1 and bp.flags['bod']: bp.flags['bod'] = False; s.log(b, 'INFO', 'AON восстановлен %.2f В — загрузка' % Vo)
        # board dead?
        dead = None
        if P['U1'].state != 'ok': dead = 'U1 вышел из строя'
        elif Vo < 1.0: dead = 'нет AON_3V3'
        if dead and bp.dead is None:
            bp.dead = dead; s.log(b, 'FAIL', 'Плата не работает: %s' % dead); b.phys_dead = dead; b.node.reset()
        elif not dead and bp.dead: bp.dead = None; b.phys_dead = None

    def system_power(s):
        bs = [s.boards[b.id] for b in s.w.boards if b.id in s.boards and hasattr(s.boards[b.id], 'pw')]
        n = len(s.w.boards); k = len(bs)
        if not k: return None
        tot = sum(bp.pw['total'] for bp in bs) * n / k                       # unvisited boards extrapolated
        peak = max(bp.pw['total'] for bp in bs)
        e = sum(getattr(bp, 'e_wh', 0) for bp in bs) * n / k
        return dict(w=tot, a5=tot / 5.0, psu_w=peak * n * 1.25, psu_a=peak * n * 1.25 / 5.0, wh=e, n=n, k=k,
                    p_led=sum(bp.pw['p_led'] for bp in bs) * n / k, loss=sum(bp.pw['p_loss'] for bp in bs) * n / k)
    def summary(s, b):
        bp = s.boards.get(b.id)
        if not bp: return None
        hot = max(bp.parts.values(), key=lambda q: q.Tj)
        failed = [q.ref + ':' + q.state for q in bp.parts.values() if q.state != 'ok']
        return dict(rails=bp.rails, hot=(hot.ref, hot.Tj), failed=failed, first=bp.first_limit, dead=bp.dead, soc=bp.soc, gauge=bp.gauge,
                    i_cell=bp.info.get('i_cell', 0), pw=getattr(bp, 'pw', {}), e_wh=getattr(bp, 'e_wh', 0.0), t_panel=bp.T_panel, t_cell=bp.t_cell, fires=len(bp.fires), flags=dict(bp.flags))
