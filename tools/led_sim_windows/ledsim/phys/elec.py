"""Electrical models + solvers (all SI units).

Power tree: nodal analysis with Newton-Raphson (numeric Jacobian, damped) on the node voltages
VBUS, SYS, BAT (board side of J_BAT), LED_4V1, AON_3V3. Every element contributes a branch current
i(v) to KCL; behavioural regulators are smooth functions so Newton converges.
LED matrix: per-row ladder network (feed: AO3403 Rds(on)(T) + board copper + FFC conductor; distributed
panel row bus) with the LED Shockley diode + MBI5124 constant-current channel per column, solved by
nested Newton (per LED) / Gauss-Seidel (bus) for all 32 rows at once (numpy)."""
import math
import numpy as np

VT0 = 0.025852                       # kT/q at 300 K
def vt(T): return 8.617333e-5 * (T + 273.15)

# ------------------------------------------------------------------ datasheet constants (S = source)
DS = {
 'TPS63802': dict(vin_abs=6.0, vin_max=5.5, vin_start=1.8, isw_lim=5.0, iout_rated=2.0, theta_ja=81.0, psi_jb=23.5, tj_abs=150.0,
                  vfb=0.5, S='TI TPS63802 Rev.D: abs max VIN 6 V, VIN 1.3-5.5 V, switch limit 5 A typ, 2 A out, RθJA 81, ΨJB 23.5 °C/W, TJ 150 °C'),
 'TLV75733': dict(vin_abs=6.0, rdo=0.3 / 1.0, ilim=1.2, ignd=33e-6, theta_ja_evm=100.8, theta_ja_jedec=231.0, tsd=165.0,
                  S='TI TLV757P: dropout 300 mV @ 1 A (REWORK_LOG), ILIM ≥ 1.2 A, IGND ≤ 33 µA, RθJA 100.8 (EVM)…231 °C/W (JEDEC); abs max VIN 6.0 V и TSD 165 °C — допущение'),
 'BQ25185': dict(r_ilim=18e3, vin_abs=25.0, vin_ovp=18.5, vin_ovp_hys=0.5, vsys=4.5, ilim_max=1.1, ibat_dis=3.125, batocp=3.0, treg=100.0, tshut=150.0, tshut_rec=135.0,
                 theta_ja=60.0, S='TI BQ25185 Rev.B: VIN abs max 25 V, OVP 18.5 V (18-19), hyst 0.5 V, SYS 4.5 V, IIN ≤ 1.1 A, BAT→SYS 3.125 A, BATOCP ≥ 3 A, TREG 100 °C, TSHUT 150/135 °C; RθJA 60 °C/W — допущение'),
 'AO3403': dict(rds25=0.115, rds_tc=0.004, id_max=2.6, theta_ja=125.0, tj_abs=150.0,
                S='AOS AO3403: RDS(on) ≤ 115 mΩ @ VGS −4.5 V, ID −2.6 A; ТКС +0.4 %/°C и RθJA 125 °C/W — типовые для SOT-23 (допущение)'),
 'NCD0603W1': dict(vf5=2.8, if_max=0.020, ifp=0.050, pd=0.072, top_max=85.0, S='NationStar NCD0603W1: VF 2.6/2.8/3.6 В @ 5 мА, IF 20 мА, IFP 50 мА (≤0.1 мс, ≤1/10), PD 72 мВт, −30…+85 °C'),
 'MBI5124': dict(k=15.0 * 1.24, vknee=0.4, idd=0.008, S='Macroblock MBI5124: Iout = 1.24 В/Rext·15 (sim/bringup/netmodel); перегиб Vds 0.4 В и IDD 8 мА — допущение'),
 'USBLC6': dict(vbr=6.0, rdyn=0.6, theta_ja=250.0, tj_fail=200.0, S='ST USBLC6-2SC6: VBR ≥ 6 В (VBUS-GND); Rdyn 0.6 Ом, RθJA 250 °C/W, отказ при TJ>200 °C — допущение'),
 'ESP32S3': dict(vdd_abs=3.6, bod=2.7, modes={'deep_sleep': 8e-6, 'idle': 0.025, 'active': 0.050, 'wifi_rx': 0.095, 'wifi_tx': 0.250, 'wifi_tx_peak': 0.355},
                 S='Espressif ESP32-S3 datasheet (типовые токи режимов; TX средний 250 мА — SIM_REPORT R1); BOD 2.7 В — допущение (уровень в sdkconfig)'),
 'TPS259531': dict(vin_abs=20.0, vovc=5.7, ron=0.034, k_ilim=2156.0, r_ilim=2700.0, uvlo=1.2 * (100 + 39) / 39, theta_ja=60.0, tsd=150.0,
                   S='TI TPS2595xx Rev.C: IN abs max 20 В, OVC-клампа 5.7 В тип. (5.5–5.9), RON 34 мОм, ILIM = 2156/R_ILM (R_ILM1 2.7 кОм → 0.80 А), EN-UVLO 100k/39k → 4.28 В, OTP авто-повтор; RθJA 60 °C/W — допущение'),
 'SMF12A': dict(vbr=13.3, vc=19.9, ipp=10.1, ppk=200.0, p_cont=0.5, S='SMF12A: VBR 13.3 В мин, VC 19.9 В при IPP 10.1 А (10/1000 мкс), PPK 200 Вт; длительно ~0.5 Вт (допущение). Rdyn = (VC−VBR)/IPP'),
 'F466_2A': dict(i_n=2.0, r=0.031, i2t=0.2326, S='Littelfuse 0466002.NRHF: 2 А, 63 В, R_хол 0.031 Ом, I²t плавл. 0.2326 А²с; 200 % ≤ 5 с, 300 % ≤ 0.2 с'),
 'AO3401A': dict(rds=0.044, vds_abs=-30.0, S='AOS AO3401A: RDS(on) 44 мОм тип. при VGS −4.5 В; VDS −30 В. Реверс батареи: затвор/исток обратны → FET закрыт, ток не течёт'),
 'PicoBlade': dict(i_contact=1.0, r_contact=0.010, S='Molex 53398 PicoBlade: 1 А/контакт (SIM_REPORT R5); 10 мОм контакт — допущение'),
}

