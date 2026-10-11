# Virtual bench bring-up (v12c)

`run_bringup.sh` starts the real `mono_split` firmware (MONO_SIM build) in Espressif QEMU and opens a pygame scene of a bench session. It shows a top render of `mono_electronics` v11b (`kicad-cli pcb render` of the committed .kicad_pcb), two FFC ribbons, and `mono_panel_32x32` with its 1024 LEDs placed from that panel's .kicad_pcb. The firmware console is shown live.

## Electrical model (`netmodel.py`, `cable.py`)

**Board side.** Built from the real `.kicad_pcb` pad nets:
- **Rows:** firmware row r → DEC_A (r<16) or DEC_B → 74HC154 output Y(r&15), using the datasheet pins → `ROW_xx_Y` → `R_Gxx` → `ROW_xx_GATE` → the AO3403 with that gate (source checked on `LED_4V1`) → drain net.
- **Columns:** the 32-bit word goes out MSB first into `LED_SDI_Y` → U_LED1 → SDO → U_LED2. Bit c lands on OUT(c%16) = pin 5+c%16 of chip c//16.

**Cable.** `cable.py` computes the conductor mapping from the receptacle pad coordinates. Inputs: cable exit direction (both board receptacles exit east; panel J_ROW exits west, J_COL south), mounting side (board F.Cu, panel B.Cu), FH12 bottom contact (exposed contacts face the PCB), and the FFC type. The result does not change with how the ribbon is bent, folded or twisted.
- **Type B (opposite-side contacts):** pin 1→1, 0 net errors.
- **Type A (same-side contacts):** pin 1→40, all 32 nets wrong.

**Panel side.** Panel connector pad → panel net → LED (pad 2 = `ROW_xx_ANODE`, pad 1 = `COL_xx`). An LED lights only when its anode net, traced back through cable and board, is the row being driven AND its cathode net is a column being sunk.

**Readout.** Per-row current = lit columns × 10.2 mA (estimate). Drop = I × R(row) from `ir_v3.json`.

## Session

1. Pinout check.
2. VBUS → SYS → AON_3V3 → CHIP_PU, using the datasheet timeline. LED_LOGIC_3V3, LED_4V1 and the translator OE come from the real firmware power_seq log lines.
3. Boot and `i2cscan` (BMI270 and MAX17048 are mocked in MONO_SIM).
4. `test all`, `row`, `col`, `checker`. Each complete scan is checked LED by LED: design intent vs. what lights through copper and cable.
5. Fault 1: Type A cables. Fault 2: COL conductor 7 open.
6. `bench_report.md`, then `demo cycle`, left running.

## Panel selection (`--panel`)

`bringup.py --panel mono32` (default), `--panel lattice` or `--panel full`. You can also set `BRINGUP_PANEL=lattice`. `panels.py` holds the per-panel settings: the `.kicad_pcb`, the pad dump, the cable exit directions for `cable.py`, the background image and the IR model.
- **mono32**: unchanged. Uses `panel.json`, `cable_check.json`, `ir_v3.json`, `bench_report.md`.
- **lattice**: `hardware/mono_panel_32x32_lattice`. `panel_lattice.json` is re-dumped from the `.kicad_pcb` with `pdump.py` (KiCad 10 python) whenever the board is newer. Both receptacles sit on the south tab with the cables exiting south, and `cable.py` re-derives Type B = pin 1→1 for that geometry (`cable_check_lattice.json`). The drop readout keeps the board part of `ir_v3.json` and swaps in the lattice panel copper from `analysis.json`. The scene shows the lattice (bars and windows) with lit LEDs. Outputs: `bench_report_lattice.md`, `bench_session_lattice.log`, `png/bringup_lattice_*.png`.
- **full**: `hardware/mono_panel_32x32_full` (edge-to-edge, 5.0 mm pitch, 160 × 160 mm, 4 layers). `panel_full.json` is re-dumped from the `.kicad_pcb` the same way. Both receptacles are on the back near the centre with the cables exiting south; `cable.py` re-derives Type B = pin 1→1 (`cable_check_full.json`). The drop readout swaps in the full panel's row copper from its `analysis.json`. Outputs: `bench_report_full.md`, `bench_session_full.log`, `png/bringup_full_*.png`.

QEMU runs from a private flash copy (`/tmp/bench_bringup_fw.bin`) under a private process name, and only its own instance (port 5555) is killed on restart. This lets the stacking sim's QEMUs run alongside it.
