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

Preliminary mono rail: 4.24 V from `TPS63802` with 681 kΩ / 91 kΩ 0.1% (`EVT`, measure the farthest blue-white pixel and driver temperature). Do not copy the RGB 655/91 kΩ divider onto this board. `TPS63802` VOUT is `LED_4V1`, VIN is `SYS`, and MODE is tied to `GND`. `LED_EN` has a 100 kΩ pulldown. `TPS7A2033` takes `SYS` and holds `AON_3V3` on by tying EN to IN. The LED `TPS22917` switches `AON_3V3` to `LED_LOGIC_3V3`, with `LED_LOGIC_EN` pulled down by 100 kΩ and a 1 kΩ QOD resistor. The audio switch has the same default-off pulldown; its QOD pin stays open. `C_SYS` is 10 µF on the buck input. `C_LED1` and `C_LED2` are 22 µF on `LED_4V1`. `C_LDO_IN` and `C_LDO_OUT` are 1 µF. `U_CHG` is the 10-pin DLH package with the TI 0.90 × 1.50 mm exposed pad. `IN` is `VBUS`, `SYS` joins the buck and the LDO, `/CE` and the thermal pad are `GND`, `ILIM/VSET` is 18 kΩ, which is 4.2 V and a 500 mA input limit. `ISET` is 600 Ω, which is 500 mA of charge. That is 0.5C for a 1000 mAh cell and 0.33C for a 1500 mAh cell. The pack is Jauch `LP523450JU` (Jauch No. 249796): 3.7 V, 1000 mAh typical, 950 mAh minimum, charge to 4.2 V, maximum charge and discharge 1C, NTC 10 kΩ ±1% β3435. The body is 53.0 × 34.5 × 5.4 mm. Its housing is Molex 51021-0300: pin 1 red is BAT+, pin 2 yellow is the NTC, pin 3 black is GND. `J_BAT` is the mating vertical header Molex 53398-0371, with pad 1 `BAT_RAW`, pad 2 `TS_MR`, and pad 3 `GND`. The header is rotated so those pins run top to bottom in the same order as the pack drawing: black on top, yellow in the middle, red on the bottom. That pack thermistor is the only resistor on `TS/MR`. The status pins stay open. `IN`, `SYS`, and `BAT_RAW` each have a local 0805 10 µF capacitor.

## Electronics zones

Every white LED is one intersection of `ROW_nn_ANODE` and `COL_nn`. Those nets stay separate, so each pixel can be on or off by itself. BMI270 accelerometer and gyroscope use `IMU_SDA`, `IMU_SCL`, and `IMU_INT1`, and those three nets run from the IMU to their reserve pads. The same band holds pads for `LED_CLK`, `LED_SDI`, `LED_LE`, the row address, and the decoder enables. Motion decides whether the scan runs and which pixels are loaded. `LED_OE_N` is the blank for the whole matrix. `SN74LV125A` buffers `LED_CLK`, `LED_SDI`, `LED_LE`, and `LED_OE_N` from their reserve pads onto `LED_CLK_Y`, `LED_SDI_Y`, `LED_LE_Y`, and `LED_OE_Y` at the MBI5124 pins. All four buffer output enables are tied to `GND`, and the buffer supply is `LED_LOGIC_3V3`. `LED_CLK`, `LED_SDI`, and `LED_LE` have 100 kΩ pulldowns. `LED_OE_N` has a 47 kΩ pull-up to `AON_3V3`. 22 Ω resistors sit between the buffer outputs and `LED_CLK_Y`, `LED_SDI_Y`, and `LED_LE_Y`. `LED_OE_Y` has a 47 kΩ pull-up to `LED_LOGIC_3V3`. ESP32 QFN pads are not bonded until that pin map is checked. `SN74LVC8T245` is inserted between those reserve pads and the decoders: `VCCA` and `DIR` are `AON_3V3`, `VCCB` is `LED_4V1`, and `/OE` is `ROW_XLAT_OE_N`. A1–A6 keep the MCU names `ROW_A0`–`ROW_A3`, `DEC_A_EN_N`, and `DEC_B_EN_N`. B1–B6 drive `ROW_A0_4V`–`ROW_A3_4V`, `DEC_A_EN_N_4V`, and `DEC_B_EN_N_4V`. A7, A8, and the ground pins are `GND`. B7 and B8 stay open, and the exposed pad is not via-stitched. `ROW_A0_4V`–`ROW_A3_4V` each have a 100 kΩ pulldown to `GND`. `DEC_A_EN_N_4V` and `DEC_B_EN_N_4V` each have a 47 kΩ pull-up to `LED_4V1`. `ROW_XLAT_OE_N` has a 10 kΩ pull-up to `AON_3V3`.

