# Scaling beyond 32×32: options and recommendation

Baseline: one electronics board drives 32 rows × 32 columns at 1/32 duty. The row high side gives 0.32 A per row (32 × 10 mA); each LED averages 10 mA / 32 = 0.31 mA. The ESP32 has no free GPIOs left (see the GPIO map in MONO_SPLIT_ARCHITECTURE.md).

| Option | What changes | Duty | Row current | Brightness / pixel | Refresh cost | Main-board change |
|---|---|---|---|---|---|---|
| **A. Tile boards** over the stacking ports (64×32 = 2 boards, 64×64 = 4) | nothing; each board drives its own 32×32 tile, the leader streams frames over RS-485 and `FRAME_SYNC` aligns the row scan | 1/32 | 0.32 A | unchanged | unchanged, shift time per board unchanged | **none** |
| B. Column expansion: +2 MBI5124 on an expansion board, SDI chained from `U_LED2` SDO, 32 rows × 64 cols | expansion board on J_COL pins 34–37/39 (EXP_*); 64-bit shift per row | 1/32 | **0.64 A** at 10 mA (above the 0.5 A FFC contact); stays 0.32 A only if `i_led` drops to 5 mA | unchanged at 0.64 A; halved at 5 mA | shift 64 bits instead of 32 (still < 3 µs at 25 MHz) | route U_LED2 SDO + CLK_Y/LE_Y/OE_Y + 3V3 to J_COL1 34–37/39, GND on 33/38/40; row current needs a remote row repeater or ≤ 5 mA columns |
| C. Row expansion: 2nd decoder pair + 32 more P-FETs, 64 rows × 32 cols | needs one more address/enable signal (no free GPIO) and 32 more high-side lines (no FFC pins left) | **1/64** | 0.32 A | **halved** (needs 2× peak current to compensate; MBI5124 and LED efficiency droop limit this) | refresh rate halves at the same row time | new GPIO (e.g. share GPIO26/PRES_W), second row FFC, 32 FETs: effectively a new board |
| D. B + C (64×64 on one board) | both | 1/64 | 0.64 A | ¼ of tiled | 2× | both, i.e. a different product |

## Recommendation

**Option A, tiling.** It needs no copper change. Brightness and refresh stay at the 32×32 values, and each tile keeps its own short LED wiring (that wiring is what limits garlands). The system already has the infrastructure: four stacking ports, RS-485, `FRAME_SYNC`, and PRES topology discovery. Each tile also carries its own panel-ID EEPROM, so the leader learns size and mapping per tile. Costs: one electronics board per 32×32 (~$25–35 BOM), plus RS-485 bandwidth. A 64×64 1-bit frame is 512 B. At 1 Mbit/s that is ~5 ms per frame; 4-bit grey is ~20 ms. That fits 30–50 fps if the leader sends deltas, or if each board renders locally from a shared scene and a shared time base (preferred).

**Keep B as the single-board 64×32 path** for a later revision: wide strips and garland rows ≤ 1 m where a second ESP32 is not wanted. It only becomes worthwhile together with a "row repeater" expansion that re-drives each row through its own P-FET from local VLED (this is also where `VINJ` on the garland breakout gets used). Without the repeater, run 5 mA columns.

**Do not do C.** It halves brightness, costs a GPIO the board does not have, and needs 32 more high-side lines through a connector that has no pins left.

## Main-board changes (none required for the recommended option)

To make the standard complete (ID + expansion-ready), the next main-board revision should:

1. `J_ROW1` pins 33, 38, 40 → `GND`; pin 35 → `IMU_SDA`, pin 36 → `IMU_SCL` (each through 33 Ω series, plus a PESD3V3S2UT dual TVS at the connector); pin 37 → `AON_3V3` through 100 Ω (limits ID supply and short-circuit current); pin 39 (`ID_PRESENT_N`) → optional, firmware uses EEPROM ACK instead (no free GPIO); pin 34 (`VLED_SENSE`) → optional ADC divider, NC is acceptable.
2. `J_COL1` pins 33, 38, 40 → `GND`. Pins 34–37 → `U_LED2` SDO (`LED_SDO2`, today open), `LED_CLK_Y`, `LED_LE_Y`, `LED_OE_Y` through 33 Ω, with DNP options so they can stay unloaded. Pin 39 → `LED_LOGIC_3V3` through a 0 Ω / polyfuse (DNP).
3. Optional: per-row 10 kΩ bleed (row → GND) for hardware pre-discharge of long garland rows (0.4 mA × 1/32 duty waste). Firmware pre-discharge (see GARLAND_REFERENCE_BUILD.md) covers it until then.

The board works without any of these. Until item 1 exists, firmware never sees an EEPROM and uses the default profile. The garland breakout still provides ESD/TVS and fan-out, but its TVS GND return only goes through the breakout mounting holes / `J_INJ` pin 1 to installation earth.
