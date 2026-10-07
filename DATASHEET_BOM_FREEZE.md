# Wearable RGB MVP — datasheet/BOM freeze

Дата проверки: 2026-10-07.

Статус: частичный freeze. Полная generated hierarchy существует, но детали со
статусом `BLOCKED` не имеют разрешённых production footprints и не могут
заказываться для PCBA без закрытия указанной проверки.

## Источники

- ESP32-S3 Hardware Design Guidelines: https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/esp-hardware-design-guidelines-en-master-esp32s3.pdf
- ESP32-S3 GPIO documentation: https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/gpio.html
- ESP32-S3 sleep modes: https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/system/sleep_modes.html
- MBI5124 preliminary datasheet V1.01: https://www.mblock.com.tw/upload/Datasheet/LED%20Driver%20IC/MBI5124/MBI5124%20Preliminary%20Datasheet_V1.01_EN.pdf
- BQ25185 datasheet Rev. B: https://www.ti.com/lit/ds/symlink/bq25185.pdf
- TPS63802 datasheet Rev. D: https://www.ti.com/lit/ds/symlink/tps63802.pdf
- MHPA1010RGBDT datasheet Rev. 2: https://www.lcsc.com/datasheet/C404280.pdf
- SN74LVC8T245 datasheet Rev. D: https://www.ti.com/lit/ds/symlink/sn74lvc8t245.pdf
- SN74LV125A datasheet Rev. O: https://www.ti.com/lit/ds/symlink/sn74lv125a.pdf
- SN74LVC1G125 datasheet Rev. V: https://www.ti.com/lit/ds/symlink/sn74lvc1g125.pdf
- Nexperia 74HC154/HCT154 datasheet: https://assets.nexperia.com/documents/data-sheet/74HC_HCT154.pdf
- AO3403 datasheet: https://www.aosmd.com/res/datasheets/AO3403.pdf
- TPS22917 datasheet Rev. B: https://www.ti.com/lit/ds/symlink/tps22917.pdf

## Подтверждённые решения

### ESP32-S3FN8 — CONDITIONAL

- Встроенная память — 8 МБ Quad SPI flash. Она занимает `SPICLK`, `SPICS0`, `SPID`, `SPIQ`, `SPIWP` и `SPIHD`.
- `GPIO33…37` требуются встроенной памяти только для octal-вариантов; у `ESP32-S3FN8` они доступны, но находятся не в RTC power domain и не подходят для deep-sleep wake.
- `GPIO10` и `GPIO11` находятся в `VDD3P3_RTC`; предварительное назначение IMU/button wake допустимо.
- Native USB использует `GPIO19` как D− и `GPIO20` как D+. Espressif рекомендует зарезервировать последовательные 22/33 Ом рядом с MCU.
- Подтверждены обязательный кварц 40 МГц с точностью ±10 ppm и стартовое значение 24 нГн последовательно с `XTAL_P`.
- Для `L327S400H11L` выпущены отдельные 4-pin symbol и footprint по
  manufacturer drawing: pins 1/3 — `XTAL_P/XTAL_N`, pins 2/4 — GND,
  lands 1,40×1,20 мм с зазорами 0,80×0,50 мм. Прежний двухвыводный символ
  был электрически несовместим с корпусом SMD3225-4P и удалён из генератора.
- Подтверждена стартовая цепь `CHIP_PU`: 10 кОм и 1 мкФ. Для медленного или нестабильного питания необходимо оставить возможность установить supervisor.
- Остаются открытыми полный pin audit, power-up glitches, ADC-конфликты и проверка routing в выбранной версии ESP-IDF.

### MHPA1010RGBDT — CONDITIONAL

- Подтверждены common-anode, корпус 1,0×1,0 мм, top-view и black diffused lens.
- По manufacturer datasheet Rev.2 page 2 подтверждено: pin 1 common anode, pin 2 red cathode, pin 3 green cathode, pin 4 blue cathode.
- Manufacturer land pattern: четыре pad 0,43×0,43 мм в поле 1,20×1,20 мм с зазором 0,34 мм. Создан и проверен KiCad footprint `hardware/libraries/leds.pretty/MHPA1010RGBDT.kicad_mod`.
- Профиль допускает 260 °C до 10 секунд и не более двух reflow.
- Двухсторонняя сборка допустима только при документированном порядке сборки и подтверждении реального профиля PCBA-поставщиком.
- Остаются открытыми binning, доступность и approved alternate.

### MBI5124GP-B — CONDITIONAL

