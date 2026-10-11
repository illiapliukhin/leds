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

**Interconnect cable (required type): 2 × 40-pin, 0.5 mm pitch FFC, Type B (reverse / opposite-side contacts), 0.3 mm thick with stiffened ends, one for ROW (J_ROW1↔J_ROW) and one for COL (J_COL1↔J_COL).**

- **Why Type B.** The board receptacles are on F.Cu with the cable exiting east. The panel receptacles are on B.Cu with the cable exiting west (J_ROW) and south (J_COL). Both ends are FH12 bottom-contact. In that geometry pin 1 meets pin 1 only with a Type B cable. A Type A (same-side) cable mirrors pins 1↔40, so all 32 nets land wrong. This holds however the ribbon is bent or folded; `firmware/mono_split/sim/bringup/cable.py` derives it from the pad coordinates.
- **Default length 100 mm:** LCSC C2857750, JS05B-40P-100-4-8. Same series, all Type B: 80 mm C5371275, 120 mm C5371276, 150 mm C2857751, 200 mm C2857752.
- **Choosing a length.** Use the shortest one that reaches the panel with a gentle bend. Each conductor is about 0.3 × 0.035 mm copper, roughly 0.16 Ω per 100 mm. One row contact at 0.32 A drops about 50 mV per 100 mm, on top of the board's 92 mV worst case. Above about 150 mm, parallel the spare contacts 33…40 onto the farthest rows.
- **Installation build (v14).** `J_RH1`/`J_CH1` (2×20 1.27 mm SMD, DNP in the wearable build) sit in a 12.5 mm strip east of the FFCs and repeat J_ROW1/J_COL1 pin for pin, with 64 DNP PESD5V0S1BL TVS (`D_R01…32`, `D_C01…32`). Fit them instead of the FFC/garland breakout for stationary installations; see LED_INTERFACE_STANDARD.md §6.1. The FFC cables lie flat over the unpopulated strip.
- **Board marking.** F.Silkscreen reads "FFC TYPE B" and "PIN1" beside J_ROW1 and J_COL1. Pin 1 is the north end of each receptacle.

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

Preliminary mono rail: 4.24 V from `TPS63802` with 681 kΩ / 91 kΩ 0.1% (`EVT`, measure the farthest blue-white pixel and driver temperature). Do not copy the RGB 655/91 kΩ divider onto this board. `TPS63802` VOUT is `LED_4V1`, VIN is `SYS`, and MODE is tied to `GND`. `LED_EN` has a 100 kΩ pulldown. `TLV75733P` (1 A, v11b; was TPS7A2033 300 mA) takes `SYS` and holds `AON_3V3` on by tying EN to IN; 22 µF bulk (`C_MCU11`) sits at the ESP32 for radio bursts. `LED_EN` reaches the TPS63802 through a 100 kΩ / 10 nF RC (`R_EN_SER1`, `C_EN1`) that swallows the 60 µs GPIO18 power-up pulse. v11b renamed references without a trailing digit by appending "1" (see `hardware/mono_electronics/REF_RENAME_v11b.json`); names in this document are the pre-v11b names. The LED `TPS22917` switches `AON_3V3` to `LED_LOGIC_3V3`, with `LED_LOGIC_EN` pulled down by 100 kΩ and a 1 kΩ QOD resistor. The audio switch has the same default-off pulldown; its QOD pin stays open. `C_SYS` is 10 µF on the buck input. `C_LED1` and `C_LED2` are 22 µF on `LED_4V1`. `C_LDO_IN` and `C_LDO_OUT` are 1 µF. `U_CHG` is the 10-pin DLH package with the TI 0.90 × 1.50 mm exposed pad. `IN` is `VBUS`, `SYS` joins the buck and the LDO, `/CE` and the thermal pad are `GND`, `ILIM/VSET` is 18 kΩ, which is 4.2 V and a 500 mA input limit. `ISET` is 600 Ω, which is 500 mA of charge. That is 0.5C for a 1000 mAh cell and 0.33C for a 1500 mAh cell. The pack is Jauch `LP523450JU` (Jauch No. 249796): 3.7 V, 1000 mAh typical, 950 mAh minimum, charge to 4.2 V, maximum charge and discharge 1C, NTC 10 kΩ ±1% β3435. The body is 53.0 × 34.5 × 5.4 mm. Its housing is Molex 51021-0300: pin 1 red is BAT+, pin 2 yellow is the NTC, pin 3 black is GND. `J_BAT1` (v13b) is a JST PH S3B-PH-SM4-TB side-entry SMD header (2 A/contact, 2.0 mm pitch, 5.5 mm tall), with pin 1 `BAT_PACK` (through F_BAT1 and Q_BAT1 to `BAT_RAW`), pin 2 `TS_MR`, and pin 3 `GND`. The cable enters from the west board edge. **The pack lead must be re-terminated in a JST PHR-3 housing** (pin 1 red BAT+, pin 2 yellow NTC, pin 3 black GND), because the original Molex 51021-0300 housing no longer mates. It was replaced because PicoBlade is rated 1 A/contact, below the 1.22 A peak. The header is rotated so those pins run top to bottom in the same order as the pack drawing: black on top, yellow in the middle, red on the bottom. That pack thermistor is the only resistor on `TS/MR`. The status pins stay open. `IN`, `SYS`, and `BAT_RAW` each have a local 0805 10 µF capacitor.

