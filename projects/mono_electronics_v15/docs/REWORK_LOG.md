# Rework step 1: netlist fixes (2026-10-10)

## mono_electronics v7: all deferred parts placed, continuity check, corner cleanup (148.0 × 99.5 mm, 4 layers)

- **Parts added (top side only):** MAX17048 fuel gauge U_GAUGE + C_GAUGE + R_ALRT (BAT_RAW cell/VDD, shared I2C IMU_SDA/SCL at 0x36, ALRT → GPIO1); MEMS mic MIC1 (Gettop MA-HFA381, custom footprint) + TLV9001 preamp U_AUDIO with bias/gain network (C_AUD, C_MIC, C_AC, R_INB, R_B1, R_B2, C_B, R_F, R_GN, C_GN) on the switched AUDIO_3V3 rail (U_AUDIO_SW moved next to it, C_AUD_SW), output → GPIO4 (ADC1_CH3); board NTC TH_PCB + R_TH divider → GPIO2 (ADC1_CH1); 1 µF VIN caps C_ASW_IN / C_LL_IN at both TPS22917s.
- **Footprint fix:** U_ROW_XLAT (SN74LVC8T245**RHL**R) was on a 4×4 mm VQFN-24; replaced with the correct 3.5×5.5 mm RHL0024A land pattern and rerouted.
- **GPIO changes:** GPIO1 = GAUGE_ALRT_N, GPIO2 = TH_ADC, GPIO4 = AUDIO_ADC (GPIO0_BOOT escape rerouted to free them). Architecture doc GPIO map updated; firmware board_pins.h is not on this branch (patch is in the report).
- **Continuity check:** see PROZVONKA.md: 204/204 parts PASS, every IC powered/grounded/decoupled, 0 unconnected; only single-pad nets are the 16 FFC spares.
- **Track cleanup:** collinear segments merged, stair-stepped/chopped corners replaced with single 45° chamfers (segments 1851 → 1739; interior stair joints 99 → 41, the rest sit on via-limited ROW_04/05_Y In1 runs).
- DRC: 0 errors, 0 unconnected, 14 warnings (silk only). No parts on B; LED worst drop 92 mV (unchanged); In2 signal copper 27.6 mm (unchanged); B GND pieces stitched ≥2 vias.

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


## v8 (2026-10-10): stacking ports, staircases, arcs
- Moved ROW_A3 from U1 pad 38 to pad 42, and ROW_XLAT_OE_N from pad 37 to pad 50 (B escape moved to the GPIO44 pocket via at 51.1, 9.2).
- Placed J_PORT_N (126.0, 3.125, 180°), J_PORT_E (144.915, 42.0, 90°), J_PORT_S (64.0, 96.375, 0°) and J_PORT_W (3.125, 88.0, 270°).
- Placed an ESD pair at every port: D_x_AB (SM712) and D_x_SP (PESD3V3S2UT).
- Placed the RS-485 block: U_485 THVD1406DR at (60, 86), C_485 at (63.5, 82.6), R_TERM 120R 0603 at (66.0, 85.365), JP_TERM at (68.9, 86.0, 90°).
- Routed new nets with gated point-to-point octilinear routes on F/In1/B, one net per step, each with DRC: RS485_A/B, FRAME_SYNC, PRES_N/E/S/W, RS485_TX/RX, LED_LOGIC_3V3. Added 4 B GND stitching vias.
- Reshaped ROW_04_Y and ROW_05_Y on In1 into vertical + 45° segments (west) and horizontal + 45° segments (east): staircase joints 41 → 0.
- Offset the ROW_02_Y B corner to x 34.2, clear of the F USB_D_N stub end.
- Added 550 tangent-arc corners (arcplan.py / arcapply.py), excluding GND and the USB pair.


## v9 (2026-10-10): track cleanup
- Ran simplify.py (chain window replacement scored by turns, short and non-45° segments; clearance ≥0.115 mm vs all other-net copper). Rounds were gated by DRC, copper renames and total error count, and failing chains were dropped. Then colmerge.py (16 collinear merges).
- Rerouted the AON_3V3 F escape off the B LED_SDI line. Regenerated tangent arcs (arcplan.py/arcapply.py).
- Ran copcheck.py (shapely, all nets) after every change: 0 violations.

## v10 — clearance widening, last bends rounded, M2.5 mounting holes

