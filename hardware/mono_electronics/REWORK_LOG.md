# Rework step 1: netlist fixes (2026-10-10)
Backup: mono_electronics.step0.kicad_pcb. Result: mono_electronics.kicad_pcb. Machine-readable: rework_routes.json (step JSONs in rw/).
DRC before: 0 unconnected / 0 shorts / 0 crossing / 0 clearance (1 pre-existing hole_to_hole GND/GND @32.5,8.88-9.2)
DRC after:  the same. Warnings: silk_overlap 23->29, silk_over_copper 12->13, silk_edge_clearance 0->2 (ref text of R_SDA/R_SCL near the top edge). The four removed parts took 21 pads off the board.

| step | change | routing |
|---|---|---|
| 01_esd | U_ESD p4 GND->USB_D_N, p5 GND->VBUS. Removed the GND stub and via at 17.14,12.5 (it sat between p4 and p5) | D-: p3->p4 link under body at y12.95, then flow-through p4->(17.137,13.65)->east to R_USB_N. VBUS: p5->F 0.25->via 18.45,12.0->In2 0.25 vertical to the VBUS In2 track at y24.0 (C_USB1) |
| 03b_cc | +R_CC1, R_CC2 5.1k 0402 @ (11.9,19.25)/(11.9,20.35), rot 0, just outside the J_USB courtyard (x<=10.7). Nets USB_CC1/USB_CC2 | CC1: A5->F straight y19.25. CC2: B5->via 3.45,16.25->B 45deg->y20.35->via 10.6,20.35->pad. GND: 0.25 dogbones to vias at 13.0 |
| 05_imu_sdo | U_IMU p1 SDO->GND (addr 0x68) | F dogbone to GND via 60.0,4.25 |
| 06_imu_csb | U_IMU p12 CSB->AON_3V3 (=VDDIO) | F 62.85,3.49->y2.9->AON vertical x64.2 |
| 07_i2c_pullups | +R_SDA, R_SCL 4.7k 0402 @ (61.3,1.2)/(63.3,1.2), rot 0, pad1=signal, pad2=AON_3V3 | short F stubs to pad14 / SCL via; AON 0.2 bus y0.65 into AON x64.2 |
| 08_xlat_ep | U_ROW_XLAT EP(25)->GND | No via fits (In2 ROW_05..08_Y run under the EP). F 0.15 bridge from EP to GND pad 10, whose existing F tracks go to the GND vias |
| 09_remove_unwired | Deleted MIC1, U_AUDIO, U_GAUGE, TH_PCB (DEFERRED) | none |

Verified, no change needed: BMI270 VDD (p8) and VDDIO (p5) both on AON_3V3; GND/GNDIO p6/p7 on GND; U_ESD p2 GND (with via). BMI270 p2/3 (ASDx/ASCx), p9 (INT2), p10/11 (OCSB/OSDO) left unconnected, which Table 22 allows (DNC, and ASDx/ASCx must not go to GND).

Deferred parts:
- MIC1 (analog mic) + U_AUDIO (preamp): the architecture doc assigns them no GPIO/ADC pin and gives no gain network values, so the intent is unclear.
- U_GAUGE (MAX17048): the intent is plausible (I2C + CELL/VDD to BAT), but the datasheet isn't in the cache (download failed), the ALRT GPIO isn't assigned, and the footprint (Texas WSON-8 2x2) is unverified against the MAX17048 TDFN-8. Re-add it once the datasheet is cached.
- TH_PCB (NTC): no ADC pin and no divider defined.
- AUDIO_3V3 / AUDIO_EN nets still exist (U_AUDIO_SW and its In1 track remain). Decide when audio comes back.

# Rework steps 2+3 (2026-10-10)
Backup: mono_electronics.step1.kicad_pcb. Steps in rw2/. Every step gated: 0 shorts / 0 crossings / clearance not above baseline (1 pre-existing GND-GND hole_to_hole) / 0 unconnected.
DRC before: 0/0/0/0. After: 0/0/0/0. New warnings: starved_thermal 2 (B pads of C_MCU_RTC, C_MCU_CPUB), silk_overlap 29->79, silk_over_copper 13->30 (ref text, to clean up in the silk pass).

