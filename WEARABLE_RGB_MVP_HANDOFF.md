# Wearable RGB MVP — передача проекта

Статус документа: предварительная инженерная спецификация для продолжения в репозитории.  
Важно: доказанная полная трассировка LED-матрицы перенесена в рабочие KiCad 10
PCB обеих версий. Harness-free roots включают generated power, MCU/USB,
IMU/gauge/input, audio, LED-driver, полные LED-matrix и row-selection sheets.
Точные внешние компоненты, несколько критических footprints, backside
placement/routing, L2 GND и физические измерения ещё не выполнены.
Все значения, помеченные как требующие проверки, нельзя считать
production-ready.

## 1. Цель

Разработать два носимых квадратных RGB-устройства:

| Версия | Матрица | Пиксели | Ориентировочная PCB | Шаг LED |
|---|---:|---:|---:|---:|
| Compact | 20×20 | 400 | 49,3×49,3 мм | 2,50 мм |
| High-resolution | 28×28 | 784 | 61,2×61,2 мм | 2,20 мм |

Функции:

- безрамочная RGB-матрица до визуального края;
- реакция на наклон, движение и встряхивание;
- визуализация жидкости, игры и предустановленные анимации;
- реакция на музыку через микрофон;
- задняя кнопка: пробуждение и навигация;
- USB-C сбоку: зарядка, WebUSB, загрузка ресурсов и recovery;
- deep sleep, пробуждение кнопкой или IMU;
- без вибромотора и динамика;
- аккумулятор полностью внутри контура PCB.

## 2. Зафиксированная архитектура

### MCU

- ESP32-S3FN8, QFN56 7×7 мм.
- 8 МБ встроенной Flash, 512 КБ SRAM, native USB OTG, GDMA.
- Wi-Fi/BLE не используются и не инициализируются.
- RF-антенна в MVP не устанавливается.
- Внешняя SPI Flash исключена.
- 40 МГц crystal, ±10 ppm; кандидат L327S400H11L.
- CHIP_PU: 10 кОм pull-up и 1 мкФ на GND.
- USB: GPIO19 D−, GPIO20 D+, 22–33 Ом последовательно.
- Strapping GPIO0/3/45/46 не занимать рабочими функциями.
- Встроенная Quad SPI flash занимает выделенные SPI-пины, но не GPIO33…37; GPIO10/11 подходят как предварительные deep-sleep wake pins.

Предварительный pin map:

| GPIO | Функция |
|---:|---|
| 1 | MIC_ADC |
| 2 | BAT_TS_ADC |
| 4 | PCB_NTC_ADC |
| 5 | PCB_NTC_EXCITE |
| 8/9 | I²C |
| 10 | IMU wake |
| 11 | rear button wake |
| 12 | fuel-gauge alert |
| 13/14/15/16 | LED clock/data/latch/OE |
| 17/18/21/33 | row address A0…A3 |
| 34 | DEC_A_EN_N |
| 35 | DEC_B_EN_N |
| 36 | LED_EN |
| 37 | AUDIO_EN |
| 38…41 | charger control/status/ship |
| 42 | LED_LOGIC_EN |
| 43/44 | service UART |
| 47 | ROW_XLAT_OE_N |
| 48 | LED_SDO_RETURN |

Физические QFN56 pins и GPIO-функции проверены в
`hardware/common/MCU_PIN_AUDIT.md`. Reset glitches, ADC-конфликты и ограничения
выбранного ESP-IDF peripheral routing остаются EVT/firmware-проверками.

### RGB-матрица

