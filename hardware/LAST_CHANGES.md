# Latest changes

## Mono split boards

- Added a black-and-white split architecture next to the existing RGB wearables. The RGB 20×20 and 28×28 boards are untouched.
- One electronics board now drives two LED-only panels through two 40-pin 0.50 mm FFC receptacles. The shared driver set is 32 rows × 32 columns, so the high-resolution panel is 32×32.
- Front of each LED panel is only the matrix and margins. Rear of each LED panel holds `J_ROW` and `J_COL`.
- First-pass outlines stay large: 136.3 mm and 166.7 mm panels, 160 × 110 mm electronics, 2.54 mm pitch, 44 mm panel margin for a non-crossing 32-net FFC fan-in.
- Every mono LED stays independently addressable. On the electronics board each row and each column is now a single copper net from the driver pad to its FFC pin. `LED_4V1` is not tied into one rail yet. BMI270 and scan/blank nets still end on reserve pads.
- ESP32-S3 sits on the top edge, with the crystal under it and BMI270 on that same edge. The open strip to the right is the MCU pin-escape field.
- LED: NationStar `NCD0603W1` with datasheet pads. Connector land pattern: Hirose `FH12-40S-0.5SH`. Row-farm 0402 references are on `F.Fab`; transistor references stay on silk.
- Preliminary white LED rail is 4.24 V, not the RGB 4.10 V divider.
- Panel row fan-in is a front U-turn into a 0.55 mm via row, then back-copper L-routes to `J_ROW`. Columns stay on back copper, turn onto pad centerlines above the `J_COL` courtyard, and drop vertically. Both panels and the electronics board pass geometric DRC; electronics still has expected unconnected nets.