## Electronics zones

Every white LED is one intersection of `ROW_nn_ANODE` and `COL_nn`. Those nets stay separate, so each pixel can be on or off by itself. BMI270 accelerometer and gyroscope use `IMU_SDA`, `IMU_SCL`, and `IMU_INT1`, and those three nets run from the IMU to their reserve pads. The same band holds pads for `LED_CLK`, `LED_SDI`, `LED_LE`, the row address, and the decoder enables. Motion decides whether the scan runs and which pixels are loaded. `LED_OE_N` is the blank for the whole matrix. `SN74LV125A` buffers `LED_CLK`, `LED_SDI`, `LED_LE`, and `LED_OE_N` from their reserve pads onto `LED_CLK_Y`, `LED_SDI_Y`, `LED_LE_Y`, and `LED_OE_Y` at the MBI5124 pins. All four buffer output enables are tied to `GND`, and the buffer supply is `LED_LOGIC_3V3`. `LED_CLK`, `LED_SDI`, and `LED_LE` have 100 kΩ pulldowns. `LED_OE_N` has a 47 kΩ pull-up to `AON_3V3`. 22 Ω resistors sit between the buffer outputs and `LED_CLK_Y`, `LED_SDI_Y`, and `LED_LE_Y`. `LED_OE_Y` has a 47 kΩ pull-up to `LED_LOGIC_3V3`. ESP32 QFN pads are not bonded until that pin map is checked. `SN74LVC8T245` is inserted between those reserve pads and the decoders: `VCCA` and `DIR` are `AON_3V3`, `VCCB` is `LED_4V1`, and `/OE` is `ROW_XLAT_OE_N`. A1–A6 keep the MCU names `ROW_A0`–`ROW_A3`, `DEC_A_EN_N`, and `DEC_B_EN_N`. B1–B6 drive `ROW_A0_4V`–`ROW_A3_4V`, `DEC_A_EN_N_4V`, and `DEC_B_EN_N_4V`. A7, A8, and the ground pins are `GND`. B7 and B8 stay open, and the exposed pad is not via-stitched. `ROW_A0_4V`–`ROW_A3_4V` each have a 100 kΩ pulldown to `GND`. `DEC_A_EN_N_4V` and `DEC_B_EN_N_4V` each have a 47 kΩ pull-up to `LED_4V1`. `ROW_XLAT_OE_N` has a 10 kΩ pull-up to `AON_3V3`.