- При 3,3 В допустимый диапазон заданного тока — 1…10 мА на канал.
- Формула: `IOUT = 1.23 V / Rext × 15`. Стартовый `Rext` — 1,96 кОм ±0,1%, что задаёт около 9,41 мА. Совместный worst case с ошибками +3% между IC и +2,5% между каналами составляет около 9,95 мА.
- Один 16-битный configuration register управляет pre-charge всего IC. Datasheet задаёт разные полные слова для красного (`0x7D6B`), зелёного (`0xF16B`) и синего (`0xED6B`), поэтому подтверждённая архитектура использует шесть цвето-однородных драйверов в обеих версиях.
- Ordering table подтверждает `MBI5124GP-B` как SSOP24L-150-0.64; LCSC `C256866` использует тот же ordering code.
- Максимальная частота CLK — 25 МГц. Рабочие 24 МГц оставляют только 4% запаса, поэтому baseline снижен до 20 МГц; 24 МГц разрешены только после SI/timing-проверки на EVT.
- При VDD = 3,3 В минимальный `VIH` равен 0,7×VDD, а минимальный CLK high/low pulse — 20 нс.
- Постоянный режим тока характеризуется при `VDS = 1,0 В`; datasheet рекомендует держать `VDS` примерно 0,4…0,8 В с учётом рассеиваемой мощности. Необходимо проверить worst-case `LED_4V1 − VF` отдельно для R/G/B и температуру корпуса.
- Остаются открытыми lifecycle/alternate, полный thermal calculation и фактический ток/цветовой баланс.

### BQ25185 — CONDITIONAL

- `RILIM/VSET = 24 кОм` задаёт 4,2 В и лимит входа 100 мА.
- `RILIM/VSET = 18 кОм` задаёт 4,2 В и лимит входа 500 мА. Параллельное подключение 72 кОм к базовым 24 кОм даёт ровно 18 кОм.
- После изменения `RILIM/VSET` необходимо переключить `CE` в enable; во время определения `TS/MR` не должен быть LOW.
- `RISET = 1 кОм` задаёт около 300 мА; `RISET = 750 Ом` — около 400 мА. Изменение `RISET` во время заряда влияет на ток немедленно.
- Управляющий ключ 72 кОм должен по умолчанию быть выключен, чтобы до USB enumeration аппаратный лимит оставался 100 мА.
- Остаются открытыми точная схема TS/NTC, MOSFET для переключения лимита, thermal calculation при одновременной нагрузке и charge throttling policy.

### TPS63802 — CONDITIONAL

- Подтверждены 0,47 мкГн, 10 мкФ на входе и 2×22 мкФ nominal на выходе при 4,1 В.
- После допуска и DC-bias эффективная входная ёмкость должна быть не менее 4 мкФ, выходная — не менее 7 мкФ.
- `VFB` nominal равен 0,5 В, нижний резистор divider не должен превышать 100 кОм.
- Для 4,1 В выбран divider 655/91 кОм, 0,1%, nominal около 4,099 В.
- Предварительно выбран Murata `DFE201612E-R47M=P2`: 0,47 мкГн, Isat 5,5 А, thermal current 4,5 А, DCR до 26 мОм, высота 1,2 мм.
- Локальный footprint `Murata_DFE201612E_2.0x1.6mm` воспроизводит
  manufacturer recommended pattern: два lands 0,55×1,60 мм, межпадовый
  зазор 0,90 мм и общий span 2,00 мм.
- `TPS63802DLAR` назначен на локальный
  `PartSignal_Packages:TI_DLA0010A_VSON-HR-10_2x3mm_P0.5mm`, созданный
  по TI 4223750 Rev. D. Footprint сохраняет асимметричную HotRod-геометрию:
  пять lands 0,60×0,25 мм, четыре lands 0,90×0,25 мм и pad 8
  1,30×0,25 мм с двумя stencil apertures и покрытием paste около 83,8%.
- Остаются открытыми проверка точного ordering code/stock, output-current margin при минимальном BAT, enclosure thermal test и load-transient measurement.

### Row selection и domain isolation — CONDITIONAL

- Прямое управление 74HC154 от ESP32-S3 запрещено: при LED_4V1 = 4,1 В требуемый `VIH` около 2,87 В, а гарантированный MCU `VOH` около 2,64 В.
- Выбран `SN74LVC8T245RHLR`: VCCA = 3,3 В, VCCB = LED_4V1, `Ioff`, VCC isolation и аппаратный `/OE` pull-up.
- Для `SN74LVC8T245RHLR` создан точный footprint TI `RHL0024A` по
  package drawing 4225250 Rev. C: VQFN-24 3,5×5,5 мм, pitch 0,5 мм,
  signal lands 0,60×0,24 мм и exposed pad 2,05×4,05 мм. Exposed pad
  электрически объединён с GND pin 11; paste разбита на четыре окна с
  покрытием около 78%.