- LED: MHPA1010RGBDT, common-anode, 1×1×0,6 мм.
- Предварительный LCSC: C404280.
- Проверенный pin map: 1 — common anode, 2 — red cathode, 3 — green cathode, 4 — blue cathode.
- Локальный KiCad footprint: `hardware/libraries/leds.pretty/MHPA1010RGBDT.kicad_mod`, pads 0,43×0,43 мм по datasheet Rev.2 page 2.
- Драйверы: MBI5124GP-B, 16 constant-current sink channels.
- 20×20: 6 драйверов, 96 передаваемых бит на строку.
- 28×28: 6 драйверов, 96 передаваемых бит на строку.
- По два драйвера выделены каждому цвету; смешивать R/G/B на одном IC нельзя без неподтверждённого компромисса, поскольку один configuration register задаёт pre-charge для всех 16 выходов.
- Configuration words: red `0x7D6B`, green `0xF16B`, blue `0xED6B`.
- Rext: 1,96 кОм ±0,1% задаёт около 9,41 мА/канал при VDD 3,3 В; совместный worst case ошибок между IC/каналами составляет около 9,95 мА.
- Rext, реальный ток и цветовой баланс обязательно измерить на EVT.
- Драйверы питаются от отключаемой LED_LOGIC_3V3.

Строки:

- common-anode строки коммутируются `AO3403`, source к LED_4V1, drain к анодной строке;
- затвор: 33 Ом последовательно и 47 кОм gate-to-source;
- два `74HC154PW,118` питаются от LED_4V1;
- `SN74LVC8T245RHLR` переводит A0…A3 и два bank-enable с 3,3 В на LED_4V1;
- translator имеет `Ioff`, VCC isolation и аппаратный `/OE` pull-up;
- `SN74LV125APWR` изолирует LED clock/data/latch/OE от выключенного LED_LOGIC_3V3;
- `SN74LVC1G125DBVR` возвращает SDO последнего MBI5124 на `GPIO48`, имеет `Ioff`, постоянно разрешён и дополнен 100 кОм pull-down на стороне MCU;
- отдельные DEC_A_EN_N и DEC_B_EN_N исключают включение двух банков.

Безопасная последовательность строки:

1. Передать следующие 96 бит при текущей активной строке и `MBI_LE = 0`.
2. `MBI_OE = 1`.
3. `DEC_A_EN_N = 1` и `DEC_B_EN_N = 1`.
4. Выдержать измеренный break-before-make dead time.
5. Изменить адрес.
6. Выполнить latch уже переданных данных.
7. Включить только нужный дешифратор.
8. `MBI_OE = 0`.

Точные connections, default pulls и power sequencing зафиксированы в `hardware/common/PCB_ARCHITECTURE.md`; поведение на медленных фронтах питания проверить на EVT.

KiCad 10 driver sheets:

- `hardware/wearable_20x20/led_drivers.kicad_sch`;
- `hardware/wearable_28x28/led_drivers.kicad_sch`;
- воспроизводятся `hardware/tools/generate_led_driver_schematics.py`;
- используют pin-verified `PartSignal_Wearable:MBI5124GP-B`;
- содержат шесть драйверов, `R-EXT`, decoupling, полный SDO-chain и
  `SN74LVC1G125DBVR`;
- явный non-BOM ERC harness моделирует внешние MCU/power/matrix connections до
  появления top-level hierarchy;
- обе версии проходят KiCad 10 ERC с `0 violations`.

KiCad 10 matrix sheets:

- `hardware/wearable_20x20/led_matrix.kicad_sch` содержит 400 LED;
- `hardware/wearable_28x28/led_matrix.kicad_sch` содержит 784 LED;
- воспроизводятся `hardware/tools/generate_led_matrix_schematics.py`;
- references `D1…D400/784` совпадают с PCB и назначаются row-major;
- pin 1 каждого LED подключён к `ROW_nn_ANODE`, pins 2/3/4 — к
  `COL_R/G/B_nn`;
- оба листа проходят KiCad 10 ERC с `0 violations`; XML netlist подтверждает
  80/112 уникальных row и color-column nets.

KiCad 10 row-selection sheets:

