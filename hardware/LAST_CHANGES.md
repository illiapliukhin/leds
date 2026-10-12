# Latest changes

## mono_electronics v12
- mono_electronics v15: FFC shift. J_ROW1/J_COL1 moved 13.5 mm west, the header/TVS strip is at x 136.8–148 and J_PORT_E1 at y 44, so the board is back to 148.0 × 99.5 mm. ID/EXP/port TVS parts were re-placed. RS-485 was re-routed as a matched pair (skew ≤ 0.03 mm). The default FFC is now 120 mm (C5371276). All gates are clean. Fab v15 has wearable and installation BOM/CPL; the sims were updated (board_v15).
- mono_electronics v14b: installation headers are now XFCN BH127VS-40P-H49 2×20 1.27 mm shrouded, keyed box headers (C42462832; mate IDC3-40232A1EUB1 C49232620 + 0.635 mm ribbon); board 159.45 mm wide (+11.4); gates clean; fab v14 regen.
- mono_electronics v14: installation headers J_RH1/J_CH1 (2×20 1.27 mm SMD, pin n = FFC pin n) + 64 PESD5V0S1BL, all DNP in the wearable build; board 148 → 160.5 mm wide; wearable and installation BOM/CPL; gates clean (DRC 0/0/0, ERC 0, 0 diffs, прозвонка 309/309); fab v14.
- mono_electronics v13d: R_ILM1 reverted to 2.7k (C25885, 0.78 A eFuse limit, under the BQ25185 1.1 A abs max); v13c U_OVP1 thermal copper kept; gates clean; fab v13 regen.
- mono_electronics v13c: R_ILM1 2.7k → 1.6k (C4908), eFuse limit 0.78 → 1.29 A (1.19–1.39 A, TPS2595 Eq.4); U_OVP1 F GND pour 21.5 mm² + 2 thermal vias; gates clean; fab v13 regen.
- mono_electronics v13b: J_BAT1 → JST PH S3B-PH-SM4-TB (2 A/contact, C265101; pack needs PHR-3), battery path re-placed with 1.0 mm copper, gates clean, BOM stock/prices refreshed from JLC API.
- mono_electronics v13: protections — F_BAT1 2 A fuse + Q_BAT1 reverse-battery PFET + 1 mm BAT copper; U_OVP1 TPS259531 eFuse (5.7 V clamp, 0.79 A) + D_VBUS1 SMF12A; BQ25185 GND pour + thermal vias; abs-max review (R_ILM1 2.7k); full check clean (DRC 0/0/0, ERC 0, 0 diffs, прозвонка 243/243), fab v13.
- mono_electronics v12a: every track corner arced (sharp 35, 45° 70, chopped 9, jogs 17, kinks 27 → 0), USB re-matched (skew −0.13/0.19 mm), gates unchanged, fab regenerated.
- LED interface standard v1 on the main board. J_ROW1 spares: GND 33/38/40, ID I²C on 35/36 (33 Ω + PESD5V0S2BT to IMU_SDA/SCL), 100 Ω ID_3V3 from AON_3V3 on 37. J_COL1 spares: GND 33/38/40, DNP 33 Ω taps of U_LED2 SDO / CLK_Y / LE_Y / OE_Y on 34–37, DNP 0 Ω LED_LOGIC_3V3 on 39. Row bleeds not added. DRC 0/0/0, copper 0 < 0.127, no renames, no B parts, LED drop 92.5 mV, B GND stitched; ERC 0, sch-vs-PCB 0 diffs (235 refs). Fab v12 zip/BOM/CPL.

## mono_electronics v11b

- AON LDO → TLV75733P (1 A), 22 µF bulk at ESP32, RC filter on LED_EN, J_USB value fixed, refs renamed to end in a digit (REF_RENAME_v11b.json). DRC 0/0/0, ERC 0, sch-vs-PCB 0 diffs.

## mono_schematic synced to PCB v11

