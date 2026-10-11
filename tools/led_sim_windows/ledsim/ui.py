"""Tiny immediate-mode UI on pygame + RU/EN strings."""
import pygame
from . import host

LANG = ['ru']
S = {
 'title': ('Симулятор LED-системы mono_split', 'mono_split LED system simulator'),
 'tab_sys': ('Система', 'System'), 'tab_boards': ('Платы', 'Boards'), 'tab_panels': ('Панели', 'Panels'), 'tab_cube': ('Куб', 'Cube'),
 'add_board': ('+ Плата', '+ Board'), 'add_panel': ('+ Панель', '+ Panel'), 'delete': ('Удалить', 'Delete'),
 'autocable': ('Авто-кабели', 'Auto-cable'), 'autopanel': ('Авто-панели', 'Auto-panels'),
 'presets': ('Пресеты:', 'Presets:'), 'save': ('Сохранить', 'Save'), 'load': ('Загрузить', 'Load'),
 'pause': ('Пауза', 'Pause'), 'run': ('Пуск', 'Run'), 'brightness': ('Яркость', 'Brightness'), 'gamma': ('Гамма', 'Gamma'),
 'fps': ('Кадры/с стека', 'Stack fps'), 'speed': ('Скорость симуляции', 'Sim speed'),
 'demo': ('Анимация', 'Animation'), 'cycle': ('Цикл (холст)', 'Cycle (canvas)'), 'canvas': ('Холст', 'Canvas'), 'panel': ('Панель', 'Panel'),
 'group_all': ('для всех групп', 'for all groups'), 'group_sel': ('для группы выбранной платы', "for the selected board's group"),
 'power_off': ('Обесточить', 'Power off'), 'power_on': ('Включить', 'Power on'), 'rotate': ('Повернуть (R)', 'Rotate (R)'),
 'ffc_a': ('FFC: Тип A (зеркальный)', 'FFC: Type A (mirrored)'), 'ffc_b': ('FFC: Тип B (норма)', 'FFC: Type B (ok)'),
 'open_col': ('Обрыв столбца', 'Open column'), 'none': ('нет', 'none'),
 'unplug': ('Отключить кабель', 'Unplug cable'), 'plug': ('Подключить кабель', 'Plug cable'),
 'cable_a': ('Кабель тип A (зеркальный)', 'Cable Type A (mirrored)'), 'cable_b': ('Кабель тип B (норма)', 'Cable Type B (ok)'),
 'connect_near': ('FFC к ближайшей плате', 'FFC to nearest board'), 'disconnect_ffc': ('Отсоединить FFC', 'Disconnect FFC'),
 'groups': ('Группы (стеки)', 'Groups (stacks)'), 'leader': ('лидер', 'leader'), 'members': ('плат', 'boards'),
 'canvas_size': ('холст', 'canvas'), 'boards': ('Платы', 'Boards'), 'timing': ('Тайминги', 'Timing'),
 'hint_sys': ('ЛКМ: выбрать/тащить · тянуть от порта к порту = кабель · от квадрата панели к плате = FFC · клик по кабелю = вкл/выкл · ПКМ/колесо: обзор · R поворот · Del удалить · Пробел пауза',
              'LMB: select/drag · drag port->port = cable · panel square->board = FFC · click cable = plug/unplug · RMB/wheel: view · R rotate · Del delete · Space pause'),
 'layers': ('Слои', 'Layers'), 'search': ('Поиск (цепь или позиционное обозн.)', 'Search (net or reference)'),
 'net': ('Цепь', 'Net'), 'pads': ('Контакты', 'Pads'), 'length': ('Длина', 'Length'), 'width': ('Ширина', 'Width'), 'vias': ('Переходные', 'Vias'),
 'trace_to': ('FFC → панель', 'FFC → panel'), 'open_on_panel': ('Показать на панели', 'Show on panel'),
 'hint_pcb': ('Наведите на контакт/дорожку/переходное — подсветка цепи · клик = закрепить · колесо/ПКМ: зум/сдвиг · клик по J_ROW1/J_COL1 = трассировка через FFC',
              'Hover pad/track/via to highlight the net · click = pin · wheel/RMB: zoom/pan · click J_ROW1/J_COL1 pin = trace through the FFC'),
 'layers_n': ('Слоёв', 'Layers'), 'cube_demo': ('Объёмная анимация', 'Volumetric demo'), 'cube_panel': ('Тип слоёв', 'Layer type'),
 'hint_cube': ('ЛКМ: вращать камеру · колесо: зум', 'LMB: orbit · wheel: zoom'),
 'maxb': ('MAXB', 'MAXB'), 'selected': ('Выбрано', 'Selected'), 'saved': ('Сохранено', 'Saved'), 'loaded': ('Загружено', 'Loaded'),
 'faults': ('Неисправности', 'Faults'), 'lang': ('EN', 'RU'),
}
def T(k): v = S.get(k, (k, k)); return v[0] if LANG[0] == 'ru' else v[1]

