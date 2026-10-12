# LED Interface Standard v1 (mono split, 40-pin FFC pair)

One output standard for every LED load driven by the mono electronics board (`hardware/mono_electronics/`): flat 32×32 / 20×20 panels, lattice panels, the full-bleed panel, the garland breakout + wire nets, and future column expansions. Related docs: [MONO_SPLIT_ARCHITECTURE.md](MONO_SPLIT_ARCHITECTURE.md), [GARLAND_REFERENCE_BUILD.md](GARLAND_REFERENCE_BUILD.md), [LED_SCALING_OPTIONS.md](LED_SCALING_OPTIONS.md), [firmware/panel_id](../../firmware/panel_id/README.md), [hardware/garland_breakout](../garland_breakout/README.md).

## 1. Electrical model (unchanged from the board)

- **Rows** `ROW_01…ROW_32`: P-FET high side (`AO3403`) from `LED_4V1`, one row on at a time (1/32 duty), up to **0.32 A per row** (32 × 10 mA).
- **Columns** `COL_01…COL_32`: 2 × `MBI5124` constant-current sinks, ≈10 mA each (set by Rext).
- LED anode → row line, LED cathode → column line. Any load that keeps this polarity and stays within the current/voltage budget in §4 is compliant.

## 2. Connectors and cable

| Item | Value |
|---|---|
| Board side | `J_ROW1`, `J_COL1`: Hirose `FH12-40S-0.5SH`, F.Cu, cable exits east, pin 1 north |
| Load side (panel or breakout) | same part on **B.Cu**, ROW exits west, pin 1 north (the panel footprint is the reference; the garland breakout clones it) |
| Cable | 40-way 0.5 mm FFC, **Type B**, 0.3 mm, stiffened ends, pin 1 → pin 1 |
| Contact rating | 0.5 A/contact (FH12) |

## 3. Pinout (v1 formalises pins 33–40)

### J_ROW (40 pins)

| Pin | Net | Direction (board view) | Rule |
|---:|---|---|---|
| 1–32 | `ROW_01`…`ROW_32` | out, high side | row n on pin n |
| 33 | `GND` | — | reference / ESD return / ID ground |
| 34 | `VLED_SENSE` | in (optional) | load-end tap of `LED_4V1` rail or of ROW_01 far end, for drop diagnostics; NC if unused |
| 35 | `ID_SDA` | I²C | panel ID EEPROM data |
| 36 | `ID_SCL` | I²C | panel ID EEPROM clock |
| 37 | `ID_3V3` | out, ≤ 5 mA | EEPROM supply (from always-on 3V3 so the EEPROM is never back-powered through SDA/SCL) |
| 38 | `GND` | — | |
| 39 | `ID_PRESENT_N` | in | tied to GND on any compliant load; floating = no cable / legacy |
| 40 | `GND` | — | |

### J_COL (40 pins)

| Pin | Net | Direction | Rule |
|---:|---|---|---|
| 1–32 | `COL_01`…`COL_32` | sink | column n on pin n |
| 33 | `GND` | — | |
| 34 | `EXP_SDI` | out | `U_LED2` SDO → expansion MBI5124 chain (reserved, see LED_SCALING_OPTIONS.md) |
| 35 | `EXP_CLK` | out | buffered `LED_CLK_Y` (reserved) |
| 36 | `EXP_LE` | out | buffered `LED_LE_Y` (reserved) |
| 37 | `EXP_OE_N` | out | buffered `LED_OE_Y` (reserved) |
| 38 | `GND` | — | |
| 39 | `EXP_3V3` | out, ≤ 50 mA | logic supply for an expansion (reserved) |
| 40 | `GND` | — | |

Loads that do not implement a function leave the pin **unconnected**, except the three GND pins, which every new load must tie to its ground. Today's 32×32 and 20×20 panels leave 33–40 open; they read as "legacy, no ID" and get the default profile. The 20×20 panel keeps using lines 1–20.

