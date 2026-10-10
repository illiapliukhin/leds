# mono_electronics v11 — JLCPCB fab package (from PR #4 board, v10b + phase-1 cleanup)

Board: 148.0 × 99.5 mm, 4 layers (F / In1 / In2 / B), single-sided assembly (top only). KiCad DRC 0 errors / 0 warnings / 0 unconnected.

## Files
- `gerbers/` — Protel extensions, no X2, soldermask subtracted from silk, drill-file (aux) origin. Layer order for the JLC stackup: GTL (F.Cu) / G1 (In1) / G2 (In2) / GBL (B.Cu). Excellon drill, mm, separate PTH / NPTH, with drill maps.
- `BOM_mono_electronics_v11_JLCPCB.csv` — JLC upload format (Comment, Designator, Footprint, LCSC Part #).
- `BOM_mono_electronics_v11_annotated.csv` — with MPN, basic/extended, live stock and unit price (queried from the JLCPCB parts API on 2026-10-10), and flags.
- `CPL_mono_electronics_v11.csv` — placement (Designator, Mid X, Mid Y, Layer, Rotation), 217 placed parts, all Top.

## Order settings (JLCPCB)
4 layers, FR-4, 1.6 mm (project rule says 1.0 mm — pick deliberately), JLC04161H-7628 or any stackup with ≥0.127 mm trace/space capability (board min other-net spacing 0.127 mm, min track 0.125 mm, vias 0.40/0.20 mm), ENIG recommended (QFN/LGA/VQFN fine pitch), tented vias, Standard PCBA, top side, remove order number or "specify position".

## Flags before ordering
- Check every rotation in the JLC CPL preview (KiCad → JLC offsets are typical on SOT-23, SOT-23-6, QFN, the FFC and JST connectors).
- J_USB: footprint is HRO TYPE-C-31-M-12; ordered as HRO C165948. The PCB value field still says USB4105 (cosmetic).
- Y1: original part (L327S400H11L) not stocked; substitute Yangxing X3S040000BA1H-R C136083 (40 MHz, 3225, 10 pF, ±10 ppm), only 882 in stock.
- TH_PCB: Sunlord SDNT1005X103F3435FTF (10 k, B3435) C279801.
- R_ISET: 600 R not stocked, 620 R (C4961) used — BQ25185 charge current about 3 % lower.
- J_PORT_*: XY clone of JST SM06B-SRSS-TB (C56123098, 1291 in stock); genuine JST 6P SH right-angle not in the JLC library. Ports are DNP-friendly: drop the 4 ports + 8 ESD + U_485/C_485/R_TERM lines to save cost.
- Not assembled: H1–H4 (plated holes), TP1/TP2 (test pads), JP_TERM (solder jumper).
- MIC1 (MA-HFA381) stock 368 — enough for 50 boards but thin.

## Price ESTIMATE (not a quote)
Based on JLCPCB public pricing rules as understood on 2026-10-10 (Standard PCBA setup ≈ $25, stencil ≈ $8, extended-part loading fee $3 per unique extended part, ≈ $0.0017 per solder joint) and live part prices. 871 SMD joints/board, 52 BOM lines (37 extended, 15 basic). Shipping, tax/duty and engineering-fee surprises are excluded; get a real quote by uploading the zip.

| Item | 5 boards | 50 boards |
|---|---:|---:|
| Bare PCB, 4L 148×99.5 mm, ENIG | ~$35–50 | ~$120–170 |
| PCBA setup + stencil | ~$33 | ~$33 |
| Extended-part fees (37 × $3) | ~$111 | ~$111 |
| Joints (871 × $0.0017 × qty) | ~$7 | ~$74 |
| Components (live JLC prices, with attrition) | ~$137 | ~$1060 |
| **Total** | **~$325–340 (~$65–68/board)** | **~$1400–1450 (~$28–29/board)** |

Dropping the stacking-port group (DNP) removes ~6 extended lines (~$18 in fees) plus ~$1.6/board in parts.
