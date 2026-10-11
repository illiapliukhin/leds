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

Headroom budget at 10 mA/LED, white:

| Item | Drop |
|---|---:|
| `LED_4V1` | 4.10 V |
| P-FET + board copper at 0.32 A | −0.05 V |
| LED Vf (white, 10 mA, worst bin) | −3.10 V |
| MBI5124 output knee (keep ≥ 0.4 V for regulation) | −0.40 V |
| **Left for row wiring (FFC + lead-in + net)** | **≈ 0.55 V**, design to **0.35 V** to keep margin for Vf spread and temperature |

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

The main board carries two DNP connectors wired **in parallel, pin for pin**, with `J_ROW1` and `J_COL1`:

| Ref | Part | Pins | Position (board mm) |
|---|---|---|---|
| `J_RH1` | 2×20 1.27 mm SMD male pin header, JXT-PZ1.27-2X20P-A2 (LCSC C54803356; alt C55020606) | **header pin n = J_ROW1 pin n** for n = 1…40: rows 1–32, then 33 GND, 34 VLED_SENSE (`ROW_SPARE_34`, no connection on the main board), 35/36 ID_SDA/ID_SCL, 37 ID_3V3, 38 GND, 39 ID_PRESENT_N (`ROW_SPARE_39`, no connection), 40 GND | centre (152.2, 21.68) |
| `J_CH1` | same | **header pin n = J_COL1 pin n**: cols 1–32, then 33 GND, 34–37 EXP_SDI/CLK/LE/OE (DNP taps), 38 GND, 39 EXP_3V3, 40 GND | centre (152.2, 68.28) |
| `D_R01…D_R32`, `D_C01…D_C32` | PESD5V0S1BL (LCSC C84374), SOD-882 | one per LED line, to GND (via to the B/In2 GND planes) | two columns east of each header |

- **Wearable build:** FFC fitted, headers and all 64 TVS DNP. Unpopulated pads are flat, the stub is ≤ 16 mm of 0.2–0.25 mm copper (irrelevant at the scan frequencies). The FFC cable still exits east and lies flat over the DNP strip.
- **Installation build:** headers + TVS fitted; the FFCs are optional (remove them from the BOM if no panel is plugged in). Do not plug an FFC panel and a header load at the same time — they are the same lines.
- **Cable:** a 40-way 1.27 mm IDC socket on 0.635 mm flat ribbon (e.g. 3M/Samtec FFSD-20 class). Ribbon conductor n = line n, exactly like the FFC, so the panel ID EEPROM, VLED sense and GND pins ride along. Pins 33/38/40 give three GND returns per cable; for long runs add GND conductors/earth at the far end as in §5.
- **Row copper:** 0.2 mm in the 0.5→0.635 mm fan (≈3 mm long), 0.25 mm to the TVS. The added header path is ≈ 15 mm of 0.2–0.25 mm copper, ≈ 30–36 mΩ, ≈ 11 mV at 0.32 A (worst on-board LED drop stays 92.5 mV to the FFC, ≈ 104 mV to the header).
- **Why 2×20 1.27 mm and not 4 × 2×8 2.54 mm box headers (garland-breakout grouping):** the east edge between the two FFCs is taken by `J_PORT_E1` (y 37–47, cable exits east), so the free edge length is ~36 mm above it and ~51 mm below it. Two stacked 2×8 box headers need 58 mm (courtyard 10 × 29 mm each) and two unshrouded 2×8 2.54 mm headers 43 mm — the row pair does not fit above J_PORT_E without moving that port or putting the headers in two columns (board +23 mm). 2×8 2.0 mm fits but breaks ribbon compatibility anyway. A 2×20 1.27 mm header is one connector per FFC, keeps the FFC pin numbering 1:1 including the ID/GND/sense spares, and fits in a 12.5 mm strip. Trade-off: the 1.27 mm ribbon is finer and the header is unshrouded (unkeyed) — pin 1 is marked on silk; use a keyed socket/strain relief. To reach the garland 2×8 2.54 mm wiring, use a passive 2×20 1.27 → 4× 2×8 2.54 adapter (pin n → line n).

## 7. Compliance checklist for a new load

- [ ] Line n of the load is row/col n of the FFC; mapping deviations go in the EEPROM `mapping`, not in copper.
- [ ] GND on pins 33/38/40 of J_ROW and J_COL; `ID_PRESENT_N` (J_ROW 39) to GND.
- [ ] 24C02 at 0x50 on pins 35/36/37 (J_ROW), 100 nF on `ID_3V3`, WP to GND, no pull-ups.
- [ ] Row-path drop per §5 ≤ 0.35 V; record `row_path_mohm` and `blank_ns` in the EEPROM.
- [ ] Wires longer than about 0.3 m that people can touch: TVS on every line (the breakout does this).