**Why GND on three pins per cable:** long nets collect ESD and common-mode noise. Without a ground in the FFC, the only return for a TVS on the load side is through the LEDs. Three contacts (1.5 A total) are also enough for the EEPROM and any expansion logic.

## 4. Panel ID EEPROM

- Part: any 24C02-class EEPROM, 2 kbit, SOT-23-5 (`24LC02BT-I/OT`), 7-bit address **0x50**, WP tied to GND (writable from the main board for provisioning).
- Main board v12 implements this: J_ROW1 35/36 → 33 Ω (`R_ID_SDA1`/`R_ID_SCL1`) → `IMU_SDA`/`IMU_SCL`, with `D_ID1` PESD5V0S2BT (35 pF dual ESD) on the bus side; J_ROW1 37 → 100 Ω (`R_ID_3V1`) → `AON_3V3`; 33/38/40 → GND; 34 and 39 left open (firmware detects the EEPROM by ACK). J_COL1 33/38/40 → GND; 34–37 → `LED_SDO2`/`LED_CLK_Y`/`LED_LE_Y`/`LED_OE_Y` and 39 → `LED_LOGIC_3V3` through DNP 33 Ω / 0 Ω (`R_EXP_*`).
- Bus: `ID_SDA`/`ID_SCL` join the main board's existing `IMU_SDA`/`IMU_SCL` bus (GPIO8/9). The BMI270 sits at 0x68/0x69, so there is no address clash. Pull-ups stay on the main board; loads carry none, so the bus never ends up with two sets of pull-ups.
- Record: 64 bytes at 0x00, little-endian, CRC-16/CCITT-FALSE. The layout lives in `firmware/panel_id/panel_id.h`; `mkpanelid.py` builds the image. Fields: class (flat / lattice / full-bleed / garland / breakout / expansion), LED type, rows, cols, pitch (0 = freeform), peak LED current, max row current, Vf, mapping (identity / mirror / rot180 / transpose / serpentine / table id), flags, blank ns, pre-discharge ns, scan divider (1 = 960 Hz, 2 = 480 Hz garland mode), row-path resistance, hw rev, serial, name, row/col population masks (for freeform nets).
- Missing EEPROM (no ACK), bad magic or bad CRC → default profile = flat 32×32 white 10 mA identity. Old panels keep working unchanged.

## 5. Current and voltage-drop rules vs. cable length

Headroom budget at 10 mA/LED, white (rail per R_FB_TOP1/R_FB_BOT1 681k/91k: VOUT = 0.5 V × (1 + 681/91) = **4.24 V**; the net is still called `LED_4V1` for history):

| Item | Drop |
|---|---:|
| `LED_4V1` (TPS63802, FB 681k/91k 0.1 %) | 4.24 V |
| P-FET + board copper at 0.32 A (v15 worst row 17: 0.106 V) | −0.11 V |
| MBI5124 output knee (keep ≥ 0.4 V for regulation) | −0.40 V |
| Row wiring design budget (FFC + lead-in + net) | −0.35 V |
| **Allowed LED Vf at 10 mA** | **≤ 3.38 V** |

NCD0603W1 (C84265) Vf: datasheet min/typ/max 2.6/2.8/3.6 V at 5 mA, unbinned. At 10 mA expect about +0.1 V, so worst case is about 3.7 V, which exceeds the 3.38 V allowance. Fit the Vf bins up to 3.0–3.2 V @ 5 mA only (± 0.1 V bin tolerance, ≈ ≤ 3.4 V at 10 mA); see §5.1. Typical parts (2.8 V @ 5 mA ≈ 2.9 V @ 10 mA) leave ≈ 0.5 V spare.

### 5.1 LED Vf bin (order note for every panel BOM)

