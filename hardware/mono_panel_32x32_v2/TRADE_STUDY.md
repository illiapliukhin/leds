# mono_panel_32x32_v2 — LED trade study (2026-10-12)

Constraints: anode=row (AO3403), cathode=column (MBI5124, ≤10 mA), VLED 4.24 V, Vf ≤ 3.38 V @ 10 mA, row drop ≤ 0.35 V, JLC PCBA, JLC max 470×500 mm.
Stock and prices are from LCSC on 2026-10-12 (fab/lcsc_stock_2026-10-12.txt).

| Part (LCSC) | Pkg | Lib | Stock | $/pc | Light (datasheet) | Est. @10 mA | Vf | Angle | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| NCD0603W1 (C84265) | 0603 | ext | 659k | 0.011 | 300 mcd @20 mA | ~0.15 cd | 2.6–3.6 V | 130° | current v1, too small/dim at 8 mm |
| KT-0603W (C2290) | 0603 | basic | 1.28M | 0.0066 | 360 mcd @5 mA | ~0.5 cd | 2.6–3.1 | 120° | cheap, but a dot at 8 mm |
| KT-0805W (C34499) | 0805 | basic | 236k | 0.013 | 350 mcd | ~0.3 cd | 2.6–3.2 | 120° | small |
| XL-3216UWC (C965828) | 1206 | ext | 106k | 0.0074 | 1.3 cd @20 mA | ~0.7 cd | 3.4 V typ @20 mA | 120° | Vf too close to the 3.38 V limit |
| KT-1206W (C71796) | 1206 | — | 5.2k | — | 430 mcd @5 mA | — | — | — | stock too low for 30×1024 |
| XL-3528UWC (C2843809) | 3528 | — | 558k | 0.0129 | 4–10 lm @20 mA | 2–5 lm | 2.8–3.4 @20 mA | 120° | good, ~2× the price of the 2835 |
| **XL-2835UWC-02 (C2843876)** | **2835** | ext | **364,950** | **0.0066** | 20–33 lm @60 mA | **4–6.6 lm (~1.5–2 cd)** | **~2.35 typ / 2.75 max @10 mA** | 120° | **chosen** |
| XL-504UWC (C2895481) | 5 mm THT | — | 16.5k | 0.0216 | 30 cd | — | 3.6 V @20 mA | 30° | narrow beam, THT cost, Vf |
| XL-502UWC (C2895480) | 5 mm THT | — | 66k | — | 20 cd | — | 3.3 V | — | THT, narrow beam |

**Choice: XL-2835UWC-02 at 8.0 mm pitch, 256×256 mm, 4 layers 1.6 mm.**
- Bigger part: 2.8×3.5 mm emitter, wide 120° lambertian. At 10 mA it gives roughly 10× the light of NCD0603W1.
- The cheapest LED in the table, with 365k in stock (≈11 boards' worth; buy the full lot for 30 boards: 30,720 + attrition).
- Vf at 10 mA (from the IV curve) is 2.35 V typ / ≈2.75 V max. That leaves ≥0.6 V margin to the 3.38 V budget, and sink headroom is ≈1.26 V worst case.
- Pitch: 8 mm (2.3× the LED body) keeps the dots distinct and leaves 2 channels per cell for buses/vias. 256 mm is far below the JLC 470×500 limit.
  - A 10 mm pitch (320 mm) would raise PCB cost by about 1.56× for no gain.
  - 6 mm does not leave room for the 2.6 mm bus offset plus the via grid.
- Layers: F = LEDs + 1.0 mm row buses; In1 = column lines; In2 = GND + column fan-out; B = connectors, row fan-out, GND.
  - 2 layers were rejected: the connector escape is infeasible without breaking the column grid.

## Cost estimate per panel (JLC, USD, excl. shipping/tax)
| Item | 5 pcs | 30 pcs |
|---|---|---|
| PCB 4L 256×256 1.6 mm (~$0.055/cm² → ~$0.035/cm²) | 36 | 23 |
| LEDs 1024 × $0.0066 (+2% attrition) | 6.9 | 6.9 |
| 2× FH12 + EEPROM + cap | 1.6 | 1.2 |
| Joints (~2,140 × $0.0017) | 3.6 | 3.6 |
| Setup + stencil both sides + 3 extended part fees (~$39 per order) | 7.8 | 1.3 |
| **Total ≈** | **~$56** | **~$36** |

Option: assemble the top side only and hand-solder the 4 bottom parts. This saves the second setup and stencil (~$15 per order).

## Risks
- The 2835 3D model is a generated VRML (not a vendor STEP). Check LED polarity and rotation in the JLC CPL preview: pin 1 = large pad = cathode.
- FH12 C202114 has 5,021 in stock, enough for 2,500 boards. The 2×20 shrouded headers (C42462832, only 125 in stock) are **not** placed. The standard allows FFC alone.
- The FFC length dominates row drop. Keep it ≤200 mm (see README).
