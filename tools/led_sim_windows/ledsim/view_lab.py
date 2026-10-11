"""'Лаборатория' tab: electrothermal state of the selected board (heatmap, parts, rails, currents, battery),
parameters, presets and fault injection. The Lab itself (phys/lab.py) runs in every tab."""
import math, os, random, time, json
import numpy as np
import pygame
from .ui import text
from .phys.lab import Lab, PRESETS, PART_REFS
from .phys.elec import DS
from .view_system import layout_dir

def heat_rgb(t, lo, hi):
    x = np.clip((t - lo) / max(hi - lo, 1e-6), 0, 1)
    r = np.clip(3 * x, 0, 1); g = np.clip(3 * x - 1, 0, 1); b = np.clip(3 * x - 2, 0, 1) * 0.8 + (1 - np.clip(3 * x, 0, 1)) * 0.35
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)

LIMIT = {'U_LED_PWR1': 150, 'U_LDO1': 165, 'U_CHG1': 150, 'U_ESD1': 200, 'U1': 105, 'U_LED1': 125, 'U_LED2': 125, 'J_BAT1': 105,
         'L_LED1': 125, 'U_GAUGE1': 85, 'U_485': 125}

class LabView:
    def __init__(s, app):
        s.app = app; s.lab = None; s.parts_fx = []; s.msg = ''; s.scroll = 0
        s.surge_v, s.surge_ms, s.dip_v = 12.0, 50.0, 2.5
    def get(s):
        w = s.app.views['system'].w
        if s.lab is None or s.lab.w is not w: s.lab = Lab(w); w.lab = s.lab
        return s.lab
    def board(s):
        sv = s.app.views['system']; w = sv.w
        if hasattr(sv.sel, 'node') and sv.sel in w.boards: return sv.sel
        return w.boards[0] if w.boards else None
    def tick(s, dt):
        lab = s.get(); lab.sel = s.board()
        if not lab.w.paused: lab.tick(dt, budget=3 if len(lab.w.boards) > 20 else 6)
    def event(s, e, view):
        if e.type == pygame.MOUSEWHEEL: s.scroll = max(0, s.scroll + e.y * 3)

    def draw(s, surf, view):
        lab = s.get(); b = s.board(); surf.fill((14, 15, 19), view)
        if b is None: text(surf, 'Нет плат — добавьте на вкладке «Система»', view.center, center=True); return
        bp = lab.bp(b); th = bp.thermal()
        # heatmap of the board (FD grid), scaled to fit the left 60 %
        W = int(view.w * 0.58); sc = min(W / th.nx, (view.h * 0.62) / th.ny)
        x0, y0 = view.x + 16, view.y + 34
        T = th.T; lo, hi = lab.p['ambient'], max(lab.p['ambient'] + 10, float(T.max()))
        img = heat_rgb(T, lo, hi)
        srf = pygame.surfarray.make_surface(img.transpose(1, 0, 2))
        srf = pygame.transform.smoothscale(srf, (int(th.nx * sc), int(th.ny * sc)))
        surf.blit(srf, (x0, y0)); pygame.draw.rect(surf, (90, 96, 110), (x0, y0, th.nx * sc, th.ny * sc), 1)
        text(surf, 'Плата %08X — тепловая карта (МКР %d×%d, шаг %.1f мм), %.1f…%.1f °C, время модели %.0f с' % (b.id, th.nx, th.ny, th.dx * 1e3, lo, hi, bp.t), (x0, view.y + 10), (190, 200, 215), 13)
        # colour bar
        for k in range(200):
            c = heat_rgb(np.array(lo + (hi - lo) * k / 199), lo, hi).tolist()
            pygame.draw.line(surf, c, (x0 + k, y0 + th.ny * sc + 6), (x0 + k, y0 + th.ny * sc + 14))
        text(surf, '%.0f °C' % lo, (x0, y0 + th.ny * sc + 16), sz=10); text(surf, '%.0f °C' % hi, (x0 + 180, y0 + th.ny * sc + 16), sz=10)
        def P(px, py): return (x0 + ((px + th.cx - th.x0) / (th.dx * 1e3)) * sc, y0 + ((py + th.cy - th.y0) / (th.dx * 1e3)) * sc)
        for part in bp.parts.values():
            q = P(part.x, part.y); lim = LIMIT.get(part.ref, 150)
            col = (255, 70, 70) if part.state != 'ok' else (255, 210, 80) if part.Tj > 0.8 * lim else (230, 235, 245)
            pygame.draw.circle(surf, col, (int(q[0]), int(q[1])), 4, 0 if part.state != 'ok' else 2)
            text(surf, '%s %.0f°' % (part.ref.replace('U_', ''), part.Tj), (q[0] + 6, q[1] - 7), col, 10)
        # fires / smoke / char marks
        now = lab.w.now
        for f in bp.fires:
            if 'x' not in f: continue
            q = P(f['x'], f['y']); age = (now - f['t0']) / 1000
            pygame.draw.circle(surf, (25, 18, 12), (int(q[0]), int(q[1])), int(5 + min(age, 3) * 3))      # char mark
            if age < (12 if f['fire'] else 2.5):
                for _ in range(10 if f['fire'] else 4):
                    a = random.random(); hgt = random.random() * (40 if f['fire'] else 18)
                    c = (255, int(120 + 120 * a), 40) if hgt < (25 if f['fire'] else 8) else (110, 110, 115)
                    pygame.draw.circle(surf, c, (int(q[0] + random.gauss(0, 4)), int(q[1] - hgt)), random.randint(2, 5 if f['fire'] else 3))
            if age < 0.4: pygame.draw.circle(surf, (255, 255, 220), (int(q[0]), int(q[1])), int(20 * (0.4 - age) / 0.4) + 2)
        # LED panel current map (actual I in the MSB plane)
        px0 = x0 + int(th.nx * sc) + 24; cs = max(3, min(8, (view.right - px0 - 20) // 32))
        I = bp.led_I; iset = DS['MBI5124']['k'] / lab.p['rext']
        text(surf, 'Панель: ток LED (мА), %d погибших' % int(bp.led_dead.sum()), (px0, view.y + 10), (190, 200, 215), 12)
        for r in range(32):
            for c in range(32):
                v = I[r, c] / max(iset, 1e-6)
                col = (90, 0, 0) if bp.led_dead[r, c] else (int(min(255, 255 * v)), int(min(255, 230 * v)), int(min(255, 140 * v)))
                pygame.draw.rect(surf, col, (px0 + c * cs, y0 + r * cs, cs - 1, cs - 1))
        text(surf, 'макс %.1f мА, мин (горящих) %.2f мА, Iset %.2f мА' % (I.max() * 1e3, (I[I > 1e-5].min() * 1e3 if (I > 1e-5).any() else 0), iset * 1e3), (px0, y0 + 32 * cs + 4), sz=10)
        # rails and currents
        y = y0 + th.ny * sc + 36; R = bp.rails; inf = bp.info
        cols = [('VBUS', R.get('VBUS', 0)), ('SYS', R.get('SYS', 0)), ('BAT', R.get('BAT', 0)), ('LED_4V1', R.get('LED_4V1', 0)), ('AON_3V3', R.get('AON_3V3', 0))]
        for i, (n, v) in enumerate(cols):
            text(surf, '%s' % n, (x0 + i * 120, y), (150, 160, 180), 11); text(surf, '%.3f В' % v, (x0 + i * 120, y + 14), (240, 240, 250), 16)
        y += 40
        st = 'CC заряд' if inf.get('i_chg', 0) > 0.05 and R.get('BAT', 0) < 4.18 else 'CV заряд' if inf.get('i_chg', 0) > 0.01 else 'разряд' if inf.get('i_cell', 0) > 0.01 else 'покой'
        icell = inf.get('i_cell', 0)
        run = (bp.soc * lab.p['cap_mah'] / 1000) / icell if icell > 0.01 else float('inf')
        lines = ['I USB %.3f А · I вход BQ %.3f А · I заряд %.3f А · I ячейки %+.3f А (+ разряд) · TPS вх %.3f / вых %.3f А, η %.1f %% · LDO %.3f А' %
                 (inf.get('i_usb', 0), inf.get('i_in', 0), inf.get('i_chg', 0), icell, inf.get('i_tps_in', 0), inf.get('i_tps_out', 0), inf.get('tps_eta', 0) * 100, inf.get('i_ldo', 0)),
                 'Батарея: SOC %.1f %% (MAX17048 читает %.1f %%), ячейка %.1f °C, OCV %.3f В · состояние: %s · время работы ≈ %s' %
                 (bp.soc * 100, bp.gauge * 100, bp.t_cell, __import__('ledsim.phys.elec', fromlist=['ocv']).ocv(bp.soc), st, ('%.1f ч' % run) if run != float('inf') else '∞'),
                 'Панель %.1f °C · защиты: %s · решатель: невязка %.1e А за %d итер.' % (bp.T_panel, ', '.join(k for k, v in bp.flags.items() if v) or 'нет', inf.get('residual', 0), inf.get('iters', 0)),
                 'Первым достигнут предел: %s' % ('%s (t=%.0f с)' % (bp.first_limit[1], bp.first_limit[0]) if bp.first_limit else '—') + ('   ПЛАТА НЕ РАБОТАЕТ: ' + bp.dead if bp.dead else '')]
        pw = getattr(bp, 'pw', None)
        if pw:
            lines.insert(0, 'МОЩНОСТЬ: вход %.2f Вт (USB %.2f Вт / %.3f А, батарея %+.2f Вт / %+.3f А) · LED %.2f Вт · ESP32 %.0f мВт · в ячейку %.2f Вт · потери %.2f Вт · КПД %.0f %% · энергия %.1f мВт·ч' % (
                pw['total'], pw['usb_w'], pw['usb_a'], pw['bat_w'], pw['bat_a'], pw['p_led'], pw['p_esp'] * 1e3, pw['p_store'], pw['p_loss'], pw['eff'] * 100, getattr(bp, 'e_wh', 0) * 1e3))
            lines.insert(1, 'Токи шин: SYS %.3f А · LED_4V1 %.3f А · AON_3V3 %.3f А' % (pw['i_sys'], pw['i_led'], pw['i_aon']))
        for ln in lines: text(surf, ln, (x0, y), (210, 215, 225), 12); y += 17
        # time graphs: input W, panel T, hottest TJ
        H = getattr(bp, 'hist', [])
        if len(H) > 2:
            gx, gy, gw, gh = px0, int(y0 + 32 * cs + 22), max(120, view.right - px0 - 16), 90
            pygame.draw.rect(surf, (24, 26, 32), (gx, gy, gw, gh)); arr = np.array(H)
            for li, (col, k, lbl) in enumerate((((120, 220, 120), 1, 'Вт'), ((255, 170, 80), 5, 'TJ max °C'), ((120, 170, 255), 4, 'панель °C'))):
                v = arr[:, k]; lo_, hi_ = float(v.min()), float(v.max()) + 1e-6
                pts = [(gx + i * gw / (len(v) - 1), gy + gh - 4 - (v[i] - lo_) / (hi_ - lo_) * (gh - 8)) for i in range(len(v))]
                pygame.draw.lines(surf, col, False, pts, 1)
                text(surf, '%s %.2f…%.2f' % (lbl, lo_, hi_), (gx + 4 + 150 * li, gy + 4), col, 10)
            text(surf, 'последние %.0f с модели' % (arr[-1, 0] - arr[0, 0]), (gx, gy + gh + 2), sz=10)
        # part table
        y += 4; text(surf, 'Деталь       P, мВт   TJ, °C   предел  состояние', (x0, y), (150, 160, 180), 11, mono=True); y += 14
        for part in sorted(bp.parts.values(), key=lambda q: -q.Tj)[:8]:
            text(surf, '%-12s %7.1f  %7.1f   %5d   %s' % (part.ref, part.P * 1e3, part.Tj, LIMIT.get(part.ref, 150), part.state), (x0, y),
                 (255, 90, 90) if part.state != 'ok' else (220, 225, 235), 11, mono=True); y += 13
        # event log
        y = int(max(y + 6, view.bottom - 150))
        ev = [e for e in lab.events if e['board'] in ('%08X' % b.id, '--------')]
        n = (view.bottom - y - 6) // 13; end = max(0, len(ev) - s.scroll)
        for e in ev[max(0, end - n):end]:
            c = {'FAIL': (255, 90, 90), 'WARN': (255, 200, 70), 'DEBUG': (120, 126, 140)}.get(e['level'], (200, 205, 215))
            text(surf, '%8.3f %-5s %s' % (e['t'], e['level'], e['msg'])[:190], (x0, y), c, 11, mono=True); y += 13

    def panel(s, surf, ui, rr):
        lab = s.get(); p = lab.p; f = lab.faults; x, y, W = rr.x + 10, rr.y + 6, rr.w - 20
        text(surf, 'Пресеты', (x, y), (170, 180, 200), 12); y += 16
        names = list(PRESETS); bw = (W - 8) // 3
        for i, n in enumerate(names):
            if ui.button(surf, (x + (i % 3) * (bw + 4), y + (i // 3) * 26, bw, 23), n, sz=10): lab.apply_preset(n)
        y += 56
        hb = (W - 4) // 2
        if ui.button(surf, (x, y, hb, 22), 'Батарея', on=p['src'] == 'battery', sz=11): p['src'] = 'battery'
        if ui.button(surf, (x + hb + 4, y, hb, 22), 'Лаб. источник', on=p['src'] == 'bench', sz=11): p['src'] = 'bench'
        y += 40
        def sl(label, key, lo, hi, fmt='%.2f'):
            nonlocal y
            p[key] = ui.slider(surf, (x, y, W, 8), label, p[key], lo, hi, fmt); y += 30
        if p['src'] == 'battery':
            sl('Ёмкость, мА·ч', 'cap_mah', 200, 5000, '%.0f'); sl('Rвн при 25 °C, Ом (допущение 80 мОм)', 'rint25', 0.02, 0.5, '%.3f')
            v = ui.slider(surf, (x, y, W, 8), 'SOC, %', lab.bp(s.board()).soc * 100 if s.board() else 50, 0, 100, '%.0f'); y += 30
            if s.board() and ui.active and ui.active[1] == 'SOC, %': lab.bp(s.board()).soc = v / 100
        else:
            sl('Источник, В', 'bench_v', 0, 6, '%.2f'); sl('Ограничение тока, А', 'bench_ilim', 0.05, 5, '%.2f')
        if ui.button(surf, (x, y - 8, W, 22), 'USB подключён: ' + ('да' if p['usb_on'] else 'нет'), on=p['usb_on'], sz=11): p['usb_on'] = not p['usb_on']
        y += 32
        sl('USB, В', 'usb_v', 0, 25, '%.2f'); sl('Лимит адаптера USB, А', 'usb_ilim', 0.1, 3.0, '%.2f')
        sl('Окружающая T, °C', 'ambient', -20, 85, '%.0f'); sl('Rext MBI5124, Ом (1820 = 10.2 мА)', 'rext', 250, 4000, '%.0f')
        sl('Ускорение тепла/батареи, ×', 'time_k', 1, 300, '%.0f')
        modes = list(DS['ESP32S3']['modes']); bw = (W - 10) // 3
        for i, m in enumerate(modes):
            if ui.button(surf, (x + (i % 3) * (bw + 5), y - 8 + (i // 3) * 24, bw, 21), m, on=p['esp_mode'] == m, sz=10): p['esp_mode'] = m
        y += 44
        if ui.button(surf, (x, y, hb, 22), 'Полный белый', on=p['full_white'], sz=11): p['full_white'] = not p['full_white']
        if ui.button(surf, (x + hb + 4, y, hb, 22), 'Защита ячейки (PCM)', on=p['pcm'], sz=11): p['pcm'] = not p['pcm']
        y += 30
        text(surf, 'Неисправности', (x, y), (255, 160, 120), 12); y += 32
        s.surge_v = ui.slider(surf, (x, y, W, 8), 'Импульс, В', s.surge_v, 0, 30, '%.1f'); y += 26
        s.surge_ms = ui.slider(surf, (x, y, W, 8), 'Длительность, мс', s.surge_ms, 0.1, 1000, '%.1f'); y += 16
        tb = (W - 8) // 3
        if ui.button(surf, (x, y, tb, 22), 'на VBUS', sz=10): lab.trigger_surge('VBUS', s.surge_v, s.surge_ms)
        if ui.button(surf, (x + tb + 4, y, tb, 22), 'на BAT', sz=10): lab.trigger_surge('BAT', s.surge_v, s.surge_ms)
        if ui.button(surf, (x + 2 * (tb + 4), y, tb, 22), 'провал VBUS', sz=10): lab.trigger_surge('VBUS_dip', min(s.surge_v, 5), s.surge_ms)
        y += 26
        def tog(lbl, key, xx, ww):
            if ui.button(surf, (xx, y, ww, 22), lbl, on=bool(f.get(key)), sz=10):
                f[key] = not f.get(key); lab.log(None, 'WARN', '%s: %s' % (lbl, 'вкл' if f[key] else 'выкл'))
        tog('Обратная батарея', 'reverse', x, hb); tog('КЗ батареи', 'bat_short', x + hb + 4, hb); y += 26
        sr, scl = f.get('short_row', -1), f.get('short_col', -1)
        if ui.button(surf, (x, y, hb, 22), 'КЗ строки: %s' % (sr + 1 if sr >= 0 else 'нет'), on=sr >= 0, sz=10): f['short_row'] = (sr + 1) if sr < 31 else -1
        if ui.button(surf, (x + hb + 4, y, hb, 22), 'КЗ столбца: %s' % (scl + 1 if scl >= 0 else 'нет'), on=scl >= 0, sz=10): f['short_col'] = (scl + 1) if scl < 31 else -1
        y += 26
        f['extra_load'] = ui.slider(surf, (x, y + 8, W, 8), 'Доп. нагрузка LED_4V1, А (перегрузка)', f.get('extra_load', 0.0), 0, 4, '%.2f'); y += 24
        if ui.button(surf, (x, y, hb, 24), 'Новые платы (сброс)', sz=11): lab.reset_damage(); f.clear()
        if ui.button(surf, (x + hb + 4, y, hb, 24), 'Экспорт журнала', sz=11):
            base = os.path.join(layout_dir(), time.strftime('lab_log_%Y%m%d_%H%M%S'))
            with open(base + '.txt', 'w', encoding='utf-8') as fo:
                for e in lab.events: fo.write('%9.3f %s %-5s %s\n' % (e['t'], e['board'], e['level'], e['msg']))
            json.dump({'params': p, 'faults': f, 'boards': {('%08X' % k): lab.summary(bp.b) for k, bp in lab.boards.items()}, 'log': lab.events},
                      open(base + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
            s.msg = base + '.txt/.json'
        y += 28
        if s.msg: text(surf, s.msg[-60:], (x, y), (255, 230, 150), 10)
        text(surf, 'Значения из даташитов; допущения помечены во вкладке «Модели».', (x, rr.bottom - 18), (140, 146, 160), 10)