- Выбраны два Nexperia `74HC154PW,118` в TSSOP-24 и `AO3403` для каждой строки.
- `AO3403` имеет Qg около 2,8 нКл typical и RDS(on) до 200 мОм при VGS = −2,5 В. Voltage drop и switching dead time остаются EVT-параметрами.
- Для изоляции MBI5124 выбран `SN74LV125APWR`, который явно специфицирует `Ioff`; похожий `SN74LVC125A` отклонён из-за отсутствия явной partial-power-down гарантии.
- Для обязательного configuration readback выбран отдельный `SN74LVC1G125DBVR`: вход от SDO последнего MBI5124, выход `LED_SDO_RETURN` на `GPIO48`, `/OE` на GND и 100 кОм pull-down на стороне MCU. Его `Ioff` гарантирует изоляцию при выключенном `LED_LOGIC_3V3`.
- Для обоих отключаемых 3,3-вольтовых доменов выбран `TPS22917DBVR`; нужны внешние enable pull-down и configurable QOD.
- Полная topology, pulls и sequencing зафиксированы в `hardware/common/PCB_ARCHITECTURE.md`.

### BMI270, MAX17048 и package release — CONDITIONAL

- `BMI270` назначен на KiCad
  `Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm`, соответствующий Bosch
  14-pin LGA 3,0×2,5 мм и datasheet landing pattern.
- `MAX17048G+T10` назначен на
  `Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm`,
  соответствующий Maxim package outline 21-0168 и land pattern 90-0065.
  Exposed pad добавлен в symbol как GND pin 9.
- `BQ25185DLHR` назначен на
  `Package_DFN_QFN:Texas_DLH0010A_WSON-10-1EP_2.2x2mm_P0.4mm_EP0.9x1.5mm`.
  Exposed pad добавлен в symbol как GND pin 11.
- Эти package releases, включая `TPS63802DLAR`, закрывают геометрию, но не
  заменяют low-power/wake,
  fuel-gauge runtime, TS/NTC, charger thermal и power-ramp EVT.

### Расчётная модель — CONDITIONAL

- `hardware/tools/model_power_scan.py` воспроизводимо генерирует `hardware/analysis/POWER_SCAN_MODEL.md` и CSV.
- При full-white модель даёт 2,47 Вт и 0,87 А от батареи 3,15 В для 20×20; 3,46 Вт и 1,22 А для 28×28 при 90% efficiency.
- Для continuous LED rail limit 1 Вт стартовые global brightness caps составляют около 40% и 29% соответственно.
- При SPI 20 МГц и 1,5 мкс break-before-make расчётный LSB hold остаётся положительным: 4,09 мкс и 4,33 мкс.
- Это screening model, не замена SPICE, SI/PI, enclosure thermal и EVT-измерениям.

## Блокирующие вопросы до production layout

1. Выбрать точный USB-C и завершить механический cross-section.
2. Завершить reset-glitch/ESP-IDF audit ESP32-S3FN8; физические QFN56 pins и
   GPIO назначения проверены в `hardware/common/MCU_PIN_AUDIT.md`.
3. Проверить оставшиеся критические компоненты: BMI270, MAX17048, TPS7A2033, microphone, TLV9001 и USB ESD.
4. Получить актуальные stock/lifecycle данные и compatible alternate минимум для LED, драйвера, microphone и DC/DC.

## Gate для начала KiCad

KiCad PCB и общую схему можно продолжать. Электрические LED footprints
проверены по первичному datasheet. Сгенерированные driver projects для обеих
матриц используют проверенный pinout MBI5124, явные NC на неиспользуемых
outputs и изолированный SDO return; оба проходят KiCad 10 ERC без нарушений.
Полные matrix projects содержат 400/784 LED с тем же проверенным pin map и
footprint; оба также проходят ERC без нарушений, а XML netlist подтверждает все
row и RGB-column connections.
Row-selection projects содержат translator, два decoder banks и 20/28 PMOS;
оба проходят ERC без нарушений, а XML netlist подтверждает каждую цепь
decoder-output/gate/row и явные NC. Точный TI RHL-24 footprint translator
назначен и проверяется из локальной библиотеки
`hardware/libraries/packages.pretty`.
Обе harness-free top-level hierarchy содержат power, MCU/USB, IMU/gauge/input,
audio, LED drivers, row selection и полную matrix; standalone harness sheets
сохранены только для автономного ERC. USB connector, battery/NTC/button,
microphone и несколько package land patterns остаются намеренно заблокированы,
поэтому hierarchy не является разрешением на PCBA-заказ.
