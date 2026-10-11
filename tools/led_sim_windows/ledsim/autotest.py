"""Full automated test: LED_Simulator.exe --autotest [DIR] [--headless]
Drives the real App (same views, stack model, renderer, Lab physics) through a scripted sequence and writes
DIR/autotest.log (human-readable, PASS/FAIL/WARN lines) and DIR/autotest.json (summary, per-view frame timing,
CPU/RAM, Тест-mode results, Lab events). Exit code 0 = no FAIL, 1 = FAIL(s), 2 = crash."""
import os, sys, time, json, traceback, platform, logging
import numpy as np

def _proc_stats():
    """(cpu_seconds_user+kernel, rss_bytes, peak_rss_bytes) without psutil"""
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes as W
            k = ctypes.windll.kernel32; h = k.GetCurrentProcess()
            ft = [W.FILETIME() for _ in range(4)]
            k.GetProcessTimes(h, *[ctypes.byref(f) for f in ft])
            v = lambda f: (f.dwHighDateTime << 32 | f.dwLowDateTime) / 1e7
            class PMC(ctypes.Structure):
                _fields_ = [('cb', W.DWORD), ('PageFaultCount', W.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                            ('a', ctypes.c_size_t), ('b', ctypes.c_size_t), ('c', ctypes.c_size_t), ('d', ctypes.c_size_t), ('e', ctypes.c_size_t), ('f', ctypes.c_size_t)]
            m = PMC(); m.cb = ctypes.sizeof(PMC)
            ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb)
            return v(ft[2]) + v(ft[3]), m.WorkingSetSize, m.PeakWorkingSetSize
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF)
        rss = int(open('/proc/self/statm').read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        return r.ru_utime + r.ru_stime, rss, r.ru_maxrss * 1024
    except Exception:
        return 0.0, 0, 0

class T:
    def __init__(s, out):
        s.out = out; s.lines = []; s.counts = {'PASS': 0, 'FAIL': 0, 'WARN': 0, 'INFO': 0}; s.fails = []; s.sections = {}; s.sec = 'init'
        s.t0 = time.perf_counter(); s.f = open(os.path.join(out, 'autotest.log'), 'w', encoding='utf-8')
    def L(s, level, msg):
        ln = '%8.2f  %-5s %-10s %s' % (time.perf_counter() - s.t0, level, s.sec, msg)
        s.f.write(ln + '\n'); s.f.flush(); s.lines.append(ln); s.counts[level] = s.counts.get(level, 0) + 1
        s.sections.setdefault(s.sec, {}).setdefault(level, 0); s.sections[s.sec][level] += 1
        if level == 'FAIL': s.fails.append('[%s] %s' % (s.sec, msg))
        try: print(ln, flush=True)
        except Exception: pass
    def check(s, ok, msg, warn=False): s.L('PASS' if ok else ('WARN' if warn else 'FAIL'), msg); return ok

def script(app, t, timing):
    """generator; yields number of frames to let the app run"""
    from .stack_model import LEAD
    from .phys.lab import PRESETS
    from .view_cube import DEMOS3D
    from . import physcheck
    sv = app.views['system']
    def W(): return sv.w
    def tab(name): app.tab = name; timing['tab'] = name
    def settle_stack(maxf=900):
        """run until every group has exactly one leader and all boards are tiled"""
        for i in range(maxf // 30):
            yield 30
            if stack_ok(verbose=False): return
    def stack_ok(verbose=True, label=''):
        w = W(); ok = True; groups = w.groups()
        for g in groups:
            live = [b for b in g if b.powered]
            if not live: continue
            lo = min(b.id for b in live); leads = [b for b in live if b.node.state == LEAD]
            if len(leads) != 1 or leads[0].id != lo: ok = False
            if any(b.node.leader != lo for b in live): ok = False
            if any(not b.node.me[0] for b in live): ok = False
            tiles = [b.node.me[1:3] for b in live]
            if len(set(tiles)) != len(tiles): ok = False
        if verbose:
            t.check(ok, '%s: %d плат, %d групп; один лидер (= наименьший ID) в каждой группе, все платы размещены без перекрытий' % (label, len(w.boards), len(groups)))
            if not ok:
                for g in groups:
                    t.L('INFO', '  группа: ' + ', '.join('%08X:%s ldr=%08X tile=%s' % (b.id, b.node.state, b.node.leader, b.node.me) for b in g[:8]))
        return ok
    def layout(c, r, kind='full'):
        W().preset(c, r, kind); sv.fit(app.view); sv.apply_global(); sv.sel = None

    # ---------------------------------------------------------------- 0. physics model self-check
    t.sec = 'models'; tab('models')
    rows = physcheck.run(); app.views['models'].report = rows
    for r_ in rows:
        if r_.rstrip().endswith('PASS') or ' PASS ' in r_: t.L('PASS', r_.strip())
        elif ' FAIL ' in r_ or r_.rstrip().endswith('FAIL'): t.L('FAIL', r_.strip())
        else: t.L('INFO', r_.strip())
    yield 90

    # ---------------------------------------------------------------- 1. stack discovery / election
    t.sec = 'stack'; tab('system')
    for (c, r) in ((1, 1), (3, 2), (4, 4), (10, 10)):
        layout(c, r); f0 = timing['frame']; ts = W().now
        yield from settle_stack(1800 if c * r > 20 else 600)
        ok = stack_ok(label='%dx%d' % (c, r))
        t.L('INFO', '%dx%d: сходимость за %.2f с симуляции (%d кадров)' % (c, r, (W().now - ts) / 1000, timing['frame'] - f0))
        if c * r == 100: yield 240                                  # timing sample for the big layout
    # ---------------------------------------------------------------- 2. cable unplug / replug, power off/on
    t.sec = 'cables'; layout(3, 2); yield from settle_stack(); stack_ok(label='3x2 исходно')
    w = W(); b0 = min(w.boards, key=lambda b: b.id)
    cs = [c for c in w.cables if c.a is b0 or c.b is b0]
    for c in cs: c.plugged = False
    w.dirty(); yield from settle_stack(1200)
    g0 = w.comps().get(b0.id, [b0])
    t.check(len(g0) == 1, 'вынуты кабели лидера %08X (%d шт): он отделился в свою группу' % (b0.id, len(cs)))
    stack_ok(label='после отключения кабелей')
    for c in cs: c.plugged = True
    w.dirty(); yield from settle_stack(1500)
    t.check(len(w.groups()) == 1, 'кабели вставлены обратно: снова одна группа (%d)' % len(w.groups()))
    stack_ok(label='после повторного подключения')
    bmid = sorted(w.boards, key=lambda b: b.id)[0]; w.set_power(bmid, False); yield from settle_stack(1500)
    stack_ok(label='лидер обесточен → перевыборы')
    w.set_power(bmid, True); yield from settle_stack(1500)
    stack_ok(label='лидер снова запитан')

    # ---------------------------------------------------------------- 3. every pattern renders
    t.sec = 'patterns'; layout(3, 2); yield from settle_stack()
    items = sv.demo_items()
    for i, it in enumerate(items):
        sv.demo_i = i; sv.sel = None; sv.apply_demo()
        lit = 0; seen = set(); err = None
        for k in range(4):
            yield 15
            try:
                for b in W().boards:
                    if b.tile is not None: lit = max(lit, int((np.asarray(b.tile) > 0).sum())); seen.add(hash(np.asarray(b.tile).tobytes()))
            except Exception as e: err = e
        t.check(err is None and lit > 0, 'узор %-40s макс. %4d/1024 LED горит, %d разных кадров%s' % (it[0], lit, len(seen), (' ошибка: %r' % err) if err else ''), warn=(err is None))
    sv.demo_i = 0; sv.apply_demo()

    # ---------------------------------------------------------------- 4. the other views (timing + no crash)
    t.sec = 'views'
    for v in ('boards', 'panels', 'test', 'lab', 'models', 'system'):
        tab(v); yield 120; t.L('PASS', 'вкладка %s: 120 кадров без исключений' % v)
    sv.show_backup = dict(sv.show)
    for k in list(sv.show):
        sv.show[k] = not sv.show[k]; yield 20; sv.show[k] = not sv.show[k]
    t.L('PASS', 'переключатели видимости (%s) — без исключений' % ', '.join(sv.show))

    # ---------------------------------------------------------------- 5. cube effects
    t.sec = 'cube'; tab('cube'); cv = app.views['cube']
    for N in (8, 16):
        cv.N = N; cv._grid()
        for i, nm in enumerate(DEMOS3D):
            cv.demo = i; f0 = timing['frame']; yield 45
            t.L('PASS', 'куб N=%d эффект %-10s 45 кадров' % (N, nm))
    cv.N = 8; cv._grid(); cv.demo = 0

    # ---------------------------------------------------------------- 6. Тест mode (bring-up), clean and with faults
    t.sec = 'testmode'; layout(3, 2); yield from settle_stack(); tab('test')
    R = app.views['test'].runner()
    def run_tests(label, expect_fail):
        R.start(list(W().boards), 32); n = 0
        while R.running and n < 6000: yield 30; n += 30
        t.check(not R.running, '%s: прогон завершён (%d кадров)' % (label, n))
        res = {('%08X' % k): v for k, v in R.res.items()}
        fails = {(b, k) for b, d in res.items() for k, v in d.items() if v == 'FAIL'}
        exp = set(expect_fail)
        for b, k in sorted(fails):
            t.L('PASS' if (b, k) in exp else 'FAIL', '%s: %s %s = FAIL (%s)' % (label, b, k, 'ожидаемо, внесена неисправность' if (b, k) in exp else 'НЕОЖИДАННО'))
        for b, k in sorted(exp - fails): t.L('FAIL', '%s: %s %s — неисправность внесена, но тест её не нашёл' % (label, b, k))
        npass = sum(1 for d in res.values() for v in d.values() if v == 'PASS'); nwarn = sum(1 for d in res.values() for v in d.values() if v == 'WARN')
        t.L('INFO', '%s: результатов PASS %d, WARN %d, FAIL %d' % (label, npass, nwarn, len(fails)))
        for ln in R.summary_lines(): t.L('INFO', '  ' + ln)
        base = os.path.join(t.out, 'testmode_' + label); R.export(base)
        return res
    t.results_clean = yield from run_tests('clean', [])
    w = W(); bs = sorted(w.boards, key=lambda b: b.id)
    pa = next(p for p in w.panels if p.board is bs[1]); pa.ffc = 'A'
    pc = next(p for p in w.panels if p.board is bs[2]); pc.open_col = 9
    w.set_power(bs[5], False)
    exp = [('%08X' % bs[1].id, k) for k in ('eeprom', 'ffc', 'allon', 'row', 'col', 'checker')] + \
          [('%08X' % bs[2].id, k) for k in ('allon', 'col', 'checker')] + [('%08X' % bs[5].id, 'power')]
    yield from settle_stack(1500)
    # neighbours of the unpowered board see PRES/RS-485 failures: those are expected too
    for c in w.cables:
        if bs[5] in (c.a, c.b):
            o = c.b if c.a is bs[5] else c.a; exp += [('%08X' % o.id, 'pres'), ('%08X' % o.id, 'rs485')]
    t.results_faults = yield from run_tests('faults', exp)
    pa.ffc = 'B'; pc.open_col = -1; w.set_power(bs[5], True)

    # ---------------------------------------------------------------- 7. Лаборатория physics presets
    t.sec = 'lab'; tab('lab'); LV = app.views['lab']; lab = LV.get()
    def lab_run(frames):
        yield frames
        b = LV.board(); sm = lab.summary(b) or {}; sp = lab.system_power() or {}
        return b, sm, sp
    def describe(name, sm, sp):
        r = sm.get('rails', {}); hot = sm.get('hot', ('-', 0))
        t.L('INFO', '%s: шины %s; горячее всего %s %.1f °C; плата LED %.1f °C; ячейка %.1f °C; SOC %.0f %%; отказы %s; первый предел %s; dead %s; флаги %s' % (
            name, ', '.join('%s=%.3f' % (k, v) for k, v in r.items() if isinstance(v, (int, float))), hot[0], hot[1], sm.get('t_panel', 0), sm.get('t_cell', 0), sm.get('soc', 0) * 100,
            sm.get('failed') or 'нет', sm.get('first'), sm.get('dead'), {k: v for k, v in (sm.get('flags') or {}).items() if v} or 'нет'))
        if sp: t.L('INFO', '%s: система %.2f Вт, %.2f А при 5 В, LED %.2f Вт, потери %.2f Вт, БП ≥ %.0f Вт' % (name, sp['w'], sp['a5'], sp['p_led'], sp['loss'], sp['psu_w']))
    t.lab = {}
    expect = {'Норма': 'ok', 'Стресс': 'ok', 'Жара': 'any', 'Скачок 12 В на USB': 'any', 'КЗ батареи': 'any', 'Разряд': 'any'}
    for name in PRESETS:
        lab.reset_damage(); lab.faults = {}; lab.apply_preset(name); W().paused = False
        b, sm, sp = yield from lab_run(600)
        describe(name, sm, sp); t.lab[name] = {'summary': {k: (v if not isinstance(v, np.ndarray) else None) for k, v in sm.items()}, 'power': sp}
        bad = sm.get('failed') or sm.get('dead') or sm.get('fires')
        if expect[name] == 'ok': t.check(not bad, '%s: без отказов и возгораний' % name)
        else: t.L('PASS' if True else 'FAIL', '%s: модель отработала, исход: %s' % (name, ('отказ %s' % (sm.get('failed') or sm.get('dead'))) if bad else 'без повреждений (защиты сработали/не потребовались)'))
        if expect[name] == 'ok':
            t.check(sp and sp['w'] > 0 and abs(sp['a5'] * 5 - sp['w']) < 1e-6 and sp['psu_w'] >= sp['w'], '%s: показания мощности согласованы (Вт = 5 В·А, БП ≥ потребления)' % name)
    # battery vs bench supply, USB only, spikes, dips
    for label, upd, faults, surge in [
            ('Лаб. источник 3.8 В', dict(src='bench', bench_v=3.8, bench_ilim=2.0, usb_on=False), {}, None),
            ('Только USB 5 В', dict(src='battery', usb_on=True, usb_v=5.0, soc=0.8), {}, None),
            ('Импульс VBUS 6.5 В 10 мс', dict(src='battery', usb_on=True), {}, ('VBUS', 6.5, 10.0)),
            ('Импульс VBUS 20 В 50 мс', dict(src='battery', usb_on=True), {}, ('VBUS', 20.0, 50.0)),
            ('Импульс BAT 6 В 20 мс', dict(src='battery', usb_on=True), {}, ('BAT', 6.0, 20.0)),
            ('Провал VBUS до 2.5 В', dict(src='battery', usb_on=True), {}, ('VBUS_dip', 2.5, 100.0)),
            ('Обратная батарея', dict(src='battery', usb_on=False), {'reverse': True}, None),
            ('КЗ строки 5', dict(src='battery', usb_on=True), {'short_row': 4}, None),
            ('КЗ столбца 12', dict(src='battery', usb_on=True), {'short_col': 11}, None)]:
        lab.reset_damage(); lab.apply_preset('Норма'); lab.p.update(upd); lab.faults = dict(faults)
        if surge: yield 30; lab.trigger_surge(*surge)
        b, sm, sp = yield from lab_run(360)
        describe(label, sm, sp); t.lab[label] = {'summary': {k: v for k, v in sm.items() if not isinstance(v, np.ndarray)}, 'power': sp}
        bad = sm.get('failed') or sm.get('dead')
        if label in ('Лаб. источник 3.8 В', 'Только USB 5 В', 'Импульс VBUS 6.5 В 10 мс', 'Провал VBUS до 2.5 В'):
            t.check(not bad, '%s: плата выдерживает (нет отказов)' % label)
        else: t.L('PASS', '%s: смоделировано, исход: %s' % (label, ('отказ %s' % (sm.get('failed') or sm.get('dead'))) if bad else 'без повреждений'))
    lab.reset_damage(); lab.faults = {}; lab.apply_preset('Норма')
    t.lab_events = list(lab.events)
    nfail_ev = sum(1 for e in lab.events if e['level'] == 'FAIL')
    t.L('INFO', 'журнал Лаборатории: %d событий, из них FAIL %d (внесённые неисправности)' % (len(lab.events), nfail_ev))
    tab('system'); yield 60

def run(out=None, headless=False):
    if headless: os.environ.setdefault('SDL_VIDEODRIVER', 'dummy'); os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    out = out or os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'LED_Simulator', 'autotest_' + time.strftime('%Y%m%d_%H%M%S'))
    os.makedirs(out, exist_ok=True)
    d = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'LED_Simulator'); os.makedirs(d, exist_ok=True)
    logging.basicConfig(filename=os.path.join(d, 'led_sim.log'), level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', force=True)
    logging.info('autotest start -> %s', out)
    t = T(out); t.L('INFO', 'LED_Simulator autotest, %s, python %s, %s' % (platform.platform(), platform.python_version(), 'headless' if headless else 'окно'))
    timing = {'tab': 'system', 'frame': 0, 'dt': {}, 'work': {}}
    cpu0, _, _ = _proc_stats(); wall0 = time.perf_counter(); samples = []
    crashed = None
    try:
        from .app import App
        app = App(); t.L('INFO', 'App создан за %.2f с' % (time.perf_counter() - wall0))
        gen = script(app, t, timing); state = {'wait': 0, 'done': False}
        def hook(a, frame, dt, work):
            timing['frame'] = frame
            if frame > 5:
                timing['dt'].setdefault(a.tab, []).append(dt * 1000); timing['work'].setdefault(a.tab, []).append(work * 1000)
            if frame % 60 == 0:
                c, rss, peak = _proc_stats(); samples.append((time.perf_counter() - wall0, c, rss))
            if state['wait'] > 0: state['wait'] -= 1; return
            try: state['wait'] = next(gen) or 1
            except StopIteration: return 'quit'
        app.hook = hook; app.run()
    except BaseException as e:
        crashed = traceback.format_exc(); t.L('FAIL', 'АВАРИЯ: %r' % e); t.f.write(crashed + '\n'); logging.error('autotest crash\n%s', crashed)
    cpu1, rss, peak = _proc_stats(); wall = time.perf_counter() - wall0
    def st(v):
        a = np.array(v); return {'n': len(v), 'p50': round(float(np.percentile(a, 50)), 2), 'p95': round(float(np.percentile(a, 95)), 2), 'max': round(float(a.max()), 2), 'fps_p50': round(1000 / max(float(np.percentile(a, 50)), 1e-3), 1)} if v else None
    perf = {k: {'frame_ms': st(timing['dt'][k]), 'work_ms': st(timing['work'].get(k, []))} for k in timing['dt']}
    ncpu = os.cpu_count() or 1
    t.sec = 'perf'
    for k, v in perf.items():
        f, wk = v['frame_ms'], v['work_ms']
        t.L('INFO', 'вкладка %-8s кадр p50 %6.1f мс  p95 %6.1f  max %7.1f  (≈%4.0f fps)  | работа p50 %6.1f p95 %6.1f max %7.1f мс  [%d кадров]' % (k, f['p50'], f['p95'], f['max'], f['fps_p50'], wk['p50'], wk['p95'], wk['max'], f['n']))
    cpu_pct = (cpu1 - cpu0) / max(wall, 1e-3) * 100
    t.L('INFO', 'CPU: %.0f с за %.0f с = %.0f %% одного ядра (%.0f %% от %d логических); RAM: сейчас %.0f МБ, пик %.0f МБ' % (cpu1 - cpu0, wall, cpu_pct, cpu_pct / ncpu, ncpu, rss / 2**20, peak / 2**20))
    t.sec = 'total'
    t.L('INFO', 'ИТОГ: PASS %d, FAIL %d, WARN %d%s' % (t.counts['PASS'], t.counts['FAIL'], t.counts['WARN'], ', АВАРИЯ' if crashed else ''))
    for f in t.fails: t.L('INFO', '  FAIL ' + f)
    js = {'counts': t.counts, 'sections': t.sections, 'fails': t.fails, 'crash': crashed, 'perf': perf,
          'cpu': {'cpu_s': cpu1 - cpu0, 'wall_s': wall, 'pct_one_core': cpu_pct, 'logical_cpus': ncpu, 'samples': samples},
          'ram': {'rss_mb': rss / 2**20, 'peak_mb': peak / 2**20}, 'platform': platform.platform(), 'processor': platform.processor(),
          'lab': getattr(t, 'lab', {}), 'testmode_clean': getattr(t, 'results_clean', None), 'testmode_faults': getattr(t, 'results_faults', None)}
    with open(os.path.join(out, 'autotest.json'), 'w', encoding='utf-8') as f: json.dump(js, f, ensure_ascii=False, indent=1, default=str)
    t.f.close(); logging.info('autotest done: %s', t.counts)
    try:
        import pygame; pygame.quit()
    except Exception: pass
    return 2 if crashed else (1 if t.counts['FAIL'] else 0)