- Mounting holes H1–H4: MountingHole_2.7mm_M2.5_Pad (2.7 mm plated hole, 5.4 mm pad on GND) at (3.8,3.8), (144.24,3.8), (3.8,96.0), (144.24,95.7); each with an all-copper-layer rule area r=3.0 mm (no tracks/vias) and r≈3 mm courtyard (component keepout). Outline unchanged (148.0 × 99.5).
  - NW: MIC1 moved (6.0,4.0 r0) → (2.1,8.8 r180), rerouted MIC_OUT (F, straight to C_AC), VDD via + In1 to AUDIO_3V3, GND pads tied + via. Removed GND stitch vias (2,2), (6,1.9), (6,6.1), (142.64,2.0), (2,98) and the via at (2,10) that would sit in a MIC pad.
  - SW hole placed 3.5 mm from the bottom edge so its courtyard clears J_PORT_W; N/E ports not affected.
- Clearance: 118 vias next to other-net copper 0.45 → 0.40 mm (board minimum, already used by 428 vias); ROW_13..32_Y F feed band re-pitched 0.375 → 0.43 mm (vias + In1 feeds moved with it); COL_01..32 B fan re-pitched 0.405 → 0.43 mm (east-anchored); B anode verticals 0.40 → 0.39 mm (ROW_32 0.38) to reach 0.15; USB_D_N_MCU horizontal moved 0.03 mm off R_USB_P pad; LED_EN and IMU_SDA re-drawn at U1; 11 via moves along their own stub; 31 local neck-downs of signal tracks to 0.145 mm (and 4 to 0.125–0.13 on long AUDIO_ADC/PRES_E/LED_EN runs; SYS arc 0.30→0.26, GND In1 0.25→0.245).
- Bends: remaining 9 unrounded + 2 chopped corners → arcs (stale key rounding in arcapply fixed); 0 unrounded signal bends.

## v10b — C_MIC next to MIC1
- MIC1 moved 0.8 mm south to (2.1,9.6 r180); C_MIC moved (8.3,5.1) → (0.75,6.6 r270). C_MIC VDD pad 1.43 mm centre-to-centre (0.62 mm edge gap) from MIC1 pin 6; GND pad straight to a via 0.67 mm away at (0.75,5.45). AUDIO_3V3 via moved to (1.6,7.6), feeding In1; MIC GND via moved to (2.1,11.65); MIC_OUT redrawn. Old C_MIC stubs and via removed. Gates unchanged (DRC 0/0, copcheck 0 < 0.127, 224/224 continuity).

## v11 phase 1 — board leftovers
- B.Cu GND sliver (2.6 mm², 56.6–61.7 × 2.35–2.90, one via) removed with a B-only rule area "KO_B_SLIVER" (no zone fill). Every B GND piece now has ≥2 stitching vias.
- Silkscreen: refs of U_LED_BUF, U_LED_PWR, Y1, U1, SW1 hidden (same policy as the small labels); U1 pin-1 marker moved 0.5/0.2 mm off copper (kept); one overlapping silk segment each removed from C_LL_IN, U_AUDIO, R_F. KiCad DRC now 0 errors, 0 warnings, 0 unconnected.
- 3D models (KiCad library, kicad-packages3D): U_GAUGE → DFN-8-1EP_2x2mm_P0.5mm_EP0.6x1.2mm; U_LED_PWR → DFN-10-1EP_2x3mm_P0.5mm_EP0.64x2.4mm; J_ROW/J_COL → Hirose_FH12-40S-0.5SH_1x40-1MP_P0.50mm_Horizontal (the footprint is FH12 geometry); J_USB → USB_C_Receptacle_GCT_USB4105-xx-A_16P (stand-in: no HRO TYPE-C-31-M-12 model in the KiCad library; same class/size, visual only).

