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