`U_LED1` pads 5–20 are `COL_01`–`COL_16` and `U_LED2` pads 5–20 are `COL_17`–`COL_32`. The MBI5124 pin configuration places OUT0 on pad 5 and OUT15 on pad 20. Pad 1 is `GND`, pad 2 `SDI`, pad 3 `CLK`, pad 4 `LE`, pad 21 `OE`, pad 22 `SDO`, pad 23 `R-EXT`, and pad 24 `VDD`. `LED_SDO` joins `U_LED1` SDO to `U_LED2` SDI. `LED_CLK_Y` and `LED_LE_Y` are common to both drivers. `U_LED2` SDO stays open.

`U_DEC_A` Y0–Y15 drive rows 1–16 and `U_DEC_B` Y0–Y15 drive rows 17–32. On the 74HC154, Y0–Y10 are pads 1–11, Y11–Y15 are pads 13–17, the shared address is pads 23–20 (`ROW_A0_4V`–`ROW_A3_4V`), E0 is pad 18 on `DEC_A_EN_N_4V` or `DEC_B_EN_N_4V`, E1 is pad 19 and tied to `GND`, and VCC is pad 24 on `LED_4V1`. Each `ROW_nn_Y` reaches `R_G` pad 2. `ROW_nn_GATE` ties the AO3403 gate, `R_G` pad 1, and the pull-up. The MCU-side address and bank enables land on their reserve pads. The second pad of each `Rext` returns to `GND`.

The electronics board is 190 × 148 mm. Each `ROW_nn_ANODE` and `COL_nn` is one copper path from the driver pad to the matching FFC pin. `LED_4V1` is one rail across the transistor sources, the gate pull-ups, and `TPS63802` VOUT. USB `VBUS` is one net across the stacked receptacle pads. `GND` joins the USB shells and ground pins, BMI270 pads 6–7, both MBI5124 pad 1 pins, `TP2`, and the converter returns. `AON_3V3` joins BMI270 VDDIO and VDD, `TP1`, and `TPS7A2033` OUT. Each `REXT` reaches its 1.82 kΩ resistor, and `LED_LOGIC_3V3` ties the two driver logic pins. Zones from left to right:

1. USB-C, ESD, CC on the left edge.
2. **MCU (committed baseline):** `U1` at **(46, 10) mm**, **270°** — functional GPIOs on the west face, still overlapping the row fan-in field in Y. **`Y1`** north of `U1`; **`U_IMU`** at **(62.35, 4.5) mm**. Strap/USB passives west of `U1`. **GPIO map unchanged.**

### Planned MCU island relocation (2026-10-09, not yet committed)

Goal: move **`U1` + Y1, IMU, USB series, straps, `C_MCU1`, `SW1`** out of the **`x≈13–42`, `y≈4–70`** row fan-in / **`ROW_nn_Y`** corridor into a **south-west keep-in** that is empty on **F / In1 / In2** in the layout database.

**Free-area map (190 × 148 mm, branding strip `y > 142` excluded):**

| Region | Approx. bounds | Fixed copper / parts | Suitability |
|---|---|---|---|
| Row fan-in + `ROW_nn_Y` | `x≈13–42`, `y≈4–72` | F + In1/In2 matrix stubs | **Avoid** (locked) |
| Power / charger | `x≈6–44`, `y≈38–76` | `SYS`, `BAT`, buck/LDO | Keep MCU out |
| Translator + decoders | `x≈57–110`, `y≈4–28` | Address spines to reserves | Targets to the **north** |
| Reserve strip | `y≈98`, `x≈8–127` | Drops from buffer/translator | **Short north** taps if MCU sits **`y≈90–112`** |
| MBI + column field | `x≈62–120`, `y≈60–90` | Driver + `COL_nn` | Avoid |
| **South-west keep-in** | **`x≈22–58`, `y≈88–125`** | Mostly open; **`GND` In2 spine `x=41`** | **Preferred island** |
| USB edge | `x≈0–12`, `y≈12–28` | `J_USB`, ESD | Keep connector; **In2/USB bus west** |

**Recommended placement (next implementation pass):**

