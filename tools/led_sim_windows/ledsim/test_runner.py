"""'Тест' mode: the full bring-up sequence per board, run on all boards in parallel (in batches), on the
simulated time base. LED-level checks drive the real patterns through the board->FFC->panel map that
sim/bringup/netmodel.py computes from the .kicad_pcb netlists (data/cable_*.json), including Type A FFCs
and open columns, and compare every LED against the design intent."""
import json, random, time
import numpy as np
from .world import panel_data, PANEL_CONN, PANELS
from .stack_model import LEAD, FOLLOW

TESTS = [('power', 'Питание'), ('boot', 'Загрузка'), ('i2c', 'I2C скан'), ('eeprom', 'EEPROM панели'), ('ffc', 'Кабель FFC'),
         ('allon', 'Все вкл'), ('row', 'Строки'), ('col', 'Столбцы'), ('checker', 'Шахматка'),
         ('pres', 'PRES'), ('rs485', 'RS-485'), ('fsync', 'FRAME_SYNC'), ('elect', 'Выборы'), ('tile', 'Плитка'), ('phys', 'Электротермика')]
LEVELS = ['DEBUG', 'INFO', 'PASS', 'WARN', 'FAIL']
SIDES = 'NESW'

def patterns(kind):
    """yield (label, 32x32 bool drive frame) for one LED test"""
    if kind == 'allon': yield 'all', np.ones((32, 32), bool)
    elif kind == 'row':
        for r in range(32):
            f = np.zeros((32, 32), bool); f[r] = True; yield 'row %d' % (r + 1), f
    elif kind == 'col':
        for c in range(32):
            f = np.zeros((32, 32), bool); f[:, c] = True; yield 'col %d' % (c + 1), f
    elif kind == 'checker':
        i = np.add.outer(np.arange(32), np.arange(32)) & 1
        yield 'checker', i == 0; yield 'checker inv', i == 1

def panel_response(panel, drive):
    """LED states the panel actually shows for a firmware drive frame (netmodel map + faults)"""
    m = panel_data(panel.kind)[panel.ffc]
    d = drive.reshape(-1).copy()
    if panel.open_col >= 0: d.reshape(32, 32)[:, panel.open_col] = False
    lit = np.zeros(1024, bool); ok = (m >= 0) & d
    lit[m[ok]] = True
    return lit