# ------------------------------------------------------------------ battery: Thevenin + OCV(SOC)
OCV_SOC = np.array([0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1.0])
OCV_V = np.array([3.00, 3.45, 3.60, 3.68, 3.73, 3.77, 3.81, 3.86, 3.93, 4.00, 4.08, 4.13, 4.20])   # generic LCO/NMC 1S curve (assumption)
def ocv(soc): return float(np.interp(soc, OCV_SOC, OCV_V))
def r_int(r25, T): return r25 * math.exp(0.025 * (25 - T))        # ~2.5 %/°C rise when cold (assumption)

# ------------------------------------------------------------------ TPS63802 efficiency map
def tps_eta(iout, vin, vout):
    """digitised shape of datasheet Fig. 'Efficiency vs Output Current' (PFM/PWM, VOUT 3.3 V): ~94-96 % at
    0.1-1 A, falling at light load (Iq, PFM) and heavy load (I²R); buck-boost region penalty. Assumption-level fit."""
    i = max(iout, 1e-6)
    eta = 0.955 - 0.035 * math.exp(-i / 0.02) - 0.022 * i - 0.010 * abs(math.log(max(vin, 0.5) / vout)) - (0.015 if abs(vin - vout) < 0.3 else 0)
    if vin < vout: eta -= 0.015 * (vout - vin)                         # boost: higher RMS current
    return max(0.3, min(0.97, eta))

def _sp(z): return z + math.log1p(math.exp(-z)) if z > 0 else math.log1p(math.exp(z))
# BQ25185 ILIM/VSET resistor map (datasheet Table 6-1): no formula — the pin decodes one of 16 resistor values.
# (R kΩ, input current limit A (typ: ILIM100 = 0.090, ILIM500 = 0.475, ILIM1100 = 1.050), VBATREG V)
BQ_ILIM_MAP = [(130, .475, 4.1), (100, 1.05, 4.1), (75, .475, 4.4), (56, 1.05, 4.4), (43, .475, 4.35), (33, 1.05, 4.35),
               (24, .090, 4.2), (18, .475, 4.2), (13, 1.05, 4.2), (9.1, .475, 4.05), (6.8, 1.05, 4.05), (5.1, 1.05, 3.65),
               (3.6, .475, 3.6), (2.4, 1.05, 3.6)]