- Regenerated hardware/mono_schematic from the PR #4 PCB (224 parts, 9 sheets incl. stacking and mechanical); generator fixed (pin Y mirror, global labels, lib tables, footprint lib). ERC 0, schematic netlist vs PCB 0 differences.

## mono_electronics v11 phase 1

- Removed the last B GND sliver, DRC now 0 errors / 0 warnings / 0 unconnected (silk cleaned), 3D models for U_GAUGE, U_LED_PWR, J_ROW, J_COL, J_USB.

## mono_electronics v10 (clearances, last arcs, mounting holes)

- C_MIC now 1.4 mm from the MIC1 supply pin (v10b).
- 4 × M2.5 plated mounting holes (GND ring, 5.4 mm pad) in the corners, 3.8 mm from both edges (SW: 3.8/3.5 mm), each with a 3 mm copper keepout rule area and courtyard. Board stays 148.0 × 99.5 mm. MIC1 moved to make room in the NW corner.
- Clearance: every other-net track spacing now ≥ 0.127 mm (was 166 spots < 0.127, min 0.100); spots < 0.15 mm 254 → 113. Done by shrinking crowded vias to the 0.40 mm board minimum, re-pitching the ROW_Y feed band (0.43) and the COL fan (0.43), small track/via moves and local neck-downs (mostly 0.15→0.145).
- 0 unrounded signal bends, 0 chopped corners (arcs 499 → 507).
- Gates: DRC 0 errors / 0 unconnected (14 silk warnings, unchanged), copcheck 0, no renames, no B parts, worst LED drop 92.5 mV, continuity 224/224 PASS.

## mono_electronics v9: track cleanup pass (148.0 × 99.5 mm, 4 layers)

- Every signal/power chain rebuilt from v8's pre-arc state. Collinear segments merged; chopped corners, tiny jogs and non-45° bend segments replaced with straight/45° runs where every change kept ≥0.115 mm to other-net copper. Then all arcs were regenerated (r = 3×w where room, smaller where tight). GND and the USB pair untouched.
- AON_3V3 F escape under U1 pad 29 shifted 0.35 mm off the B LED_SDI line it used to sit on top of (stacked length 6.1 → 1.2 mm; the remainder is the pad itself).
- Segments 1901 → 1841, arcs 550 → 501 (fewer corners after merging). Before arcs: chopped corners 48 → 22, short interior segments 19 → 8, non-45° bend segments 35 → 15. After arcs, 9 unrounded bends remain (signal nets), all pinned between a via, a pad and a neighbour track.
- Gates: DRC 0 errors / 0 unconnected / 14 silk warnings; independent copper-geometry check 0 violations; no copper renames; no parts on B; LED worst drop 92.2 mV; B GND stitched.

## mono_electronics v8: four stacking ports + RS-485, staircases removed, arc corners (148.0 × 99.5 mm, 4 layers)