## v11b — AON headroom, LED_EN glitch filter, J_USB value, reference renames
- U_LDO1: TPS7A2033 (300 mA) → **TI TLV75733PDBVR** (1 A, SOT-23-5, same DBV pinout IN/GND/EN/NC/OUT — drop-in on the existing pads; LCSC C485517, 87k in stock). Dropout 300 mV typ / 425 mV max at 1 A (≈180/255 mV at 600 mA) → full regulation at 600 mA down to VBAT ≈ 3.56 V, at 150 mA average down to ≈ 3.36 V; below that AON tracks VBAT−VDO (ESP32-S3 runs to 3.0 V). Ground current ≤ 33 µA (vs ~6.5 µA for TPS7A20) — +27 µA in sleep. Thermal: RθJA 100.8 °C/W (TI EVM) – 231 °C/W (JEDEC); worst case on USB (SYS 4.5 V), 250 mA average radio load: (4.5−3.3)·0.25 ≈ 0.3 W → +30…70 °C; 600 mA bursts are ms-long. Foldback current limit 1.2 A min.
- C_MCU11 (was C_MCU1) bulk at the ESP32: 10 µF → **22 µF** 0805 (CL21A226MQQNNNE) for radio bursts.
- LED_EN glitch filter at U_LED_PWR1: series **R_EN_SER1 100 k** + **C_EN1 10 nF** to GND (τ = 1 ms). The S3's 60 µs GPIO18 power-up pulse reaches 0.19 V at EN (VIL 0.4 V); a real enable reaches VIH 1.2 V after ≈ 0.45 ms. R_EN_PD1 stays on the GPIO side. New net LED_EN_RC.
- J_USB1 value → TYPE-C-31-M-12 (matches the HRO footprint).
- All 93 references without a trailing number got a "1" (map in REF_RENAME_v11b.json) so the schematic annotates cleanly.
- Gates: DRC 0 errors / 0 warnings / 0 unconnected, copcheck 0 < 0.127 mm, no copper renames, no parts on B, dangling 0. Schematic: ERC 0, netlist vs PCB 226/226, 0 pin differences, no annotation notice.

## v12 — LED interface standard v1: FFC spare pins (ID EEPROM bus + column-expansion taps)
Reference: hardware/common/LED_INTERFACE_STANDARD.md, LED_SCALING_OPTIONS.md (main-board changes 1 + 2).
- J_ROW1: pins 33/38/40 → GND (F stub east to a 0.45 mm GND via at x 146.6). Pin 35 `ID_SDA` → R_ID_SDA1 33 R → IMU_SDA. Pin 36 `ID_SCL` → R_ID_SCL1 33 R → IMU_SCL. Pin 37 `ID_3V3` → R_ID_3V1 100 R → AON_3V3. D_ID1 PESD5V0S2BT (dual bidirectional ESD, 35 pF, SOT-23) on IMU_SDA/IMU_SCL at the resistors, GND to the D_E_SP1 GND via. Pins 34 and 39 stay unconnected (ROW_SPARE_34/39).
- J_COL1: pins 33/38/40 → GND. Pins 34–37 `EXP_SDI`/`EXP_CLK`/`EXP_LE`/`EXP_OE` → R_EXP_SDI1/CLK1/LE1/OE1 33 R **DNP** → `LED_SDO2` (U_LED2 pad 22 SDO, previously open), LED_CLK_Y, LED_LE_Y, LED_OE_Y. Pin 39 `EXP_3V3` → R_EXP_3V1 0 R **DNP** → LED_LOGIC_3V3.
- Parts placed at x 134–137.6, east of the PRES_E diagonal and outside the J_ROW1/J_COL1 courtyards. All on F, refs hidden (small-label policy); R_EXP_* carry the KiCad DNP attribute and are excluded from the CPL.
- Routing: gated point-to-point octilinear A* on F/In1 (B only for the 5 mm IMU_SCL hop to its existing via), one net per step, clearance 0.14 mm, DRC + copper check after each step. Added copper: F 288 mm, In1 205 mm, B 5 mm, In2 0, plus 20 vias (0.40/0.20; GND 0.45/0.20). The ID bus runs on F along the north-east diagonal between the row fan and the RS-485 pair, then on In1 west to the IMU pull-ups. Expansion taps run on F/In1 from U_LED2 east to the R_EXP column.
- Optional item 3 (32 × 10 k row bleed) **not applied**: the anode band (F/B, x 120–138) has no via room and no clean placement.
- Gates: KiCad DRC 0 errors / 0 warnings / 0 unconnected, 0 dangling; copper check 0 spots < 0.127 mm between different nets (< 0.15: 115, was 113); no copper renamed (netcheck 0); no parts on B; worst LED drop 92.5 mV (row 17, unchanged); all 8 B GND pieces ≥ 2 stitching vias. Schematic regenerated (new sheet `led_interface`): ERC 0, sch netlist vs PCB 235/235 refs, 0 pin differences.
- Images: img/v12_id_bus.png, img/v12_col_exp.png. Fab: manufacturing/mono_electronics/v12/, mono_electronics_v12_fab.zip.

