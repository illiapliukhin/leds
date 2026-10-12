# mono_electronics v15 — JLCPCB fab package (PR #4 board), two assembly variants

Board: **148.0 × 99.5 mm** (v15: FFCs J_ROW1/J_COL1 moved 13.5 mm west, box headers + TVS strip at x 136–148, back to the v13 outline; v14/v14b were 160.5/159.45 wide), 4 layers (F / In1 / In2 / B), **1.6 mm JLC04161H-7628 stackup** (explicit in the board file since v15b), single-sided assembly (top only), 3 fiducials (FID1–3, not in BOM/CPL). KiCad DRC 0 errors / 0 warnings / 0 unconnected.

## Files
- `gerbers/` — Protel extensions, no X2, soldermask subtracted from silk, drill-file (aux) origin. Layer order for the JLC stackup: GTL (F.Cu) / G1 (In1) / G2 (In2) / GBL (B.Cu). Excellon drill, mm, separate PTH / NPTH, with drill maps.
- **Wearable variant:** `BOM_mono_electronics_v15_wearable_JLCPCB.csv` + `CPL_mono_electronics_v15_wearable.csv` — FFC J_ROW1/J_COL1 fitted; J_RH1, J_CH1 and the 64 TVS D_R01–D_R32 / D_C01–D_C32 DNP (not listed). Identical part list to v13.
- **Installation variant:** `BOM_mono_electronics_v15_installation_JLCPCB.csv` + `CPL_mono_electronics_v15_installation.csv` — adds J_RH1/J_CH1 (XFCN BH127VS-40P-H49 2×20 1.27 mm SMD shrouded, keyed box header, C42462832, stock 125; mates XFCN IDC3-40232A1EUB1 IDC socket C49232620 on 0.635 mm 40-way ribbon) and 64 × PESD5V0S1BL (Nexperia, C84374, stock 127k). The FFC lines are kept; delete the J_ROW1/J_COL1 line (and its CPL rows) to drop the FFCs.
- `BOM_mono_electronics_v15_annotated.csv` — with MPN, basic/extended, live stock and unit price (queried from the JLCPCB parts API on 2026-10-11), and flags.
- CPL: placement (Designator, Mid X, Mid Y, Layer, Rotation), all Top; wearable 231 parts, installation 297 parts (R_EXP_* DNP in both).

## Order settings (JLCPCB)
4 layers, FR-4, **1.6 mm, JLC04161H-7628** (the board file stackup since v15b; no impedance control needed), ≥0.127 mm trace/space capability (board min other-net spacing 0.127 mm, verified by DRC with min_clearance 0.127, min track 0.10 mm (IMU_SDA/DEC_B_EN_N etc.; JLC 4L min 0.09), vias 0.40/0.20 + 0.45/0.20 mm), ENIG recommended (QFN/LGA/VQFN fine pitch), tented vias, Standard PCBA, top side, remove order number or "specify position".