| ref | value | side | pos | rot | for pin | cap pad-to-pin mm |
|---|---|---|---|---|---|---|
| C_LED1_V | 100n | F | (90.1,71.427) | 90.0 | U_LED1.24 | 1.62 |
| C_LED2_V | 100n | F | (110.492,72.295) | 0.0 | U_LED2.24 | 1.43 |
| C_DECA_V | 100n | F | (90.88,10.925) | 0.0 | U_DEC_A.24 | 1.54 |
| C_DECB_V | 100n | F | (106.4,10.445) | 90.0 | U_DEC_B.24 | 1.54 |
| C_XLAT_A | 100n | F | (66.813,12.558) | 90.0 | U_ROW_XLAT.1 | 1.27 |
| C_XLAT_B | 100n | F | (68.27,11.325) | 180.0 | U_ROW_XLAT.24 | 1.24 |
| C_BUF_V | 100n | F | (65.95,71.17) | 90.0 | U_LED_BUF.14 | 2.63 |
| C_IMU_VDD | 100n | F | (64.75,5.73) | -90.0 | U_IMU.8 | 1.14 |
| C_IMU_VIO | 100n | F | (62.33,6.65) | 0.0 | U_IMU.5 | 1.14 |
| C_LL1 | 1u | F | (22.6,60.57) | 90.0 | U_LED_LOGIC.6 | 1.46 |
| C_LL2 | 100n | F | (23.65,61.53) | -90.0 | U_LED_LOGIC.6 | 2.51 |
| C_MCU_A3 | 100n | F | (47.32,5.175) | 180.0 | U1.3 | 1.39 |
| C_MCU_A2 | 1u | F | (49.246,5.209) | 0.0 | U1.2 | 1.47 |
| C_MCU_RTC | 100n | B | (41.15,10.35) | 90.0 | U1.20 | 1.49 |
| C_MCU_SPI | 1u | F | (45.238,17.093) | -90.0 | U1.29 | 3.67 |
| C_MCU_CPU | 100n | F | (53.147,9.208) | 0.0 | U1.46 | 3.9 |
| C_MCU_CPUB | 100n | B | (51.63,10.15) | 0.0 | U1.46 | 2.12 |
| C_MCU_DA1 | 100n | B | (50.98,6.4) | 0.0 | U1.55 | 1.76 |
| C_MCU_DA2 | 1u | B | (49.02,6.9) | 0.0 | U1.56 | 0.5 |
| L_XTAL | 24nH | F | (51.25,8.0) | 0.0 | U1.54 | 1.34 |
| R_CHIP_PU | 10k | B | (47.83,3.9) | 0.0 | U1.4 | 2.66 |
| C_CHIP_PU | 1u | B | (46.4,6.3) | 90.0 | U1.4 | 1.02 |

Notes:
- U1 decoupling: F caps where they fit; B-side caps fed from the pin escape vias where F was full (DA1/DA2 on the 55/56 via, RTC on the pin-20 via, CPUB on the pin-46 via). C_MCU_SPI (pin 29, VDD_SPI) and C_MCU_CPU (pin 46) are about 4 mm away: there's no F spot within 2.4 mm and no via spot near pin 29 (B LED_SDI/CLK/LE plus In2 ROW_06..08_Y). The pin-46 B cap makes up for it; pin 29 is still a deviation. C_MCU1 (10u) stays as the bulk cap about 5 mm SW.
- XTAL: XTAL_N rerouted SE (49.44,8.6)->(52,8.6)->(54.15,6.45), which opens a 1.48 mm gap between the P and N lines. L_XTAL 24nH sits in series at pin 54. No GND guard ring added yet.
- CHIP_PU RC moved to B, directly under pin 4: R 10k to the AON via (48.2,5.3), C 1u into the B GND pour. Removed the 25 mm route on B/In1.
- Step 3: KEEP U1 at (46,10). Evidence: total Manhattan wire demand from the 23 U1 signal nets to their 53 far pads is 3604 mm at (46,10) vs 3590 mm at (52,94), so there's no gain. Moving would mean re-routing every MCU net, moving USB/XTAL/IMU/XLAT, and doing step 4 first. Instead the area was decongested locally (CHIP_PU route removed, XTAL lines separated). Step 4 not done.

