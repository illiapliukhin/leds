"""'Модели' tab: equations, sources and assumptions of every physical model (+ live unit-test table)."""
import os, sys, subprocess
import pygame
from .ui import text
from .phys.elec import DS

DOC = r"""
ЭЛЕКТРИКА — дерево питания (phys/elec.py, PowerTree)
  Узлы VBUS, SYS, BAT, LED_4V1, AON_3V3. На каждом шаге — закон Кирхгофа для токов, решение методом Ньютона
  (численный якобиан, демпфирование, поиск вдоль направления, холодный перезапуск). Невязка показывается в «Лаборатории».
  USB: источник Тевенина Vusb, Rкабеля 0.15 Ом (допущение), ограничение тока адаптера.
  USBLC6: I = (V − 6 В)/0.6 Ом выше VBR; TJ = Tплаты + P·θ(1−e^(−t/20 мс)); отказ «КЗ» при TJ > 200 °C (допущение).
  BQ25185: SYS = min(4.5 В, VIN − 0.25 Ом·I), ILIM 1.1 А, OVP 18.5 В, abs max 25 В, ICHG 0.5 А, CV 4.2 В,
           TREG 100 °C (линейный спад до 0 при 150 °C), TSHUT 150/135 °C, BATFET 50 мОм (идеальный диод), BATOCP 3 А.
  Ячейка: E = OCV(SOC) (типовая кривая Li-ion, допущение), Rвн(T) = R25·e^(0.025(25−T)), R пути = R меди BAT_RAW (из
           .kicad_pcb, узловой анализ) + 2×10 мОм контакты PicoBlade. PCM ячейки: отключение при |I| > 4 А (допущение).
  TPS63802: VOUT = 0.5·(1+681k/91k) = 4.24 В, η(I,VIN) — аппроксимация графика даташита, ограничение ключа 5 А →
           средний ток выхода ≈ 0.55·5·min(1,VIN/VOUT) (допущение), abs max VIN 6 В, OTP 150 °C.
  TLV75733: VOUT = min(3.3, VIN − 0.3 Ом·I), ILIM 1.2 А, TSD 165 °C (допущение), abs max 6 В.
  ESP32-S3: ток по режиму (deep sleep … Wi-Fi TX), brown-out 2.7 В (допущение), abs max VDD 3.6 В.
СВЕТОДИОДЫ (LedModel, solve_rows)
  V = n·Vt·ln(I/Is) + I·Rs − 2 мВ/К·(T−25): подгонка VF(5 мА)=2.8 В (даташит NCD0603W1) и VF(20 мА)=3.10 В (допущение), n=4.
  Канал MBI5124: I = Iset·(1 − e^(−3·Vds/0.4 В)), Iset = 1.24·15/Rext. Строка: подача V_LED − Iстр·(R платы + Rds AO3403(T)
  + R FFC), шина панели — лестница из 31 сегмента с суммарным R = 2·R_eff (наши IR-данные: ir_rows.json).
  Яркость ∝ I^0.95·(1 − 0.3 %/К) (допущение), фантомное свечение 0.4 % из предыдущей строки (допущение).
  Отказ LED: пиковый ток > IFP 50 мА накапливает повреждение (I/IFP − 1)·0.5 в секунду → обрыв (допущение).
ТЕПЛО (phys/thermal.py)
  Плата — сетка МКР 2.5 мм: k·t на ячейку из плотности меди 4 слоёв (растеризация .kicad_pcb), C = ρc·объём,
  потери в воздух h = 7 Вт/м²К (конвекция, допущение) + излучение εσ(T⁴−Ta⁴), ε = 0.9, обе стороны.
  Явная схема с устойчивым шагом dt ≤ 0.2·dx²·ρc/k. TJ = T ячейки + P·ΨJB, инерция корпуса τ = 0.5 с (допущение).
  Панель — сосредоточенная модель (площадь, обе стороны). Ячейка: C = 40 Дж/К, θ = 20 К/Вт (допущения).
ОТКАЗЫ
  По превышению abs max (V), по TJ (тепло), по I²t меди — уравнение Ондердонка (основа графиков IPC-2152):
  t_плавл = log10((Tm−Ta)/(234+Ta)+1)·A_cmil² / (33·I²); ток по сегментам BAT_RAW — из узлового решения.
  «Возможно возгорание» — только когда энергия не ограничена (ячейка без PCM, нет предохранителя);
  иначе — «гибель компонента без открытого огня».
МЕХАНИКА
  Кабели: Верле + проекция ограничений (PBD), 14 сегментов, длина = реальная длина кабеля, натяжение = хорда/длина.
"""

class ModelsView:
    def __init__(s, app): s.app = app; s.scroll = 0; s.report = None
    def tick(s, dt): pass
    def event(s, e, view):
        if e.type == pygame.MOUSEWHEEL: s.scroll = max(0, s.scroll - e.y * 3)
    def draw(s, surf, view):
        surf.fill((14, 15, 19), view)
        lines = DOC.strip('\n').split('\n') + ['', 'ИСТОЧНИКИ ДАННЫХ (даташиты)'] + ['  %s: %s' % (k, v['S']) for k, v in DS.items()]
        if s.report: lines += ['', 'ПРОВЕРКА МОДЕЛЕЙ (ручной расчёт vs модель)'] + ['  ' + l for l in s.report]
        y = view.y + 8
        for ln in lines[s.scroll:]:
            c = (150, 200, 255) if ln and not ln.startswith(' ') else (210, 215, 225)
            if 'FAIL' in ln: c = (255, 90, 90)
            text(surf, ln[:200], (view.x + 12, y), c, 12, mono=ln.startswith('  ')); y += 15
            if y > view.bottom - 14: break
    def panel(s, surf, ui, rr):
        x, y, W = rr.x + 10, rr.y + 8, rr.w - 20
        text(surf, 'Модели, уравнения, допущения', (x, y), (170, 180, 200), 13); y += 26
        if ui.button(surf, (x, y, W, 28), 'Проверить модели (ручной расчёт)'):
            from . import physcheck
            s.report = physcheck.run()
        y += 36
        text(surf, 'Колесо — прокрутка.', (x, y), (140, 146, 160), 11)