_fonts = {}
def font(sz, mono=False):
    k = (sz, mono)
    if k not in _fonts: _fonts[k] = pygame.font.Font(host.data_path('DejaVuSansMono.ttf' if mono else 'DejaVuSans.ttf'), sz)
    return _fonts[k]

def text(surf, s, pos, col=(220, 225, 235), sz=13, mono=False, center=False):
    img = font(sz, mono).render(str(s), True, col)
    r = img.get_rect(center=pos) if center else img.get_rect(topleft=pos)
    surf.blit(img, r); return r

class UI:
    def __init__(s): s.mpos = (0, 0); s.click = False; s.held = False; s.active = None; s.focus = None; s.keys = []; s.consumed = False
    def begin(s, events):
        s.click = False; s.keys = []; s.consumed = False; s.release = False
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1: s.click = True
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1: s.active = None; s.release = True
            if e.type == pygame.KEYDOWN: s.keys.append(e)
        s.mpos = pygame.mouse.get_pos(); s.held = pygame.mouse.get_pressed()[0]
    def hot(s, r): return pygame.Rect(r).collidepoint(s.mpos)
    def button(s, surf, r, label, on=False, col=None, sz=13):
        r = pygame.Rect(r); h = s.hot(r)
        bg = (70, 110, 190) if on else (58, 64, 78) if h else (42, 46, 56)
        if col: bg = col
        pygame.draw.rect(surf, bg, r, border_radius=5); pygame.draw.rect(surf, (90, 98, 118), r, 1, border_radius=5)
        text(surf, label, r.center, sz=sz, center=True)
        if h and s.click: s.consumed = True; return True
        return False
    def slider(s, surf, r, label, v, lo, hi, fmt='%.0f'):
        r = pygame.Rect(r); key = ('sl', label)
        text(surf, '%s: %s' % (label, fmt % v), (r.x, r.y - 16), sz=12)
        pygame.draw.rect(surf, (40, 44, 54), r, border_radius=4)
        fx = r.x + (v - lo) / (hi - lo) * r.w
        pygame.draw.rect(surf, (70, 110, 190), (r.x, r.y, fx - r.x, r.h), border_radius=4)
        pygame.draw.circle(surf, (230, 230, 240), (int(fx), r.centery), r.h // 2 + 3)
        if s.hot(r.inflate(0, 10)) and s.click: s.active = key; s.consumed = True
        if s.active == key and s.held:
            v = lo + min(1, max(0, (s.mpos[0] - r.x) / r.w)) * (hi - lo)
        return v
    def field(s, surf, r, key, val):
        r = pygame.Rect(r); f = s.focus == key
        pygame.draw.rect(surf, (30, 33, 40), r, border_radius=4); pygame.draw.rect(surf, (110, 150, 230) if f else (80, 86, 100), r, 1, border_radius=4)
        text(surf, val + ('|' if f and pygame.time.get_ticks() // 500 % 2 else ''), (r.x + 6, r.y + 4), sz=13)
        if s.click: s.focus = key if s.hot(r) else (None if s.focus == key else s.focus)
        if s.hot(r) and s.click: s.consumed = True
        enter = False
        if f:
            for e in s.keys:
                if e.key == pygame.K_BACKSPACE: val = val[:-1]
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER): enter = True
                elif e.key == pygame.K_ESCAPE: s.focus = None
                elif e.unicode and e.unicode.isprintable(): val += e.unicode
        return val, enter