# Rework step 4 + single-sided assembly fix (2026-10-10)
Backup: mono_electronics.step23.kicad_pcb. Steps in rw4/. The gate now also fails if any footprint is on B.Cu (step.sh counts them in try.kicad_pcb).
## Single-sided assembly
- Removed the 6 bottom parts and their bottom copper (rw4/b_remove).
- Moved C_MCU_A3 to a vertical position at (48.0,4.82) to clear pin 4. CHIP_PU now runs straight up from pin 4 to C_CHIP_PU 1u at (46.4,3.0) and R_CHIP_PU 10k (rot 90) at (47.4,1.95). The R's AON side is an F track to C_MCU_A2.
- C_MCU_DA2 1u at (51.13,6.98), for pin 56, 1.7 mm away. C_MCU_DA1 100n at (50.78,5.52), for pin 56, 2.3 mm away.
- C_MCU_RTC 100n at (38.0,11.5), on the west AON F trunk. This is about 4.6 mm from pin 20 (feeds through the AON escape via and In1 AON zone). The west face had no closer spot.
- C_MCU_CPUB dropped. Pin 46 keeps C_MCU_CPU (top, 3.9 mm).
- Final count of B-side footprints: 0.
## Step 4: LED anode path
- All 32 ROW_nn_ANODE routes rebuilt (old route: 0.15 mm, In2 south to y 104-120, In1 east, In2 north; 250-310 mm each).
- New route: drain -> 0.4 F stub -> via (x0+2.6) -> B drop 0.3 -> B lane 0.2 in the free gaps between transistor rows -> B vertical 0.4 at X=137.6+0.6*i -> via -> F 0.3 straight to the J_ROW pin.
- Lanes are packed 0.35 pitch. Gap1 y30.85-34.35 has row1 all + row2 c0-2. Gap2 has row2 c3-7 + row3 c1-5. Gap3 has row3 c0,6,7 + row4 all.
- The east verticals are sorted by lane depth so there are no crossings. The J_ROW pinout and position are unchanged.
- Prep moves: the LED_4V1 In1/In2 transition vias at (89.5,32.4) and (109.2,32.4) moved to y 35.3. The LED_SDI lower vertical (x 52.15, y 50-68.5) moved from B to In2.
- LED_4V1 pour on In1, outline (26,22)-(140,66), 0.2 clearance, plus 8 new LED_4V1 vias at TPS63802 VOUT, C_LED1/2 and along the F feed.
- Side effect: the B GND pour is now cut by the 3 lane bands and the east verticals. In2 carries the GND reference, and it lost about 5 m of old anode copper.
## IR drop (copper only, 0.32 A; 1 oz outer, 0.5 oz inner, 1 mOhm/via; In1 pour solved as a resistive mesh)
| row | before src+anode mOhm | before mV | after src mOhm | after anode mOhm | after mV |
|---|---|---|---|---|---|
| 1 | 316+1938 | 722 | 29.8 | 336 | 117 |
| 2 | 277+1875 | 689 | 26.9 | 309 | 108 |
| 3 | 257+1811 | 662 | 24.1 | 283 | 98 |
| 4 | 244+1747 | 637 | 21.3 | 256 | 89 |
| 5 | 234+1684 | 614 | 18.7 | 229 | 79 |
| 6 | 227+1620 | 591 | 16.4 | 203 | 70 |
| 7 | 220+1556 | 568 | 14.3 | 176 | 61 |
| 8 | 214+1492 | 546 | 12.6 | 149 | 52 |
| 9 | 293+1878 | 695 | 8.9 | 327 | 108 |
| 10 | 253+1814 | 662 | 9.3 | 302 | 100 |
| 11 | 234+1751 | 635 | 9.8 | 278 | 92 |
| 12 | 221+1687 | 610 | 10.2 | 271 | 90 |
| 13 | 211+1623 | 587 | 10.4 | 245 | 82 |
| 14 | 203+1560 | 564 | 10.9 | 218 | 73 |
| 15 | 196+1496 | 542 | 11.2 | 191 | 65 |
| 16 | 191+1432 | 519 | 11.3 | 165 | 56 |
| 17 | 291+1818 | 675 | 8.7 | 359 | 118 |
| 18 | 252+1754 | 642 | 9.3 | 316 | 104 |
| 19 | 232+1690 | 615 | 10.0 | 291 | 96 |
| 20 | 219+1627 | 591 | 10.4 | 267 | 89 |
| 21 | 209+1563 | 567 | 10.8 | 242 | 81 |
| 22 | 201+1499 | 544 | 11.6 | 217 | 73 |
| 23 | 195+1436 | 522 | 12.2 | 206 | 70 |
| 24 | 189+1372 | 500 | 12.1 | 179 | 61 |
| 25 | 314+1758 | 663 | 10.5 | 355 | 117 |
| 26 | 275+1694 | 630 | 10.8 | 331 | 109 |
| 27 | 256+1630 | 603 | 11.8 | 306 | 102 |
| 28 | 242+1566 | 579 | 12.6 | 281 | 94 |
| 29 | 233+1503 | 555 | 13.2 | 256 | 86 |
| 30 | 225+1439 | 532 | 13.6 | 231 | 78 |
| 31 | 218+1375 | 510 | 13.6 | 206 | 70 |
| 32 | 213+1312 | 488 | 13.2 | 182 | 62 |
GND return, MBI5124 pad 1 -> TPS63802 GND: 25.7 mOhm (8 mV at 0.32 A).
Step 5 (TPS63802 hot loop) not done.