- **`U1`:** **(52, 94) mm**, **0°** — GPIO row faces **+Y** toward reserves **`y=98`** and **+X** toward **`U_ROW_XLAT`** A-side (**~68 mm, 14 mm**). Package **west** edge toward the **left board edge** (RF keep-out along the edge per Espressif guidance).
- **`Y1`:** **(52, 88) mm** (north, no tracks under crystal).
- **`U_IMU`:** **(62, 94) mm** (local I²C on F.Cu).
- **Straps / `C_MCU1` / `SW1`:** cluster **`x≈24–40`, `y≈112–120`** (above island, still below branding).
- **`J_USB`:** **unchanged** on the **left edge**; MCU USB uses **In2** west bus **`y≈108`** to **`U_ESD`** (mechanical USB stays put).

**Routing plan:**

- **Do not** run long eastbound buses at a single **`y`** on In2 — they cross the locked **`GND` spine at `x=41`** and matrix In1/In2 trunks.
- **Do** pre-route or reserve **per-net In1 lanes** in the generator **`y=105.5…109.5`**, **`x=52→reserve_x`**, then **F** up to **`y=98`**, **or** extend existing reserve vias at **`(reserve_x, 97.35)`** south with **staggered In1** stubs before locking matrix copper.
- **Freerouting** only inside a **DSN keep-in** rectangle **`(20, 86)–(66, 126)`** for cleanup after scripted buses.
- **Electrical join:** MCU signal nets should meet the **existing reserve/translator graph** at **`y=98`** (same net already routed to decoders/MBI) — not a second path through **`y≈15`** translator pads unless stubs are unlocked.

**Status:** Relocation was attempted on PR #4 pass 3; scripted buses from **`(34–40, 107–112)`** produced **60+ shorts / 40+ crossings** against locked matrix/`GND` geometry. **Committed PCB remains baseline `0 / 0 / 74`** until collision-aware tunnels or the **`(52, 94)`** plan above is implemented in the generator first.

### Why the old corner was congested

| Source | Effect |
|---|---|
| QFN **0.4 mm** south row at **0°** | Row, LED, USB pads shared one **`y≈11.4 mm`** line — parallel F escapes collided. |
| Row-select **fan-in / reserve drops** near **`x≈37`** | MCU paths to MBI reserves crossed **`ROW_nn_Y`** (e.g. **`LED_SDI` vs `ROW_08_Y`**). |
| **`route_mcu_side_to_drop`** through the grid | Long F/In1 columns from **`x≈28–40`** through the row farm. |
| Fixed **decoder spines** at **`x≈63–70`** | Every MCU move still needs a clean **In2 corridor** at **`x≈44–50`**, not ad-hoc F columns. |

**MCU copper (2026-10-08, Freerouting path):** The generator **no longer** calls `route_esp32_mcu()`. Matrix, FFC fan-in, power, decoders, buffers, and reserve rails stay in **`generate_mono_split_boards.py`**. The MCU corner is filled by **`hardware/tools/autoroute_mcu.py`**:

1. **`generate_mono_split_boards.py`** (optional `--no-regenerate` to reuse `.kicad_pcb`).
2. Lock all existing tracks/vias → **`ExportSpecctraDSN`** → patch DSN net classes: **`matrix_and_fixed`** (173 nets, Freerouting **`-inc`**) vs **`mcu_autoroute`** (27 nets).
3. **Freerouting 2.5.0** (JAR + OpenJDK 25, headless): `-mp60`, `-mt3`, fanout off, routable **F / In1 / In2 / B**, preferred directions **H / V / H / V**.
4. **Do not use `ImportSpecctraSES`** for this flow — KiCad replaces the whole board routing. Append only new SES `(network_out …)` wires/vias via **`specctra_ses_append.py`**.
5. Zone refill and save. Commit **`mono_electronics.ses`** when reproducible.

Run: **`hardware/tools/run_autoroute_mcu.sh`** (sources **`kicad10_env.sh`** for KiCad **10.0.5** `python3.11` / `kicad-cli`). Download the router JAR with **`hardware/tools/download_freerouting.sh`**.

