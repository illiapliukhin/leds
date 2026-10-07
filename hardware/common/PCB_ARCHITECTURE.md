# Common PCB architecture

Status: pre-schematic architecture for KiCad 10. Values marked `EVT` require measurement before production release.

## Power domains

| Net | Source | Always on | Loads |
|---|---|---:|---|
| `VBUS_USB` | USB-C | No | BQ25185 input |
| `BAT_RAW` | Protected 1S Li-Po | Yes | BQ25185, MAX17048 |
| `SYS` | BQ25185 power path | Yes | AON LDO, LED buck-boost |
| `AON_3V3` | TPS7A2033 | Yes | ESP32-S3, BMI270, MAX17048, control-side logic |
| `LED_4V1` | TPS63802DLAR | No | LED anodes, row decoders, row translator B-side |
| `LED_LOGIC_3V3` | TPS22917DBVR | No | MBI5124 chain, LED signal buffer |
| `AUDIO_3V3` | TPS22917DBVR | No | Microphone and TLV9001 |

Both TPS22917 enable inputs require external 100 kΩ pull-downs to guarantee default-off independently of MCU state. Populate a configurable QOD resistor footprint on each switched rail. Start EVT with 1 kΩ on `LED_LOGIC_3V3` and DNP on `AUDIO_3V3`.

## Row selection

### Components

- `U_ROW_XLAT`: TI `SN74LVC8T245RHLR`, VQFN-24.
- `U_DEC_A`, `U_DEC_B`: Nexperia `74HC154PW,118`, TSSOP-24.
- `Q_ROW01…Q_ROW28`: AOS `AO3403`, SOT-23.
- Each PMOS gate has 47 kΩ gate-to-source pull-up. Add a 33 Ω series-gate resistor footprint; start EVT at 33 Ω.

### Translator connections

- `VCCA = AON_3V3`.
- `VCCB = LED_4V1`.
- `DIR = AON_3V3`, fixed A-to-B.
- `/OE = ROW_XLAT_OE_N`; pull up with 10 kΩ to `AON_3V3`.
- Channels 1…6 translate `ROW_A0…ROW_A3`, `DEC_A_EN_N`, and `DEC_B_EN_N`.
- Tie unused A-side inputs to GND and leave the corresponding B-side outputs unconnected.
- Pull B-side decoder address inputs down with 100 kΩ.
- Pull each B-side decoder enable up to `LED_4V1` with 47 kΩ.

The translator is required for two independent reasons:

1. ESP32-S3 direct drive does not guarantee `VIH` for 74HC logic at 4.1 V.
2. `Ioff` and VCC isolation prevent back-power when `LED_4V1` is off.

At 4.1 V, interpolating the 74HC requirement gives approximately `VIH ≥ 2.87 V`. ESP32-S3 guarantees only approximately 2.64 V at a 3.3 V supply, giving negative margin. The translated B-side output is referenced to `LED_4V1`.

### Decoder and PMOS connections

- Both decoders share `ROW_A0…ROW_A3`.
- One active-low enable per decoder receives the translated bank enable.
- Tie the second active-low enable of each decoder to GND.
- Decoder active-low outputs drive PMOS gates through 33 Ω.
- PMOS source connects to `LED_4V1`; drain connects to the selected LED common-anode row.
- Only rows 1…20 are populated on the compact variant; rows 21…28 exist only on the high-resolution variant.

At 0.84 A and the conservative 200 mΩ bound, instantaneous drop is 168 mV. Because each PMOS is active for only one row period, thermal dissipation is modest, but the voltage drop and brightness impact must be measured.

## MBI5124 signal isolation

`U_LED_BUF` is TI `SN74LV125APWR`, TSSOP-14, powered by `LED_LOGIC_3V3`.

The four channels buffer:

1. `LED_CLK`
2. `LED_SDI`
3. `LED_LE`
4. `LED_OE_N`

Tie all buffer output-enable inputs LOW. `SN74LV125A` is selected instead of `SN74LVC125A` because the former explicitly specifies `Ioff` partial-power-down behavior.

MCU-side default pulls:

- `LED_CLK`: 100 kΩ pull-down.
- `LED_SDI`: 100 kΩ pull-down.
- `LED_LE`: 100 kΩ pull-down.
- `LED_OE_N`: 47 kΩ pull-up to `AON_3V3`.

Add 22 Ω source-series footprints after the buffer on `LED_CLK`, `LED_SDI`, and `LED_LE`; start EVT populated. Add a 47 kΩ pull-up from the buffered `LED_OE_N` to `LED_LOGIC_3V3`.