## Step 4b/5/6 (2026-10-10)
- Courtyards: C_MCU_A2 -> (49.15,4.90) rot90, GND via (49.15,3.75), old via (50.326,5.209) removed; R_CHIP_PU -> (47.40,1.40) rot90, AON re-run x=48.575 (0.15 mm).
- Silk: Reference hidden on 25 rework-added 0402 parts (refs remain on F.Fab).
- Step 5 TPS63802: L_LED (37.2,48.0) rot90; C_SYS (37.6,45.4); C_LED1 (37.6,50.5); C_LED2 (37.6,52.95), all rot0. SW_L1/SW_L2 now 1.6 mm, 0.3 mm. EP: 2 GND vias + pad3/pad8 tie. F GND spine 0.6 mm x=38.9 joining Cin/Cout GND, 6 GND vias in pairs. Old C_LED/C_SYS/SW/GND copper removed, also F LED_4V1 y=53.2 east run (pour feeds).
- Step 6: GND zones In2 and B extended to the full board outline; 256 GND stitching vias (8 mm grid, 12 mm inside the In1 power pours); LED_OE_Y, BAT_RAW, TS_MR In2 segments moved to In1 (13 mm).
- Actions: rw5/*.json (court, court2, silk1, tps, tps2, gndzone, stitch, migrate)

## Step 7: In2 clearing (2026-10-10)
- LED_OE_Y: removed the 2 redundant vias at In1 corners (92.3,71.4),(111.45,71.4).
- swap1: 2.82 m of In2 signal chains moved whole to B/F/In1 (no new vias). split1: long In2 segments split by layer with 53 vias (0.67 m). ast1/ast2/ast3/ast4: detour reroutes (3-layer maze search in a +/-6..18 mm window per segment, 0.2 mm grid, 0.17 mm clearance) for the rest. dd1..dd5: removed vias left single-layer.
- Result: In2 signal copper 4297 mm -> 30 mm (VBUS 7.9, IMU_INT1 19.7, ROW_XLAT_OE_N 2.8). In2 GND = 1 piece.
- Backups: mono_electronics.step56 / s7a..s7e / step7 .kicad_pcb. Actions in rw6/.

## Step 8 (2026-10-10)
- Gate additions: net-relabel check (netcheck.py, catches hidden shorts) and dangling count must not rise.
- USB: D-/D+ MCU side all on F; D- crosses D+ between the R_USB_P pads; R_USB_N moved to (33.40,8.60) rot180; 4-bump meander on D+; GND guard tracks + GND via pair at (32.5,8.88/9.2) removed (clears old hole_to_hole). D+ 57.03/54.47 mm, D- 56.93/54.06 mm (A/B rows).
- ROW_XLAT_OE_N In2 piece -> F. IMU_INT1 left on In2 (19.7 mm): In1 path splits the AON_3V3 pour, B/F blocked.
- Tidy: smooth.py (2 passes) -71.3 mm, hop.py removed 3 layer hops (6 vias).
- B GND: all 9 pieces now have >=2 GND vias (4 vias added).
- RP01..RP16 deleted with stubs (~2.6 m copper, ~80 vias). R_CLK_PD / R_SDI_PD moved next to U_LED_BUF inputs (capplace), west In1 stubs removed.
- Dangling tracks/vias cleaned to 0; 74 contained duplicate segments removed; track widths 0.099998 fixed to 0.100.
- Silk: refs hidden on R_USB_N/P, C_XTAL1/2, C_MCU1, R_BOOT0, TP1, C_LED1/2, C_SYS, L_LED, R_CLK_PD, R_SDI_PD.

## Step 9 / final (2026-10-10)
- U_ESD rotation NOT done: the D+/D- crossing is topological on a single layer. J_USB pin order (B6 D+ top, B7 D- bottom, A/B rows interleaved) forces D+ to exit north; ESP32 pins 25 (D-) / 26 (D+) put D- north. Any one-layer route needs one crossing; rotating U_ESD only moves it between J_USB and U_ESD. Kept the crossing between R_USB_P's pads (0402 bridge), pair all on F, matched to 0.1/0.4 mm.
- Final DRC (KiCad 10, all severities): 0 errors, 0 unconnected; warnings: silk_over_copper 7, silk_overlap 6. R_CC1/R_CC2 5.1k to GND on CC1/CC2 present. 0 footprints on B.Cu (184 total).

## Step 10: outline shrink (2026-10-10, not committed)
- Content bbox (courtyards, pads, tracks, vias; excluding pours and free GND stitch vias): x 1.23-185.0, y 0.47-97.15. Only empty area: y 97-148 (just stitch vias) and x 185-190.
- No block moves (no clean empty bands inside the content). Edge.Cuts 190x148 -> 187x99.5 mm (square corners, no mounting holes on the board). J_USB stays on the west edge, J_ROW/J_COL 2 mm from the east edge.
- GND In2/B zone outlines clipped to 0.5..186.5 x 0.5..99.0; 118 stitch vias outside removed; LED_4V1/AON already inside.
- Removed obsolete Dwgs.User note "SCAN AND IMU SIGNAL RESERVE" (reserve pads deleted in step 8).

## Step 11: connectors west (2026-10-10, not committed)
- J_ROW moved 19.6 mm west to (162.4, 22); its 32 F fan-in tracks shortened by 19.6 mm each.
- J_COL moved to (162.4, 68.6) (19.6 mm west, 6.6 mm south); the COL fan (In1 run, B riser, F stub) shifted rigidly 19.6 mm west, with the riser tops 6.6 mm lower so they clear the anode B lanes (x <= 156.2, y <= 58.35).
- Edge.Cuts 187 x 99.5 -> 167.4 x 99.5 mm; GND In2/B clipped; 21 + 27 stitch vias in moved/cut areas removed; B GND pieces all still >= 2 vias.
- Branding (Cmts.User text "PCB CREATED BY ILLIA PLIUKHIN" + star) moved into the free bottom strip at x=40, y=96-98.7 (no parts or pads below y=93.5, board not grown). Stale Dwgs.User boxes and notes removed (12 lines, "BRANDING KEEPOUT", "MCU PIN ESCAPE").
- Full DRC: 0 errors, 0 unconnected, 13 warnings (silk_over_copper 7, silk_overlap 6), 0 parts on B.

## Step 12 (not committed): farm compaction, chunk 1 (v4 candidate)
- Backup: mono_electronics.8f7db55.kicad_pcb (committed v3). Result: mono_electronics_v4.kicad_pcb (= cur.kicad_pcb).
- Q_ROW farm columns 3..7 (Q_ROW04..08, 12..16, 20..24, 28..32 with their R_G/R_PU) brought to 8.3 mm pitch (was 10 mm). Done as a rigid per-column translate (elastic_apply.py: every cell keeps its own copper; In1 feeds and B anode lanes are horizontal, so they only get shorter). Everything east of x=125 (gate verticals, anode staircase, J_ROW, COL fan, J_COL, east edge) moved 8.5 mm west as one block.
- LED_4V1 B feed at x=89.5: bottom via moved from y 31.69 to 31.2, clear of the shortened ROW_05_ANODE lane.
- Outline 167.4 x 99.5 -> 158.9 x 99.5 mm. DRC: 0 errors, 0 unconnected, 0 dangling, 13 silk warnings. Worst LED drop 107.3 -> 100.6 mV.
- v4 accepted. Branding (text + 10-line star) moved from Cmts.User to F.SilkS so it is printed; no new silk warnings (clear of pads). DRC: 0 errors, 0 unconnected, 0 dangling, 13 silk warnings (7 silk_over_copper, 6 silk_overlap, pre-existing). 0 parts on B.

## Step 13 (not committed): farm cell rebuild + compaction (v5 candidate)
- Backup: mono_electronics.v4.f546b57.kicad_pcb. Result: mono_electronics_v5.kicad_pcb.
- Chunk A, cell rebuild (all 32 cells): R_G/R_PU moved 1.0 mm toward the transistor (R center x+4.2 -> x+3.2), drain via x+2.6 -> x+1.9, Y via x+5.55 -> x+4.45, R_PU rail via x+4.71 -> x+3.71. Cell width 7.7 -> 6.6 mm. Column-1 fixes: LED_SDI rerouted (B 43.45 -> 45° -> B x=46.5 -> via -> F y=66.53); AON_3V3 B vertical moved 49.49 -> 48.9; one stray ROW_17_ANODE via deleted.
- Chunk B: columns 5-8 (Q_ROW05-08, 13-16, 21-24, 29-32) moved to 6.8 mm pitch, rigid per column. East block (gate verticals, anode/COL risers, J_ROW, J_COL; for y>=69 only x>=119) moved 6.0 mm west. 9 duplicate or colliding GND stitching vias removed. Q_ROW refs for columns 4-8 hidden on silk.
- Outline 158.9 -> 152.9 x 99.5 mm. DRC: 0 errors, 0 unconnected, 0 dangling; 13 silk warnings. Worst LED drop 100.6 -> 95.9 mV. Track length 14.66 -> 14.04 m. In2 signal copper 27.6 mm. B GND pieces all >=2 vias.

## Step 14 (v6): band compaction, outline 148.0 x 99.5 mm
- Backup: mono_electronics.v5.d9894c2.kicad_pcb.
- Feed band (ROW_13..32_Y verticals and their staircase vias, y<69) pitch 0.5 -> 0.375 mm (x 110.5-122.1 scaled by 0.75); everything east moved 2.9 mm west.
- Riser band (anode + COL risers, J_ROW/J_COL fan, COL bottom staircase; x 122.6-142.2) scaled by 0.9; everything east moved 1.96 mm west.
- Not done: COL risers to In1. The COL bottom bus is on In1 and runs east past the risers, so In1 risers would cross it. Columns 1-3 at 6.8 mm: no length gain unless the decoders and feed band also move, and with the decoders moved 5 mm, 13-19 conflicts remain in the translator/decoder pocket (DEC_B_EN_N, ROW_02/04/05/07_Y, ROW_A1, DEC_A_EN_N). That pocket needs a full reroute.
- DRC: 0 errors, 0 unconnected, 0 dangling; 13 silk warnings. Worst LED drop 95.9 -> 92.3 mV. Track length 14.04 -> 13.65 m. In2 signal copper 27.6 mm. B GND pieces all >=2 vias. 0 parts on B, no relabels.