- `hardware/wearable_20x20/row_selection.kicad_sch`;
- `hardware/wearable_28x28/row_selection.kicad_sch`;
- воспроизводятся `hardware/tools/generate_row_selection_schematics.py`;
- содержат `SN74LVC8T245RHLR`, два `74HC154PW,118`, 20/28 `AO3403`,
  gate-series 33 Ом, gate pull-up 47 кОм, B-side defaults и decoupling;
- неиспользуемые translator inputs заземлены через 0 Ом, соответствующие
  outputs и неиспользуемые decoder outputs явно отмечены NC;
- оба листа проходят ERC с `0 violations`; XML netlist подтверждает точное
  соответствие decoder outputs строкам и 14/6 NC pins;
- footprint `SN74LVC8T245RHLR` назначен на проверенный TI `RHL0024A`
  land pattern из локальной библиотеки.

Обновление production-readiness:

- точный footprint `SN74LVC8T245RHLR` выпущен в
  `hardware/libraries/packages.pretty` по TI `RHL0024A`, drawing 4225250
  Rev. C; generic QFN не используется;
- primary-drawing footprints выпущены для `BQ25185` (TI DLH0010A),
  `TPS63802` (TI DLA0010A HotRod), `BMI270` (Bosch LGA-14) и
  `MAX17048G+T10` (Maxim 21-0168/90-0065);
- manufacturer-pattern footprints также выпущены для Murata
  `DFE201612E-R47M=P2` и Lucki `L327S400H11L`; у кварца pins 2/4 корпуса
  явно подключены к GND отдельным 4-pin symbol;
- геометрия DLA0010A, DFE201612E и SMD3225-4P проверяется
  `hardware/tools/verify_critical_footprints.py`;
- единый реестр механических входных данных и внешних блокеров находится в
  `mechanical/MECHANICAL_INPUTS.md`;
- построчный статус freeze находится в
  `manufacturing/BOM_FREEZE_STATUS.csv`;
- USB-C `C52209107` подтверждён только как EVT-кандидат; footprint и положение
  остаются заблокированы до утверждения разреза корпуса.
- `hardware/tools/export_manufacturing_package.py` формирует immutable
  Gerber/drill/BOM/CPL/PDF/IPC/STEP package с SHA-256, но отказывает в экспорте,
  пока `check_release_readiness.py` видит хотя бы один незакрытый gate.

### Расчёт обновления

- Baseline SPI 20 МГц с DMA; 24 МГц разрешать только после timing/SI-проверки, так как предел MBI5124 равен 25 МГц.
- Физическая глубина: 6 бит/канал.
- Визуальные 8 бит: temporal dithering.
- Обновление анимации: 60 FPS.
- Расчётный refresh:
  - 20×20: около 175 Гц;
  - 28×28: около 115 Гц.
- Bit-angle modulation необходимо распределять во времени, чтобы длинный MSB-период не создавал артефакты движения.

### Максимальный LED-ток

При 9,41 мА на цвет и одной активной строке:

| Версия | Ток LED_4V1 | Мощность LED_4V1 |
|---|---:|---:|
| 20×20 | 565 мА | 2,32 Вт |
| 28×28 | 791 мА | 3,24 Вт |

Полный белый должен ограничиваться прошивкой. Для носимого непрерывного режима ориентироваться на суммарную мощность около 1–1,2 Вт и дополнительно ограничивать её по температуре и аккумулятору.

## 3. Питание

### Charger и power path

- BQ25185, предварительный LCSC C19725033.
- Аккумулятор Li-Po 1S, 4,2 В.
- USB input limit:
  - 24 кОм: 100 мА;
  - параллельные 72 кОм дают около 18 кОм: 500 мА.
- После изменения ILIM/VSET переключить CE в enable при TS/MR не LOW; ключ 72 кОм по умолчанию выключен.
- Charge current:
  - 20×20: 300 мА, предварительно RISET 1 кОм;
  - 28×28: 400 мА, предварительно RISET 750 Ом.