def bq_ilim(r_ohm):
    """(ILIM A, VBATREG V) for the resistor on ILIM/VSET: nearest map entry (log scale); > 180 k → 0.475 A, charge off; < 1.5 k → battery-only"""
    k = r_ohm / 1e3
    if k > 180: return 0.475, 0.0
    if k < 1.5: return 0.0, 0.0
    e = min(BQ_ILIM_MAP, key=lambda t: abs(math.log(t[0] / k)))
    return e[1], e[2]

def smooth_clip(x, lo, hi, k=200.0):
    if not isinstance(x, np.ndarray):
        a = lo + _sp(k * (x - lo)) / k
        return hi - _sp(k * (hi - a)) / k
    """differentiable clip for Newton"""
    a = lo + np.logaddexp(0, k * (x - lo)) / k
    return hi - np.logaddexp(0, k * (hi - a)) / k

# ------------------------------------------------------------------ power tree
class PowerTree:
    """unknowns v = [VBUS, SYS, BAT, LED, AON]"""
    NODES = ['VBUS', 'SYS', 'BAT', 'LED_4V1', 'AON_3V3']
    def __init__(s): s.v = np.array([0.0, 3.8, 3.8, 4.2, 3.3]); s.info = {}
    def branch(s, v, p):
        Vb, Vs, Va, Vl, Vo = v
        I = np.zeros(5); info = {}
        # USB adapter: Thevenin (V, R cable) with constant-current limit
        # v13: USB-C VBUS_CONN (SMF12A TVS) -> U_OVP1 TPS259531 eFuse (OVC clamp 5.7 V, ILIM 0.8 A, UVLO 4.28 V) -> VBUS
        ef = p.get('efuse', 'ok'); vc = p.get('vconn', p['usb_v'])
        if p['usb_on'] and not p['f_esd_short'] and ef != 'open' and not p.get('efuse_otp') and vc > 0.5:
            if ef == 'short': v_src, r_src, ilim = vc, p['usb_r'], p['usb_ilim']
            elif vc >= DS['TPS259531']['uvlo']:
                v_src = min(vc, DS['TPS259531']['vovc']); r_src = p['usb_r'] + DS['TPS259531']['ron']
                ilim = min(p['usb_ilim'], DS['TPS259531']['k_ilim'] / DS['TPS259531']['r_ilim'])
            else: v_src, r_src, ilim = 0.0, 1.0, 0.0
            i_usb = smooth_clip((v_src - Vb) / r_src, 0.0, ilim, 400) if ilim > 0 else 0.0
        else: i_usb = 0.0
        I[0] += i_usb; info['i_usb'] = i_usb
        # USBLC6 VBUS clamp (or failed short)
        i_esd = (Vb / 0.05) if p['f_esd_short'] else max(0.0, Vb - DS['USBLC6']['vbr']) / DS['USBLC6']['rdyn']
        I[0] -= i_esd; info['i_esd'] = i_esd
        # BQ25185 power path IN->SYS (valid VIN, not OVP, not TSHUT); linear FET (Ron 0.25 Ω assumption) regulating SYS = 4.5 V
        vin_ok = p['chg_ok'] and (Vb > Va + 0.08) and (Vb < DS['BQ25185']['vin_ovp']) and Vb > 3.0
        if p['f_chg_short']:
            i_in = (Vb - Vs) / 0.02
        elif vin_ok:
            # SYS regulator: target min(VSYS_REG, VIN − Ron·I) behind 5 mΩ, clipped to [0, ILIM]
            v_t = min(DS['BQ25185']['vsys'], Vb - 0.25 * p.get('i_in_prev', 0.3))
            i_in = smooth_clip((v_t - Vs) / 0.005, 0.0, p['ilim'], 300) + 0.01 * (v_t - Vs) * (Vb > Vs)   # 10 mS output conductance in current limit (keeps Newton gradient; ≤ 5 mA error)
            # battery-tracking VINDPM (datasheet §8.3.1): input current is cut back to hold VIN ≥ VBAT + 330 mV (3.6 V if VBAT < 3.5 V)
            vindpm = Va + 0.33 if Va > 3.5 else 3.6
            i_in = i_in / (1 + math.exp(-min(60.0, max(-60.0, (Vb - vindpm) / 0.01))))
            info['vindpm'] = vindpm
        else: i_in = 0.0
        I[0] -= i_in; I[1] += i_in; info['i_in'] = i_in
        # BAT FET BAT->SYS (supplement / battery-only), 50 mΩ (assumption)
        if p['batfet_on'] and not p['f_chg_short']:
            i_bf = float(np.logaddexp(0, 300 * (Va - Vs - 0.01))) / 300 / 0.05     # ideal-diode BATFET, smoothed (C¹ for Newton)
        else: i_bf = 0.0
        I[2] -= i_bf; I[1] += i_bf; info['i_batfet'] = i_bf
        # battery / bench supply into BAT node through J_BAT contacts + BAT_RAW copper (R_path from PCB)
        if p['src'] == 'battery' and p['bat_conn'] and not p['pcm_open'] and not p.get('fuse_open'):
            if p['reverse'] and p.get('q_bat', 'ok') == 'ok': i_cell = 0.0                  # v13: AO3401A blocks a reversed cell
            else:
                e = -p['ocv'] if p['reverse'] else p['ocv']
                i_cell = (e - Va) / (p['rint'] + p['r_path'])
        elif p['src'] == 'bench' and p['bat_conn'] and not p.get('fuse_open'):
            i_cell = smooth_clip((p['bench_v'] - Va) / (0.02 + p['r_path']), -p['bench_ilim'], p['bench_ilim'], 300)
        else: i_cell = 0.0
        I[2] += i_cell; info['i_cell'] = i_cell
        if p['f_bat_short']: I[2] -= Va / 0.005; info['i_short'] = Va / 0.005
        # reverse cell: charger BAT pin / gauge ESD conduct (diode to GND), Shockley-ish clamp
        if Va < -0.3 and not p['f_chg_open']: I[2] += (-Va - 0.6) / 0.08 if Va < -0.6 else 0
        # TPS63802 buck-boost SYS -> LED_4V1
        i_out = 0.0; i_tin = 0.0
        if p['tps_en'] and not p['f_tps_open'] and Vs > (1.3 if p['tps_running'] else DS['TPS63802']['vin_start']):
            vset = DS['TPS63802']['vfb'] * (1 + 681 / 91)
            iol = min(DS['TPS63802']['isw_lim'] * min(1.0, Vs / vset) * 0.55, 3.0)      # avg out current at peak-current limit (assumption: ripple+duty)
            i_out = smooth_clip((vset - Vl) / 0.01, -0.05, iol, 200)
            eta = tps_eta(max(i_out, 0), Vs, vset)
            i_tin = max(i_out, 0) * Vl / (eta * max(Vs, 0.3))
            info['tps_eta'] = eta; info['tps_iol'] = iol
        if p['f_tps_short']: i_tin += Vs / 0.03
        I[1] -= i_tin; I[3] += i_out; info['i_tps_in'] = i_tin; info['i_tps_out'] = i_out
        I[3] -= p['led_load'](Vl); I[3] -= p['extra_led_load']
        # TLV75733: dropout Rdo*I, ILIM foldback, TSD
        i_ldo = 0.0
        if p['f_ldo_short']: i_ldo = (Vs - Vo) / 0.05
        elif not p['ldo_tsd'] and not p['f_ldo_open']:
            vt_ = min(3.3, Vs - DS['TLV75733']['rdo'] * max(p['i_aon_prev'], 0))
            i_ldo = smooth_clip((vt_ - Vo) / 0.003, 0.0, DS['TLV75733']['ilim'], 300) + 0.01 * (vt_ - Vo) * (Vs > Vo)
        I[1] -= i_ldo + (DS['TLV75733']['ignd'] if not p['f_ldo_open'] else 0); I[4] += i_ldo; info['i_ldo'] = i_ldo
        # charger SYS->BAT: ICHG, CV 4.2 V, DPM (input headroom), TREG derating
        i_chg = 0.0
        if vin_ok and not p['f_chg_short'] and p['charge_en']:
            head = max(0.0, min(p['ilim'], i_in) - i_tin - i_ldo)  # DPM/VINDPM: charge only from what the input actually delivers
            cv = 1 / (1 + math.exp(min(60, (Va - 4.2) / 0.005)))
            i_chg = min(p['ichg'] * p['treg_k'], head) * cv
        I[1] -= i_chg; I[2] += i_chg; info['i_chg'] = i_chg
        # AON loads: ESP32-S3 + LED_LOGIC (TPS22917) + misc; constant-current until ~2.4 V then resistive
        i_aon = (p['i_esp'] + 0.025 + 0.004) * (1 / (1 + math.exp(-(Vo - 2.4) / 0.08)))
        if p['f_esp_short']: i_aon += Vo / 0.2
        I[4] -= i_aon; info['i_aon'] = i_aon
        # tiny leak to ground keeps the matrix regular
        I -= v * 1e-4                                                      # 10 kΩ bleed per node (keeps floating nodes defined)
        return I, info
    def envelope(s, p):
        """no node of this passive+regulator network can exceed the highest source (adapter/TVS, cell, bench, LED boost
        set-point) or go below the most negative one — used to bound every Newton iterate"""
        hi = max(p.get('vconn', p['usb_v']) if p['usb_on'] else 0.0, abs(p['ocv']), p['bench_v'], 4.3) + 0.5
        lo = -abs(p['ocv']) - 0.5 if p.get('reverse') else -0.7
        return lo, hi
    def solve(s, p, iters=40):
        """damped Newton with backtracking line search on ||KCL residual||; restarts from a cold
        initial guess if the warm start stalls in a non-physical local minimum. A non-converged result is
        REJECTED (previous operating point kept, info['nonconv']=True) instead of being fed to the failure checks."""
        s._env = s.envelope(p); prev = s.v.copy()
        r = s._solve(p, iters, np.clip(s.v.copy(), *s._env))
        if r[1]['residual'] > 2e-4:
            ov = p.get('ocv', 3.8); uv = p.get('usb_v', 5.0) if p.get('usb_on') else 0.0
            for guess in ([uv, min(4.5, max(uv - 0.3, ov)), ov, 4.24, 3.3], [5.0, 4.5, 3.8, 4.2, 3.3], [0.0, 3.6, 3.7, 4.2, 3.3], [0.0, 0.5, 0.5, 0.5, 0.5]):
                r2 = s._solve(p, iters, np.array(guess))
                if r2[1]['residual'] < r[1]['residual']: r = r2
                if r[1]['residual'] < 2e-4: break
        if r[1]['residual'] > 5e-3:                                   # still not a solution: keep the last good point
            s.v = prev; F, info = s.branch(prev, p); info['residual'] = float(np.max(np.abs(F))); info['nonconv'] = True
            s.info = info; return dict(zip(s.NODES, prev.tolist())), info
        return r
    def _solve(s, p, iters, v):
        F, _ = s.branch(v, p); nf = np.abs(F).max()
        for it in range(iters):
            if nf < 2e-5: break
            J = np.zeros((5, 5)); h = 1e-6
            for k in range(5):
                dv = v.copy(); dv[k] += h; J[:, k] = (s.branch(dv, p)[0] - F) / h
            try: step = np.linalg.solve(J - np.eye(5) * 1e-6, -F)
            except np.linalg.LinAlgError: step = -F * 0.01
            m = np.max(np.abs(step))
            if m > 1.0: step *= 1.0 / m
            a = 1.0
            while a > 1e-4:
                vn = np.clip(v + a * step, *getattr(s, '_env', (-50, 50))); Fn, _ = s.branch(vn, p); nn = np.abs(Fn).max()
                if nn <= nf * (1 + 1e-9) or a <= 1.5e-4: break
                a *= 0.5
            v, F, nf = vn, Fn, min(nn, nf) if nn <= nf else nn
        s.v = v; F, info = s.branch(v, p); info['residual'] = float(np.max(np.abs(F))); info['iters'] = it + 1
        s.info = info
        return dict(zip(s.NODES, v.tolist())), info

