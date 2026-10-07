# План проектирования Wearable RGB MVP

## 1. Подготовить структуру проекта и зафиксировать требования

- Создать `hardware/common`, `hardware/wearable_20x20`, `hardware/wearable_28x28`, `mechanical`, `firmware`, `manufacturing`, `test` и `docs`.
- Зафиксировать оптическую матрицу: 20×20 с шагом 2,50 мм; 28×28 с шагом 2,20 мм. Текущие предварительные outline 49,3 мм и 61,2 мм подтвердить только после DRC-clean edge escape.
- PCB: 4 слоя, 1,0 мм, ENIG, чёрная маска, LED до оптического края.
- Описать режимы питания, температурные ограничения, USB-персонализацию, deep sleep и критерии приёмки.

Статус: требования зафиксированы; созданы `hardware/common`, `hardware/tools`, `hardware/analysis` и каталоги обеих PCB-версий.

## 2. Провести datasheet/BOM freeze

- Проверить электрические пределы, footprints, lifecycle и фактическую доступность ESP32-S3FN8, MHPA1010RGBDT, MBI5124, BMI270, BQ25185, TPS63802, MAX17048, микрофона, PMOS и USB-C.
- Подтвердить формулу Rext, допустимое напряжение выходов MBI5124, два reflow для LED, ток/заряд затвора PMOS и работу входного лимита BQ25185.
- Для каждого критического компонента определить совместимую замену.
- Сформировать preliminary BOM для 5 и 100 устройств.

Статус: частично выполнено. Дополнительно выбраны row translator/decoder/PMOS, MBI buffer, load switches и дроссель; решения и блокеры записаны в `DATASHEET_BOM_FREEZE.md`. Остальные компоненты, alternates, availability и количественный BOM ещё открыты.

## 3. Создать общую принципиальную схему

- Разделить на листы: USB/ESD, charger/power-path, AON 3,3 В, LED 4,1 В, ESP32/clock/boot, IMU/gauge/button, microphone AFE и factory test.
- Реализовать USB-C sink/UFP, native USB, загрузочные pogo pads, аппаратно безопасные EN/OE и защиту от обратного питания отключённых доменов.
- Проверить power sequencing, заряд 300/400 мА, NTC, brownout, ship/recovery и ток deep sleep.

## 4. Создать две схемы матриц

- 20×20: 400 common-anode RGB LED, 4× MBI5124, 20 PMOS-строк, 2× 74HC154.
- 28×28: 784 RGB LED, 6× MBI5124, 28 PMOS-строк, 2× 74HC154.
- Зафиксировать цепочку SDI/SDO, распределение RGB-каналов, отдельные enable двух банков и безопасную последовательность blank/address/latch/enable.
- Выполнить ERC и независимое ревью netlist до placement.

## 5. Спроектировать механику и оптику до разводки

- Построить STEP-контуры PCB, аккумуляторов, USB-C, задней кнопки, микрофонного порта и корпуса.
- Задать дымчатую панель 0,6–0,8 мм, чёрную решётку до края и тестовые варианты высоты/пропускания.
- Зафиксировать component/battery keepouts, технологические рейки и tab-routing.
- Исключить V-cut у крайних LED.

Статус: созданы KiCad 10 платы 49,3×49,3 мм и 61,2×61,2 мм с 400/784 проверенными LED footprints, электрическими nets, оптическими центрами и provisional battery envelopes. Outline остаётся предварительным: внутренний routing pattern помещается, но крайние строки требуют отдельного edge escape. Точные keepouts ждут чертежей аккумуляторов, USB-C и корпуса.

## 6. Разместить компоненты

- L1: регулярная LED-матрица.
- L4: вся электроника и тестовые площадки.
- Сначала зафиксировать USB, кнопку, микрофон, аккумулятор и IMU.
- Затем разместить DC/DC и charger, после них MCU, драйверы и дешифраторы.
- Разнести IMU/микрофон и импульсное питание.
- Исключить компоненты под аккумулятором и обеспечить короткие силовые петли.
- Провести placement review по механике, сборке, ремонту и теплоотводу до трассировки.

