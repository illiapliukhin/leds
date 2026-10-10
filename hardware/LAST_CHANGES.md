# Latest changes

## Mono electronics: connectors moved west, board 167.4 x 99.5 mm (PR #4, 2026-10-10)

- J_ROW -> (162.4, 22) and J_COL -> (162.4, 68.6): still on the right edge, cable exit right, pinout unchanged. Row fan-in shortened 19.6 mm per net; the COL fan was moved with J_COL as one block.
- Edge.Cuts 187 x 99.5 -> **167.4 x 99.5 mm** (-40.8 % vs. the original 190 x 148). Total track length 16.93 -> 15.47 m; worst LED anode drop 117.6 -> **107.3 mV**.
- GND In2/B clipped and refilled; every B GND piece has >= 2 vias to In2.
- Branding text + star (Cmts.User) moved into the bottom strip inside the board; stale Dwgs.User boxes removed.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 parts on B; 13 silk warnings. Image: `hardware/mono_electronics/img/v3_F.png`.


## Mono electronics: board outline shrunk to 187 x 99.5 mm (PR #4, 2026-10-10)

- Edge.Cuts 190 x 148 mm -> **187 x 99.5 mm** (-9,514 mm2, ~34 %). The south band y 97-148 and the strip x 185-190 were empty; no blocks moved, routing unchanged.
- J_USB stays on the west edge; J_ROW/J_COL end 2 mm from the east edge. No mounting holes on the board.
- GND In2/B pours clipped to the new outline and refilled; 118 stitch vias outside it removed; every B GND piece still has >= 2 vias to In2.
- Obsolete Dwgs.User note "SCAN AND IMU SIGNAL RESERVE" removed.
- KiCad 10 DRC: 0 errors, 0 unconnected, 0 parts on B; warnings silk_over_copper 7, silk_overlap 6. Worst LED anode drop 117.6 mV.
- Image: `hardware/mono_electronics/img/v2_F.png`.


## Mono electronics: hand-routed board is now the source of truth (PR #4, 2026-10-10)

`hardware/mono_electronics/mono_electronics.kicad_pcb` was reworked by hand (pcbnew API, one gated change at a time: 0 shorts / 0 crossings / 0 clearance / 0 unconnected, no net relabels, dangling count not increasing, no parts on B.Cu). **The generator output no longer matches this board**; update the generator/schematic from `hardware/mono_electronics/REWORK_LOG.md` before regenerating.

Final state (KiCad 10 DRC, all severities): **0 errors, 0 unconnected**; warnings: silk_over_copper 7, silk_overlap 6. 184 footprints, **all on F.Cu** (single-sided assembly).

Main changes:
- Netlist fixes: USBLC6 pinout (D-, VBUS, GND), **R_CC1/R_CC2 5.1k** CC pull-downs, BMI270 SDO->GND / CSB->VDDIO + 4.7k I2C pull-ups, translator EP->GND. MIC1, U_AUDIO, U_GAUGE, TH_PCB removed (deferred); AUDIO_EN kept.
- Decoupling for MBI5124, 74HC154, LVC8T245, LV125A, BMI270, TPS22917 output, ESP32-S3 (per Espressif guide), 24 nH on XTAL_P; CHIP_PU RC at the pin. All former bottom-side parts moved to the top.
- LED power: LED_4V1 pour on In1, anodes rerouted short on B/F: worst row drop **722 mV -> 117.6 mV** at 0.32 A.
- TPS63802: L/Cin/Cout within ~2 mm, double GND vias, EP vias; output-cap GND -> IC GND **33.6 -> 1.26 mOhm**.
- **In2 = continuous GND plane** (one piece, full outline); signal copper on In2 **4297 mm -> 27.6 mm** (IMU_INT1 19.7 mm, VBUS 7.9 mm, accepted). B GND pour full outline, every piece >= 2 vias, ~260 stitching vias.
- USB D+/D- fully on F, length-matched (A: 57.03/56.93 mm, B: 54.47/54.06 mm). The single crossing is between R_USB_P's pads (topologically required on one layer).
- Reserve pads RP01-RP16 and their stubs removed; LED_CLK/SDI pull-downs moved to the buffer; detours smoothed, duplicate/dangling copper removed.
- Images: `hardware/mono_electronics/img/final_F.png`, `final_In2.png`, `final_mcu_F.png`.


