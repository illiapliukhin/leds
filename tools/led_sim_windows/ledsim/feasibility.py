"""Hardware feasibility of every effect on the real board (ESP32-S3 @ 240 MHz, 512 KB SRAM, 8 MB flash, 32x32 panel
1/32 scan @ 960 Hz, 10 mA/LED, row ≤ 0.32 A, USB input limit 0.475 A via BQ25185 R_ILIM1 18k, RS-485 500 kbit/s).

CPU cost model (estimate, documented in the Модели tab / README):
  * The reference kernel is the firmware's own DEMO_PLASMA: per pixel 6 sinf + 1 sqrtf + ~25 FPU ops + store.
    On the S3 (Xtensa LX7 single-precision FPU: add/mul/madd 1 cycle, newlib sinf ≈ 120 cycles, sqrtf ≈ 30 cycles —
    assumptions from the LX7 FPU ISA and newlib's float kernels) that is ≈ 800 cycles/pixel ≈ 0.82 Mcycles/frame
    ≈ 3.4 ms. Timing the same compiled C on this box gives the box→S3 factor; timing a numpy port of the same kernel
    gives the numpy→S3 factor used for the cube effects (which are numpy in the simulator, C-equivalent on the board).
  * Budget: core 0 runs the effect; core 1 runs the scan engine (build_data ≈ 53 k cycles/frame) and RS-485. An effect
    may use ≤ 60 % of core 0 → ≤ 20 ms per frame for ≥ 30 fps (≤ 10 ms for 60 fps).
  * The cube: every layer is one board computing only its own 32x32 layer, so the per-board cost = volume cost / N
    (+ the shared per-frame part, which every board repeats — measured at N=8 where it dominates).
RAM: SRAM 512 KB − IDF/FreeRTOS/stack/RS-485/Wi-Fi off ≈ 230 KB (assumption) − 3 scan buffers 3 × 41.7 KB = 125 KB
     → ≤ 150 KB for the effect (state + float layer + 8-bit framebuffers).
Flash: 8 MB − app ≈ 1.1 MB − OTA slot ≈ 1.1 MB (if used) − NVS/phy → ≤ 4 MB for precomputed content per board.
Power: LED current = Σ duty × 10 mA / 32 (1/32 scan); peak row current = lit LEDs in a row × 10 mA (≤ 0.32 A by
     construction: 32 columns); input I = (I_LED·4.1 V / η 0.90 + 0.40 W ESP32/LDO/logic) / 5 V ≤ 0.475 A (R_ILIM1)."""
import time, math
import numpy as np
from . import host

F_CPU = 240e6
REF_CYC_PX = 6 * 120 + 30 + 25 + 20                 # plasma: 6 sinf, 1 sqrtf, ~25 FPU ops, pxf/store
REF_S3_S = REF_CYC_PX * 1024 / F_CPU                # ≈ 3.4 ms
BUDGET_S = 0.6 / 30                                 # ≤ 20 ms on core 0 for ≥ 30 fps
RAM_TOTAL, RAM_SYS, RAM_SCAN = 512 * 1024, 230 * 1024, 3 * 20832 * 2
RAM_EFFECT = RAM_TOTAL - RAM_SYS - RAM_SCAN
FLASH_CONTENT = 4 * 1024 * 1024
I_IN_LIMIT, ROW_LIMIT, I_LED = 0.475, 0.32, 0.010
BUS_BPS = 500000 / 10                               # bytes/s on RS-485 (10 bits/byte)

def _time(fn, reps):
    fn(); t0 = time.perf_counter()
    for i in range(reps): fn(i)
    return (time.perf_counter() - t0) / reps

_cal = {}
def calibrate():
    if _cal: return _cal
    plasma = host.DEMOS.index('plasma') + 1
    c = min(_time(lambda i=0: host.demo_frame(plasma, 1000 + i), 200) for _ in range(3))
    r, cc = np.mgrid[0:32, 0:32].astype(np.float32)
    def np_plasma(i=0):
        ts = (1000 + i) / 60
        v = np.sin(cc * 0.22 + ts * 1.3) + np.sin(r * 0.17 - ts * 0.9) + np.sin((r + cc) * 0.13 + ts * 1.7) + \
            np.sin(np.sqrt((cc - 16 + 8 * np.sin(ts * 0.5)) ** 2 + (r - 16) ** 2) * 0.3)
        return np.clip((v + 4) / 8, 0, 1)
    n = min(_time(np_plasma, 200) for _ in range(3))
    _cal.update(c_host=c, np_host=n, k_c=REF_S3_S / c, k_np=REF_S3_S / n)
    return _cal

