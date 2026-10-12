#!/usr/bin/env python3
"""Generates schematic (PDF/SVG/PNG) and mechanical drawing (PDF/PNG, mm, Russian labels) from params.py."""
import os, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, Polygon, Circle, FancyBboxPatch
from params import *
import dropcalc
D = dropcalc.all_()
os.makedirs('out', exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 7})
A3 = (16.54, 11.69)

def frame(fig, title, sheet):
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 420); ax.set_ylim(0, 297); ax.axis('off')
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=1.2))
    ax.add_patch(Rectangle((250, 10), 160, 22, fill=False, lw=0.8))
    ax.text(253, 26, 'wire_grid_32x32 — ' + title, fontsize=9, weight='bold')
    ax.text(253, 19, 'Сетка 32×32 на проводах · шаг %.1f мм · %s · LED_INTERFACE_STANDARD v1' % (PITCH, LED), fontsize=6.5)
    ax.text(253, 13, 'Лист %s · размеры в мм · gen_drawings.py (параметрический, params.py)' % sheet, fontsize=6.5)
    return ax

def dim(ax, x1, y1, x2, y2, txt, off=0, vert=False, fs=7):
    if vert:
        ax.annotate('', (x1 + off, y1), (x1 + off, y2), arrowprops=dict(arrowstyle='<->', lw=0.6))
        ax.plot([x1, x1 + off], [y1, y1], 'k', lw=0.3); ax.plot([x2, x2 + off], [y2, y2], 'k', lw=0.3)
        ax.text(x1 + off - 1.5, (y1 + y2) / 2, txt, rotation=90, ha='right', va='center', fontsize=fs)
    else:
        ax.annotate('', (x1, y1 + off), (x2, y1 + off), arrowprops=dict(arrowstyle='<->', lw=0.6))
        ax.plot([x1, x1], [y1, y1 + off], 'k', lw=0.3); ax.plot([x2, x2], [y2, y2 + off], 'k', lw=0.3)
        ax.text((x1 + x2) / 2, y1 + off + 1, txt, ha='center', va='bottom', fontsize=fs)

def diode(ax, x, y, s, lw=0.4, lab=None):   # anode at (x,y) top, cathode at (x, y-s) — vertical, pointing down
    h = s * 0.35
    ax.plot([x, x], [y, y - s * 0.3], 'k', lw=lw); ax.plot([x, x], [y - s * 0.7, y - s], 'k', lw=lw)
    ax.add_patch(Polygon([(x - h / 2, y - s * 0.3), (x + h / 2, y - s * 0.3), (x, y - s * 0.62)], closed=True, fc='k', lw=0))
    ax.plot([x - h / 2, x + h / 2], [y - s * 0.64, y - s * 0.64], 'k', lw=lw)
    if lab: ax.text(x + h, y - s / 2, lab, fontsize=4, va='center')