- NationStar's NCD0603W1 datasheet only defines Vf *classification ranges* at 5 mA / 25 °C: **2.6–2.8 V, 2.8–3.0 V, 3.0–3.2 V** (± 0.1 V). The bin is printed as `VF(V): xx-xx` on the reel label. There is no orderable bin suffix in the part number.
- LCSC/JLC C84265 is sold **unbinned** (listing "2.6V~3.6V"; stock 669,871, $0.016 @500, checked 2026-10-11). JLC cannot guarantee a bin.
- **Spec to order:** NCD0603W1, white, **Vf bin 2.8–3.0 V @ 5 mA preferred, 3.0–3.2 V acceptable; reject > 3.2 V @ 5 mA**, one Vf bin per panel (uniform brightness). For a JLC build either (a) consign reels bought from NationStar/a distributor with the bin on the label, or (b) accept the unbinned C84265 and screen on bring-up: any pixel dimmer at full white on the farthest row means a high-Vf part. Raising the rail is not an option without re-checking the 74HC154/AO3403 gate drive.
- Only one row is lit at a time, so a high-Vf LED loses current only on its own pixel (MBI5124 out of regulation). It does not affect others.

Only the row conductor counts: it carries up to 0.32 A, while each column carries just 10 mA. Drop per metre at 0.32 A (one way):

| Conductor | Ω/m | V/m at 0.32 A | Max length for 0.35 V |
|---|---:|---:|---:|
| FFC 0.5 mm pitch (0.3 × 0.035 mm Cu) | 1.64 | 0.52 | **0.67 m** (use ≤ 0.3 m) |
| IDC ribbon 28 AWG (7/0.127) | 0.23 | 0.074 | 4.7 m |
| 26 AWG stranded | 0.134 | 0.043 | 8.1 m |
| 24 AWG | 0.084 | 0.027 | 13 m |
| Enamelled 0.20 mm | 0.55 | 0.18 | 2.0 m |
| Enamelled 0.30 mm | 0.244 | 0.078 | 4.5 m |
| Enamelled 0.50 mm | 0.088 | 0.028 | 12 m |

Inside a net, the row current is spread along the wire. The far LED sees about **half** the end-fed drop, so a net row wire can be twice as long as the lead-in figure above.

Rules:
1. Lead-in drop plus half the in-net drop must stay **≤ 0.35 V** at the full row current `rows × i_led`. Lower `i_led` (Rext or the EEPROM `i_led_ua` cap) if you need more length; drop scales linearly.
2. Red/amber LEDs (Vf ≈ 2.0 V) have about 1 V more headroom. The table then allows roughly 3× the lengths.
3. Never parallel spare FFC contacts for row current in v1. The 0.32 A single-contact rating (64 %) is fine, and the spares now carry GND/ID.
4. VLED injection at the far end **does not help** a passive multiplexed load: the row switches are on the main board, so remote VLED cannot reach the LEDs without a remote high-side switch. The breakout reserves a `VINJ` terminal for a future active row-repeater only.

## 6. FFC direct vs. breakout

| Use | Link |
|---|---|
| Panel mounted on/behind the electronics board, ≤ 0.3 m | FFC Type B direct (flat, lattice, full-bleed panels) |
| 0.3–0.67 m, rigid mount, no hand handling | FFC is possible but marginal (drop, flex fatigue, no ESD) — prefer breakout |
| Anything that people touch, wire nets/garlands, 0.5–5 m, outdoor or installation | **Garland breakout** + 2×8 IDC ribbon (or soldered wire) — TVS on every line, GND bonding, latching connectors |
| Stationary/installation build without a breakout | **On-board installation headers** (mono_electronics v14): `J_RH1`/`J_CH1` fitted, FFC optional — see §6.1 |
| > 5 m or > 32×32 | Tile more boards over the stacking ports (RS-485 + FRAME_SYNC), keep each board's LED wiring short |

### 6.1 On-board installation headers (mono_electronics v14)

The main board carries two DNP **shrouded, keyed 40-pin IDC box headers** wired **in parallel, pin for pin**, with `J_ROW1` and `J_COL1` (40 signals per cable, same as the FFC):