`U_LED1` pads 5–20 are `COL_01`–`COL_16` and `U_LED2` pads 5–20 are `COL_17`–`COL_32`. The MBI5124 pin configuration places OUT0 on pad 5 and OUT15 on pad 20. Pad 1 is `GND`, pad 2 `SDI`, pad 3 `CLK`, pad 4 `LE`, pad 21 `OE`, pad 22 `SDO`, pad 23 `R-EXT`, and pad 24 `VDD`. `LED_SDO` joins `U_LED1` SDO to `U_LED2` SDI. `LED_CLK_Y` and `LED_LE_Y` are common to both drivers. `U_LED2` SDO stays open.

`U_DEC_A` Y0–Y15 drive rows 1–16 and `U_DEC_B` Y0–Y15 drive rows 17–32. On the 74HC154, Y0–Y10 are pads 1–11, Y11–Y15 are pads 13–17, the shared address is pads 23–20 (`ROW_A0_4V`–`ROW_A3_4V`), E0 is pad 18 on `DEC_A_EN_N_4V` or `DEC_B_EN_N_4V`, E1 is pad 19 and tied to `GND`, and VCC is pad 24 on `LED_4V1`. Each `ROW_nn_Y` reaches `R_G` pad 2. `ROW_nn_GATE` ties the AO3403 gate, `R_G` pad 1, and the pull-up. The MCU-side address and bank enables land on their reserve pads. The second pad of each `Rext` returns to `GND`.

The electronics board is 190 × 148 mm. Each `ROW_nn_ANODE` and `COL_nn` is one copper path from the driver pad to the matching FFC pin. `LED_4V1` is one rail across the transistor sources, the gate pull-ups, and `TPS63802` VOUT. USB `VBUS` is one net across the stacked receptacle pads. `GND` joins the USB shells and ground pins, BMI270 pads 6–7, both MBI5124 pad 1 pins, `TP2`, and the converter returns. `AON_3V3` joins BMI270 VDDIO and VDD, `TP1`, and `TPS7A2033` OUT. Each `REXT` reaches its 1.82 kΩ resistor, and `LED_LOGIC_3V3` ties the two driver logic pins. Zones from left to right:

1. USB-C, ESD, CC on the left edge.
2. **MCU corner (2026-10-08 rework):** `U1` at **(46, 10) mm**, **270°** so row/decoder/LED GPIOs leave the **west face** already **east of the row fan-in** (`x≈37`). Crystal **`Y1`** sits **north** of the chip (short XTAL, no routing under the resonator). **`U_IMU`** moves to **(62, 4.5) mm** (east of the MCU, clear of the switcher). Strap/USB passives sit in a **west cluster** near **x≈36–40**. GPIO map unchanged.

### Why the old corner was congested

| Source | Effect |
|---|---|
| QFN **0.4 mm** south row at **0°** | Row, LED, USB pads shared one **`y≈11.4 mm`** line — parallel F escapes collided. |
| Row-select **fan-in / reserve drops** near **`x≈37`** | MCU paths to MBI reserves crossed **`ROW_nn_Y`** (e.g. **`LED_SDI` vs `ROW_08_Y`**). |
| **`route_mcu_side_to_drop`** through the grid | Long F/In1 columns from **`x≈28–40`** through the row farm. |
| Fixed **decoder spines** at **`x≈63–70`** | Every MCU move still needs a clean **In2 corridor** at **`x≈44–50`**, not ad-hoc F columns. |

**Routing (generator, 270°):** Legacy **F-column** MCU escapes are **removed**. Constants in `mono_split_esp32.py`:

| Corridor | Role |
|---|---|
| **`WEST_SOUTH_ESCAPE_Y_BY_PAD`** | Separate south-escape **`y`** for each west-column pad (shared **`x≈42.56`**) |
| **`x≈49.0–50.1`** | Per-net **row-address stub** on F, then **In2 at spine `y`** (63.8/18.7 … 65.2/25.35) |
| **`x≈52` + `y≈20.5–22.15`** | South-face **ROW_A3**, **DEC_***, **`ROW_XLAT_OE_N`** In2 buses |
| **`MCU_LED_STUB_X≈51.5`** | **LED_CLK/SDI/LE/OE_N** → eastern **In2** rail to reserves (clears **`x≈37`** fan-in) |
| **`MCU_BOOT_IN2_X≈31`** | **`GPIO0_BOOT`** to **`SW1`** |
| USB | **`R_USB_*`** via staggered south escape; **J_USB** **split `merge_y` + In2** to **`U_ESD`** |

**Not done yet:** Copper **0/0/0**, full geometric verify (silk/mask). **`verify_mono_split_boards.py`** still checks electronics **shorts + crossings only** until copper is clean.
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

## ESP32-S3FN8 GPIO map (EVT)

Strapping pins `GPIO0`, `GPIO3`, `GPIO45`, and `GPIO46` are not used as functional outputs. In-package Quad SPI flash pins stay unnamed on the PCB. Native USB uses `GPIO19`/`GPIO20` as `USB_D_N_MCU` / `USB_D_P_MCU` through 22 Ω from `USB_D_N` / `USB_D_P` at the ESD device.

| GPIO | QFN pad | Net | Role |
|---:|---:|---|---|
| — | 4 | `CHIP_PU` | EN (`R_CHIP_PU` / `C_CHIP_PU`) |
| 0 | 5 | `GPIO0_BOOT` | Boot strap + `SW1` |
| 8 | 13 | `IMU_SDA` | BMI270 I²C |
| 9 | 14 | `IMU_SCL` | BMI270 I²C |
| 10 | 15 | `IMU_INT1` | BMI270 interrupt |
| 13–16 | 18,19,21,22 | `LED_CLK` … `LED_OE_N` | MBI5124 control (reserve → buffer) |
| 17 | 23 | `ROW_A0` | Row address |
| 18 | 24 | `ROW_A1` | Row address |
| 21 | 27 | `ROW_A2` | Row address |
| 33 | 38 | `ROW_A3` | Row address |
| 34 | 39 | `DEC_A_EN_N` | 74HC154 A enable |
| 35 | 40 | `DEC_B_EN_N` | 74HC154 B enable |
| 36 | 41 | `LED_EN` | `TPS63802` enable |
| 37 | 42 | `LED_LOGIC_EN` | LED logic switch |
| 19 | 25 | `USB_D_N_MCU` | Native USB D− |
| 20 | 26 | `USB_D_P_MCU` | Native USB D+ |
| 42 | 48 | `AUDIO_EN` | Audio switch |
| 47 | 37 | `ROW_XLAT_OE_N` | Translator `/OE` |
| — | 53–54 | `XTAL_N` / `XTAL_P` | 40 MHz crystal |

**Part choice:** BOM targets **ESP32-S3FN8** (in-package **quad** flash). Row address uses `GPIO17`/`18`/`21`/`33`; USB uses `GPIO19`/`20` only — no GPIO overlap. `GPIO33`–`GPIO37` are valid on FN8 but conflict with **octal** `-R8`/`-N16R8` modules; this PCB is not drop-in for those without respin or firmware remap.

Copper is generated in `hardware/tools/mono_split_esp32.py` and called from `generate_mono_split_boards.py`.

## DRC scope

- LED panels: geometric DRC must be clean, including connectivity of every populated row and column to the matching FFC pin.
- Electronics: matrix and driver nets listed in earlier revisions must remain one connected group each. MCU nets (`IMU_*`, `LED_CLK`/`LED_SDI`/`LED_LE`/`LED_OE_N`, row address, enables, `ROW_XLAT_OE_N`, `LED_EN`, `LED_LOGIC_EN`, `AUDIO_EN`, `CHIP_PU`, `GPIO0_BOOT`, `USB_D_*`, `XTAL_*`) are now assigned and routed in the generator; geometric clearance on the MCU escape field is still being cleaned up (not production-frozen).