## v12a — arcs on every track corner (2026-10-11)
- Scope: all nets and layers, including GND, LED_4V1, AON_3V3, VBUS, SYS, BAT, the USB pair, and the v12 ID/expansion routes. Tools are in /workspace/arc (analyze.py, plan.py, plan2.py, apply.py).
- Corners before → after: sharp 90° 35→0, unrounded 45° 70→0, chopped 9→0, jogs/stair-steps 17→0 (USB D+ meander now rounded), kinks 1–20° 27→0, same-width collinear joints 12→0 (merged). Remaining: 38 straight width steps (collinear, not corners), plus corners hidden inside pads or vias and T-junctions, which are not counted.
- Fillets: 148 arcs with radius 3×w where they fit. 30 are smaller, limited by segment length or by keeping ≥0.13 mm to other nets. 4 chamfers were collapsed into one arc each. Width-step corners use an arc at the narrower width.
- USB: the D+ meander depth went from 0.92 to 1.04 mm to make up the length lost to the arcs. Skew D+−D−: A 0.013→−0.131 mm, B 0.302→0.189 mm (limit 0.5). Both lines are arced the same way.
- IMU_SDA In1: the 0.1 mm segment was split at the T at (67.35,3.5) so the junction is a real node.
- Gates: DRC 0/0/0 (all severities); copper check 0 spots <0.127 mm; netcheck 0 relabels; 0 B-side parts; worst LED drop 92.5 mV (row 17, unchanged); B GND pieces unchanged (each has ≥2 vias); ERC 0, sch vs PCB 0 differences. Gerbers, drill files and zip regenerated.
- Images: img/v12a_usb_meander.png, v12a_usb_conn.png, v12a_gnd_pmu.png, v12a_id_bus.png, v12a_row_kinks.png, v12a_F.png.

## v13: protections from the physics simulation (2026-10-11)
- **Battery (71d356c):**
  - J_BAT1 pad 1 is now net BAT_PACK and feeds F_BAT1 0466002.NRHF (2 A FF, I²t 0.23 A²s, 50 A interrupt), then net BAT_FUSE, then Q_BAT1 AO3401A drain. Source goes to BAT_RAW; the gate goes to GND through R_BATG1 10 k (ideal-diode reverse-battery switch, 72 mV at 1.2 A).
  - BAT copper is 1.0 mm on F from J_BAT1 to Q_BAT1. It necks to 0.4 mm for the last 2.3 mm between the GND via at (13.2, 44.4) and the C_CHG_BAT1 GND pad. The In1 riser is 0.8 mm.
  - GND stitch vias at (2, 50) and (2, 58) moved to (6, 51.5) and (8.5, 51.5).
  - Short-circuit check: at 25 A the fuse clears in about 0.4 ms, against about 2.3 A²s (≈ 4 ms) for the 0.3 mm In1 trace. The pack PCM stays the primary protection (assumed, not on the board).
- **USB (bedbc9c):**
  - The connector side is now VBUS_CONN: J_USB1 A4/A9/B4/B9, the B bar, 2 vias and the In1 jog. These 5 track/via relabels are intentional.
  - D_VBUS1 SMF12A (12 V standoff, 19.9 V clamp) feeds U_OVP1 TPS259531DSGR (OV clamp 5.5–5.9 V; datasheet SLVSE57C confirms TPS259521 is the 3.8 V option, so it is not usable here). Its output drives VBUS (BQ25185 IN, USBLC6 VBUS, C_USB1).
  - EN/UVLO divider is 100 k / 39 k, giving 4.28 V. dVdt and FLT are left open.
- **Charger thermal (0ec471b):** F.Cu GND zone x 12.6–25.3, y 37–44.1 (62 mm² fill, solid pad connection), 4 GND vias on the EP return line, EP strap 0.6 mm, GND line 0.4 mm.
- **Abs-max review (64d1935):** see ABSMAX_REVIEW_v13.md. R_ILM1 changed from 1.78 k to 2.7 k because 1.09–1.24 A exceeded the BQ25185 IN DC abs max of 1.1 A.
- **Full check:**
  - DRC 0/0/0, all severities. Copper check 0 spots < 0.127 mm (25 < 0.15 mm, unchanged).
  - Net relabels vs v12a: only the 5 intended VBUS_CONN items. 0 B-side parts.
  - LED drop 92.5 mV (row 17, unchanged). B GND: every piece has ≥ 2 vias.
  - ERC 0. Schematic vs PCB: 0 refs only on one side, 0 pin differences.
  - Continuity (PROZVONKA_v13.md): 243/243 PASS.
  - All corners arced (only 39 straight width steps remain). USB skew −0.131 / +0.189 mm.