# ------------------------------------------------------------------ schematic
def sch_matrix(pdf):
    fig = plt.figure(figsize=A3); ax = frame(fig, 'Схема: матрица 32×32', '1/2 (схема)')
    x0, y0, st = 40, 270, 6.4
    for r in range(N):
        y = y0 - r * st
        ax.plot([x0 - 6, x0 + (N - 1) * st + 2], [y, y], color='#b03030', lw=0.5)
        ax.text(x0 - 7, y, 'ROW_%02d' % (r + 1), ha='right', va='center', fontsize=4.5, color='#b03030')
    for c in range(N):
        x = x0 + c * st + 2.4
        ax.plot([x, x], [y0 + 2, y0 - (N - 1) * st - 5], color='#3040b0', lw=0.5)
        ax.text(x, y0 - (N - 1) * st - 6, 'COL_%02d' % (c + 1), rotation=90, ha='center', va='top', fontsize=4.5, color='#3040b0')
    for r in range(N):
        for c in range(N):
            x = x0 + c * st; y = y0 - r * st
            ax.plot([x, x], [y, y], 'k.', ms=1.2)
            ax.plot([x, x + 0.8], [y, y - 0.6], 'k', lw=0.25); ax.plot([x + 1.6, x + 2.4], [y - 1.9, y - 2.5], 'k', lw=0.25)
            ax.add_patch(Polygon([(x + 0.5, y - 0.9), (x + 1.3, y - 0.3), (x + 1.4, y - 1.6)], closed=True, fc='k', lw=0))
            ax.plot([x + 1.9, x + 2.4], [y - 2.5, y - 2.5], 'k', lw=0.0)
            ax.plot([x + 2.4, x + 2.4], [y - 2.5, y - 2.5], 'k.', ms=1.2)
            ax.plot([x + 1.4, x + 2.4], [y - 1.6, y - 2.5], 'k', lw=0.25)
    ax.text(x0, 283, 'D(r,c), r,c = 1…32: анод → провод строки ROW_r, катод → провод столбца COL_c. Позиционное обозначение Dn, n = 32(r−1)+c (как на mono_panel_32x32). 1024 × %s (LCSC C84265).' % LED, fontsize=7)
    tx = 270
    notes = ['ROW_r: Ø%.2f мм эмаль, %.0f мм; источник P-FET LED_4V1 4,1 В, до %.2f А (32×10 мА)' % (ROW_WIRE_D, WIRE_LEN, I_ROW),
             'COL_c: Ø%.2f мм эмаль, %.0f мм; сток MBI5124 ~10 мА' % (COL_WIRE_D, WIRE_LEN),
             'Под светодиодами нет печатной платы: провода = шины',
             'Строки разводятся гребёнкой (шлейф 28 AWG) на J_R1/J_R2,',
             'столбцы — на J_C1/J_C2 (IDC 2×8, 2,54 мм): штырь n = линия n',
             '(J_R2/J_C2: штырь n = линия 16+n).',
             '', 'Вариант A: 4 шлейфа → hardware/garland_breakout',
             '  (EEPROM U_ID уже на breakout, прошить preset wire32).',
             'Вариант B: гребёнки → бирка WG_TAG → 2× IDC 2×20 1,27 мм',
             '  → J_RH1/J_CH1 платы v15 (ID EEPROM на бирке).', '',
             'Падение по строке (§5, ≤ 350 мВ при 0,32 А):',
             '  A: %d мВ (запас %d мВ), B: %d мВ (запас %d мВ)' % (D['A']['drop_mV'], D['A']['margin_mV'], D['B']['drop_mV'], D['B']['margin_mV'])]
    for i, t in enumerate(notes): ax.text(tx, 270 - i * 5, t, fontsize=7)
    # legend symbol
    diode(ax, 300, 190, 18); ax.text(304, 190, 'A (анод) → ROW', fontsize=7); ax.text(304, 172, 'K (катод) → COL', fontsize=7)
    ax.text(300, 165, 'NCD0603W1: катод = метка на корпусе (зелёная/срез), Vf 2,6…3,6 В', fontsize=6, ha='center')
    pdf.savefig(fig); fig.savefig('out/schematic_matrix.png', dpi=110); fig.savefig('out/schematic_matrix.svg'); plt.close(fig)

def box(ax, x, y, w, h, title, pins, side='r', fs=5.5):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=0.9)); ax.text(x + w / 2, y + h + 1.5, title, ha='center', fontsize=7, weight='bold')
    n = len(pins); st = h / (n + 1)
    for i, (num, name) in enumerate(pins):
        yy = y + h - (i + 1) * st
        if side == 'r':
            ax.plot([x + w, x + w + 6], [yy, yy], 'k', lw=0.5); ax.text(x + w + 0.5, yy + 0.4, str(num), fontsize=4.5)
            ax.text(x + w - 0.8, yy, name, ha='right', va='center', fontsize=fs)
        else:
            ax.plot([x - 6, x], [yy, yy], 'k', lw=0.5); ax.text(x - 0.5, yy + 0.4, str(num), fontsize=4.5, ha='right')
            ax.text(x + 0.8, yy, name, ha='left', va='center', fontsize=fs)