## 7. Развести обе PCB

- Stackup: L1 LED/вертикальные RGB-колонки, L2 сплошной GND, L3 строки и питание, L4 логика/компоненты.
- Использовать стандартные сквозные vias без via-in-pad и microvia.
- Строки: до 1,20 мм внутри матрицы; для крайних строк разработать отдельный DRC-проверенный escape.
- Колонки: 0,10–0,15 мм.
- Минимальный local matrix trace/space: 0,10/0,10 мм; standard signal via: 0,45/0,20 мм; local RGB transition via: 0,40/0,20 мм; copper-to-edge: 0,30 мм.
- Силовые шины выполнять полигонами.
- Соблюсти USB differential pair, crystal keepout, непрерывные возвратные пути, локальную развязку и Kelvin feedback DC/DC.
- Выполнить DRC, проверку токовых путей, падений напряжения, тепловых зон и экспорт 3D-модели.

Статус: LED footprints и row/RGB-column nets добавлены. Pre-route DRC проходит с 0 violations; 499 unrouted groups ожидаются до драйверов и трассировки. Отдельные top-left, 180°-rotated bottom-right и normal-to-180° transition 2×2 routing probes проходят с 0 geometric violations для обоих pitches; row buses исправлены на физический L3 (`In2.Cu`). Transition-cell использует пять RGB vias на колонку и локальное сужение row bus до 0,40 мм. Детали находятся в `hardware/analysis/MATRIX_ROUTING_FEASIBILITY.md`. Copper zones, bottom-left/top-right corners, полный повтор pattern и driver exits ещё не проверены, поэтому этот DRC не является финальным.

## 8. Подготовить прошивочную платформу

- ESP-IDF/TinyUSB: DMA/BAM LED scan, renderer 60 FPS, BMI270, audio ADC DMA, power manager, deep sleep и wake от кнопки/движения.
- Реализовать WebUSB, безопасную загрузку ресурсов, MSC как проверяемый режим обслуживания и USB recovery/update.
- Добавить ограничения мощности/температуры, журнал диагностики и производственный self-test.

## 9. Подготовить EVT и измерения

- Заказать сначала 5 PCB и минимум 2 PCBA версии 20×20.
- Провести pixel/ghosting, яркость, USB, IMU, audio, charge, sleep-current и thermal tests.
- Измерить Rext, фронты строк, провалы LED_4V1, EMI и температуру корпуса.
- Выбрать оптический стек.
- После исправлений изготовить 28×28 и повторить тесты.
- Провести 72-часовой burn-in.

## 10. Сформировать производственный пакет MVP

- Использовать JLCPCB Standard PCBA: Economic PCBA не поддерживает требуемую двухстороннюю установку и выбранный stackup/finish.
- Выпустить панель не меньше 70×70 мм с rails не меньше 5 мм и fiducials на обеих assembly sides.
- Выпустить Gerber, drill, IPC netlist, BOM, CPL, assembly drawings, schematic PDF, STEP, panel notes и инструкции программирования/тестирования.
- Провести финальные ERC/DRC/DFM/DFA и BOM availability review.
- Сверить визуализированные Gerber с исходной PCB.
- Сравнить актуальные котировки JLCPCB и PCBWay.
- Заказать 10–20 MVP только после закрытия EVT-отклонений.

## Критерий завершения

Проект считается готовым к MVP только после:

1. Закрытых ERC и DRC без необоснованных исключений.
2. Проверенных datasheet, footprints и BOM availability.
3. Успешных электрических, тепловых, оптических и USB-тестов EVT обеих версий.
4. Проверенного production package и просмотра Gerber.
5. Подтверждённой сборки и 72-часового burn-in.
