"""'Тест' tab: PASS/FAIL matrix per board x test, filterable log, export, summary."""
import os, time
import pygame
from .ui import T, text
from .test_runner import Runner, TESTS, LEVELS
from .view_system import layout_dir

LCOL = {'DEBUG': (120, 126, 140), 'INFO': (200, 205, 215), 'PASS': (90, 220, 120), 'WARN': (255, 200, 60), 'FAIL': (255, 80, 80), 'SKIP': (130, 130, 130)}

class TestView:
    def __init__(s, app):
        s.app = app; s.r = Runner(app.views['system'].w) if 'system' in app.views else None
        s.batch = 32; s.lvl = 1; s.bfilter = None; s.scroll = 0; s.msg = ''; s.mscroll = 0
    def runner(s):
        w = s.app.views['system'].w
        if s.r is None or s.r.w is not w: s.r = Runner(w)
        return s.r
    def tick(s): s.runner().tick()
    def event(s, e, view):
        if e.type == pygame.MOUSEWHEEL and view.collidepoint(pygame.mouse.get_pos()):
            if pygame.mouse.get_pos()[1] < view.y + view.h * 0.45: s.mscroll = max(0, s.mscroll - e.y * 3)
            else: s.scroll = max(0, s.scroll + e.y * 3)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and view.collidepoint(e.pos):
            hit = getattr(s, 'row_hits', {})
            for bid, rr in hit.items():
                if rr.collidepoint(e.pos): s.bfilter = None if s.bfilter == bid else bid; s.scroll = 0
    def draw(s, surf, view):
        r = s.runner(); surf.fill((14, 15, 19), view)
        x0, y = view.x + 10, view.y + 8
        cw = max(46, min(80, (view.w - 120) // len(TESTS)))
        text(surf, 'Плата', (x0, y), (170, 180, 200), 12)
        for j, (k, name) in enumerate(TESTS): text(surf, name, (x0 + 100 + j * cw + cw // 2, y + 7), (170, 180, 200), 10, center=True)
        y += 20; s.row_hits = {}
        ids = list(getattr(r, 'order', []))
        top = y; maxr = max(1, int(view.h * 0.45 - 30) // 16)
        s.mscroll = min(s.mscroll, max(0, len(ids) - maxr))
        for bid in ids[s.mscroll:s.mscroll + maxr]:
            row = pygame.Rect(x0, y, 100 + len(TESTS) * cw, 15); s.row_hits[bid] = row
            if s.bfilter == bid: pygame.draw.rect(surf, (40, 50, 80), row)
            text(surf, '%08X' % bid, (x0, y), (220, 220, 230), 11, mono=True)
            for j, (k, _) in enumerate(TESTS):
                v = r.res.get(bid, {}).get(k)
                c = {'PASS': (40, 140, 70), 'FAIL': (170, 50, 50), 'WARN': (170, 140, 40), 'SKIP': (70, 70, 70)}.get(v, (34, 37, 45))
                pygame.draw.rect(surf, c, (x0 + 100 + j * cw + 2, y + 1, cw - 4, 13), border_radius=3)
                if v: text(surf, v, (x0 + 100 + j * cw + cw // 2, y + 7), (240, 240, 240), 9, center=True)
            y += 16
        if len(ids) > maxr: text(surf, 'строки %d–%d из %d (колесо — прокрутка)' % (s.mscroll + 1, min(len(ids), s.mscroll + maxr), len(ids)), (x0, y), (140, 146, 160), 10)
        y = view.y + int(view.h * 0.45) + 6
        pygame.draw.line(surf, (50, 55, 66), (view.x, y - 4), (view.right, y - 4))
        lines = [e for e in r.log if e['level'] in LEVELS and LEVELS.index(e['level']) >= s.lvl] + [e for e in r.log if e['level'] == 'SKIP' and s.lvl <= 3]
        lines.sort(key=lambda e: e['t'])
        if s.bfilter: lines = [e for e in lines if e['board'] in ('%08X' % s.bfilter, '--------')]
        n = max(1, (view.bottom - y - 24) // 14)
        end = max(0, len(lines) - s.scroll); start = max(0, end - n)
        for e in lines[start:end]:
            text(surf, '%8.3f %s %-5s %-7s %s' % (e['t'], e['board'], e['level'], e['test'], e['msg'])[:200], (x0, y), LCOL.get(e['level']), 11, mono=True); y += 14
        st = 'идёт: %d активных, %d в очереди' % (len(r.active), len(r.queue)) if r.running else ('готово' if r.log else 'нажмите «Запустить тест»')
        text(surf, 'Журнал: %d записей (показано %d) · %s%s' % (len(r.log), len(lines), st, (' · плата %08X' % s.bfilter) if s.bfilter else ''), (x0, view.bottom - 20), (140, 146, 160), 11)
    def panel(s, surf, ui, rr):
        r = s.runner(); x, y, W = rr.x + 10, rr.y + 8, rr.w - 20; hb = (W - 4) // 2
        sv = s.app.views['system']
        if ui.button(surf, (x, y, W, 30), 'Запустить тест: все платы (%d)' % len(sv.w.boards), on=r.running): r.start(list(sv.w.boards), s.batch)
        y += 34
        sel = sv.sel if hasattr(sv.sel, 'node') else None
        if ui.button(surf, (x, y, W, 26), 'Только выбранная плата' + (' %08X' % sel.id if sel else ' (выберите на вкладке «Система»)')) and sel: r.start([sel], 1)
        y += 46
        s.batch = int(ui.slider(surf, (x, y, W, 10), 'Размер пакета (параллельно)', s.batch, 1, 100)); y += 26
        text(surf, 'Уровень журнала:', (x, y), (170, 180, 200), 12); y += 18
        bw = (W - 16) // 5
        for i, l in enumerate(LEVELS):
            if ui.button(surf, (x + i * (bw + 4), y, bw, 22), l, on=s.lvl == i, sz=10): s.lvl = i; s.scroll = 0
        y += 28
        text(surf, 'Плата: %s (клик по строке таблицы)' % ('%08X' % s.bfilter if s.bfilter else 'все'), (x, y), sz=12)
        if s.bfilter and ui.button(surf, (x + W - 60, y - 3, 60, 20), 'все', sz=10): s.bfilter = None
        y += 22
        if ui.button(surf, (x, y, W, 26), 'Экспорт журнала (.txt + .json)') and r.log:
            base = os.path.join(layout_dir(), time.strftime('test_log_%Y%m%d_%H%M%S'))
            a, b = r.export(base); s.msg = 'сохранено: %s, .json' % a
        y += 30
        if s.msg: text(surf, s.msg[-60:], (x, y), (255, 230, 150), 10); y += 16
        y += 6; text(surf, 'Сводка', (x, y), (170, 180, 200), 13); y += 18
        if r.log and not r.running:
            for ln in r.summary_lines():
                text(surf, ln[:60], (x, y), (255, 120, 120) if 'FAIL' in ln else (210, 230, 210), 11); y += 15
                if y > rr.bottom - 20: break
        text(surf, 'Неисправности — на вкладке «Система»:', (x, rr.bottom - 40), (140, 146, 160), 10)
        text(surf, 'FFC тип A, обрыв столбца, кабель тип A, обесточить плату.', (x, rr.bottom - 26), (140, 146, 160), 10)