def power(levels, br=128, gamma=2.2):
    """levels [L,32,32] uint8 of ONE board's frames -> (avg input A, peak input A, peak row A)"""
    duty = host.duty_lut(br, gamma)[levels]                                  # on-fraction per LED (8 BCM planes)
    i_led = duty.reshape(len(levels), -1).sum(1) * I_LED / 32               # 1/32 scan
    i_in = (i_led * 4.1 / 0.90 + 0.40) / 5.0
    row = ((levels > 0).sum(-1) * I_LED).max()
    return float(i_in.mean()), float(i_in.max()), float(row)

def verdict(cost_s, ram, flash, i_peak, row, bus_bps):
    lim = []
    if cost_s > BUDGET_S: lim.append('CPU %.1f мс > %.0f мс' % (cost_s * 1e3, BUDGET_S * 1e3))
    if ram > RAM_EFFECT: lim.append('RAM %d КБ > %d КБ' % (ram // 1024, RAM_EFFECT // 1024))
    if flash > FLASH_CONTENT: lim.append('flash %.1f МБ > 4 МБ' % (flash / 2 ** 20))
    if i_peak > I_IN_LIMIT: lim.append('вход %.3f А > %.3f А' % (i_peak, I_IN_LIMIT))
    if row > ROW_LIMIT + 1e-9: lim.append('строка %.2f А > 0.32 А' % row)
    if bus_bps > BUS_BPS * 0.5: lim.append('RS-485 %.0f Б/с > 50 %%' % bus_bps)
    return lim

def fps_of(cost_s): return min(60.0, 0.6 / max(cost_s, 1e-6))

# ---- 2D (firmware demo.c / patterns.c, measured as compiled C)
RAM_2D = 1024 + 4096 + 1024 + 1024 + 4096 + 1024 + 3 * 1024 + 1024    # s_fb, s_ff, s_prev, s_life, s_lifef, n, dither, from

def check_2d(frames=120):
    cal = calibrate(); out = []
    for i, nm in enumerate(host.DEMOS):
        mode = i + 1
        host_s = min(_time(lambda k=0: host.demo_frame(mode, 2000 + k), frames) for _ in range(3))
        lv = np.stack([host.demo_frame(mode, 3000 + k * 7) for k in range(60)])
        ia, ip, row = power(lv); ip255 = power(lv, 255)[1]
        cost = host_s * cal['k_c']
        out.append(dict(name=nm, kind='2d', s3_ms=cost * 1e3, fps=fps_of(cost), ram=RAM_2D, flash=0, i_avg=ia, i_peak=ip, i_peak255=ip255, row=row,
                        bus=19 * 60, lim=verdict(cost, RAM_2D, 0, ip255, row, 19 * 60)))
    for i in range(16):
        nm = host.L.sim_canvas_name(i)
        if not nm or nm == b'?': continue
        nm = nm.decode()
        host_s = min(_time(lambda k=0: host.tile(1, 0, 0, 3, 2, i, 60, 2000 + k), frames) for _ in range(3))
        lv = np.stack([host.tile(1, 0, 0, 3, 2, i, 60, 3000 + k * 7) for k in range(60)])
        ia, ip, row = power(lv); ip255 = power(lv, 255)[1]; cost = host_s * cal['k_c']
        out.append(dict(name='стек:' + nm, kind='canvas', s3_ms=cost * 1e3, fps=fps_of(cost), ram=RAM_2D, flash=0, i_avg=ia, i_peak=ip, i_peak255=ip255,
                        row=row, bus=19 * 60, lim=verdict(cost, RAM_2D, 0, ip255, row, 19 * 60)))
    return out

# ---- 3D cube effects: per-board state RAM / flash / bus beyond the common 4 KB float layer + 1 KB levels + 4 KB persistence
STATE = {  # name: (RAM bytes, flash bytes per board, bus bytes per frame per board, note)
    'life': (3 * 128 + 4096, 0, 2 * 128 / 9, 'own + 2 neighbour layers bit-packed, exchanged each generation (every 9 frames)'),
    'fireworks': (64 * 24, 0, 0, '≤ 64 particles, same seeded RNG on every board'),
    'snake': (256 * 4, 0, 0, 'body ≤ 256 cells, seeded'),
    'ambigram': (0, 1024, 0, 'precomputed layer slice in flash'),
    'anamorph': (0, 1024, 0, 'precomputed layer slice in flash'),
    'image': (1024, 1024 * 600, 0, 'LV3D: own layer of ≤ 600 frames (10 s @ 60 fps) in flash'),
    'walker': (0, 60 * 1024, 0, 'предрасчёт во flash: цикл 60 кадров × 1 КБ на плату'),
    'runner': (0, 40 * 1024, 0, 'предрасчёт во flash: цикл 40 кадров × 1 КБ на плату'),
    'gogo': (0, 225 * 1024, 0, 'предрасчёт во flash: 8 тактов @128 bpm = 225 кадров × 1 КБ на плату'),
    'vysh3d': (6 * 1024, 0, 0, 'грани 2D (как patterns.c) + звезда только в своей рамке'),
    'slices2d': (0, 0, 0, 'firmware 2D demo per layer'), 'extrude2d': (0, 0, 0, 'firmware 2D demo per layer'),
}
COMMON_3D = 4096 + 1024 + 4096

def check_3d(cv, names, Ns=(8, 16, 32), frames=24):
    cal = calibrate(); out = []
    from .view_cube import DEMOS3D
    for N in Ns:
        cv.N = N; cv._grid()
        for nm in names:
            cv.demo = DEMOS3D.index(nm); cv.t0 = time.time()
            for k in range(3): cv.volume(k / 60)                                # warm caches/state
            if nm in getattr(__import__('ledsim.view_cube', fromlist=['FIG_LOOP']), 'FIG_LOOP'):
                P = __import__('ledsim.view_cube', fromlist=['FIG_LOOP']).FIG_LOOP[nm]
                for k in range(2 * P + 40): cv.volume(k / 60)                   # bake the flash clip (build step, not per frame)
            t0 = time.perf_counter(); vols = []
            for k in range(frames): vols.append(np.clip(cv.volume(1.0 + k / 30), 0, 1))
            host_s = (time.perf_counter() - t0) / frames
            per_board = host_s * cal['k_np'] / N if N > 1 else host_s * cal['k_np']
            per_board = max(per_board, host_s * cal['k_np'] / 32 * 1.0)          # never below the 32-layer share
            lv = np.stack([(v * 255 + 0.5).astype(np.uint8) for v in vols])      # [F, N, 32, 32]
            boards = [power(lv[:, b]) for b in range(N)]
            ia = max(b[0] for b in boards); ip = max(b[1] for b in boards); row = max(b[2] for b in boards)
            ip255 = max(power(lv[:, b], 255)[1] for b in range(N))
            ram, flash, bus, note = STATE.get(nm, (0, 0, 0, ''))
            ram += COMMON_3D + RAM_SCAN * 0                                      # scan buffers are in RAM_SYS budget split
            bus_bps = (19 + bus) * 60
            out.append(dict(name=nm, kind='3d', N=N, s3_ms=per_board * 1e3, fps=fps_of(per_board), ram=ram, flash=flash, i_avg=ia, i_peak=ip,
                            i_peak255=ip255, row=row, bus=bus_bps, note=note, lim=verdict(per_board, ram, flash, ip255, row, bus_bps)))
    return out

def line(r):
    tag = ('N=%-2d ' % r['N']) if r['kind'] == '3d' else ''
    return '%s%-16s S3 ≈ %5.1f мс/кадр → %2.0f fps · RAM %3d КБ · flash %4d КБ · вход пик %.3f А (ярк. 255; лимит 0.475) · строка %.2f А · RS-485 %4.0f Б/с%s' % (
        tag, r['name'], r['s3_ms'], r['fps'], r['ram'] // 1024, r['flash'] // 1024, r['i_peak255'], r['row'], r['bus'], ('  [' + r['note'] + ']') if r.get('note') else '')