- **Stacking ports:** J_PORT_N/E/S/W, JST SH SM06B-SRSS-TB (6-pin, 1.0 mm, side-entry SMD, 2.9 mm tall). Each sits 0.55 mm inside its edge with nothing past the outline. All four share one pinout: 1 GND, 2 RS485_A, 3 RS485_B, 4 FRAME_SYNC, 5 PRES_x, 6 GND, so a straight cable mates any port to any port.
- **RS-485:** one THVD1406DR (auto-direction, SOIC-8) on the switched LED_LOGIC_3V3 rail (GPIO21, off by default, zero standby). 100 nF C_485. 120 Ω R_TERM switched in by solder jumper JP_TERM. A/B bussed to all four ports.
- **ESD at every port:** SM712 on A/B and PESD3V3S2UT on FRAME_SYNC/PRES.
- **GPIOs:** RS485_TX = GPIO34, RS485_RX = GPIO33, FRAME_SYNC = GPIO48, PRES_N/E/S/W = GPIO3/47/35/26 (internal pull-downs, no external resistors).
- **Freeing pins:** ROW_A3 moved GPIO33 → GPIO37; ROW_XLAT_OE_N moved GPIO47 → GPIO44 (U0RXD, boot pull-up keeps the translator off).
- **Docs:** pinout, GPIOs and the side-detection / topology-discovery scheme are in MONO_SPLIT_ARCHITECTURE.md § Stacking ports.
- **Stair-stepped joints:** 41 → 0. ROW_04/05_Y on In1 now run as one straight 45° segment each. The existing diagonal via row already left a legal corridor, so no vias had to move.
- **x≈33.9 corner:** B ROW_02_Y was offset 0.3 mm so it no longer ends exactly under the F USB_D_N stub. It was never connected (different layers, DRC clean).
- **Smooth corners:** 550 tangent arcs (KiCad arc tracks, r = 3 × track width where room allows, otherwise the largest that fits). They replace the 45°/90° corners on all signal and power tracks except GND and the length-matched USB pair.
- **Continuity check:** see PROZVONKA.md. 220/220 parts PASS, 0 unconnected; the only single-pad nets are the 16 FFC spares.
- **DRC:** 0 errors, 0 unconnected, 14 warnings (silk only, same as v7).
- **Other gates:** no parts on B, 0 dangling, no copper renamed, LED worst drop 92.2 mV, In2 signal copper 27.2 mm, all B GND pieces stitched.

## mono_electronics v7: all deferred parts placed, continuity check, corner cleanup (148.0 × 99.5 mm, 4 layers)

- **Parts added (top side only):** MAX17048 fuel gauge U_GAUGE + C_GAUGE + R_ALRT (BAT_RAW cell/VDD, shared I2C IMU_SDA/SCL at 0x36, ALRT → GPIO1); MEMS mic MIC1 (Gettop MA-HFA381, custom footprint) + TLV9001 preamp U_AUDIO with bias/gain network (C_AUD, C_MIC, C_AC, R_INB, R_B1, R_B2, C_B, R_F, R_GN, C_GN) on the switched AUDIO_3V3 rail (U_AUDIO_SW moved next to it, C_AUD_SW), output → GPIO4 (ADC1_CH3); board NTC TH_PCB + R_TH divider → GPIO2 (ADC1_CH1); 1 µF VIN caps C_ASW_IN / C_LL_IN at both TPS22917s.
- **Footprint fix:** U_ROW_XLAT (SN74LVC8T245**RHL**R) was on a 4×4 mm VQFN-24; replaced with the correct 3.5×5.5 mm RHL0024A land pattern and rerouted.
- **GPIO changes:** GPIO1 = GAUGE_ALRT_N, GPIO2 = TH_ADC, GPIO4 = AUDIO_ADC (GPIO0_BOOT escape rerouted to free them). Architecture doc GPIO map updated; firmware board_pins.h is not on this branch (patch is in the report).
- **Continuity check:** see PROZVONKA.md: 204/204 parts PASS, every IC powered/grounded/decoupled, 0 unconnected; only single-pad nets are the 16 FFC spares.
- **Track cleanup:** collinear segments merged, stair-stepped/chopped corners replaced with single 45° chamfers (segments 1851 → 1739; interior stair joints 99 → 41, the rest sit on via-limited ROW_04/05_Y In1 runs).
- DRC: 0 errors, 0 unconnected, 14 warnings (silk only). No parts on B; LED worst drop 92 mV (unchanged); In2 signal copper 27.6 mm (unchanged); B GND pieces stitched ≥2 vias.


## Mono electronics v6: feed/riser band compaction, board 148.0 x 99.5 mm (PR #4, 2026-10-10)

- ROW_Y feed band tightened to 0.375 mm pitch; anode/COL riser band and FFC fan scaled to 90 %. J_ROW/J_COL pinout and right-edge exit unchanged.
- Outline 152.9 x 99.5 -> **148.0 x 99.5 mm**. Track length 14.04 -> 13.65 m; worst LED anode drop 95.9 -> **92.3 mV**; In2 signal copper 27.6 mm; B GND pieces all stitched.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 dangling, 0 parts on B; 13 silk warnings. Image: `hardware/mono_electronics/img/v6_F.png`.


