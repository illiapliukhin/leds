# mono_panel_32x32_full — edge-to-edge 32×32 panel for seamless tiling

A drop-in alternative to `mono_panel_32x32`: same two Hirose `FH12-40S-0.5SH` receptacles, same pinout and LED net mapping
(`Dn`, n = 32(r−1)+c; LED pad 2 = `ROW_rr_ANODE`, pad 1 = `COL_cc`), Type B FFC pin 1 → pin 1. There is no frame. LEDs fill the
whole front, so butted panels (6-stack, 3×2, 6×1) keep one continuous pixel grid.

## Geometry (for the stacking sim)

| | |
|---|---|
| Outline | **160.0 × 160.0 mm**, square, sharp corners, origin at the top-left corner of the front (KiCad +x right, +y down) |
| Pitch | **5.0 mm** in x and y |
| LED centres | x = 2.5 + 5.0·(c−1), y = 2.5 + 5.0·(r−1); the outermost LED centre is **2.5 mm (pitch/2)** from every edge |
| Across a seam | centre-to-centre = 5.0 mm, so the pitch is continuous; 3×2 = 480 × 320 mm, 96 × 64 LEDs; 6×1 = 960 × 160 mm |
| LED | NCD0603W1 (0603), long axis vertical, centred on the node; anode north |
| Thickness | 1.6 mm FR4, 4 layers; height with FFC ≈ 1.6 + 2.0 (FH12) mm; SMT standoffs on the back |
| Back parts | J_ROW centre (72.75, 80.0), J_COL centre (107.75, 80.0), both B.Cu, pin 1 at the left (front view), cable exits +y (south). U_ID (91.0, 76.9), C_ID (91.0, 74.3). Standoffs MH1–4 at (20, 16.9), (140, 16.9), (20, 141.9), (140, 141.9) |

## Choices

- **Pitch 5.0 mm (160 mm board).** Recommended over 4.0 and 3.0. 5.0 keeps the 0603 LEDs (good side visibility, the same LED and
  10 mA as today, so brightness per pixel is unchanged) and leaves a 1.7 mm-tall via band and about 4 mm channels per cell. That room is
  what lets the 64 FFC lines fan in on the back without blind vias. 4.0 mm (128 mm) also fits 0603 but the channels hold only about
  5 lines, so the fan-out would need 6 layers or HDI. 3.0 mm (96 mm) needs 0402 and laser vias. Cost per panel is about the same at
  5.0 and 4.0 (the LED count is fixed and the PCB is about 25 % smaller). At 3.0 HDI dominates. The pitch is close to the old
  panel's 5.2 mm, so content scales almost 1:1.