- До USB enumeration — 100 мА; после успешной конфигурации — до 500 мА.
- При высокой LED-нагрузке заряд уменьшать или приостанавливать.

### Power tree

| Rail | Источник | Нагрузки |
|---|---|---|
| VBUS_USB | USB-C 5 В | BQ25185 |
| BAT_RAW | protected Li-Po 1S | BQ25185, MAX17048 |
| SYS | BQ25185 power path | LDO, LED DC/DC |
| AON_3V3 | TPS7A2033 | ESP32-S3, BMI270, MAX17048 |
| LED_4V1 | TPS63802 | LED-аноды, row decoders |
| LED_LOGIC_3V3 | TPS22917DBVR | MBI5124, SN74LV125A, SN74LVC1G125 |
| AUDIO_3V3 | TPS22917DBVR | microphone, TLV9001 |

TPS63802:

- выход 4,1 В;
- дроссель Murata DFE201612E-R47M=P2, 0,47 мкГн, Isat 5,5 А, высота 1,2 мм;
- предварительно 10 мкФ на входе и 2×22 мкФ на выходе;
- divider 720/100 кОм или 655/91 кОм для nominal 4,10 В;
- после DC-bias эффективная ёмкость должна быть не менее 4 мкФ на входе и 7 мкФ на выходе.

Power sequencing:

- LED_EN и AUDIO_EN имеют аппаратные pull-down;
- включение: LED logic power → безопасные GPIO/OE → LED_4V1 → scan;
- выключение: OE high → строки off → LED_4V1 off → LED logic off;
- USB-устройство не подаёт питание обратно на VBUS.

### Battery gauge и температуры

- MAX17048G+T10, предварительный LCSC C2682616.
- I²C общий с BMI270.
- Battery NTC: 10 кОм B3435.
- Hardware charge window ориентировочно 0…60 °C.
- MCU разрешает заряд ориентировочно только 0…45 °C.
- Отдельный PCB NTC, divider включается GPIO только во время измерения.
- Снижение яркости около 40 °C PCB.
- Жёсткое ограничение около 43 °C.
- LED off около 48 °C.
- Пороги откалибровать по фактической температуре корпуса.
- При BAT около 3,3 В под нагрузкой резко снижать яркость.
- При 3,15–3,2 В выключать LED rail и переходить в сон.

### Deep sleep

- ESP32-S3 ориентировочно 7 мкА.
- BMI270 wake-on-motion, accel-only около 10 мкА.
- MAX17048 около 3 мкА hibernate / 23 мкА active.
- Целевой ток всего устройства: 30–40 мкА; подтвердить измерением.

## 4. IMU и ввод

- BMI270, предварительный LCSC C2836813.
- В активном режиме: accelerometer + gyro.
- В sleep: accelerometer-only low-power около 50 Гц, gyro off.
- Wake interrupt идёт на RTC-capable GPIO.
- Задняя кнопка подключена только к MCU и используется для wake/navigation.
- Кнопку не связывать напрямую с TS/MR charger.
- Factory/ship mode выполняется отдельной сервисной USB-командой.

IMU не заменяет микрофон: accelerometer улавливает только механические вибрации, gyro практически бесполезен для музыкального спектра.

## 5. Микрофон

- Кандидат: MA-HFA381-H13-1AF, top-port analog MEMS.
- Предварительный LCSC C50275762.
- Запас компонента ранее был ограничен; для серии нужен approved alternate.
- Устанавливается сзади напротив акустического отверстия.
- Нужны мягкая герметизирующая прокладка и acoustic mesh.

AFE:

- op amp TLV9001IDCKR;
- mic supply через 100 Ом, локально 1 мкФ + 100 нФ;
- AC coupling 1 мкФ;
- bias 1,65 В: 47/47 кОм + 100 нФ;
- non-inverting gain около ×21: 10 кОм и 200 кОм;
- 100 пФ параллельно 200 кОм;
- ADC anti-alias: 1 кОм + 22 нФ, fc около 7,2 кГц;
- ADC 15,36 кГц, DMA, блоки 256 samples;
- после AUDIO_EN ждать около 20 мс.