## Mono electronics v5: Q_ROW cell rebuild, board 152.9 x 99.5 mm (PR #4, 2026-10-10)

- All 32 Q_ROW cells rebuilt: R_G/R_PU 1 mm closer to the AO3403, drain/Y/R_PU vias moved in; cell width 7.7 -> 6.6 mm. LED_SDI and AON_3V3 locally rerouted in column 1.
- Columns 5-8 moved to 6.8 mm pitch; the east block (gate lines, anode/COL risers, J_ROW, J_COL) moved 6 mm west. J_ROW/J_COL pinout unchanged, still on the right edge.
- Outline 158.9 x 99.5 -> **152.9 x 99.5 mm**. Track length 14.66 -> 14.04 m; worst LED anode drop 100.6 -> **95.9 mV**; In2 signal copper 27.6 mm; B GND pieces all stitched.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 dangling, 0 parts on B; 13 silk warnings. Image: `hardware/mono_electronics/img/v5_F.png`.


## Mono electronics v4: farm compaction, board 158.9 x 99.5 mm (PR #4, 2026-10-10)

- Q_ROW columns 4-8 (with R_G/R_PU) moved to 8.3 mm pitch (was 10 mm) as rigid per-column moves; the east block (gate lines, anode staircase, J_ROW, COL fan, J_COL) moved 8.5 mm west as one piece. J_ROW/J_COL pinout unchanged, still on the right edge.
- Outline 167.4 x 99.5 -> **158.9 x 99.5 mm**. Track length 15.47 -> 14.66 m; worst LED anode drop 107.3 -> **100.6 mV**; In2 signal copper 27.6 mm; B GND pieces all stitched.
- Branding text + star moved to F.SilkS (printed), in the bottom strip, clear of pads.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 dangling, 0 parts on B; 13 silk warnings. Image: `hardware/mono_electronics/img/v4_F.png`.


## Mono electronics: connectors moved west, board 167.4 x 99.5 mm (PR #4, 2026-10-10)

- J_ROW -> (162.4, 22) and J_COL -> (162.4, 68.6): still on the right edge, cable exit right, pinout unchanged. Row fan-in shortened 19.6 mm per net; the COL fan was moved with J_COL as one block.
- Edge.Cuts 187 x 99.5 -> **167.4 x 99.5 mm** (-40.8 % vs. the original 190 x 148). Total track length 16.93 -> 15.47 m; worst LED anode drop 117.6 -> **107.3 mV**.
- GND In2/B clipped and refilled; every B GND piece has >= 2 vias to In2.
- Branding text + star (Cmts.User) moved into the bottom strip inside the board; stale Dwgs.User boxes removed.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 parts on B; 13 silk warnings. Image: `hardware/mono_electronics/img/v3_F.png`.


## Mono electronics: board outline shrunk to 187 x 99.5 mm (PR #4, 2026-10-10)

- Edge.Cuts 190 x 148 mm -> **187 x 99.5 mm** (-9,514 mm2, ~34 %). The south band y 97-148 and the strip x 185-190 were empty; no blocks moved, routing unchanged.
- J_USB stays on the west edge; J_ROW/J_COL end 2 mm from the east edge. No mounting holes on the board.
- GND In2/B pours clipped to the new outline and refilled; 118 stitch vias outside it removed; every B GND piece still has >= 2 vias to In2.
- Obsolete Dwgs.User note "SCAN AND IMU SIGNAL RESERVE" removed.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 parts on B; warnings silk_over_copper 7, silk_overlap 6. Worst LED anode drop 117.6 mV.
- Image: `hardware/mono_electronics/img/v2_F.png`.