def sch_conn(pdf):
    fig = plt.figure(figsize=A3); ax = frame(fig, 'Схема: разъёмы, бирка WG_TAG, ID EEPROM, ESD', '2/2 (схема)')
    def p16(pref, off): return [(n, '%s_%02d' % (pref, n + off)) for n in range(1, 17)]
    box(ax, 20, 160, 26, 100, 'J_R1 (2×8 2,54)', p16('ROW', 0), 'r')
    box(ax, 20, 40, 26, 100, 'J_R2 (2×8 2,54)', p16('ROW', 16), 'r')
    box(ax, 90, 160, 26, 100, 'J_C1 (2×8 2,54)', p16('COL', 0), 'r')
    box(ax, 90, 40, 26, 100, 'J_C2 (2×8 2,54)', p16('COL', 16), 'r')
    ax.text(15, 268, 'Сторона сетки: гребёнки (шлейф 16 жил 28 AWG, IDC-16F).\nСовпадает 1:1 с J_R1/J_R2/J_C1/J_C2 платы garland_breakout.', fontsize=7)
    ax.text(15, 33, 'Ключ IDC: штырь 1 = красная жила шлейфа = ROW_01 / COL_01 (J_R2: ROW_17).', fontsize=6.5)
    rp = [(n, 'ROW_%02d' % n) for n in range(1, 33)] + [(33, 'GND'), (34, 'VLED_SENSE (NC)'), (35, 'ID_SDA'), (36, 'ID_SCL'), (37, 'ID_3V3'), (38, 'GND'), (39, 'ID_PRESENT_N→GND'), (40, 'GND')]
    cp = [(n, 'COL_%02d' % n) for n in range(1, 33)] + [(33, 'GND'), (34, 'EXP (NC)'), (35, 'EXP (NC)'), (36, 'EXP (NC)'), (37, 'EXP (NC)'), (38, 'GND'), (39, 'EXP_3V3 (NC)'), (40, 'GND')]
    box(ax, 175, 45, 30, 215, 'J_OUT_R → v15 J_RH1', rp, 'l', 5)
    box(ax, 230, 45, 30, 215, 'J_OUT_C → v15 J_CH1', cp, 'l', 5)
    ax.text(160, 272, 'Бирка WG_TAG (вариант B): 2× IDC 2×20 1,27 мм (BH127VS-40P),\nштырь n = линия n, ровно как J_RH1/J_CH1 и FFC.', fontsize=7)
    ax.text(160, 38, 'J_R1/J_R2 → J_OUT_R 1…32, J_C1/J_C2 → J_OUT_C 1…32 (дорожки ≥ 0,4 мм для строк, 0,32 А).', fontsize=6.5)
    # EEPROM
    ex, ey = 290, 200
    ax.add_patch(Rectangle((ex, ey), 30, 34, fill=False, lw=0.9)); ax.text(ex + 15, ey + 36, 'U_ID 24LC02BT-I/OT (SOT-23-5), 0x50', ha='center', fontsize=7, weight='bold')
    for i, (pn, nm, nt) in enumerate([(4, 'VCC', 'ID_3V3 (37)'), (3, 'SDA', 'ID_SDA (35)'), (1, 'SCL', 'ID_SCL (36)')]):
        yy = ey + 28 - i * 9; ax.plot([ex - 18, ex], [yy, yy], 'k', lw=0.6); ax.text(ex + 1, yy, '%d %s' % (pn, nm), va='center', fontsize=6)
        ax.text(ex - 19, yy, nt, ha='right', va='center', fontsize=6)
    for i, (pn, nm) in enumerate([(2, 'VSS'), (5, 'WP')]):
        yy = ey + 24 - i * 12; ax.plot([ex + 30, ex + 44], [yy, yy], 'k', lw=0.6); ax.text(ex + 29, yy, '%s %d' % (nm, pn), ha='right', va='center', fontsize=6)
        ax.text(ex + 45, yy, 'GND', va='center', fontsize=6)
    ax.text(ex, ey - 6, 'C_ID 100 нФ 0603: ID_3V3 ↔ GND у вывода 4.', fontsize=6)
    ax.text(ex, ey - 11, 'Подтяжки SDA/SCL — на основной плате (шина IMU).', fontsize=6)
    ax.text(ex, ey - 16, 'WP = GND: прошивка из платы (panel write).', fontsize=6)
    ax.text(ex, ey - 21, 'Пины 39 → GND (ID_PRESENT_N), 33/38/40 → GND.', fontsize=6)
    ax.text(ex, ey - 26, 'Вариант A: бирка не нужна — U_ID уже на breakout.', fontsize=6)
    ax.text(ex, ey - 31, 'Мини-вариант: только EEPROM на клочке', fontsize=6)
    ax.text(ex, ey - 35, 'макетки 10×15 мм, припаян к жилам 33–40 шлейфа.', fontsize=6)
    # ESD
    ax.add_patch(FancyBboxPatch((285, 45), 115, 105, boxstyle='round,pad=1', fill=False, lw=0.8, ec='#a04000'))
    esd = ['ESD — примечание', '• Сетка — 64 голых антенны ~0,34 м без платы и без TVS.',
           '• Защита стоит на стороне платы: 64× PESD5V0S1BL на garland_breakout',
           '  (вариант A) или D_R01…D_C32 у J_RH1/J_CH1 на v15 (вариант B) —',
           '  при сборке вариант B TVS ОБЯЗАТЕЛЬНО запаяны (в wearable они DNP).',
           '• Опционально на бирке: 64× PESD5V0S1BL (C84374, SOD-882)',
           '  линия → GND, у разъёмов J_R*/J_C*; GND = 33/38/40.',
           '• Рамка (если металл) и GND гребёнок — к GND одним проводом',
           '  у бирки/breakout; ESD-браслет при пайке и подключении.',
           '• Сначала подключать GND (шлейф с ключом — все жилы разом),',
           '  никогда не подключать/отключать под питанием.',
           '• Эмаль не изолирует от ESD — не трогать сетку при работе.',
           '• NCD0603W1 без встроенного стабилитрона: обратное',
           '  напряжение ≤ 5 В (строки ≤ 4,1 В — в норме).']
    for i, t in enumerate(esd): ax.text(288, 145 - i * 7, t, fontsize=6.3, weight='bold' if i == 0 else 'normal', color='#a04000' if i == 0 else 'k')
    pdf.savefig(fig); fig.savefig('out/schematic_connectors.png', dpi=110); fig.savefig('out/schematic_connectors.svg'); plt.close(fig)