Предварительные полосы:

- 60–250 Гц;
- 250–2000 Гц;
- 2–7 кГц.

## 6. USB и персонализация

- USB-C UFP/sink.
- 5,1 кОм на CC1 и CC2.
- ESD: USBLC6-2SC6, предварительный LCSC C7519.
- Native USB ESP32-S3.
- Android Chrome/desktop Chromium: WebUSB.
- iPhone Safari не поддерживает WebUSB/WebSerial.
- Потенциальный fallback для iPhone: USB Mass Storage через Files; обязательно проверить на реальном iPhone.

Composite USB:

- vendor WebUSB;
- MSC service mode;
- recovery/update.

Нельзя одновременно отдавать по MSC файловую систему, которую использует firmware. В service mode renderer прекращает чтение ресурсов, раздел размонтируется и только после этого отдаётся host. После disconnect/eject данные проверяются и раздел монтируется заново.

Протокол ресурсов:

- manifest;
- chunks 4–16 КБ;
- длина;
- CRC32;
- staging;
- atomic activation.

NFC исключён: медленнее, дороже и конфликтует с безрамочной матрицей.

## 7. Память и анимации

- 8 МБ Flash делится между двумя firmware slots, служебными разделами и примерно 4 МБ ресурсов.
- Точный partition table определить после сборки firmware.
- 28×28 RGB framebuffer: 2352 байта; double buffer около 4,7 КБ.
- SRAM достаточно для рендера, USB, IMU и audio.

Несжатые данные при 60 FPS:

- 20×20 RGB: около 72 КБ/с;
- 28×28 RGB: около 141 КБ/с.

Основные эффекты должны быть процедурными. Загружаемые анимации: indexed palette, RLE/delta compression и обычно 20–30 FPS.

Firmware tasks:

1. led_scan — DMA/BAM, highest priority.
2. renderer — 60 FPS.
3. imu — 100–200 Гц active.
4. audio — ADC DMA 15,36 кГц.
5. power_manager.
6. usb_service.
7. storage.

## 8. PCB и размещение

### Stackup

- 4 слоя, 1,0 мм, ENIG, чёрная solder mask.
- L1: LED и вертикальные RGB columns.
- L2: непрерывный solid GND.
- L3: горизонтальные row anodes и power.
- L4: MCU, drivers, power, sensors и signals.
- Без microvia, blind/buried via и via-in-pad.

Предварительные правила:

- минимальный local matrix trace/space: 0,10/0,10 мм;
- предпочтительный trace/space вне matrix escape: 0,127/0,127 мм;
- RGB columns: 0,10–0,15 мм;
- inner row buses: до 1,20 мм;
- стандартный signal via: 0,45/0,20 мм;
- локальный RGB transition via только в проверенной matrix-ячейке: 0,40/0,20 мм;
- copper-to-edge: 0,30 мм;
- black solder-mask web: не меньше 0,15 мм;
- silkscreen: не меньше 1,0 мм height / 0,15 мм stroke;
- LED_4V1: polygon;
- стандартные сквозные vias;
- differential USB pair по фактическому stackup производителя;
- crystal keepout и отсутствие сигналов под crystal;
- DC/DC feedback вести Kelvin route вдали от SW node.

KiCad 10 рабочие PCB:

- `hardware/wearable_20x20/wearable_20x20.kicad_pcb`;
- `hardware/wearable_28x28/wearable_28x28.kicad_pcb`;
- исходный каркас воспроизводится `hardware/tools/generate_board_skeletons.py`,
  а доказанная трассировка переносится
  `hardware/tools/promote_matrix_routing.py`;
