# Mono split-board architecture

Status: first healthy layout of a black-and-white wearable pair. RGB boards under `hardware/wearable_20x20` and `hardware/wearable_28x28` are unchanged. Values marked `EVT` require measurement before production.

The same electronics board drives both LED panels. Two `MBI5124GP-B` devices provide 32 cathode sinks and two `74HC154` devices provide 32 anode rows, so the high-resolution panel is 32×32 rather than 28×28. The 20×20 panel uses contacts 1…20 of the same 40-pin pinout and leaves 21…40 unrouted on the panel.

## Board set

| Board | Layers | Outline | Contents |
|---|---|---|---|
| `mono_panel_20x20` | 2 | 136.3 × 136.3 mm | 400 × `NCD0603W1` on `F.Cu`; two FFC receptacles on `B.Cu` |
| `mono_panel_32x32` | 2 | 166.7 × 166.7 mm | 1024 × `NCD0603W1` on `F.Cu`; two FFC receptacles on `B.Cu` |
| `mono_electronics` | 4 | 190 × 148 mm | MCU, power, IMU, audio, row farm, column drivers, matching FFC plugs |

Outlines are spacious first-pass envelopes, not frozen mechanics. The 44 mm panel margin is required so a 32-net U-turn fan-in can keep three bands from overlapping: the `J_ROW` courtyard, a 0.55 mm via row, and unique 0.28 mm front channels. Matching back-copper L-routes then drop from that via row to the 0.50 mm FFC pads. Shrinking this margin is a later step.

## Passive LED panel

The panel has no local ground and no active parts. Each row current leaves through `J_ROW` as `ROW_nn_ANODE` and returns through `J_COL` as `COL_nn` into an `MBI5124` sink.

Front copper carries only LED pads, anode-row buses, cathode stubs, and row fan-in. Rear copper carries column trunks, column fan-in, and the two FFC footprints. Front silkscreen stays empty except for fabrication notes on `F.Fab` / `Cmts.User`.

## FFC pinout

Both panels and the electronics board use the same two Hirose `FH12-40S-0.5SH` 0.50 mm 40-circuit bottom-contact receptacles. Each contact is specified at 0.5 A. One 32×32 row at 10 mA/pixel is 0.32 A, so a single contact per row is the starting assignment. Spare contacts 33…40 may later be paralleled onto the outer rows if a longer cable drops too much voltage.

### `J_ROW`

| Pin | Net | 20×20 panel | 32×32 panel | Electronics |
|---:|---|---|---|---|
| 1…20 | `ROW_01_ANODE` … `ROW_20_ANODE` | Routed | Routed | `Q_ROW01…20` drains |
| 21…32 | `ROW_21_ANODE` … `ROW_32_ANODE` | Unrouted | Routed | `Q_ROW21…32` drains |
| 33…40 | `ROW_SPARE_33` … `ROW_SPARE_40` | Unrouted | Unrouted | Reserved |

### `J_COL`

| Pin | Net | 20×20 panel | 32×32 panel | Electronics |
|---:|---|---|---|---|
| 1…20 | `COL_01` … `COL_20` | Routed | Routed | `U_LED1` OUT0…15, `U_LED2` OUT0…3 |
| 21…32 | `COL_21` … `COL_32` | Unrouted | Routed | `U_LED2` OUT4…15 |
| 33…40 | `COL_SPARE_33` … `COL_SPARE_40` | Unrouted | Unrouted | Reserved |

Pin 1 of each receptacle is the top-most pad after the panel-side rotation (cable exits off the board). The electronics board uses the same pad numbers on the same nets.

## LED

- Part: NationStar `NCD0603W1`, LCSC `C84265`.
- Body: 1.6 × 0.8 mm, top view, 130° typical.
- Pin 1 cathode (`K`), pin 2 anode (`A`), from datasheet polarity drawing.
- Absolute max continuous current: 20 mA. Pulse 50 mA at ≤0.1 ms and ≤1/10 duty.
- `VF`: 2.5 / 2.8 / 3.6 V at 5 mA.
- Recommended copper pads: two 0.75 × 0.8 mm pads, 0.8 mm inner gap, 2.3 mm overall, from datasheet recommended soldering pad.
- Peak channel current remains the MBI5124 1.82 kΩ setting, about 10.05 mA.
- Footprint courtyard is 2.48 × 1.40 mm so adjacent cells at 2.54 mm pitch do not overlap. This is tighter than a generic IPC-7351 0603 courtyard and is allowed only because this is a matrix cell.
- Two-sided reflow is required because the FFC parts sit on the back. Confirm the LED moisture/reflow profile with the assembler before EVT (`EVT`).

LEDs are rotated 180° so the anode faces −X and the cathode faces +X. Anode row buses run above each row on `F.Cu`. Each cathode takes a via below the body onto a `B.Cu` column trunk.

## LED rail