# ------------------------------------------------------------------ mechanical
def mech_plan(pdf):
    fig = plt.figure(figsize=A3); ax = frame(fig, 'Чертёж: общий вид, рамка, подвод', '1/3 (механика)')
    s = 205 / OUTER; ox, oy = 62, 52              # scale to fit
    def T(x, y): return ox + x * s, oy + y * s
    ax.add_patch(Rectangle(T(0, 0), OUTER * s, OUTER * s, fc='#e8dcc0', ec='k', lw=0.8))
    ax.add_patch(Rectangle(T(FRAME_W, FRAME_W), INNER * s, INNER * s, fc='white', ec='k', lw=0.6))
    g0 = FRAME_W + RAIL_GAP
    for i in range(N):
        y = g0 + (N - 1 - i) * PITCH; x1, y1 = T(FRAME_W - 4, y); x2, _ = T(OUTER - FRAME_W + 4, y)
        ax.plot([x1, x2], [y1, y1], color='#b87333', lw=0.7)
        x = g0 + i * PITCH; xa, ya = T(x, FRAME_W - 4); _, yb = T(x, OUTER - FRAME_W + 4)
        ax.plot([xa, xa], [ya, yb], color='#704020', lw=0.35)
    for r in range(N):
        for c in range(N):
            x, y = T(g0 + c * PITCH + 0.6, g0 + (N - 1 - r) * PITCH + 0.6); ax.plot(x, y, 's', ms=1.1, color='#f0c000', mec='k', mew=0.15)
    ax.text(*T(OUTER / 2, OUTER + 3), 'Вид спереди (сторона светодиодов). Строки ROW_01…32 — горизонтально (сверху вниз), столбцы COL_01…32 — вертикально (слева направо).', ha='center', fontsize=6.5)
    # dims
    y_top = oy + OUTER * s
    dim(ax, ox, y_top, ox + OUTER * s, y_top, 'рамка %.0f × %.0f' % (OUTER, OUTER), off=10)
    dim(ax, ox + FRAME_W * s, y_top, ox + (OUTER - FRAME_W) * s, y_top, 'окно / длина провода %.0f' % INNER, off=17)
    a, _ = T(g0, 0); b, _ = T(g0 + SPAN, 0)
    dim(ax, a, oy, b, oy, '31 × шаг %.1f = %.0f (центры LED)' % (PITCH, SPAN), off=-12)
    a, _ = T(g0, 0); b, _ = T(g0 + PITCH, 0); dim(ax, a, oy, b, oy, 'шаг %.0f' % PITCH, off=-5, fs=6)
    ax.text(*T(-3, OUTER / 2), 'рейка строк (макетная полоса,\nшаг отверстий 2,54, пайка + натяжение)', rotation=90, ha='right', va='center', fontsize=6)
    ax.text(*T(OUTER / 2, -24), 'рейка столбцов (снизу)', ha='center', fontsize=6)
    # fans and tag
    tx, ty = T(-80, -55)
    ax.add_patch(Rectangle((tx, ty), 22, 12, fc='#2a6a2a', ec='k')); ax.text(tx + 11, ty + 6, 'WG_TAG', color='w', ha='center', va='center', fontsize=6)
    for k, (yy, lab) in enumerate([(FRAME_W + RAIL_GAP + 23.5 * PITCH, 'J_R1\n(строки 1…16)'), (FRAME_W + RAIL_GAP + 7.5 * PITCH, 'J_R2\n(строки 17…32)')]):
        x0, y0 = T(0, yy); ax.plot([x0, x0 - 10, tx + 11], [y0, y0, ty + 12], color='gray', lw=2.2, alpha=0.7)
        ax.text(x0 - 12, y0 + 3, lab, ha='right', fontsize=5.5)
    for k, xx in enumerate([FRAME_W + RAIL_GAP + 7.5 * PITCH, FRAME_W + RAIL_GAP + 23.5 * PITCH]):
        x0, y0 = T(xx, 0); ax.plot([x0, x0, tx + 22], [y0, y0 - 10, ty + 6], color='gray', lw=2.2, alpha=0.7)
        ax.text(x0, y0 - 13, 'гребёнка J_C%d' % (k + 1), ha='center', fontsize=5.5)
    # right column: notes
    nx = 290
    lines = ['ПАРАМЕТРЫ (params.py)', 'Матрица: 32 × 32 = 1024 LED, %s 0603 белый' % LED, 'Шаг: %.1f мм (слой куба), центры: %.0f мм' % (PITCH, SPAN),
             'Строки (аноды): эмаль ПЭТВ-2 Ø%.2f мм, %.0f мм + 20 мм хвост' % (ROW_WIRE_D, WIRE_LEN),
             '   альтернатива: луженая 24 AWG (0,51 мм) — без эмали', 'Столбцы (катоды): эмаль Ø%.2f мм (0,2…0,3), %.0f мм + 20' % (COL_WIRE_D, WIRE_LEN),
             'Столбцы лежат ПОВЕРХ строк (сторона LED).', 'Рамка: фанера/алюм. уголок %.0f мм, окно %.0f мм' % (FRAME_W, INNER),
             'Рейки: полоски макетки 2,54 мм, клей + 2 винта М2', '', 'ПОДВОД', 'Гребёнки: 4× шлейф 16 жил 28 AWG, жила k',
             '  отрезается по месту: от IDC-16F до площадки рейки', '  ≤ %.0f мм (самая дальняя жила).' % (FAN_MAX_M * 1e3),
             'Вариант A: те же 4 шлейфа до garland_breakout,', '  общая длина ≤ %.1f м (по расчёту ≤ %.2f м).' % (LEAD_RIBBON_M + FAN_MAX_M, D['A']['max_lead_m'] + FAN_MAX_M),
             'Вариант B: гребёнки → бирка WG_TAG (у угла рамки)', '  → 2× шлейф 40 жил 0,635 мм (3M 3365/40) %.1f м → v15.' % LEAD_RIBBON_M,
             '  Расчётный предел подвода %.1f м.' % D['B']['max_lead_m'], '', 'См. лист 2: перекрестье, пайка, натяжение;', 'лист 3: расчёт падения.']
    for i, t in enumerate(lines): ax.text(nx, 275 - i * 6.2, t, fontsize=7, weight='bold' if t.isupper() or t in ('ПОДВОД',) else 'normal')
    pdf.savefig(fig); fig.savefig('out/mech_1_plan.png', dpi=110); plt.close(fig)

