# mono_electronics v13 — JLCPCB fab package (PR #4 board)

Board: 148.0 × 99.5 mm, 4 layers (F / In1 / In2 / B), single-sided assembly (top only). KiCad DRC 0 errors / 0 warnings / 0 unconnected.

## Files
- `gerbers/` — Protel extensions, no X2, soldermask subtracted from silk, drill-file (aux) origin. Layer order for the JLC stackup: GTL (F.Cu) / G1 (In1) / G2 (In2) / GBL (B.Cu). Excellon drill, mm, separate PTH / NPTH, with drill maps.
- `BOM_mono_electronics_v13_JLCPCB.csv` — JLC upload format (Comment, Designator, Footprint, LCSC Part #).
- `BOM_mono_electronics_v13_annotated.csv` — with MPN, basic/extended, live stock and unit price (queried from the JLCPCB parts API on 2026-10-11), and flags.
- `CPL_mono_electronics_v13.csv` — placement (Designator, Mid X, Mid Y, Layer, Rotation), 231 placed parts, all Top (R_EXP_* are DNP and excluded).

## Order settings (JLCPCB)
4 layers, FR-4, 1.6 mm (project rule says 1.0 mm — pick deliberately), JLC04161H-7628 or any stackup with ≥0.127 mm trace/space capability (board min other-net spacing 0.127 mm, min track 0.125 mm, vias 0.40/0.20 mm), ENIG recommended (QFN/LGA/VQFN fine pitch), tented vias, Standard PCBA, top side, remove order number or "specify position".

## Flags before ordering
- **v13b:** J_BAT1 is now JST PH S3B-PH-SM4-TB(LF)(SN) (C265101, JLC stock 865, enough for 50 boards; 2 A/contact). The battery lead needs a JST PHR-3 housing (pin 1 BAT+, 2 NTC, 3 GND). The annotated BOM stock and prices were refreshed from the JLCPCB parts API on 2026-10-11 (66 of 70 lines; the rest are not assembled).
- **v13 protections (see hardware/mono_electronics/ABSMAX_REVIEW_v13.md):**
  - F_BAT1 0466002.NRHF 2 A very-fast 1206 fuse (C3105, LCSC stock 33,770) right at J_BAT1.
  - Q_BAT1 AO3401A (C15127, basic) reverse-battery ideal-diode P-FET with R_BATG1 10 k gate pull-down. BAT copper is 1.0 mm on F from J_BAT1 to Q_BAT1, and the In1 BAT_RAW riser is 0.8 mm.
  - U_OVP1 TPS259531DSGR eFuse (C2155674, JLC stock 2,988): 5.7 V OV clamp, R_ILM1 2.7 k (C25885) gives a 0.79 A limit, UVLO 4.28 V from R_EN_TOP1 100 k / R_EN_BOT1 39 k (C25783, verify).
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

- **Default:** 100 mm, LCSC **C2857750** (JS05B-40P-100-4-8), about $0.14 each, 1289 in stock at lookup time.
- **Other lengths, same series (all Type B):** 80 mm C5371275, 120 mm C5371276, 150 mm C2857751, 200 mm C2857752.

A Type A (same-side) cable mirrors pins 1↔40, and nothing on the panel would light correctly; `firmware/mono_split/sim/bringup` (`cable.py`) derives this from the pad geometry.

The board's F.Silkscreen now has "FFC TYPE B" and "PIN1" beside J_ROW1/J_COL1 (silkscreen gerber regenerated; copper unchanged; DRC 0/0).