- содержат 400/784 электрических LED footprints, row/RGB-column nets, четыре copper layers, optical centers и provisional battery envelope;
- содержат DRC-ограничения JLCPCB Standard PCBA из `manufacturing/JLCPCB_STANDARD_PCBA_RULES.md`;
- полная матрица имеет 0 DRC violations и 0 unconnected matrix pads; это не
  доказывает connectivity всего продукта до добавления backside components;
- copper-to-edge rule — 0,30 мм, поэтому исходные preliminary outlines увеличены на 0,1 мм;
- `B.SilkS`: `PCB CREATED BY ILLIA PLIUKHIN` и маленькая пятиконечная звезда;
- LED references находятся на `F.Fab`; все остальные компоненты должны иметь физические reference designators не меньше 1,0/0,15 мм без перекрытий.

Текущие outline 49,3 × 49,3 мм и 61,2 × 61,2 мм ещё не заморожены для производства, но увеличивать их сейчас не требуется. Все 18 локальных corner/orientation probes прошли KiCad 10.0.6 DRC без геометрических нарушений для шага 2,50 и 2,20 мм. Проверенная карта 0°/90°/180°/270° размножена на полные массивы: обе сгенерированные платы имеют `0 DRC violations` и `0 unconnected items`. Семантическая проверка подтверждает 400/784 LED, 1 564/3 084 стандартных through vias, правильные ориентации, все row nets на физическом L3 (`In2.Cu`) и 0 tracks на L2 (`In1.Cu`). Midpoint cells используют L1/L3/L4 crossover-коридоры и локальные row buses 0,40 мм. Отдельный 20×20 L2 probe после antipads сохраняет один сплошной fill outline и 81,0% nominal zone area, но остаётся электрически изолированным до появления backside GND pads и поэтому не перенесён в working PCB. Генераторы, платы, DRC reports и расчёты находятся в `hardware/analysis/MATRIX_ROUTING_FEASIBILITY.md`. До freeze необходимо добавить production L2 GND zone после placement, проверить локальные return paths/neck widths и провести row/RGB exits к драйверам без нарушения доказанных коридоров.

### Placement

- Все LED на лицевой стороне.
- Вся остальная электроника и test pads сзади.
- USB-C по центру боковой грани.
- Battery расположен в component-free keepout.
- Нельзя размещать DC/DC и LED drivers под аккумулятором.
- IMU в жёсткой зоне, вдали от дросселя и края с USB.
- Microphone вдали от DC/DC и с прямым акустическим каналом.
- Для factory test: pogo pads GND, 3V3, CHIP_PU, GPIO0, UART TX/RX.
- Дополнительные test points: VBUS, BAT, SYS, LED_4V1, I²C и LED control.

Плата неизбежно двухсторонней сборки. LED допускает не более двух reflow; порядок сборки и фактический профиль должен подтвердить PCBA-поставщик.

## 9. Аккумуляторы и габариты

Ориентиры:

- 20×20: 700–800 мА·ч, около 32×40×6 мм;
- 28×28: 1200–1400 мА·ч, около 40×50×6 мм.

Требования:

- protected Li-Po с PCM и NTC;
- трёхконтактный низкопрофильный разъём BAT+, NTC, GND;
- батарея полностью внутри PCB outline;
- точные размеры и положение фиксировать только по чертежу конкретного поставщика.

Оценка автономности:

| Режим | 20×20, 800 мА·ч | 28×28, 1400 мА·ч |
|---|---:|---:|
| Максимальная LED-нагрузка | около 0,9 ч | около 1,3 ч |
| Типичная мощность около 1 Вт | около 3 ч | около 5 ч |

USB 5 В/500 мА даёт только 2,5 Вт, поэтому одновременно заряжать и работать на максимальной яркости нельзя.

## 10. Корпус и оптика

Предварительный stack:

- smoked front PC: 0,6–0,8 мм;
- black pixel grid: 1,0–1,5 мм;
- LED: 0,6 мм;
- PCB: 1,0 мм;
- battery: около 6 мм;
- back cover/attachment: 1–1,5 мм.