RGB wearable architecture uses 4.099 V. A white LED at maximum `VF` 3.6 V plus MBI5124 `VDS` 0.4 V plus row/FFC/PMOS drop of about 0.13 A × paths leaves negative margin at 4.10 V.

Preliminary mono rail: 4.24 V from `TPS63802` with 681 kΩ / 91 kΩ 0.1% (`EVT`, measure the farthest blue-white pixel and driver temperature). Do not copy the RGB 655/91 kΩ divider onto this board.

## Electronics zones

Every white LED is one intersection of `ROW_nn_ANODE` and `COL_nn`. Those nets stay separate, so each pixel can be on or off by itself. BMI270 accelerometer and gyroscope use `IMU_SDA`, `IMU_SCL`, and `IMU_INT1`, and those three nets run from the IMU to their reserve pads. The same band holds pads for `LED_CLK`, `LED_SDI`, `LED_LE`, the row address, and the decoder enables. Motion decides whether the scan runs and which pixels are loaded. `LED_OE_N` is the blank for the whole matrix: both MBI5124 OE pins tie to reserve pad `RP07`. ESP32 QFN pads are not bonded until that pin map is checked. The open band is the corridor for the remaining scan wiring.

`U_LED1` pads 5–20 are `COL_01`–`COL_16` and `U_LED2` pads 5–20 are `COL_17`–`COL_32`. That is the usual MBI5124GP order, OUT0 on pad 5. Confirm it on the full pin figure before fabrication. Pads 1, 22, 23, and 24 are `GND`, `REXT`, `LED_LOGIC_3V3`, and `LED_OE_N`.

The electronics board is 190 × 148 mm. Each `ROW_nn_ANODE` and `COL_nn` is one copper path from the driver pad to the matching FFC pin. `LED_4V1` is one rail across the transistor sources and the gate pull-ups. USB `VBUS` is one net across the stacked receptacle pads. `GND` joins the USB shells and ground pins, BMI270 pads 6–7, both MBI5124 pad 1 pins, and `TP2`. `AON_3V3` joins BMI270 VDDIO and VDD to `TP1`. Each `REXT` reaches its 1.82 kΩ resistor, and `LED_LOGIC_3V3` ties the two driver logic pins. Zones from left to right:

1. USB-C, ESD, CC on the left edge.
2. ESP32-S3FN8 on the top edge, crystal directly under it, BMI270 on that same edge and away from the inductor. The open strip to the right of the MCU is the pin-escape field.
3. `BQ25185`, battery connector, `TPS63802`, inductor, AON LDO, and both `TPS22917` switches.
4. Microphone and `TLV9001` on the far right, opposite the switcher.
5. Row translator, both 74HC154 devices, and the 32 × `AO3403` farm with gate and pull-up resistors.
6. Two `MBI5124`, `SN74LV125A`, and both `Rext` next to `J_COL`.
7. Rear button and factory pads.
8. Bottom 6 mm reserved for `PCB CREATED BY ILLIA PLIUKHIN` and the star. No components or test pads in that strip.

`J_ROW` and `J_COL` sit on the right edge, cable exit to the right, same pinout as the panels. Row-farm transistor references stay on `F.SilkS` at 1.0 mm. The paired 0402 gate and pull-up references for that farm sit on `F.Fab` because three 1.0 mm silk strings cannot fit in one transistor cell.

Power domains, row-translator connections, MBI isolation, and sequencing follow [PCB_ARCHITECTURE.md](PCB_ARCHITECTURE.md) except for the LED-rail divider above and the FFC break between matrix and drivers.

## Matrix geometry

| Item | Value |
|---|---|
| Pitch | 2.54 mm |
| Panel margin | 44.0 mm |
| Row bus | 0.35 mm on `F.Cu`, 0.90 mm above the optical centre |
| Column trunk | 0.20 mm on `B.Cu` through the cathode via |
| Cathode via | 0.45 / 0.20 mm, 1.10 mm below the optical centre |
| Row fan-in | 0.28 mm front channels, 0.55 mm via row at y = 16 mm, L-route on `B.Cu` |
| Column fan-in | monotonic `B.Cu` diagonal from the trunk end to `J_COL` |
| Fan-in track | 0.15 mm track / 0.10 mm clearance |
| Copper to edge | 0.30 mm |
| Via drill | 0.20 mm |

These numbers are first-pass healthy values. Shrinking the outline and the courtyard comes after both panels pass geometric DRC and the electronics placement review.

## DRC scope

- LED panels: geometric DRC must be clean, including connectivity of every populated row and column to the matching FFC pin.
- Electronics: geometric DRC must be clean. Every `ROW_01_ANODE`…`ROW_32_ANODE` and `COL_01`…`COL_32` must be a single connected net, along with `LED_4V1`, `IMU_SDA`, `IMU_SCL`, `IMU_INT1`, `GND`, `VBUS`, `AON_3V3`, `REXT1`, `REXT2`, `LED_LOGIC_3V3`, and `LED_OE_N`. Decoder, serial, charger, and ESP32 GPIO nets may stay open until those pins are bonded.