## Flags before ordering
- **v15b (2026-10-12):** D_VBUS1 moved next to J_USB1 (CPL changed). J_PORT_E1/N1/S1/W1 moved 0.25 mm inward (CPL changed). 3 fiducials added. Silk 0.15 mm. SYS widened, with doubled vias. 24 sub-0.127 mm gaps fixed. Gerbers/drill regenerated from `projects/mono_electronics_v15/` (the canonical standalone project). Re-upload this zip.
- **v15 audit (2026-10-12, hardware/mono_electronics/MFG_AUDIT_v15.md):** the earlier v15 Gerbers were plotted from stale zone fills (B.Cu/In2 GND poured over signal vias = shorts). Zones are now refilled and all Gerbers/drill files regenerated: re-upload this zip. Also: 3 sharp corners arced, thermal relief on 5 tombstone-prone passives, SYS In1/B.Cu widened to 0.45 mm, installation BOM designators comma-separated. No fiducials: ask JLC for edge rails.
- **v15 FFC shift:** the FFC length changes at the panel end: the board connectors are now 13.5 mm further from the east edge. Default FFC is now the **120 mm** Type B (C5371276); check the run against your mounting before ordering. CPL positions changed for J_ROW1, J_COL1, J_RH1, J_CH1, J_PORT_E1 (+2 mm south), D_ID1, R_ID_*, D_E_SP1, D_E_AB1, D_N_AB1 and the 64 TVS.
- **v14/v15 installation headers (LED_INTERFACE_STANDARD.md §6.1):** J_RH1/J_CH1 repeat J_ROW1/J_COL1 pin for pin (pin n = FFC pin n, rows/cols 1–32, GND on 33/38/40). Never fit FFC panels and header loads at the same time. Header stock (125) and socket stock (140) are thin; check before ordering. Check the header and SOD-882 rotations in the CPL preview.
- **v15 cost delta (estimate):** wearable: parts $0, bare PCB same as v13 (148 × 99.5). Installation: +2 extended lines ($6 loading fee per order); parts ≈ $3.8/board @5 (2 × $0.81 + 64 × $0.033) and ≈ $3.0/board @50 (2 × $0.65 + 64 × $0.026); +208 joints ≈ $0.35/board. Dropping the FFCs saves ≈ $1.46/board @5 (≈ $1.04 @50).
- **v13b:** J_BAT1 is now JST PH S3B-PH-SM4-TB(LF)(SN) (C265101, JLC stock 865, enough for 50 boards; 2 A/contact). The battery lead needs a JST PHR-3 housing (pin 1 BAT+, 2 NTC, 3 GND). The annotated BOM stock and prices were refreshed from the JLCPCB parts API on 2026-10-11 (66 of 70 lines; the rest are not assembled).
- **v13 protections (see hardware/mono_electronics/ABSMAX_REVIEW_v13.md):**
  - F_BAT1 0466002.NRHF 2 A very-fast 1206 fuse (C3105, LCSC stock 33,770) right at J_BAT1.
  - Q_BAT1 AO3401A (C15127, basic) reverse-battery ideal-diode P-FET with R_BATG1 10 k gate pull-down. BAT copper is 1.0 mm on F from J_BAT1 to Q_BAT1, and the In1 BAT_RAW riser is 0.8 mm.
  - U_OVP1 TPS259531DSGR eFuse (C2155674, JLC stock 2,988): 5.7 V OV clamp, R_ILM1 2.7 k (C25885) gives a 0.78 A limit (0.72–0.84 A), under the BQ25185 1.1 A IN abs max, UVLO 4.28 V from R_EN_TOP1 100 k / R_EN_BOT1 39 k (C25783, verify).
  - D_VBUS1 SMF12A (JSMSEMI C2857273, stock 25,035) on the connector side (VBUS_CONN).
  - BQ25185: F.Cu GND pour plus 4 thermal vias.
  - The battery pack's own PCM (Jauch LP523450JU) is still assumed as primary over-current/over-discharge protection. F_BAT1 is the board-level backstop against a short on the board.