| Ref | Part | Pins | Position (board mm) |
|---|---|---|---|
| `J_RH1` | XFCN **BH127VS-40P-H49**, 2×20 1.27 mm SMD vertical box header, shrouded with key slot (LCSC C42462832); body 31.75 × 6.0 × 4.9 mm, pads 0.6 × 2.6 mm on ±2.2 mm | **header pin n = J_ROW1 pin n**, n = 1…40: rows 1–32, 33 GND, 34 VLED_SENSE (`ROW_SPARE_34`, no connection on the main board), 35/36 ID_SDA/ID_SCL, 37 ID_3V3, 38 GND, 39 ID_PRESENT_N (`ROW_SPARE_39`, no connection), 40 GND | centre (140.4, 22.78) (v15; v14b: 151.9), key/pin 1 north |
| `J_CH1` | same | **header pin n = J_COL1 pin n**: cols 1–32, 33 GND, 34–37 EXP_SDI/CLK/LE/OE (DNP taps), 38 GND, 39 EXP_3V3, 40 GND | centre (140.4, 68.28) (v15; v14b: 151.9) |
| `D_R01…D_R32`, `D_C01…D_C32` | PESD5V0S1BL (C84374), SOD-882 | one per LED line to GND | two columns east of each header |

- **Mating cable:** XFCN **IDC3-40232A1EUB1** 2×20 1.27 mm IDC socket (LCSC C49232620, polarised to the header key) crimped on 40-way **0.635 mm** flat ribbon (3M 3365/40 or 3756/40 class; stocked by Digi-Key/Mouser, not LCSC). Ribbon conductor n = line n, exactly like the FFC, so the panel ID EEPROM, VLED sense and GND pins ride along.
- **Wearable build:** FFC fitted; headers and TVS DNP. The unpopulated strip is flat; the FFC cables and the `J_PORT_E1` plug lie over it.
- **Installation build:** headers + TVS fitted; FFCs optional. Never plug an FFC panel and a header load at the same time.
- **Row copper:** 0.2 mm in the ≤ 2.7 mm 0.5→0.635 mm fan, 0.25 mm to the TVS; ≈ +11 mV at 0.32 A to the header pins.
- **Board size (v15):** back to **148.0 × 99.5 mm**. J_ROW1/J_COL1 moved 13.5 mm west to x 129.54. The header + TVS strip now sits at x 136.8–148, and J_PORT_E1 is at y 44. FFC rows 17/21–32 and cols 1–13 reach the shifted pads through In1. The ID/EXP/port TVS parts and the RS-485 N→E→W pair were re-placed and re-routed (pair skew ≤ 0.03 mm per leg). Default FFC is now **120 mm** (C5371276). v14/v14b were 160.5/159.45 mm wide.
- **Rejected:** 2×20 2.54 mm (56 mm long) or 2.0 mm (≈ 46 mm) box headers do not fit the ≈ 36 mm of edge above `J_PORT_E1`; fitting them would mean moving `J_PORT_E1` and re-routing the RS-485 port, and/or two header columns (≥ +20 mm). The v14 draft's unshrouded pin header was replaced as requested. The garland breakout's 2×8 2.54 mm wiring needs a passive 2×20 1.27 → 4× 2×8 adapter.

## 7. Compliance checklist for a new load

- [ ] Line n of the load is row/col n of the FFC; mapping deviations go in the EEPROM `mapping`, not in copper.
- [ ] GND on pins 33/38/40 of J_ROW and J_COL; `ID_PRESENT_N` (J_ROW 39) to GND.
- [ ] 24C02 at 0x50 on pins 35/36/37 (J_ROW), 100 nF on `ID_3V3`, WP to GND, no pull-ups.
- [ ] Row-path drop per §5 ≤ 0.35 V; record `row_path_mohm` and `blank_ns` in the EEPROM.
- [ ] Wires longer than about 0.3 m that people can touch: TVS on every line (the breakout does this).