- Fab: manufacturing/mono_electronics/v13 and mono_electronics_v13_fab.zip. Images: img/v13_battery.png, v13_usb_ovp.png, v13_charger_thermal.png, v13_F.png.

## v13b: 2 A battery connector (2026-10-11)
- J_BAT1: Molex PicoBlade 53398-0371 (1 A/contact) replaced by JST PH S3B-PH-SM4-TB(LF)(SN) (2 A/contact, side entry, 5.5 mm tall), placed at (7.0, 57.0) rot 270 with the cable entering from the west edge. Pin 1 BAT_PACK, pin 2 TS_MR, pin 3 GND. The battery lead must be re-terminated in a PHR-3 housing.
- Re-placed: F_BAT1 to (8.6, 48.9), Q_BAT1 to (8.6, 44.4) rot 270, R_BATG1 to (11.0, 45.5).
- Battery copper: BAT_PACK and BAT_FUSE 1.0 mm on F. BAT_RAW 1.0 mm from Q_BAT1 to x = 11, then 0.6 mm down to the 0.4 mm entry at (12.4, 45.2), where GND vias leave no room for more.
- TS_MR rerouted east of the connector along x = 12.4. The old x = 3.4 run and the west part of the y = 48.4 run were removed.
- GND vias: 3 stitch vias plus the connector GND via were re-placed.
- Gates: DRC 0/0/0; copper check 0 < 0.127 mm; netcheck 0 relabels; 0 B parts; LED drop 92.5 mV; B GND ≥ 2 vias per piece; ERC 0; schematic vs PCB 0 diffs; continuity 243/243 PASS; all corners arced; USB skew unchanged.
- BOM: JLC stock and prices refreshed from the JLCPCB API. AO3401A C15127 is a basic part with 680,966 in stock. 39 k is C25783 0402WGF3902TCE, an extended part with 201,024 in stock.

## v13c: eFuse current limit and thermal copper (2026-10-11)
- R_ILM1 2.7 k → 1.6 k (0402WGF1601TCE, C4908, extended part, JLC stock 73,801). TPS2595 Eq. 4 gives I_LIMIT = 2000/R + 0.04 = 1.29 A (1.19–1.39 A at ±7.5 %); it was 0.78 A.
- U_OVP1 thermal: F.Cu GND zone x 5.5–10.8, y 24.9–30.4 (21.5 mm² fill, solid pad connection), an EP strap down to a GND via at (7.0, 29.6), and a second GND via at (8.0, 30.0).
- Note: the BQ25185 ILIM (18 k) caps the steady-state input at 0.5 A. The new eFuse limit is above the BQ's 1.1 A IN DC abs max, so it only bounds faults and inrush (see ABSMAX_REVIEW_v13.md).
- Gates: DRC 0/0/0; copper check 0 < 0.127 mm; netcheck 0 relabels; 0 B parts; LED drop 92.5 mV; B GND ≥ 2 vias per piece; ERC 0; schematic vs PCB 0 diffs; continuity 243/243 PASS; all corners arced; USB skew −0.131/+0.189 mm.

## v13d: R_ILM1 back to 2.7 k (2026-10-11)
- Your decision: R_ILM1 1.6 k → 2.7 k (C25885). The eFuse limit is 0.78 A (0.72–0.84 A), which stays under the BQ25185 1.1 A IN DC abs max. The v13c thermal copper and vias under U_OVP1 are kept. The abs-max trade-off note was removed.
- Gates: DRC 0/0/0; copper check 0 < 0.127 mm; netcheck 0 relabels; 0 B parts; ERC 0; schematic vs PCB 0 diffs; continuity 243/243 PASS; all corners arced.