def mech_detail(pdf):
    fig = plt.figure(figsize=A3); ax = frame(fig, 'Чертёж: узлы (перекрестье, пайка, натяжение, вариант 3 мм)', '2/3 (механика)')
    # A: crossing top view, scale 20:1
    S = 20; cx, cy = 70, 200
    ax.text(25, 275, 'А. Перекрестье, вид сверху (М 20:1)', fontsize=8, weight='bold')
    rw, cw = ROW_WIRE_D * S, COL_WIRE_D * S
    ax.add_patch(Rectangle((cx - 45, cy - rw / 2), 100, rw, fc='#c87533', ec='k', lw=0.4))
    ax.add_patch(Rectangle((cx - cw / 2, cy - 45), cw, 100, fc='#8a4a20', ec='k', lw=0.4, zorder=3))
    ax.add_patch(Rectangle((cx - 1.2 * S / 2, cy - 0.75 * S), 1.5 * S, 1.5 * S, fc='#ffd0ff', ec='m', lw=0.5, alpha=0.5, zorder=2))
    # LED on the diagonal: anode on row at (+1.1,0), cathode on column at (0,+1.1)
    import numpy as np
    a = np.array([cx + 1.1 * S, cy]); k = np.array([cx, cy + 1.1 * S]); u = (a - k) / np.linalg.norm(a - k); n = np.array([-u[1], u[0]])
    m = (a + k) / 2; L, W = 1.6 * S, 0.8 * S
    pts = [m + u * L / 2 + n * W / 2, m - u * L / 2 + n * W / 2, m - u * L / 2 - n * W / 2, m + u * L / 2 - n * W / 2]
    ax.add_patch(Polygon(pts, fc='#fff6c0', ec='k', lw=0.6, zorder=5))
    for e, col in ((a, '#c0c0c0'), (k, '#c0c0c0')):
        ax.add_patch(Circle(e, 0.45 * S, fc='#d8d8d8', ec='k', lw=0.4, zorder=6, alpha=0.9))
    ax.text(*(a + [8, -10]), 'анод → строка\n(галтель припоя)', fontsize=6)
    ax.text(*(k + [-38, 8]), 'катод (метка) →\nстолбец', fontsize=6)
    ax.text(cx + 30, cy + 6, 'строка Ø%.2f' % ROW_WIRE_D, fontsize=6); ax.text(cx + 3, cy - 44, 'столбец Ø%.2f' % COL_WIRE_D, fontsize=6)
    ax.text(cx - 44, cy - 20, 'изоляция в точке\nкреста: каптон 1,5×1,5 мм\n+ эмаль обоих проводов', fontsize=6, color='m')
    dim(ax, cx, cy - 12, cx + 1.1 * S, cy - 12, '1,1', off=-4, fs=6); ax.text(cx - 44, cy + 52, 'LED 0603 (1,6×0,8) лежит по диагонали угла, светит вверх (+Z)', fontsize=6)
    # B: section
    ax.text(25, 128, 'Б. Разрез по диагонали LED (М 20:1)', fontsize=8, weight='bold')
    bx, by = 40, 85
    ax.add_patch(Circle((bx, by), rw / 2, fc='#c87533', ec='k')); ax.text(bx - 6, by - 10, 'строка', fontsize=6)
    ax.add_patch(Circle((bx + 1.556 * S, by + (ROW_WIRE_D / 2 + COL_WIRE_D / 2) * S * 0 + (ROW_WIRE_D - COL_WIRE_D) / 2 * S), cw / 2, fc='#8a4a20', ec='k'))
    ax.text(bx + 1.556 * S - 4, by - 10, 'столбец', fontsize=6)
    ax.add_patch(Rectangle((bx - 6, by + rw / 2), 1.6 * S + 12, 0.6 * S, fc='#fff6c0', ec='k', lw=0.6))
    ax.add_patch(Polygon([(bx - 8, by), (bx - 6, by + rw / 2), (bx + 4, by + rw / 2), (bx + 5, by)], fc='#d8d8d8', ec='k', lw=0.3))
    ax.add_patch(Polygon([(bx + 1.556 * S - 5, by + 1), (bx + 1.556 * S - 4, by + rw / 2), (bx + 1.556 * S + 6, by + rw / 2), (bx + 1.556 * S + 7, by + 1)], fc='#d8d8d8', ec='k', lw=0.3))
    ax.text(bx + 8, by + rw / 2 + 0.6 * S + 2, 'NCD0603W1, h 0,6', fontsize=6); ax.text(bx + 40, by + 3, 'припой (Sn63, флюс без отмывки)', fontsize=6)
    ax.text(25, 60, 'Столбец лежит поверх строки (в точке креста — каптон 1,5×1,5 мм).\nВ 1,1 мм от креста перепад высот ≈ 0,1 мм выбирается припоем;\nLED спаян «мостиком» поверх. Зазор между площадками 1,56 мм.', fontsize=6)
    # C: solder joint procedure
    ax.text(150, 275, 'В. Паяное соединение', fontsize=8, weight='bold')
    st = ['1. Эмаль снять ТОЛЬКО под LED: точка 1,5 мм, паяльник 380–400 °C', '   с каплей припоя (ПЭТВ/УЭВ «самолудящаяся» эмаль) или скальпель.',
          '2. Облудить точку на строке (+1,1 мм от креста) и на столбце.', '3. LED пинцетом в кондуктор (паз 0,9×1,7 по диагонали),',
          '   катод — к столбцу. Прихватить анод, затем катод, 330 °C, ≤ 2 с.', '4. Флюс-гель, без лишнего припоя: галтель ≤ 0,3 мм над корпусом.',
          '5. Остаток эмали у креста НЕ трогать; каптон 1,5×1,5 мм под крест.', 'Контроль: лупа ×10, нет мостика на крест, LED светит от CR2032.']
    for i, t in enumerate(st): ax.text(150, 266 - i * 6, t, fontsize=6.5)
    # D: 3 mm option
    ax.text(150, 205, 'Г. Вариант 3 мм выводной LED (белый, рассеянный)', fontsize=8, weight='bold')
    gx, gy = 175, 160; S2 = 3
    ax.plot([gx - 30, gx + 40], [gy, gy], color='#c87533', lw=2); ax.plot([gx + 8, gx + 8], [gy - 30, gy + 30], color='#8a4a20', lw=1.2)
    ax.add_patch(Circle((gx, gy + 6), 1.5 * S2, fc='#fffbe0', ec='k')); ax.plot([gx - 1.27 * S2 / 2, gx - 1.27 * S2 / 2 - 2, gx - 2], [gy + 6, gy + 2, gy], 'k', lw=0.6)
    ax.plot([gx + 1.27 * S2 / 2, gx + 8], [gy + 6, gy + 6], 'k', lw=0.6)
    ax.text(gx + 12, gy + 12, 'длинная нога (A) загнута на строку,\nкороткая (K) — на столбец, по 2 витка,\nпайка, остаток откусить. Столбец\nсмещён на 4 мм от креста: изоляция\nне нужна, если провода не касаются.', fontsize=6)
    ax.text(150, 128, '3 мм: Vf и ток те же; яркость ниже, угол 30–60°. Шаг ≥ 8 мм.', fontsize=6.5)
    # E: tensioning
    ax.text(300, 275, 'Д. Рамка и натяжение', fontsize=8, weight='bold')
    ex, ey = 310, 215
    ax.add_patch(Rectangle((ex, ey), 12, 40, fc='#e8dcc0', ec='k')); ax.add_patch(Rectangle((ex + 12, ey + 5), 3, 30, fc='#3a7a3a', ec='k'))
    ax.add_patch(Rectangle((ex + 70, ey), 12, 40, fc='#e8dcc0', ec='k')); ax.add_patch(Rectangle((ex + 67, ey + 5), 3, 30, fc='#3a7a3a', ec='k'))
    ax.plot([ex + 13.5, ex + 68.5], [ey + 20, ey + 20], color='#c87533', lw=1.5)
    ax.add_patch(Circle((ex + 6, ey + 20), 2, fc='w', ec='k')); ax.add_patch(Circle((ex + 76, ey + 20), 2, fc='w', ec='k'))
    ax.text(ex - 2, ey - 6, 'рейка A: провод\nзапаян в отверстие', fontsize=6); ax.text(ex + 55, ey - 6, 'рейка B: натяг ~3 Н (300 г)\nгрузиком, затем пайка', fontsize=6)
    tens = ['• Строки Ø0,5: натяг 3–5 Н, удлинение < 0,1 %, прогиб < 1 мм.', '• Столбцы Ø0,25: натяг 1–1,5 Н (обрыв ~ 9 Н).',
            '• Порядок: все 32 строки → каптон на кресты → столбцы.', '• Рейки: полоска макетки 2,54 мм (FR4) на клею к рамке,',
            '  провод в отверстие с шагом 10 мм (каждое 4-е ≈ 10,16 —', '  используйте отверстия через 2,54×4 и смещение ≤ 0,16 мм/шаг', '  или сверлите свою рейку с шагом %.1f мм по кондуктору).' % PITCH,
            '• Для куба: рамка = слой; слои на 4 стойках М3, шаг слоёв = %.0f мм.' % PITCH, '• Снятие с рамки (если нужен «голый» слой): обрезать', '  провода у реек, оставив хвосты 20 мм для пайки к стойкам.']
    for i, t in enumerate(tens): ax.text(295, 200 - i * 6, t, fontsize=6.3)
    pdf.savefig(fig); fig.savefig('out/mech_2_details.png', dpi=110); plt.close(fig)