# ------------------------------------------------------------------ LED: Shockley fit + MBI5124 channel
class LedModel:
    """V = n·Vt·ln(I/Is) + I·Rs, fitted to VF(5 mA) = 2.8 V (datasheet typ) and VF(20 mA) = 3.10 V (assumption,
    typical InGaN 0603 slope); n = 4.0 (assumption); TC −2 mV/K at constant current (assumption)."""
    def __init__(s, vf5=2.8, vf20=3.10, n=4.0):
        s.n = n; s.Rs = (vf20 - vf5 - n * VT0 * math.log(4)) / 0.015
        s.Is = 0.005 / math.exp((vf5 - 0.005 * s.Rs) / (n * VT0))
    def vf(s, I, T=25.0):
        I = np.maximum(I, 1e-9)
        return s.n * VT0 * np.log(I / s.Is) + I * s.Rs - 0.002 * (T - 25)
    def current(s, V, T=25.0, iset=0.0102, vknee=0.4, short=None):
        """Newton per LED: V = Vf(I) + Vds(I), MBI channel I = Iset·(1-exp(-Vds/Vk')) -> Vds = -Vk'·ln(1-I/Iset).
        short=True: column shorted to GND (no MBI regulation) -> V = Vf(I)."""
        V = np.asarray(V, float); I = np.full(V.shape, iset * 0.9)
        vk = vknee / 3.0                                                       # 95 % of Iset at Vds = Vknee
        for _ in range(14):
            if short is None: sh = np.zeros(V.shape, bool)
            else: sh = short
            Ic = np.clip(I, 1e-9, None)
            ratio = np.clip(Ic / iset, 0, 0.999999)
            vds = np.where(sh, 0.0, -vk * np.log1p(-ratio))
            f = s.vf(Ic, T) + vds - V
            dvf = s.n * VT0 / Ic + s.Rs
            dvds = np.where(sh, 0.0, vk / (iset * (1 - ratio)))
            I = I - f / (dvf + dvds)
            I = np.where(sh, np.clip(I, 1e-9, 2.0), np.clip(I, 1e-9, iset * 0.999999))
        return np.where(V <= 0.5, 0.0, I)