**Placement tweaks for autoroute (same PR):** **`C_CHIP_PU`** → **(33.5, 13.5) mm**; **`TP1`** → **(28, 76) mm** (both pads on **`AON_3V3`**); **`AON_3V3`** spine east of **`U1`** on **In1/In2** only (no F.Cu hooks through the EP).

Legacy scripted helpers remain in **`mono_split_esp32.py`** (`route_mcu_xtal_only`, full **`route_esp32_mcu()`**) for hand touch-up or regression.

**Not done yet:** After grid apply, copper gate is **0 shorts / 0 crossings**, but KiCad still reports **39 unconnected groups** (mostly **`AON_3V3`** / **`GND`** islands and four open signal nets: **`GPIO0_BOOT`**, **`USB_D_N_MCU`**, **`DEC_A_EN_N`**, plus three **IMU** links). Post-grid hand routes on **F.Cu** through the MCU field collide with grid copper; **In2-only** ties and blind stitch vias still need pocket validation. **`verify_mono_split_boards.py`** remains red on electronics until unconnected and silk/dangling cleanup reach zero. Panels stay **0/0/0**.
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

Strapping pins `GPIO0`, `GPIO45`, and `GPIO46` are not used as functional outputs. `GPIO3` (JTAG-source strap, only sampled when `EFUSE_STRAP_JTAG_SEL` is burned, which this design never does) is used as the north-port `PRES_N` input; it is not driven during reset. In-package Quad SPI flash pins stay unnamed on the PCB. Native USB uses `GPIO19`/`GPIO20` as `USB_D_N_MCU` / `USB_D_P_MCU` through 22 Ω from `USB_D_N` / `USB_D_P` at the ESD device.

| GPIO | QFN pad | Net | Role |
|---:|---:|---|---|
| — | 4 | `CHIP_PU` | EN (`R_CHIP_PU` / `C_CHIP_PU`) |
| 0 | 5 | `GPIO0_BOOT` | Boot strap + `SW1` |
| 8 | 13 | `IMU_SDA` | BMI270 I²C |
| 9 | 14 | `IMU_SCL` | BMI270 I²C |
| 10 | 15 | `IMU_INT1` | BMI270 interrupt |
| 13–16 | 18,19,21,22 | `LED_CLK` … `LED_OE_N` | MBI5124 control (reserve → buffer) |
| 1 | 6 | `GAUGE_ALRT_N` | MAX17048 ALRT (open-drain, active low, 10 k pull-up) |
| 2 | 7 | `TH_ADC` | Board NTC divider (ADC1_CH1) |
| 4 | 9 | `AUDIO_ADC` | Mic preamp output (ADC1_CH3) |
| 6 | 11 | `AUDIO_EN` | Audio switch |
| 37 | 42 | `ROW_A3` | Row address (moved from GPIO33 in v8) |
| 38 | 43 | `ROW_A2` | Row address (east face) |
| 39 | 44 | `ROW_A0` | Row address (east face) |
| 40 | 45 | `ROW_A1` | Row address (east face) |
| 41 | 47 | `DEC_A_EN_N` | 74HC154 A enable |
| 42 | 48 | `DEC_B_EN_N` | 74HC154 B enable |
| 18 | 24 | `LED_EN` | `TPS63802` enable |
| 21 | 27 | `LED_LOGIC_EN` | LED logic switch |
| 19 | 25 | `USB_D_N_MCU` | Native USB D− |
| 20 | 26 | `USB_D_P_MCU` | Native USB D+ |
| 44 | 50 | `ROW_XLAT_OE_N` | Translator `/OE` (moved from GPIO47 in v8; U0RXD has an internal pull-up during reset, so the translator stays disabled until firmware drives it) |
| 33 | 38 | `RS485_RX` | THVD1406 `R` → MCU (UART RX) |
| 34 | 39 | `RS485_TX` | MCU → THVD1406 `D` (UART TX, auto-direction transceiver) |
| 48 | 36 | `FRAME_SYNC` | Stacking ports pin 4, shared frame sync |
| 3 | 8 | `PRES_N` | North port pin 5 (presence / side detect) |
| 47 | 37 | `PRES_E` | East port pin 5 |
| 35 | 40 | `PRES_S` | South port pin 5 |
| 26 | 28 | `PRES_W` | West port pin 5 (pad 28 = SPICS1, free on FN8: no PSRAM) |
| — | 53–54 | `XTAL_N` / `XTAL_P` | 40 MHz crystal |