- **v13 changes (LED interface standard v1, see hardware/common/LED_INTERFACE_STANDARD.md):** J_ROW1 33/38/40 and J_COL1 33/38/40 → GND; J_ROW1 35/36 → IMU_SDA/IMU_SCL through R_ID_SDA1/R_ID_SCL1 33 R (C25105) with D_ID1 PESD5V0S2BT (C49338, 35 pF dual ESD); J_ROW1 37 → AON_3V3 through R_ID_3V1 100 R (C25076); J_COL1 34–37 → U_LED2 SDO (new net LED_SDO2) / LED_CLK_Y / LED_LE_Y / LED_OE_Y through R_EXP_SDI1/CLK1/LE1/OE1 33 R **DNP**; J_COL1 39 → LED_LOGIC_3V3 through R_EXP_3V1 0 R **DNP**. Fit the DNP parts only when a column-expansion board is used. Row bleed resistors (optional item 3) were not added. They don't fit cleanly in the anode band.
- Check every rotation in the JLC CPL preview (KiCad → JLC offsets are typical on SOT-23, SOT-23-6, QFN, the FFC and JST connectors).
- v11b changes: U_LDO1 = TLV75733PDBVR (C485517, 1 A LDO), C_MCU11 = 22 µF 0805, new R_EN_SER1 100 k (C25741) + C_EN1 10 nF (C15195) on LED_EN, J_USB1 value = TYPE-C-31-M-12 (C165948). All references now end in a digit (J_ROW → J_ROW1 etc.).
- Y1: original part (L327S400H11L) not stocked; substitute Yangxing X3S040000BA1H-R C136083 (40 MHz, 3225, 10 pF, ±10 ppm), only 882 in stock.
- TH_PCB: Sunlord SDNT1005X103F3435FTF (10 k, B3435) C279801.
- R_ISET: 600 R not stocked, 620 R (C4961) used — BQ25185 charge current about 3 % lower.
- J_PORT_*: XY clone of JST SM06B-SRSS-TB (C56123098, 1291 in stock); genuine JST 6P SH right-angle not in the JLC library. Ports are DNP-friendly: drop the 4 ports + 8 ESD + U_485/C_485/R_TERM lines to save cost.
- Not assembled: H1–H4 (plated holes), TP1/TP2 (test pads), JP_TERM1 (solder jumper).
- MIC1 (MA-HFA381) stock 368 — enough for 50 boards but thin.

## Price ESTIMATE (not a quote)
Based on JLCPCB public pricing rules as understood on 2026-10-11 (v11b numbers + v13 delta) (Standard PCBA setup ≈ $25, stencil ≈ $8, extended-part loading fee $3 per unique extended part, ≈ $0.0017 per solder joint) and live part prices. ≈886 SMD joints/board, 55 BOM lines (38 extended, 17 basic). Shipping, tax/duty and engineering-fee surprises are excluded; get a real quote by uploading the zip.

| Item | 5 boards | 50 boards |
|---|---:|---:|
| Bare PCB, 4L 148×99.5 mm, ENIG | ~$35–50 | ~$120–170 |
| PCBA setup + stencil | ~$33 | ~$33 |
| Extended-part fees (38 × $3) | ~$114 | ~$114 |
| Joints (886 × $0.0017 × qty) | ~$8 | ~$75 |
| Components (live JLC prices, with attrition; v13 adds ~$0.06/board) | ~$136 | ~$1064 |
| **Total** | **~$330–345 (~$66–69/board)** | **~$1405–1455 (~$28–29/board)** |

Dropping the stacking-port group (DNP) removes ~6 extended lines (~$18 in fees) plus ~$1.6/board in parts.

## FFC cables (off-board, order separately)

The board and the panel need **2 × 40-pin 0.5 mm FFC, Type B (reverse / opposite-side contacts), 0.3 mm thick with stiffened ends**. They are not part of the SMT order and are not in the JLCPCB BOM upload; they are listed in the annotated BOM.

- **Default (v15):** 120 mm, LCSC **C5371276** (JS05B-40P-120-4-8, Type B / reverse, same series), JLC stock 701, $0.154 each (@50 $0.121), checked 2026-10-11. 100 mm C2857750 was the v13 default and is now too short for most mountings.
- **Other lengths, same series (all Type B):** 80 mm C5371275, 100 mm C2857750, 150 mm C2857751, 200 mm C2857752.

A Type A (same-side) cable mirrors pins 1↔40, and nothing on the panel would light correctly; `firmware/mono_split/sim/bringup` (`cable.py`) derives this from the pad geometry.

The board's F.Silkscreen now has "FFC TYPE B" and "PIN1" beside J_ROW1/J_COL1 (silkscreen gerber regenerated; copper unchanged; DRC 0/0).