Реалистичная общая толщина: около 10,5–12 мм.

Pixel grid:

- 20×20: aperture около 2,1 мм, wall около 0,4 мм;
- 28×28: aperture около 1,8 мм, wall около 0,4 мм;
- крайние ячейки продолжаются до визуального края без внешнего bezel.

EVT optical samples:

- transmission 30%, 40%, 50%;
- LED-to-diffuser distance 0,8 / 1,2 / 1,6 мм.

Прототип:

- SLA black grid;
- laser/CNC front panel;
- printed rear enclosure.

Lanyard loop выполняется корпусом, не PCB. IP-рейтинг для MVP не заявлять без отдельных испытаний.

## 11. Производство

- Основной кандидат: JLCPCB Standard PCBA.
- Economic PCBA исключён: он поддерживает только одностороннюю установку и не обеспечивает требуемое сочетание 1,0 мм, чёрной маски и ENIG для этой двухсторонней платы.
- Панель Standard PCBA: не меньше 70 × 70 мм, rails не меньше 5 мм, глобальные fiducials на обеих assembly sides.
- Крайние LED требуют письменного подтверждения engineering review поставщика и защищённых routed rails при сборке/депанелизации.
- Перед заказом сравнить актуальную полную стоимость с PCBWay.
- EVT 20×20: 5 PCB, минимум 2 собранные платы.
- После исправлений — EVT 28×28.
- Затем 10–20 MVP units.

Требуемый production package:

- KiCad source;
- Gerber;
- Excellon drill;
- IPC netlist;
- BOM;
- CPL/position files;
- schematic PDF;
- assembly drawings;
- STEP;
- panelization notes;
- programming and factory-test instructions.

## 12. EVT-проверки

- все пиксели и цвета;
- open/short channels;
- ghosting и row transitions;
- яркость и цветовой баланс;
- фронты PMOS gate;
- провалы LED_4V1;
- USB enumeration/WebUSB/MSC/recovery;
- IMU wake и false wake;
- microphone frequency response и LED switching noise;
- charge current, NTC и power path;
- deep-sleep current;
- температура PCB, корпуса и battery;
- автономность;
- 24-часовой тест EVT;
- 72-часовой burn-in DVT.

## 13. Незакрытые обязательные проверки

1. Binning и approved alternate MHPA1010RGBDT.
2. Реальные switching times и voltage drop AO3403 с выбранным дешифратором.
3. Power-ramp/back-power проверка SN74LVC8T245, SN74LV125A, SN74LVC1G125 и TPS22917.
4. TPS63802 output-current/thermal margin в закрытом корпусе.
5. Полный ESP32-S3FN8 pin audit, reset glitches и ADC-конфликты.
6. USB-C connector по механическому разрезу корпуса.
7. Точные аккумуляторы с чертежами, PCM, NTC и UN38.3.
8. MSC compatibility с iPhone.
9. Реальная яркость через выбранный diffuser.
10. DFM двухстороннего PCBA и подтверждение reflow-профиля.
11. Lifecycle, stock и approved alternates критических компонентов.
12. ERC, финальный DRC, SI/PI и независимое schematic/layout review.

## 14. Рекомендуемая структура репозитория

```text
hardware/
  common/
  wearable_20x20/
  wearable_28x28/
  libraries/
mechanical/
firmware/
manufacturing/
test/
docs/
```

Результаты частичного freeze находятся в `DATASHEET_BOM_FREEZE.md`, схемная
архитектура — в `hardware/common/PCB_ARCHITECTURE.md`, расчётные ограничения —
в `hardware/analysis/DESIGN_BUDGETS.md`, а release gates — в
`manufacturing/RELEASE_CHECKLIST.md`. Следующий этап: выбрать заблокированные
внешние MPN и выполнить backside placement/routing и L2 GND; критический
HotRod-footprint `TPS63802` уже выпущен, но его силовой layout и тепловые
измерения остаются обязательными.