**Part choice:** BOM targets **ESP32-S3FN8** (in-package **quad** flash). Row address uses **`GPIO39`/`40`/`38`** (pads 44/45/43) plus **`GPIO37`** (pad 42, v8). Enables and audio use remapped west/east pads: **`GPIO18`/`GPIO21`** (pads 24/27), **`GPIO41`/`GPIO42`** (pads 47/48 — datasheet **MTDI/MTMS**; acceptable here because bring-up uses **USB Serial/JTAG**, not a header on those balls), **`GPIO6`** (pad 11). USB stays on **`GPIO19`/`GPIO20`** (pads 25/26). **Pad 32 (`SPICS0`) stays NC** — never tie to `GND`. `GPIO33`–`GPIO37` on FN8 conflict with **octal** `-R8`/`-N16R8` modules; this PCB is not drop-in for those without respin or firmware remap.

MCU copper is **PathFinder-first** grid-routed in `hardware/tools/mcu_grid_route.py` (F/In1/In2/**B**, via-legal pockets): compute runs greedy + PathFinder, applies the larger complete set that passes DRC (**0 shorts / 0 crossings**), then **`kicad-cli pcb drc --refill-zones --save-board`** fills GND pours on In2/B.

## DRC scope

- LED panels: geometric DRC must be clean, including connectivity of every populated row and column to the matching FFC pin.
- Electronics: matrix and driver nets listed in earlier revisions must remain one connected group each. MCU nets (`IMU_*`, `LED_CLK`/`LED_SDI`/`LED_LE`/`LED_OE_N`, row address, enables, `ROW_XLAT_OE_N`, `LED_EN`, `LED_LOGIC_EN`, `AUDIO_EN`, `CHIP_PU`, `GPIO0_BOOT`, `USB_D_*`, `XTAL_*`) are now assigned and routed in the generator; geometric clearance on the MCU escape field is still being cleaned up (not production-frozen).

## Stacking ports (v8)

Four identical ports, one per board edge (`J_PORT_N`, `J_PORT_E`, `J_PORT_S`, `J_PORT_W`), so several boards can be tiled into a larger wearable. Every port has the same pinout, so any port mates any port with a straight (pin 1 ↔ pin 1) cable.

**Connector:** JST SH 1.0 mm, 6-pin, side-entry SMD, **SM06B-SRSS-TB** (mating housing SHR-06V-S, pre-crimped SH jumpers). It is 2.9 mm tall, has no through-hole pins, and sits 0.55 mm inside the outline with its opening facing outward, so nothing sticks out past the board edge. Every port part is DNP-friendly: an unpopulated port leaves only floating, ESD-free pads on lines with internal pull-downs.

| Pin | Net | Notes |
|---:|---|---|
| 1 | `GND` | |
| 2 | `RS485_A` | shared multi-drop bus, bussed to all four ports |
| 3 | `RS485_B` | |
| 4 | `FRAME_SYNC` | shared, push-pull from the current leader, GPIO48 |
| 5 | `PRES_x` | per-port presence line, own GPIO (N=GPIO3, E=GPIO47, S=GPIO35, W=GPIO26) |
| 6 | `GND` | |
| MP | `GND` | mechanical pads |

**RS-485:** one **TI THVD1406DR** (SOIC-8; same die as the SOT-8 THVD1426 but available in SOIC), half duplex with automatic direction control, so only `RS485_TX` (GPIO34 → D) and `RS485_RX` (GPIO33 ← R) are needed. `/RE` is tied to GND and `/SHDN` to VCC. VCC comes from **`LED_LOGIC_3V3`**, the TPS22917 load-switched rail (enable GPIO21, off by default, quick output discharge). When the rail is off the transceiver is unpowered, so standby current is zero. Firmware rule: before turning the rail off, put GPIO34 into input or drive it low so D is not back-powered. The bus has 100 nF decoupling (`C_485`). A 120 Ω termination (`R_TERM`, 0603) can be switched across A/B by closing the solder jumper `JP_TERM`. Close it only on the two physical ends of a chain; there was no free GPIO left for an electronic switch.

**ESD:** behind every connector there is an **SM712** (SOT-23, asymmetric −7/+12 V TVS for RS-485) on A/B (`D_x_AB`) and a **PESD3V3S2UT** (SOT-23, dual 3.3 V TVS) on FRAME_SYNC/PRES (`D_x_SP`).

**Side detection / topology discovery:** every `PRES_x` pin idles as an input with the ESP32 internal pull-down (GPIO-enabled, no external resistor, no standby current). The cable ties board A's port pin 5 directly to the neighbour's port pin 5. Discovery runs over RS-485:
1. After power-up, each board waits a random back-off, then claims an ID on the bus (the lowest MAC wins the leader role).
2. The leader grants a token to one board at a time. The token holder drives `PRES_x` high on one port for about 1 ms and broadcasts "board <id> port <x> high".
3. Any board that sees a high on one of its own `PRES` inputs answers "board <id'> port <y>". This gives the edge (id, x) ↔ (id', y): the neighbour's identity and which side it is on, including its rotation.
4. Steps 2–3 repeat for all four ports of every board, and the leader distributes the resulting grid map.

Only one board drives a `PRES` line at a time, and the other side is always an input, so there is no contention. `FRAME_SYNC` is driven only by the leader; everyone else keeps it as an input with the internal pull-down.

**Bus termination for stacks and split strips (v13 recommendation).**
Every board busses A/B to all four of its ports, so a stack is a tree of short stubs, not one line with two ends. A strip
that is split (one board unplugged) becomes two independent buses, and the 2D grids have no real "ends" at all.

*Electrical length:* the bus runs at 500 kbps (2 µs bit). The THVD1406 is slew-limited, with driver edges of a few hundred ns. A 6-board stack with 100 mm cables plus the board copper adds up to about 1–1.5 m, roughly 5–8 ns one way. The edge is about 50× longer than the round trip, so reflections settle within the edge. **Termination is not needed for signal integrity at this rate and size**, and closing jumpers on the wrong boards only adds DC load (each 120 Ω pair draws about 15 mA while driving).

*Recommendation:*
1. **Default (v1 boards): leave `JP_TERM` open on every board.** This is correct for any arrangement, including a split strip: nothing has to be reconfigured on unplug or replug. Idle and open-bus states are defined by the THVD1406's built-in receiver fail-safe, so do not add bias resistors.
2. **Jumper termination** (close `JP_TERM` on the two most distant boards) is only worth it for long or fast buses (> about 3 m total, or > 1 Mbps). It is fixed: after a rearrangement or a split, one half ends up with no terminator, or a terminated board sits mid-bus. Use it only for permanent installations.
3. **Auto-termination (future rev, recommended if the bus speed goes up):** a GPIO-switched 120 Ω, for example a small PhotoMOS (AQY221/TLP3412-class, which tolerates the RS-485 −7…+12 V common-mode range) or back-to-back N-MOSFETs in series with `R_TERM`. Firmware already knows the topology: after discovery the leader computes the graph diameter (the two boards farthest apart in bus distance) and switches termination on only there. It recomputes on every unplug or rejoin, so each half of a split strip is terminated at its own ends. This costs one GPIO; none is free on v10b, so it needs a pin freed (or an I/O expander) in the next revision. Default it **off** at reset so a lone board draws nothing.

**PCB placement (v8):** S port at (64.0, 96.4) 0°, W at (3.1, 88.0) 270°, E at (144.9, 42.0) 90°, N at (126.0, 3.1) 180°. The RS-485 block sits at (60–69, 82–89), just above the S port. The outline was 148.0 × 99.5 mm until v13; v14 grows it east to 160.5 × 99.5 mm for the installation headers. All parts are on the top side.