## Mono split boards (PR #4) — clearance gate + one-command generate (2026-10-10)

### Reproduce (single command)

```bash
cd /workspace
source hardware/tools/kicad10_env.sh
env -u PYTHONHOME -u PYTHONPATH \
  /workspace/.kicad10/squashfs-root/usr/bin/python3.11 \
  hardware/tools/generate_mono_split_boards.py
```

Default **`MONO_POST_GRID=1`** runs phases **`gnd,aon_zone,aon,grid_one,cleanup`** via `mono_split_post_grid_finish.py` (subprocess per phase). Aggregate revert in `mcu_grid_route.py` if copper or monotonic (unconnected/clearance) regresses vs pre-post-grid snapshot.

Optional env:

- `MONO_POST_GRID=0` — grid + zone refill only (debug).
- `MONO_POST_GRID_PHASES=...` — override phase list.
- `MONO_EMBED_U1_AON_FANOUT=1` (default) — locked U1 AON stubs/vias at end of `generate_electronics_board`.
- `MONO_PRE_GRID_FANOUT=0` (default) — avoid double fanout before geometry dump.
- `MONO_AON_IN1_KEEPOUT=1` (default) — grid avoids In1 inside AON pocket.
- `MONO_FANOUT_GND_FIXED=0` (default) — optional pre-grid GND fallbacks (`mono_split_copper_utils.GND_STITCH_FIXED_FALLBACK`).

### DRC gate rules (restored)

- Every GND stitch and post-grid step uses **`monotonic_gate_allows`**: 0/0 copper, unconnected non-increasing, **clearance non-increasing**.
- Trial edits apply **in-place** on `mono_electronics.kicad_pcb` with backup restore (KiCad DRC requires the project-linked PCB path; copies under `/tmp` inflate false clearance counts).
- `board_metrics()` refills zones before baseline DRC; post-edit metrics use `refill=False` when refill already ran.

### Committed board target (this pass)

- One-command generate → **`mono_electronics.kicad_pcb`**: **26** unconnected (gate **&lt;24** not met), copper **0/0**, clearance **0** after cleanup.
- **Structural AON fix**: pre-grid U1 fanout (pads **2+3**, **55+56**, **20/29/46** dogbones + vias) embedded in generate; geometry dump logs **locked AON tracks=6**; **In1 AON fill = 1 polygon**, **0** foreign In1 slicers in pocket.
- **ROW_01**: comb on **In2** @ **y=9.7**; west **GND** In2 stub shortened to **y=8.55** (no crossing with ROW_01).
- Post-grid **skips** redundant U1 dogbones (fanout already locked); **`tie_*`** distant AON steps still run under monotonic gate.
- **Diagnostics**: `hardware/tools/aon_zone_diagnostic.py` (zone refill, fill-poly index, foreign In1 slicers in pocket).
- **`grid_one`**: default net list includes **DEC_B_EN_N** (was ROW_A3).

### Panels

`mono_panel_*` remain **0/0/0**; generator restores panel PCBs from git at end of `generate_mono_split_boards.py`.

### Backlog (same DRC gate)

See **`hardware/MONO_ELECTRONICS_BACKLOG.md`**:

1. **Full-board GND zones** on In2/B (extend past 151×137 mm; stitch at J_ROW/J_COL fan-in).
2. **USB-C CC1/CC2** — **5.1 kΩ** pulldowns to GND (sink/UFP) for C-to-C VBUS.