class Runner:
    def __init__(s, world):
        s.w = world; s.log = []; s.res = {}; s.active = []; s.queue = []; s.batch = 32; s.running = False
        s.t0 = 0; s.started = None; s.done_at = None; s.rng = random.Random(5)

    def L(s, b, level, test, msg):
        s.log.append({'t': (s.w.now - s.t0) / 1000.0, 'board': '%08X' % b.id, 'level': level, 'test': test, 'msg': msg})
        if level in ('PASS', 'FAIL', 'WARN', 'SKIP'):
            cur = s.res.setdefault(b.id, {}).get(test)
            if cur != 'FAIL': s.res[b.id][test] = level

    def start(s, boards, batch):
        s.log = []; s.res = {b.id: {} for b in boards}; s.batch = max(1, batch); s.t0 = s.w.now
        if getattr(s.w, 'lab', None) is not None: s.w.lab.running = True     # the 'phys' step needs the electrothermal model
        s.queue = list(sorted(boards, key=lambda b: b.id)); s.active = []; s.running = True; s.started = time.time(); s.done_at = None
        s.order = [b.id for b in s.queue]
        s.L_sys('INFO', 'Запуск теста: %d плат, пакеты по %d' % (len(boards), s.batch))

    def L_sys(s, level, msg): s.log.append({'t': (s.w.now - s.t0) / 1000.0, 'board': '--------', 'level': level, 'test': 'run', 'msg': msg})

    def tick(s):
        if not s.running: return
        if not s.active and s.queue:
            batch, s.queue = s.queue[:s.batch], s.queue[s.batch:]
            s.L_sys('INFO', 'Пакет: %d плат (%s…)' % (len(batch), ', '.join('%08X' % b.id for b in batch[:4])))
            s.active = [[b, s.seq(b), 0] for b in batch]
        now = s.w.now
        for a in s.active:
            if a[2] <= now:
                try: a[2] = now + (next(a[1]) or 1)
                except StopIteration: a[2] = None
        s.active = [a for a in s.active if a[2] is not None]
        if not s.active and not s.queue:
            s.running = False; s.done_at = s.w.now
            for b in s.w.boards: b.override = None
            s.L_sys('INFO', 'Готово за %.2f с (симуляция), %.1f с (реальное время)' % ((s.w.now - s.t0) / 1000, time.time() - s.started))
            for ln in s.summary_lines(): s.L_sys('INFO', ln)

    # ------------------------------------------------ per-board bring-up sequence (generator, yields ms)
    def seq(s, b):
        w = s.w; tag = lambda t: t
        panel = next((p for p in w.panels if p.board is b), None)
        if not b.powered:
            s.L(b, 'FAIL', 'power', 'нет питания: плата отключена (USB/BAT не подан) — остальные тесты пропущены')
            for k, _ in TESTS[1:]: s.L(b, 'SKIP', k, 'пропущено: нет питания')
            return
        # power (power_seq.c order and delays)
        s.L(b, 'INFO', 'power', 'шаг 1: LED_EN=0 LED_LOGIC_EN=0 XLAT_OE_N=1 OE_N=1 DEC_EN_N=1; порты вход+PD')
        s.L(b, 'INFO', 'power', 'AON 3V3 (TPS7A2033): %.3f В' % (3.300 + s.rng.uniform(-0.012, 0.012))); yield 2
        s.L(b, 'INFO', 'power', 't=+0 мс LED_LOGIC_EN=1 → LED_LOGIC_3V3 %.3f В (THVD1406 VCC)' % (3.30 + s.rng.uniform(-0.02, 0.02))); yield 5
        v41 = 4.10 + s.rng.uniform(-0.04, 0.03) - (0.047 if panel and panel.kind == 'full' else 0.06)
        s.L(b, 'INFO', 'power', 't=+5 мс LED_EN=1 → LED_4V1 %.3f В (TPS63802; худшая просадка строки учтена)' % v41); yield 10
        s.L(b, 'INFO', 'power', 't=+15 мс ROW_XLAT_OE_N=0, транслятор строк активен'); yield 1
        s.L(b, 'PASS' if v41 > 3.9 else 'FAIL', 'power', 'шины в норме: 3V3, LED_LOGIC_3V3, LED_4V1 %.2f В' % v41)
        # boot
        yield 180 + s.rng.randrange(60)
        s.L(b, 'INFO', 'boot', 'ESP32-S3 boot, app mono_split, MAC → ID %08X' % b.id)
        s.L(b, 'PASS', 'boot', 'загрузка за %d мс, heap ok, scan engine v13 (LCD_CAM 20 МГц, 8 bit BCM)' % (190 + s.rng.randrange(60)))
        # I2C scan
        yield 12
        found = ['0x36 MAX17048', '0x68 BMI270']
        has_id = panel is not None and panel.kind in ('full', 'wire') and panel.ffc == 'B'
        if has_id: found.append('0x50 24LC02 (ID панели, FFC)')
        s.L(b, 'INFO', 'i2c', 'найдено: ' + ', '.join(found))
        s.L(b, 'PASS', 'i2c', '%d устройств на шине' % len(found))
        # EEPROM
        yield 6
        if panel is None: s.L(b, 'FAIL', 'eeprom', 'панель не подключена (FFC)')
        elif panel.kind == 'wire' and panel.ffc == 'B': s.L(b, 'PASS', 'eeprom', 'ID: wire32_grid (WG_TAG / garland_breakout), 32x32, шаг 10 мм, flags LONG_WIRES, row_path %d мОм' % 415)
        elif panel.kind != 'full': s.L(b, 'WARN', 'eeprom', '%s: нет EEPROM (панель до стандарта LED interface v1) — тип задан вручную' % PANELS[panel.kind][2])
        elif panel.ffc == 'A': s.L(b, 'FAIL', 'eeprom', '0x50 не отвечает: ID I2C на запасных контактах FFC зеркалирован (тип A)')
        else: s.L(b, 'PASS', 'eeprom', 'ID: mono_panel_32x32_full, 32x32, шаг 5.0 мм, LED interface std v1, GND/ID ok')
        # FFC cable check (row/col continuity via ID/GND spares)
        yield 4
        if panel is None: s.L(b, 'FAIL', 'ffc', 'J_ROW1/J_COL1: кабели не вставлены')
        else:
            lit = panel_response(panel, np.ones((32, 32), bool)).sum()
            if panel.ffc == 'A': s.L(b, 'FAIL', 'ffc', 'тип A (контакты с одной стороны): контакт 1→40 зеркалирован, светится %d/1024 LED' % lit)
            else: s.L(b, 'PASS', 'ffc', 'тип B, %d мм, J_ROW1→J_ROW, J_COL1→J_COL, 40/40 цепей' % panel.ffc_len)
        # LED tests, LED-by-LED
        for test in ('allon', 'row', 'col', 'checker'):
            if panel is None: s.L(b, 'SKIP', test, 'нет панели'); continue
            bad_leds, bad_rows, bad_cols, frames = 0, set(), set(), 0
            for label, drive in patterns(test):
                b.override = (drive * 255).astype(np.uint8)
                yield 34 if test in ('allon', 'checker') else 17
                lit = panel_response(panel, drive).reshape(32, 32)
                mism = lit != drive
                frames += 1
                if mism.any():
                    bad_leds += int(mism.sum())
                    rr, cc = np.nonzero(mism); bad_rows.update((rr + 1).tolist()); bad_cols.update((cc + 1).tolist())
                    if test in ('row', 'col') and len(bad_rows) + len(bad_cols) < 8:
                        s.L(b, 'DEBUG', test, '%s: %d LED не совпали' % (label, int(mism.sum())))
            b.override = None
            if bad_leds == 0: s.L(b, 'PASS', test, '%d кадров, 1024/1024 LED совпали' % frames)
            else:
                def fmt(v): v = sorted(v); return (', '.join(map(str, v[:8])) + ('…' if len(v) > 8 else '')) if v else '-'
                s.L(b, 'FAIL', test, '%d кадров, %d несовпадений LED; строки %s; столбцы %s' % (frames, bad_leds, fmt(bad_rows), fmt(bad_cols)))
        # stacking: PRES per side
        yield 5
        w.comps(); any_cable = False; pres_fail = False
        for side in range(4):
            c = w._cmap.get((b.id, side))
            if c is None: s.L(b, 'DEBUG', 'pres', '%s: не подключено' % SIDES[side]); continue
            any_cable = True
            o, os_ = (c.b, c.bs) if c.a is b else (c.a, c.as_)
            if not c.plugged: s.L(b, 'WARN', 'pres', '%s: кабель к %08X.%s вынут' % (SIDES[side], o.id, SIDES[os_]))
            elif not o.powered: s.L(b, 'FAIL', 'pres', '%s: соседа %08X нет (не запитан)' % (SIDES[side], o.id)); pres_fail = True
            elif c.type == 'A': s.L(b, 'FAIL', 'pres', '%s: PRES не виден у %08X.%s — кабель тип A (GND↔PRES)' % (SIDES[side], o.id, SIDES[os_])); pres_fail = True
            else: s.L(b, 'INFO', 'pres', '%s → %08X.%s: PRES высокий, %d мм' % (SIDES[side], o.id, SIDES[os_], c.length))
            yield 2
        if not pres_fail: s.L(b, 'PASS', 'pres', 'порты проверены' if any_cable else 'одиночная плата, порты свободны')
        # RS-485
        yield 3
        grp = w.comps().get(b.id, [b]); bad = False
        for side in range(4):
            c = w._cmap.get((b.id, side))
            if c is None or not c.plugged: continue
            o = c.b if c.a is b else c.a
            if o in grp and o.powered: s.L(b, 'INFO', 'rs485', 'PING %08X → PONG, %.2f мс (500 кбит/с, 12+10 Б)' % (o.id, 22 * 10 / 500 + s.rng.uniform(0.05, 0.2)))
            else: s.L(b, 'FAIL', 'rs485', 'нет связи с %08X (A/B не соединены)' % o.id); bad = True
        if not bad: s.L(b, 'PASS', 'rs485', 'шина: %d плат в сегменте, кадров rx %d, ошибок CRC 0' % (len(grp), b.node.rx_ok))
        # FRAME_SYNC
        yield 20
        n = b.node
        lead = next((o for o in grp if o.node.state == LEAD), None)
        if lead is None: s.L(b, 'FAIL', 'fsync', 'нет лидера — фронты FRAME_SYNC отсутствуют')
        else:
            df = n.frame - lead.node.frame if lead is not b else 0
            ok = n.skew_us < 10 and abs(df) <= 1 and len(n.edge_times) > 30
            s.L(b, 'PASS' if ok else 'FAIL', 'fsync', 'скос фронта %.2f мкс, Δкадр %d, %d фронтов/с' % (n.skew_us, df, len(n.edge_times)))
        # election
        yield 2
        lo = min(o.id for o in grp)
        if n.leader == lo: s.L(b, 'PASS', 'elect', '%s, лидер %08X = наименьший ID из %d' % ('ЛИДЕР' if n.state == LEAD else 'ведомая', lo, len(grp)))
        else: s.L(b, 'FAIL', 'elect', 'лидер %08X, ожидался %08X (состояние %d)' % (n.leader, lo, n.state))
        # tile
        yield 2
        clash = [o for o in grp if o is not b and o.node.me[0] and n.me[0] and o.node.me[1:3] == n.me[1:3]]
        if n.me[0] and not clash: s.L(b, 'PASS', 'tile', 'плитка (%d,%d) поворот %d°, холст %dx%d' % (n.me[1], n.me[2], n.me[3] * 90, n.W * 32, n.H * 32))
        else: s.L(b, 'FAIL', 'tile', 'не размещена' if not n.me[0] else 'перекрытие с %08X' % clash[0].id)

    # ------------------------------------------------ reports
    def summary_lines(s):
        out = []
        boards = s.order if hasattr(s, 'order') else list(s.res)
        np_ = sum(1 for i in boards if s.res.get(i) and all(v in ('PASS', 'WARN') for v in s.res[i].values()))
        lab = getattr(s.w, 'lab', None); sp = lab.system_power() if lab else None
        if sp: out.append('ПИТАНИЕ: %.2f Вт, %.2f А при 5 В, рекомендуемый БП ≥ %.0f Вт / %.1f А, энергия %.2f Вт·ч' % (sp['w'], sp['a5'], sp['psu_w'], sp['psu_a'], sp['wh']))
        out.append('ИТОГ: %d плат, %d без ошибок, %d с ошибками' % (len(boards), np_, len(boards) - np_))
        for k, name in TESTS:
            f = [i for i in boards if s.res.get(i, {}).get(k) == 'FAIL']
            if f: out.append('  %-12s FAIL: %s' % (name, ', '.join('%08X' % i for i in f[:10]) + (' …' if len(f) > 10 else '')))
        return out
    def export(s, path_base):
        with open(path_base + '.txt', 'w', encoding='utf-8') as f:
            f.write('LED_Simulator — журнал тестов\n\n')
            for e in s.log: f.write('%9.3f  %-8s %-5s %-7s %s\n' % (e['t'], e['board'], e['level'], e['test'], e['msg']))
            lab = getattr(s.w, 'lab', None)
            if lab and lab.events:
                f.write('\n--- Лаборатория (электротермика) ---\n')
                for e in lab.events: f.write('%9.3f  %-8s %-5s lab     %s\n' % (e['t'], e['board'], e['level'], e['msg']))
            f.write('\n'); f.write('\n'.join(s.summary_lines())); f.write('\n')
        with open(path_base + '.json', 'w', encoding='utf-8') as f:
            json.dump({'lab': getattr(getattr(s.w, 'lab', None), 'events', []), 'results': {'%08X' % k: v for k, v in s.res.items()}, 'summary': s.summary_lines(), 'log': s.log}, f, ensure_ascii=False, indent=1)
        return path_base + '.txt', path_base + '.json'
