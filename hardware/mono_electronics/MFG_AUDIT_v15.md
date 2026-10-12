# mono_electronics v15: manufacturing-standards audit (2026-10-12)

Verdict: **PASS WITH RISKS** after the fixes below. Before this pass, the committed v15 Gerbers would have been **FAIL**: they were plotted from stale zone fills.

## Gates (after fixes)
- DRC (kicad-cli 10.0.7, zones refilled): 0 violations, 0 unconnected. Re-run with the min clearance forced to 0.127 mm: still 0.
- ERC: 0. Schematic netlist vs PCB: 309/309 refs, 0 pin differences. Continuity check: 309/309 PASS. Net names: 224, unchanged.
- Arcs: no free-space bend left un-arced. The only remaining non-arc nodes are 8 T-junctions.

## Defects found
| # | Sev | Defect | Action |
|---|---|---|---|
| 1 | CRITICAL | The board file held stale zone fills. Run without a refill, DRC reported 590 errors (401 via-in-zone, 189 track-in-zone, actual clearance 0.000 mm) on the B.Cu/In2 GND pours, e.g. on COL_19 and RS485_B vias. The committed B_Cu/In2 Gerbers came byte-for-byte from that stale fill: signal vias were shorted to GND. | Fixed: zones refilled and saved, Gerbers and drill files regenerated. |
| 2 | MED | 3 sharp 45° corners in free space, which breaks the arc-only rule: LED_CLK_Y and LED_LE_Y at (104, 73.8/74.4), USB_D_P at (14.25, 11.35). | Fixed: arcs with R = 1.0, 0.8 and 0.2 mm. |
| 3 | MED | Tombstoning risk (IPC-A-610): the GND pad of R_ILIM1, R_ISET1, R_ILM1, R_EN_BOT1 (0402) and C_CHG_SYS1 (0805) was full-connected to the F.Cu GND pour, while the other pad was on a thin trace. | Fixed: those pads now use thermal relief (local override). EPs stay full. |
| 4 | MED | SYS feed to TPS63802 VIN: In1 0.30 mm (0.5 oz inner) plus B.Cu 0.25/0.30 mm, about 0.8 A peak. IPC-2221 internal gives ΔT ≫ 20 °C. | Partly fixed: the 3 In1/B.Cu SYS segments are now 0.45 mm (clearance ≥ 0.15 mm). Still recommend a pour or ≥ 0.6 mm and 2 vias per transition. |
| 5 | LOW | Installation BOM: J_CH1/J_RH1 and the 64 TVS designators were space-separated and unquoted, unlike every other line. | Fixed: quoted, comma-separated. |
| 6 | LOW | README said min track 0.125 mm. The board has 0.10 mm tracks (IMU_SDA ×40 segments, DEC_B_EN_N, etc.). That is OK for JLC 4L (0.09 mm), but the doc was wrong. | README corrected. |
| 7 | MED | No fiducials. IPC/DFA practice wants 3 global fiducials. JLC assembles without them. | Recommendation (adding footprints changes the 309-part gate). |
| 8 | MED | The J_PORT_E1/N1/S1/W1 courtyards cross the board edge by 0.17 mm. Pads are 0.38 mm from the edge (JLC min 0.3). | Order with edge rails (JLC "add rails" or panel) so the connectors are not on a conveyor edge. |
| 9 | MED | No stackup section in the board file. The board thickness is 1.0 mm, but the README hinted at 1.6 mm. | Choose 1.0 mm deliberately (the file is 1.0) and pick the JLC 4L stackup. No impedance control is claimed. |
| 10 | LOW | Silk: 837 lines at 0.12 mm and 8 at 0.10 mm, under the JLC 0.153 mm recommended minimum (may print faint). Text is 1.0/0.15 mm, which is at the JLC minimum. | Recommendation. |
| 11 | LOW | USB protection: U_ESD1 is about 11 mm and D_VBUS1 about 13 mm from J_USB1 (centre to centre). Ideally < 5 mm. | Recommendation for the next spin. |
| 12 | LOW | Decoupling > 3 mm from the pin: U_485 VCC (6.8 mm), U1 pin 20 (5.5 mm), U_LDO1 IN/OUT (4–5 mm), U_CHG1 IN/BAT (4.5–4.8 mm). | Recommendation. |
| 13 | INFO | The CPL is raw KiCad position/rotation and matches the board exactly (0 mismatches). JLC offsets are not applied: check SOT-23/-5/-6, QFN-56, VQFN-24, TSSOP/SSOP, SOIC-8, FFC, JST and USB-C in the JLC preview. | Check before ordering. |
| 14 | INFO | All 63 LCSC codes resolve live (2026-10-12). Low stock: C42462832 (125), MIC1 C50275762 (368), J_BAT1 C265101 (825), Y1 C136083 (867), SN74LV125A (1470), 74HC154 (1830), ESP32-S3FN8 (2482), TPS259531 (2680). The C4961 "600R" line is really 620R. | Buy or reserve before ordering. |

## Follow-up pass (v15b, 2026-10-12): recommendations applied

Canonical standalone project: `projects/mono_electronics_v15/`.