## Safe sequencing

### Start

1. Keep `LED_EN = 0`, `LED_LOGIC_EN = 0`, and `ROW_XLAT_OE_N = 1`.
2. Configure row address low, both decoder enables high, `LED_OE_N` high, clock/data/latch low.
3. Set `LED_LOGIC_EN = 1` and wait for the switched 3.3 V rail to settle.
4. Set `LED_EN = 1` and wait for `LED_4V1` power-good or a validated delay.
5. Drive valid row controls, then set `ROW_XLAT_OE_N = 0`.
6. Shift data while blanked, latch, enable one decoder bank, and finally deassert `LED_OE_N`.

### Row transition

1. Assert `LED_OE_N`.
2. Set both decoder enables high.
3. Wait the EVT-derived PMOS turn-off dead time.
4. Change row address.
5. Shift/latch column data.
6. Enable exactly one decoder bank.
7. Deassert `LED_OE_N`.

### Shutdown

1. Assert `LED_OE_N`.
2. Disable both decoder banks.
3. Set `ROW_XLAT_OE_N = 1`.
4. Set `LED_EN = 0`.
5. Set `LED_LOGIC_EN = 0`.

Hardware pull resistors must make this state safe during reset, deep sleep, and incomplete power ramps without firmware.

## LED buck-boost

- `U_LED_PWR`: TI `TPS63802DLAR`.
- `L_LED`: Murata `DFE201612E-R47M=P2`, 0.47 µH, 5.5 A saturation, 4.5 A thermal current, 26 mΩ maximum DCR, 2.0 × 1.6 × 1.2 mm.
- Feedback: 655 kΩ top and 91 kΩ bottom, 0.1%, nominal output approximately 4.099 V.
- Input: 10 µF X5R/X7R with at least 4 µF effective capacitance.
- Output: 2×22 µF X5R/X7R with at least 7 µF total effective capacitance.
- Use Kelvin feedback routing and keep the switch node away from microphone, IMU, crystal, and ADC nets.

## ESP32-S3 pin-map addition

Reserve `GPIO47` as `ROW_XLAT_OE_N`. It is not a deep-sleep wake source. The complete pin map still requires a schematic-level audit before symbol annotation is frozen.

## Board and marking conventions

- Preliminary outlines are 49.3 × 49.3 mm and 61.2 × 61.2 mm. The extra 0.1 mm over the original estimates provides 0.30 mm copper-to-routed-edge clearance at the outer LED pads.
- These outlines are not production-frozen. A dedicated top-edge escape using a 0.40 mm L3 row bus and RGB transitions to L4 passes KiCad DRC at both matrix pitches. Keep the current bezel-free outline while expanding and checking the full matrix, the other three edges, L2 continuity, and driver exits. See `hardware/analysis/MATRIX_ROUTING_FEASIBILITY.md`.
- Fabrication and panel rules are defined in `manufacturing/JLCPCB_STANDARD_PCBA_RULES.md`. Use JLCPCB Standard PCBA, not Economic PCBA, because assembly is two-sided.
- `hardware/libraries/leds.pretty/MHPA1010RGBDT.kicad_mod` comes from manufacturer datasheet Rev.2 page 2.
- LED pin map: pin 1 common anode, pin 2 red cathode, pin 3 green cathode, pin 4 blue cathode.
- Recommended land pattern: four 0.43 × 0.43 mm pads in a 1.20 × 1.20 mm field with 0.34 mm horizontal and vertical gaps.
- Pin 1 uses a rectangular pad; the other pads are rounded rectangles. The orientation marker is on `F.Fab`, not over copper on `F.SilkS`.
- `User.1`: LED optical-center cross marks.
- `Dwgs.User`: provisional battery envelope, not an enforced keepout.
- `Cmts.User`: matrix and pitch note.

All LED references remain visible on `F.Fab` for assembly documentation. Printing hundreds of full LED references on physical silkscreen is prohibited because JLCPCB requires at least 1.0 mm text height and 0.15 mm stroke, which cannot fit reliably at 2.2 mm pitch.

Every non-matrix component must have a readable physical reference designator placed outside pads and courtyards. Use at least 1.0 mm text height, 0.15 mm stroke, and 0.15 mm pad clearance. Move references after final placement instead of hiding them.

The back silkscreen contains `PCB CREATED BY ILLIA PLIUKHIN` and a small five-point star in the lower battery-free strip. This strip is reserved from component placement. If mechanical changes consume the strip, relocate the complete branding group without reducing it below manufacturing limits.