## Mono electronics: hand-routed board is now the source of truth (PR #4, 2026-10-10)

`hardware/mono_electronics/mono_electronics.kicad_pcb` was reworked by hand (pcbnew API, one gated change at a time: 0 shorts / 0 crossings / 0 clearance / 0 unconnected, no net relabels, dangling count not increasing, no parts on B.Cu). **The generator output no longer matches this board**; update the generator/schematic from `hardware/mono_electronics/REWORK_LOG.md` before regenerating.

Final state (KiCad 10 DRC, all severities): **0 errors, 0 unconnected**; warnings: silk_over_copper 7, silk_overlap 6. 184 footprints, **all on F.Cu** (single-sided assembly).

Main changes:
- Netlist fixes: USBLC6 pinout (D-, VBUS, GND), **R_CC1/R_CC2 5.1k** CC pull-downs, BMI270 SDO->GND / CSB->VDDIO + 4.7k I2C pull-ups, translator EP->GND. MIC1, U_AUDIO, U_GAUGE, TH_PCB removed (deferred); AUDIO_EN kept.
- Decoupling for MBI5124, 74HC154, LVC8T245, LV125A, BMI270, TPS22917 output, ESP32-S3 (per Espressif guide), 24 nH on XTAL_P; CHIP_PU RC at the pin. All former bottom-side parts moved to the top.
- LED power: LED_4V1 pour on In1, anodes rerouted short on B/F: worst row drop **722 mV -> 117.6 mV** at 0.32 A.
- TPS63802: L/Cin/Cout within ~2 mm, double GND vias, EP vias; output-cap GND -> IC GND **33.6 -> 1.26 mOhm**.
- **In2 = continuous GND plane** (one piece, full outline); signal copper on In2 **4297 mm -> 27.6 mm** (IMU_INT1 19.7 mm, VBUS 7.9 mm, accepted). B GND pour full outline, every piece >= 2 vias, ~260 stitching vias.
- USB D+/D- fully on F, length-matched (A: 57.03/56.93 mm, B: 54.47/54.06 mm). The single crossing is between R_USB_P's pads (topologically required on one layer).
- Reserve pads RP01-RP16 and their stubs removed; LED_CLK/SDI pull-downs moved to the buffer; detours smoothed, duplicate/dangling copper removed.
- Images: `hardware/mono_electronics/img/final_F.png`, `final_In2.png`, `final_mcu_F.png`.


## Mono split boards (PR #4) — clearance gate + one-command generate (2026-10-10)

### Reproduce (single command)

```bash
cd /workspace
source hardware/tools/kicad10_env.sh
env -u PYTHONHOME -u PYTHONPATH \
  /workspace/.kicad10/squashfs-root/usr/bin/python3.11 \
  hardware/tools/generate_mono_split_boards.py
```

Default **`MONO_POST_GRID=1`** runs phases **`gnd,aon_zone,aon,grid_one,cleanup`** via `mono_split_post_grid_finish.py` (subprocess per phase). Aggregate revert in `mcu_grid_route.py` if copper or monotonic (unconnected/clearance) regresses vs pre-post-grid snapshot.

Optional env:

- `MONO_POST_GRID=0` — grid + zone refill only (debug).
- `MONO_POST_GRID_PHASES=...` — override phase list.
- `MONO_EMBED_U1_AON_FANOUT=1` (default) — locked U1 AON stubs/vias at end of `generate_electronics_board`.
- `MONO_PRE_GRID_FANOUT=0` (default) — avoid double fanout before geometry dump.
- `MONO_AON_IN1_KEEPOUT=1` (default) — grid avoids In1 inside AON pocket.
- `MONO_FANOUT_GND_FIXED=0` (default) — optional pre-grid GND fallbacks (`mono_split_copper_utils.GND_STITCH_FIXED_FALLBACK`).

### DRC gate rules (restored)