| Item | Result |
|---|---|
| **Spacing ≥ 0.127 mm: correction** | The 0.127 mm re-check in the first pass was **invalid**. The board minimum clearance is stored in the .kicad_pro, and copying the project file back reset it to 0.1. A real 0.127 run found **24 pre-existing violations**: 22 ROW_xx_ANODE In1 track-to-via gaps of 0.120 mm, U_OVP1 pad 6 to VBUS at 0.125 mm, and a SYS arc to a BAT_RAW via at 0.124 mm. **Fixed:** the In1 ROW anode tracks on the 13 affected nets go 0.36 → 0.345 mm (+1.4 mV worst-case row drop, so 105.7 → ~107.1 mV), the VBUS escape from U_OVP1 pin 5 goes 0.5 → 0.3 mm for 0.9 mm, the SYS arc goes 0.26 → 0.25 mm, and 3 unconnected ROW vias now have their inner-layer pads removed. The project min_clearance rule is now 0.127 mm, so DRC 0 enforces it. |
| D_VBUS1 (SMF12A) | Moved from (6.5, 31.2), a stub past the eFuse, to (3.2, 26.6), rotated 270°. It now sits on VBUS_CONN between J_USB1 and U_OVP1, about 1 mm from the J_USB1 courtyard. It has its own GND via, and the 0.6 mm feed has an arc at the U_OVP1 branch. |
| U_ESD1 (USBLC6) | Not moved. It is already 3.2 mm courtyard-to-courtyard from J_USB1; the 11 mm figure in the first pass was centre to centre. It is inline: D+/D- pass through its pins. Moving it closer would mean re-routing the USB pair inside the connector keepout. That is not worth the risk for USB FS. |
| Decoupling | U_485 pin 3 is SHDN (tie-high), not a supply, so that was a false positive; VCC pin 8 has C_485 at 1.6 mm. U1 pin 20 (VDD3P3_RTC) has C_MCU_RTC1 100 nF at 5.5 mm centre to centre. U_LDO1 and U_CHG1 caps are at 3.6–4.8 mm centre to centre (≈2–3 mm pad gap), which is in line with the TI EVM layouts. None of these were moved, because moving them means re-routing dense nets. The risk is accepted. |
| SYS | B.Cu 0.45 → 0.6 mm. The In1 segment stays at 0.45 mm (0.6 mm breaks clearance to LED_LOGIC_EN). A second via was added at each of the 4 layer changes (2 vias per change). |
| Fiducials | FID1 (11.5, 11.0), FID2 (135.0, 96.5), FID3 (8.5, 96.5). 1 mm copper, 2 mm mask opening, ≥ 3 mm from the edge. Board-only and excluded from BOM/CPL. **Part count is now 312 footprints = 309 schematic parts + 3 fiducials.** Continuity: 312/312. sch-vs-PCB: 309/309, with the fiducials excluded as board-only. |
| Silkscreen | 782 lines widened to 0.15 mm. Left as they were: 59 filled polygons (line width is irrelevant there) and 4 segments of C_AC1/R_B1/U_OVP1/R_EN_BOT1, where 0.15 mm would overlap neighbouring silk. |
| J_PORT courtyards | All four connectors moved 0.25 mm inward. Their courtyards are now 0.075 mm inside the edge (they were 0.17–0.2 mm outside). Their tracks and GND stubs were shifted with them. |
| Stackup | Explicit JLC04161H-7628, 1.6 mm: 1 oz outer, 0.5 oz inner, 7628 prepreg 0.2104 mm, core 1.065 mm, ENIG. 1.6 mm was chosen because the FFC (FH12 SMD), JST SMD, box headers and USB-C (TYPE-C-31-M-12, designed for 1.6 mm) are not thickness-limited, it is JLC's standard and cheapest option, and it is stiffer for a 148 × 99.5 mm board. USB FS (12 Mb/s) needs no controlled impedance. For the record, 0.15 mm microstrip over In1 on 0.21 mm 7628 (εr 4.4) is about 62 Ω single-ended and about 100 Ω differential at a 0.15 mm gap (IPC-2141 estimate). It is not impedance-controlled. |
| Gates | DRC 0 at a 0.127 mm minimum, 0 unconnected, KiCad native schematic parity 0 (run from the project folder). ERC 0. compare_sch_netlist 0 differences. Continuity 312/312. Nets 224, unchanged. No B-side parts. Every free-space bend is an arc (8 T-junctions only). |
| Schematic attributes | DNP is set on 71 symbols (64 TVS, J_RH1/J_CH1, 5 × R_EXP) and in_bom no on H1–H4/JP_TERM1, to match the board, which is the wearable default. R_F1 and C_LL_IN1 point to `*_SilkTrim` library copies, because their board instances have one silk line removed. |
| Library | Board footprints now carry the `mono_electronics:` library nickname. 13 library footprints were re-exported from the board, and the Fiducial footprint was added. |
| Abs-max | No part changed. D_VBUS1 still clamps VBUS_CONN (SMF12A, VC 19.9 V vs U_OVP1 IN 20 V abs max). It is now upstream of the eFuse with a shorter path, so it clamps better. Every row in ABSMAX_REVIEW_v13 is unchanged. |
