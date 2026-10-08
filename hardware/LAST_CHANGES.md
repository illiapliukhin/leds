# Latest changes

## Mono split boards

- Added a black-and-white split architecture next to the existing RGB wearables. The RGB 20×20 and 28×28 boards are untouched.
- One electronics board now drives two LED-only panels through two 40-pin 0.50 mm FFC receptacles. The shared driver set is 32 rows × 32 columns, so the high-resolution panel is 32×32.
- Front of each LED panel is only the matrix and margins. Rear of each LED panel holds `J_ROW` and `J_COL`.
- First-pass outlines stay large: 136.3 mm and 166.7 mm panels, 120 × 80 mm electronics, 2.54 mm pitch, 44 mm panel margin for a non-crossing 32-net FFC fan-in.
- LED: NationStar `NCD0603W1` with datasheet pads. Connector land pattern: Hirose `FH12-40S-0.5SH`.
- Preliminary white LED rail is 4.24 V, not the RGB 4.10 V divider.
