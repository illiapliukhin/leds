# Garland reference build: 32×32 LED net on thin wire

A "net" or garland is the same multiplexed matrix as a panel, but built from wire instead of PCB. 32 row conductors and 32 column conductors cross, and one LED bridges each crossing. It plugs into the electronics board through the [garland breakout](../garland_breakout/README.md) and follows [LED_INTERFACE_STANDARD.md](LED_INTERFACE_STANDARD.md).

## Wiring diagram

```
 breakout J_R1/J_R2 (rows, anode side, up to 0.32 A)         breakout J_C1/J_C2 (cols, cathode side, 10 mA)
                                                               COL_01  COL_02  COL_03 ...  COL_32
                                                                 |       |       |           |
 ROW_01 ════════════════════════════════════════════════════════╪═[>|]══╪═[>|]══╪═[>|]  ...  ╪═[>|]
                                                                 |       |       |           |
 ROW_02 ════════════════════════════════════════════════════════╪═[>|]══╪═[>|]══╪═[>|]  ...  ╪═[>|]
   ...                                                           |       |       |           |
 ROW_32 ════════════════════════════════════════════════════════╪═[>|]══╪═[>|]══╪═[>|]  ...  ╪═[>|]

  ═  row conductor (thicker, carries the whole row)   |  column conductor (thin)   [>|] LED: anode on row, cathode on column
```

- Row n = header pin n of J_R1 (rows 1–16) / J_R2 (rows 17–32). Column n = pin n of J_C1 / J_C2. Ribbon conductor n = line n.
- Wire crossings must not touch. Rows and columns use insulated (enamelled or clear-PVC) wire and are bared only at the node.
- A freeform net (cube faces, irregular shapes) can leave nodes empty. Record the populated row/col masks and a mapping table id in the EEPROM (`PANEL_FLAG_PARTIAL`, `MAP_TABLE`).

## Materials

| Item | Choice | Why |
|---|---|---|
| Row conductors | **0.30 mm solderable enamelled Cu** (polyurethane, Class 155, "self-fluxing") or 0.3 mm silver-plated Cu in clear PVC/FEP | 0.244 Ω/m. At the full 0.32 A the distributed drop is ≈ 0.04 V/m. Fine for nets up to ~4 m wide. Use 0.5 mm for > 4 m. |
| Column conductors | 0.15–0.20 mm enamelled Cu | 10 mA only. 0.2 mm loses 5.5 mV/m. Thinner wire is nearly invisible. |
| LEDs | 0603 or 0805 single-colour SMD (same bin for the whole net), or 2 mm "micro" fairy LEDs with leads | Vf spread matters: one bin per net. |
| Lead-in | 2×8 IDC ribbon 28 AWG (0.23 Ω/m), ≤ 3 m from breakout to net (0.22 V at 0.32 A) | Latching, cheap. For > 3 m, solder 24–26 AWG pairs into the IDC socket, or tile more boards. |
| Strain relief | Silicone sleeve + hot glue at each net edge; cable ties at the breakout | |

## Building it

1. **Jig:** pegboard or 3D-printed frame with 32 × 32 pins at the target pitch (e.g. 25–50 mm). Lay all column wires first, run row wires over them, and keep the layers 1–1.5 mm apart at each node with a printed spacer comb.
2. **Strip at the node:** with solderable enamel, a 380–400 °C iron and a solder blob burns off ~2 mm of enamel at each node on both the row and column wire. With PVC wire, window-strip 2 mm.
3. **Solder the LED** across the gap: anode pad to the row wire, cathode pad to the column wire. Orientation check: every cathode mark points to the column wire. Test every finished row with a 3 V coin cell + 1 kΩ before moving on.
4. **Seal** each node with a drop of UV-cure clear resin. This gives strain relief and covers the bare copper.
5. **Terminate** the 32 row ends and 32 column ends at the net edge into two IDC sockets per group (ribbon conductor n = line n), or solder directly into the breakout headers.
6. Program the net's EEPROM. The breakout's `U_ID` carries it: run `mkpanelid.py --preset garland32` and set masks, mapping and measured `row_path_mohm`.

## Max length vs. voltage drop

Budget 0.35 V for (lead-in + ½ × net row wire) at `I_row = cols × i_led` (see standard §5):

| Lead-in (28 AWG ribbon) | Net row wire 0.3 mm (distributed) | Total drop at 0.32 A | Verdict |
|---|---|---:|---|
| 0.5 m | 1 m | 0.037 + 0.039 = 0.08 V | ok |
| 1.5 m | 2 m | 0.11 + 0.08 = 0.19 V | ok |
| 3.0 m | 2 m | 0.22 + 0.08 = 0.30 V | ok, near limit |
| 3.0 m | 4 m | 0.22 + 0.16 = 0.38 V | reduce `i_led` to 8 mA (0.30 V) or use 0.5 mm rows |
| 5.0 m | any | > 0.37 V | tile another board closer to the net |

Red/amber nets have ~1 V more headroom, so these lengths can be roughly tripled.

## Ghosting, crosstalk and capacitance on long wires