- Every GND stitch and post-grid step uses **`monotonic_gate_allows`**: 0/0 copper, unconnected non-increasing, **clearance non-increasing**.
- Trial edits apply **in-place** on `mono_electronics.kicad_pcb` with backup restore (KiCad DRC requires the project-linked PCB path; copies under `/tmp` inflate false clearance counts).
- `board_metrics()` refills zones before baseline DRC; post-edit metrics use `refill=False` when refill already ran.

### Committed board target (this pass)

- One-command generate → **`mono_electronics.kicad_pcb`**: **26** unconnected (gate **&lt;24** not met), copper **0/0**, clearance **0** after cleanup.
- **Structural AON fix**: pre-grid U1 fanout (pads **2+3**, **55+56**, **20/29/46** dogbones + vias) embedded in generate; geometry dump logs **locked AON tracks=6**; **In1 AON fill = 1 polygon**, **0** foreign In1 slicers in pocket.
- **ROW_01**: comb on **In2** @ **y=9.7**; west **GND** In2 stub shortened to **y=8.55** (no crossing with ROW_01).
- Post-grid **skips** redundant U1 dogbones (fanout already locked); **`tie_*`** distant AON steps still run under monotonic gate.
- **Diagnostics**: `hardware/tools/aon_zone_diagnostic.py` (zone refill, fill-poly index, foreign In1 slicers in pocket).
- **`grid_one`**: default net list includes **DEC_B_EN_N** (was ROW_A3).

### Panels

`mono_panel_*` remain **0/0/0**; generator restores panel PCBs from git at end of `generate_mono_split_boards.py`.

### Backlog (same DRC gate)

See **`hardware/MONO_ELECTRONICS_BACKLOG.md`**:

1. **Full-board GND zones** on In2/B (extend past 151×137 mm; stitch at J_ROW/J_COL fan-in).
2. **USB-C CC1/CC2** — **5.1 kΩ** pulldowns to GND (sink/UFP) for C-to-C VBUS.

## v11c — FFC cable spec and silkscreen note
- Specified 2 × 40-pin 0.5 mm FFC, **Type B** (reverse / opposite-side contacts), 100 mm, LCSC C2857750 (JS05B-40P-100-4-8). Other lengths: 80 mm C5371275, 120 mm C5371276, 150 mm C2857751, 200 mm C2857752. Added to `MONO_SPLIT_ARCHITECTURE.md` and the annotated fab BOM as an order-separately item. A Type A cable mirrors pins 1↔40.
- F.Silkscreen: "FFC TYPE B" beside J_ROW1 and J_COL1, and "PIN1" at the north (pin 1) end of each. Copper unchanged. DRC 0 errors / 0 warnings / 0 unconnected. The F_Silkscreen gerber was regenerated with the same options (`--no-x2 --subtract-soldermask`) and the fab zip rebuilt.
- v15 check (docs only, no copper change): MBI5124 VDD is on LED_LOGIC_3V3 (3.3 V); Rext 1.82k gives 10.1 mA, which is the datasheet 3.3 V test point and OK. VDD on LED_4V1 is not recommended (VIH 2.97 V vs 3.3 V buffer VOH). The LED rail is 4.24 V (681k/91k) everywhere in the mono docs. NCD0603W1 Vf bin order note added (bin ≤ 3.0–3.2 V @ 5 mA; C84265 is unbinned).

## 2026-10-12: mono_electronics v15b, audit fixes and standalone project
- Canonical standalone KiCad project: `projects/mono_electronics_v15/`. It opens on its own and passes kicad-cli DRC/ERC/parity from that folder.
- Fixes: refilled zones (the earlier v15 Gerbers had GND poured over signal vias), D_VBUS1 next to J_USB1, SYS 0.6 mm with doubled vias, 3 fiducials, silk 0.15 mm, J_PORT courtyards inside the edge, 1.6 mm JLC04161H-7628 stackup, 24 sub-0.127 mm gaps fixed, arcs everywhere. See hardware/mono_electronics/MFG_AUDIT_v15.md.