## v14 — installation-build cable headers (DNP in the wearable build)
- Board outline 148.0 → **160.5 × 99.5 mm** (east edge +12.5 mm); B.Cu and In2 GND planes extended into the strip. Nothing else moved.
- `J_RH1` / `J_CH1`: 2×20 1.27 mm SMD male pin headers (JXT-PZ1.27-2X20P-A2, C54803356) at (152.2, 21.68) and (152.2, 68.28), wired in parallel with `J_ROW1` / `J_COL1` **pin n = FFC pin n** for all 40 pins (lines 1–32, GND 33/38/40, ID/sense/expansion spares). Each line leaves the FFC pad east on F.Cu, 0.2 mm, a 45° fan from 0.5 to 0.635 mm pitch (≤ 2.7 mm), even pins pass between the odd pads.
- ESD: 64 × PESD5V0S1BL (C84374, SOD-882) `D_R01–D_R32`, `D_C01–D_C32`, one per LED line in two columns east of each header, each with its own GND via. Odd lines reach their TVS through a via under the header body and a B.Cu hop. SOD-882 courtyards are trimmed to ±0.62 mm (IPC least) so they stack at 1.27 mm.
- The six old FFC GND stub vias (J_ROW1/J_COL1 pins 33/38/40, x 146.6) were removed; those pins now reach GND through the header GND vias in the strip.
- Why not 4 × 2×8 2.54 mm box headers: `J_PORT_E1` occupies the east edge between the FFCs (y 37–47, cable exits east) and must stay accessible, leaving ~36 mm above it; two 2×8 box headers need 58 mm, unshrouded 2.54 mm 43 mm. See LED_INTERFACE_STANDARD.md §6.1.
- The DNP strip is flat in the wearable build. The FFC cables and the J_PORT_E1 plug lie on it. No parts are in the J_PORT_E1 band (y 35–48).
- Gates: DRC 0/0/0 (all severities); copper check 0 < 0.127 mm; netcheck 0 relabels; 0 B parts; worst LED drop to the FFC 92.5 mV (row 17, unchanged), about +11 mV more to the header pins; B GND pieces each have ≥ 2 vias; ERC 0; schematic vs PCB 309/309 refs, 0 pin differences (new sheet `install_headers`); continuity (PROZVONKA_v14.md) 309/309 PASS; all corners arced (only straight width steps remain); USB skew unchanged (−0.131/+0.189 mm).
- Fab: manufacturing/mono_electronics/v14/ (wearable and installation BOM/CPL) and mono_electronics_v14_fab.zip. Images: hardware/mono_electronics/img/v14/.

## v14 (rev b) — shrouded keyed box headers
- J_RH1/J_CH1 changed from unshrouded 2×20 1.27 mm pin headers to XFCN BH127VS-40P-H49 2×20 1.27 mm SMD shrouded, keyed IDC box headers (C42462832). The custom footprint `BoxHeader_XFCN_BH127VS-40P-H49_2x20_P1.27mm_Vertical_SMD` follows the datasheet land pattern (pads 0.6 × 2.6 mm, rows ±2.2 mm, body 31.75 × 6.0 mm). The silk shows the body ends and a pin-1 triangle. Centres (151.9, 21.68) and (151.9, 68.28). Same 1:1 pinout and the same 64 TVS.
- Board 160.5 → **159.45 mm** wide (v13 was 148.0). The E-column TVS GND vias are tied by an In1.Cu GND strap per header, with GND vias at both ends.
- Gates: DRC 0/0/0; copper 0 < 0.127 mm; netcheck 0; 0 B parts; LED drop 92.5 mV (FFC, unchanged); B GND pieces ≥ 2 vias; ERC 0; sch vs PCB 309/309, 0 diffs; прозвонка 309/309 PASS; all corners arced; USB skew unchanged.

## v15 — FFC shift, back to 148.0 × 99.5 mm