Per row line the capacitance is the LEDs plus the wire: 32 × ~20 pF (small LED junctions at 0 V) + ~50–100 pF/m lead-in ribbon ≈ **0.7–1 nF** at 3 m. A column line is about the same. Effects:

- **Upper ghost (previous row bleeds into the next row's data):** when row n turns off, its long line stays charged at ~4 V, because nothing on the board pulls rows down. When the column data for row n+1 is enabled, that charge flows through row n's LEDs. The pixels of row n that match row n+1's pattern flash faintly.
- **Lower ghost / smear:** when row n+1 rises, the "off" columns' capacitance charges through row n+1's LEDs. Charge per event is ~1 nF × 2 V = 2 nC, against ~300 nC for a lit pixel's row slot (10 mA × 30 µs). That is < 1 %, normally invisible.
- **Crosstalk in ribbon:** adjacent-conductor coupling ~50 pF/m. Row edges are slow (FET gate RC, µs), so coupling into column lines stays well below an LED's turn-on threshold. Keep rows and columns in separate ribbons (the breakout already splits them).
- **Ringing / ESD:** long wires are antennas and get touched. The breakout clamps every line with a 5 V TVS to GND, which must be bonded to the installation earth (mounting holes or `J_INJ` pin 1).

### Firmware mitigation (parameters come from the EEPROM)

1. **Blanking:** `LED_OE_N` high → deselect rows (both `DEC_x_EN_N` high) → change address → re-enable the decoder → wait → `LED_OE_N` low. Defaults: `blank_ns` = 2 µs for panels, **3 µs** for garlands (`garland32` preset). 3 µs is plenty: the 74HC154 outputs drive the AO3403 gates push-pull through 33 Ω, so the FET edge is well under 100 ns, and a 3 m ribbon's round trip is about 30 ns. The margin covers ringing and the MBI5124 OE delay.
2. **Pre-discharge slot:** with *no* row selected, latch all-ones into the MBI5124s and pulse OE for `predischarge_ns` (1 µs garland preset; draining ~1.5 nC through up to 32 × 10 mA sinks takes well under 1 µs). The previous row's line capacitance drains through the column sinks down to the LED knee. The energy is ~nJ, which is not visible. Then latch the next row's data while still blanked.
3. **Order:** OE off → rows off → pre-discharge pulse → latch next data → address → row on → wait `blank_ns` → OE on.
4. **Scan rate and brightness cost.** The v13 firmware scans 32 rows at **960 Hz**, so each row slot is **32.55 µs**. Blank and pre-discharge overhead comes straight out of the slot:

   | Mode | Frame rate | Row slot | Overhead per row | Brightness loss |
   |---|---:|---:|---:|---:|
   | Panel (default) | 960 Hz | 32.55 µs | 2 µs blank | 6.1 % |
   | Garland at panel rate (not recommended) | 960 Hz | 32.55 µs | 3 + 1 µs | 12.3 % |
   | Old garland preset at 960 Hz (8 + 1.5 µs) | 960 Hz | 32.55 µs | 9.5 µs | 29.2 % |
   | **Garland scan mode (proposed)** | **480 Hz** | **65.1 µs** | **3 + 1 µs** | **6.1 %** |

   **Garland scan mode: 480 Hz.** The EEPROM field `scan_div` = 2 asks firmware to halve the LCD_CAM row clock. That gives each row 65.1 µs, so the long-wire overhead costs the same 6.1 % as a panel at 960 Hz. Peak current and the 8-bit BCM depth are unchanged. The BCM LSB doubles to ≈0.25 µs, which is easier for 3 m wires with ~1 nF per line. 480 Hz is still far above visible flicker. Phone cameras with fast shutters may show faint banding, which is the reason to keep 960 Hz for panels. Average brightness per LED stays the same, since duty is still 1/32 minus overhead.
5. If ghosting persists: add 10 kΩ row bleed resistors (listed as an optional main-board change in LED_SCALING_OPTIONS.md), or lower the frame rate so the row slot gets longer.

## Bigger installations: tiling over the stacking ports

- One electronics board + one breakout + one 32×32 net = one **tile**. Tiles connect board-to-board with the 6-pin JST SH stacking cables (RS-485 A/B, `FRAME_SYNC`, `PRES`, GND).
- **Topology discovery** (PRES token walk, MONO_SPLIT_ARCHITECTURE.md) gives each board its grid position and rotation. The panel ID EEPROM supplies each tile's size, mapping and current limits. The leader builds the global canvas from both.
- **Cube:** 6 tiles, one per face. Each board links to 4 neighbours, so the faces form a ring of 4 plus top/bottom. Face rotation comes out of the PRES side detection.
- **Long runs between boards:** RS-485 runs tens of metres on twisted pair (use an SH-to-twisted-pair pigtail, and close `JP_TERM` only at the chain ends). `FRAME_SYNC` is single-ended 3.3 V CMOS: keep it ≤ 1 m. Beyond that, leave it disconnected and sync from an RS-485 broadcast timestamp (frame start = broadcast + fixed latency; ±20 µs jitter is invisible).
- **Power:** each tile has its own LED supply. Do not chain VLED between tiles. Tie all tile grounds together via the stacking GND and a common earth point for ESD.