- **4 layers (JLC 1.6 mm, order 1 oz inner copper).** F.Cu: LEDs, 1.0 mm row bus on the anode line, cathode stubs to one
  0.2/0.45 mm via per LED (1.9 mm below the LED centre, so the bottom row's via keeps 0.35 mm to the edge). In1.Cu: the 32 column lines, straight under
  the vias. In2.Cu + B.Cu: FFC fan-out. Rows go straight up/down on B.Cu in the via channels (8 per channel) to a via on their
  own bus. Columns, ID and GND are maze-routed (`route_full.py`, A* on 0.125 mm grid, real clearance ≥ 0.10 mm).
- **Mounting: SMT M2 standoffs on the back, no front holes.** Four Ø4.2 mm SMD pads on B.Cu between via rows. Suggested parts:
  Würth WA-SMSI/WA-SMSN M2 (blind, flat-bottom) or similar no-hole SMT nuts. Check the exact MPN pad before ordering. PEM SMTSO and the
  LCSC SMTSO clones need a Ø3.7 board hole and are **not** compatible. Hand-solder them or consign them to JLC. The front stays solid LEDs.
- **LED interface standard v1** (`hardware/common/LED_INTERFACE_STANDARD.md`): J_ROW 33/38/40 = GND, 39 (`ID_PRESENT_N`) = GND,
  35/36 = ID_SDA/ID_SCL, 37 = ID_3V3; J_COL 33/38/40 = GND; 34 (and J_COL 34–37, 39) are NC. `U_ID` 24LC02BT-I/OT (0x50,
  pin 4 VCC, pin 5 WP = GND, no pull-ups) and `C_ID` 100 nF on ID_3V3. EEPROM record: class = full-bleed, pitch 5.0 mm,
  `row_path_mohm` = 148 (worst row, panel only), mapping identity.

## Current / IR drop (row = 32 × 10 mA = 0.32 A, `analyze_full.py` → `analysis.json`)

| | |
|---|---|
| Row feed | 0.30 mm × 1 oz on B.Cu, ≤ 80.7 mm (ROW_01) = 132 mΩ; jog sections 0.2 mm |
| Row bus | 1.0 mm × 1 oz F.Cu, fed at one point, worst bus drop 4.6 mV |
| Via | 1.75 mΩ (0.2 mm drill, 1.6 mm) |
| **Worst panel drop** | **47 mV at 20 °C, 55 mV at 60 °C** (target ≤ 100 mV) |
| Temperature rise | 0.3 mm at 0.32 A ≈ 4.6 °C (IPC-2221 external, conservative versus IPC-2152) |

## DRC / fab

- `kicad-cli pcb drc --severity-all`: **0 violations, 0 unconnected** (clearance 0.10, track ≥ 0.15, via 0.2/0.45, copper–edge 0.2).
- `./make_fab.sh` → `mono_panel_32x32_full_fab.zip` (Gerbers F/In1/In2/B, drill, BOM + CPL JLC format).
- **Assembly:** LEDs on top (1024 × C84265). The back has 2 × FH12 (C202114), U_ID (C2655410) and C_ID (C1525), so JLC needs **double-sided assembly**.
  A cheaper option: top-side assembly only, then hand-solder the 2 FFCs + 0402 + SOT-23 (and the standoffs).
- **Price (ESTIMATE, JLC/LCSC list prices, `fab/price_estimate.json`, priced BOM `fab/BOM_mono_panel_32x32_full_priced.csv`):**
  parts ≈ $8.5/board (1024 LEDs ≈ $7.0, 2 × FH12 ≈ $1.24, EEPROM $0.27); 4L 160×160 PCB with 1 oz inner ≈ $70 for 5;
  double-sided SMT setup ≈ $50 + 4 extended-part fees ≈ $12 → **≈ $38 per assembled panel at qty 5, ≈ $23 at qty 30**.
  Top-only assembly with the back parts hand-soldered saves about $25 per order.

## Renders (`renders/`)

`full_front_lit.png` (front, lit), `full_back.png` (back: copper of all layers + parts), `full_kicad_top.png` /
`full_kicad_bottom.png` (KiCad 3D), `full_tiled_3x2.png` (3×2 butted wall, red ticks = seams), `full_seam_closeup.png`, `full_sim_bg.png`.

## Regenerate

```
source ../tools/kicad10_env.sh
python3.11 gen_full.py          # base board + fixed.json
python3 route_full.py           # numpy/scipy maze router -> routes.json (~3 min)
python3.11 gen_full.py routes   # final .kicad_pcb
kicad-cli pcb drc --severity-all --format json -o drc.json mono_panel_32x32_full.kicad_pcb
python3 analyze_full.py && python3 render_full.py && ./make_fab.sh
```
Bring-up sim: `firmware/mono_split/sim/bringup/bringup.py --panel full`.

## Bring-up sim (`--panel full`)

`cable.py --panel full`: Type B gives J_ROW1→J_ROW and J_COL1→J_COL pin 1→1 with 0 net mismatches (Type A mirrors 1→40, 32 errors).
Nominal tests: I2C scan, all on, row walk, column walk, and checkerboard all **PASS** (32/32 rows and columns, 0 LED mismatches). Fault injection: F1 (Type A cable) and F2 (open COL_07) are **caught**.
See `firmware/mono_split/sim/bringup/bench_report_full.md` and `png/bringup_full_*.png`.

## LED Vf bin (order note)

NCD0603W1 (C84265) is sold unbinned on LCSC/JLC (2.6–3.6 V @ 5 mA). The main board's 4.24 V rail allows ≤ 3.38 V at 10 mA, which is about ≤ 3.2 V @ 5 mA. **Order Vf bin 2.8–3.0 V @ 5 mA (preferred) or 3.0–3.2 V; reject > 3.2 V**, one bin per panel. The bin is printed as `VF(V)` on the reel label, and NationStar has no part-number suffix for it. With JLC either consign labelled reels or accept unbinned parts and screen at bring-up. Details: `hardware/common/LED_INTERFACE_STANDARD.md` §5.1.