def solve_rows(V_led, on, r_feed, r_panel, led, T_led=25.0, iset=0.0102, vknee=0.4, short_cols=None, shorted_rows=None, gs=10, I0=None):
    """All 32 rows: feed node = V_led − I_row·r_feed[r]; the panel row bus is a 31-segment ladder with total
    resistance 2·R_eff (uniform-load equivalent of the IR analysis' effective resistance). on[r,c] bool.
    Returns (I[r,c] LED currents in the MSB plane, V at each LED anode)."""
    on = np.asarray(on, bool)
    R = (2 * np.asarray(r_panel))[:, None] / 31.0                             # per segment
    Vn = np.full((32, 32), float(V_led)); I = np.zeros((32, 32)) if I0 is None else I0.copy()
    sc = np.zeros((32, 32), bool)
    if short_cols is not None: sc[:, short_cols] = True
    for _ in range(gs):
        Inew = np.where(on | sc, led.current(Vn, T_led, iset, vknee, sc), 0.0)
        I = 0.5 * I + 0.5 * Inew
        Irow = I.sum(1)
        vfeed = V_led - Irow * np.asarray(r_feed)
        down = np.cumsum(I[:, ::-1], 1)[:, ::-1]                                # current through segment c-1 -> c
        drop = np.cumsum(np.concatenate([np.zeros((32, 1)), down[:, 1:]], 1) * R, 1)
        Vn = vfeed[:, None] - drop
    if shorted_rows is not None:
        for r in shorted_rows: I[r] = 0.0; Vn[r] = 0.0
    return I, Vn
