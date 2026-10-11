# panel_id: firmware hook for the LED interface standard (stub / spec)

Not linked into `firmware/mono_split` yet. Another worker owns that tree; integration steps are below.

## Files
- `panel_id.h`: 64-byte EEPROM record (`panel_id_t`), enums, API.
- `panel_id.c`: CRC-16/CCITT-FALSE, `panel_id_read()` (probe + validate + default fallback), `panel_map()` (logical x,y → physical row/col).
- `mkpanelid.py`: builds 256-byte images; presets `flat32`, `flat20`, `lattice32`, `full32`, `garland32`, `wire32` (hardware/wire_grid_32x32: 32×32 LEDs on wires, 10 mm pitch, 960 Hz, long-wire blanking). Python and C CRC were cross-checked (garland32 image parsed by the C code; a corrupted byte falls back to `default32`).

## Boot sequence (spec)
1. `AON_3V3` up, I²C master on GPIO8/9 (`IMU_SDA`/`IMU_SCL`, existing 4.7 kΩ pull-ups, 100 kHz). Devices on the bus: MAX17048 0x36, BMI270 0x68, panel ID **0x50** (through J_ROW 35/36; on the v12 main board these are wired through R_ID_SDA1/R_ID_SCL1 33 Ω with D_ID1 PESD5V0S2BT on the bus side). Use 100 kHz while a panel is attached: the cable, panel and TVS add ≈70 pF, giving tr ≈ 0.85·4.7 kΩ·~150 pF ≈ 0.6 µs.
2. `panel_id_read(i2c_read, &id)`: one 64-byte random read from word address 0x00. No ACK, bad magic/version/CRC, or out-of-range size → `panel_id_default()` (flat 32×32 white, identity, 2 µs blank) and log `panel: legacy/no-id`.
3. Apply:
   - scan: rows `id.rows` (skip rows not in `row_mask`), shift `id.cols` bits (`>32` only with a column expansion: class `PANEL_COL_EXPANSION`);
   - current: clamp the brightness/duty so the peak stays ≤ `i_led_ua` and `rows × cols_lit × i_led ≤ i_row_ma` per row (MBI5124 current is fixed by Rext, so firmware limits on-time, not amplitude);
   - timing: `blank_ns`, and `predischarge_ns` if `PANEL_FLAG_LONG_WIRES` (sequence in GARLAND_REFERENCE_BUILD.md);
   - scan rate: `scan_div` divides the v13 LCD_CAM row clock (1 = 960 Hz, 32.55 µs/row; 2 = 480 Hz garland mode, 65.1 µs/row). `garland32` uses 480 Hz with 3 µs blank + 1 µs pre-discharge, i.e. 6.1 % overhead, the same as a panel's 2 µs blank at 960 Hz;
   - mapping: framebuffer (x,y) → `panel_map()` → (row, col) → MBI bit / decoder address. `MAP_TABLE` uses a built-in LUT selected by `table_id` (for freeform nets; 24C02 has no room for a 1024-entry LUT).
4. Report `id.name`, `serial`, size and class to the stacking leader in the topology-discovery reply, so the leader can build the global canvas of mixed tiles.
5. Re-probe on USB command `panel rescan` (hot-plug is not supported while the scan is running: stop the scan first).

## Provisioning
`mkpanelid.py --preset garland32 --serial N -o x.bin`, then write it either through the main board (`panel write` console command, WP is tied low on loads) or with a clip programmer.