def mech_drop(pdf):
    fig = plt.figure(figsize=A3); ax = frame(fig, 'Расчёт падения напряжения (§5 стандарта)', '3/3 (механика)')
    ax.text(25, 275, 'Бюджет: LED_4V1 4,10 − P-FET 0,05 − Vf 3,10 − колено MBI5124 0,40 = 0,55 В; проектный предел проводки строки 0,35 В при %.2f А.' % I_ROW, fontsize=8)
    def table(x, y, hdr, rows, widths, title):
        ax.text(x, y + 8, title, fontsize=8, weight='bold')
        cx = x
        for h, w in zip(hdr, widths): ax.text(cx, y, h, fontsize=6.5, weight='bold'); cx += w
        ax.plot([x, x + sum(widths)], [y - 2, y - 2], 'k', lw=0.5)
        for i, r in enumerate(rows):
            cx = x
            for v, w in zip(r, widths): ax.text(cx, y - 7 - i * 6, str(v), fontsize=6.5); cx += w
        return y - 7 - len(rows) * 6
    for j, key in enumerate('AB'):
        b = D[key]
        title = {'A': 'Вариант A: v15 → FFC → garland_breakout → шлейф → сетка', 'B': 'Вариант B: v15 J_RH1 → шлейф 0,635 → WG_TAG → гребёнка → сетка'}[key]
        yy = table(25 + j * 195, 255, ['Участок', 'R, мОм', 'ΔU, мВ'], b['items'] + [('ИТОГО (худший LED)', b['R_mohm'], b['drop_mV'])], [120, 30, 30], title)
        ax.text(25 + j * 195, yy - 4, 'Запас до 350 мВ: %d мВ. Макс. длина подвода 28 AWG: %.2f м.' % (b['margin_mV'], b['max_lead_m']), fontsize=7, color='#006000')
    rows = [(n, r, a, b) for n, r, a, b in D['wires']]
    yy = table(25, 160, ['Провод строки', 'Ом/м', 'ΔU½ в сетке, мВ', 'ΔU с конца, мВ'], rows, [80, 30, 45, 45], 'Провод строки: падение внутри сетки (%.0f мм, %.2f А)' % (WIRE_LEN, I_ROW))
    ax.text(25, yy - 4, 'Внутри сетки падение мало при любом проводе ≥ 0,3 мм; Ø0,5 выбран ради жёсткости и натяга, а не ради падения.', fontsize=7)
    notes = ['Столбец Ø%.2f мм: %.3f Ом/м × %.2f м × 10 мА = %.2f мВ — пренебрежимо.' % (COL_WIRE_D, D['col_ohm_per_m'], WIRE_LEN / 1000, D['col_drop_mV']),
             'Сопротивление контакта IDC принято 10 мОм, шлейф 28 AWG (7/0,127) 0,23 Ом/м, FFC 1,64 Ом/м (по §5).',
             'Неравномерность яркости по строке: MBI5124 — источник тока, пока запас ≥ 0 В яркость не зависит от падения.',
             'EEPROM row_path_mohm = %d (вариант A, худший; preset wire32).' % D['row_mohm_eeprom'],
             'Нагрев: строка Ø0,5 при 0,32 А·(1/32 скважность) — < 0,1 °C; 28 AWG шлейф — < 1 °C.']
    for i, t in enumerate(notes): ax.text(220, 150 - i * 7, t, fontsize=6.8)
    pdf.savefig(fig); fig.savefig('out/mech_3_dropcalc.png', dpi=110); plt.close(fig)

HQ = os.path.join('renders', 'hq'); os.makedirs(HQ, exist_ok=True)
_orig_save = plt.Figure.savefig
def _save(self, fn, *a, **k):
    _orig_save(self, fn, *a, **k)
    if isinstance(fn, str) and fn.startswith('out/') and fn.endswith('.png'):
        _orig_save(self, os.path.join(HQ, os.path.basename(fn).replace('.png', '_300dpi.png')), dpi=300)
plt.Figure.savefig = _save

if __name__ == '__main__':
    with PdfPages('wire_grid_32x32_schematic.pdf') as pdf:
        sch_matrix(pdf); sch_conn(pdf)
    with PdfPages('wire_grid_32x32_mechanical.pdf') as pdf:
        mech_plan(pdf); mech_detail(pdf); mech_drop(pdf)
    print('ok')