- J_ROW1/J_COL1 moved 13.5 mm west (x 143.04 → 129.54, same y). Row/col line ends were re-terminated at the new pads. Lines whose old via fell inside the new pad window go down to In1 and come back up at a via column x 132.24/132.79: rows 17 and 21–32, with row 17 at 0.5 mm on In1. Cols 1–13 use B → via at x 129.0/129.55 → F. FFC GND pins 33/38/40 get new stub vias.
- The header/TVS strip was rebuilt at the old FFC site: J_RH1 at (140.4, 22.78), J_CH1 at (140.4, 68.28), and 64 × PESD5V0S1BL in two columns at x ≈ 145–147. Pinout is 1:1 with the FFC. Fan-out is 0.2 mm, with 0.25 mm to the TVS. Pin-1 silk was moved to the west side and the header courtyards were trimmed to the body.
- Re-placed: J_PORT_E1 y 42 → 44; D_E_SP1 (138.7, 41.0) 90°; D_E_AB1 (139.2, 47.6) −90°; D_N_AB1 (134.7, 7.7); D_ID1 (121.6, 33.0) −90°; R_ID_SDA1/SCL1/3V1 at x 123.4 (y 35.7/36.9/38.1); R_EXP_* at x 123.4 (y 75.5–80.3). IMU_SDA/SCL, AON_3V3, ID_*, EXP_*, LED_SDO2, LED_CLK_Y/LE_Y/OE_Y, LED_LOGIC_3V3, PRES_E and FRAME_SYNC were re-routed locally.
- RS-485: N → E taps → transceiver were re-routed as a parallel pair, 0.2 mm, mostly on In1, with length bumps. Leg lengths: N→E A 53.92 / B 53.91 mm, E→W A 22.88 / B 22.91 mm.
- "PIN1" and "FFC TYPE B" silk moved with the FFCs.
- Gates: DRC 0 errors / 0 warnings / 0 unconnected; copper clearance ≥ 0.127 mm (0 violations); 0 relabelled copper vs v14b; 0 parts on B; 9 B.Cu GND pieces, each with ≥ 2 vias; ERC 0; sch-vs-PCB 309/309, 0 pin differences; прозвонка 309/309 PASS (PROZVONKA_v15.md); all corners arced (only width steps left); USB skew unchanged (A −0.131, B +0.189 mm). LED drop worst row 17 at 105.7 mV and row 25 at 103.2 mV (v14b worst was ≈ 92 mV). This is the cost of the In1 detour, still inside the 0.35 V budget.
- Fab: manufacturing/mono_electronics/v15 + mono_electronics_v15_fab.zip. BOMs are unchanged from v14. CPL rows were updated for the 76 moved parts. Default FFC is now 120 mm (C5371276).
- Sims: firmware/mono_split/sim/bringup/board*.json (FFC pads −13.5 mm x, E port +2 mm y); tools/led_sim_windows world.py BOARD_CONN/SIDE_OFF, new data/pcb/board_v15.json.gz (now the current board in the inspector/cube/system views).
- Images: img/v15/v15_top.png (3D), v15_F.png, v15_F_strip.png, v15_In1.png, v15_In1_strip.png.
- v15 cleanup: the "FFC TYPE B" silk labels moved to x 122.4, off the FFC outlines. The 120 mm FFC C5371276 is in the annotated BOM: JLC stock 701, $0.154 each ($0.121 @50). Silkscreen gerber and fab zip regenerated. Copper unchanged.

## v15 audit fixes (2026-10-12)
- Zones refilled. The committed v15 file and Gerbers had stale fills: 590 DRC errors, with GND overlapping signal vias on B.Cu/In2. Gerbers and drill files regenerated.
- Arcs on the LED_CLK_Y, LED_LE_Y and USB_D_P 45° corners. Thermal relief on the GND pads of R_ILIM1, R_ISET1, R_ILM1, R_EN_BOT1 and C_CHG_SYS1. SYS In1/B.Cu 0.25–0.30 → 0.45 mm.
- Gates: DRC 0 (also at 0.127 mm min), ERC 0, sch-vs-PCB 0, continuity 309/309, nets unchanged. See MFG_AUDIT_v15.md.

## v15b (2026-10-12): audit recommendations applied
- D_VBUS1 moved next to J_USB1, upstream of U_OVP1. SYS B.Cu 0.6 mm, plus a second via at every SYS layer change. 3 fiducials (board-only). Silk widened to 0.15 mm. J_PORT_* 0.25 mm inward. Explicit 1.6 mm JLC04161H-7628 stackup.
- Real 0.127 mm spacing: 24 pre-existing sub-0.127 gaps fixed (ROW anode In1 0.36 → 0.345 mm, VBUS escape 0.3 mm, SYS arc 0.25 mm). min_clearance rule set to 0.127.
- Schematic DNP/in_bom attributes now match the board. Footprint library nicknames added. KiCad native parity 0.
- Standalone project: projects/mono_electronics_v15/.
