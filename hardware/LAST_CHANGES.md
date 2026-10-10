# Latest changes

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
- `MONO_PRE_GRID_FANOUT=0` (default) — do not lock stubs before geometry dump.

### DRC gate rules (restored)

- Every GND stitch and post-grid step uses **`monotonic_gate_allows`**: 0/0 copper, unconnected non-increasing, **clearance non-increasing**.
- Trial edits apply **in-place** on `mono_electronics.kicad_pcb` with backup restore (KiCad DRC requires the project-linked PCB path; copies under `/tmp` inflate false clearance counts).
- `board_metrics()` refills zones before baseline DRC; post-edit metrics use `refill=False` when refill already ran.

### Committed board target (this pass)

- One-command generate → **`mono_electronics.kicad_pcb`**: ~**25** unconnected groups, copper **0/0**, **clearance 0** after `cleanup` (baseline clearance **1** preserved through gated steps).
- Per-net (typical): **AON_3V3 ~13**, **GND ~5**, plus open MCU signals (**DEC_A_EN_N**, **USB_D_N_MCU**, IMU, **LED_CLK**, **ROW_A3**).
- **AON**: In1 zone **Y≤14.85 mm** (was 9.35), IMU/translator In2 ties, split distant steps (`aon_ldo` / `aon_roe` / `aon_tp`); east dogbones **2/3/46/55/56**; **pad20** still gate-blocked.
- **ROW select**: **ROW_02..11** decoder→comb on **In2** (ROW_01 jog + ROW_12 pin13 stay **In1**). GND/AON MCU spines moved west (x≈26.5 / 32.5) on In2 with GND hook on **F** at y≈8.55 so In2 ROW legs stay **0/0** static.
- **MCU grid**: stale `*.mcu_geom.json` / `*.mcu_routes*.json` deleted each run; **ROW_*_Y** In2 tracks are **hard obstacles** in `mcu_grid/grid.py`; PathFinder **In1 layer cost 0.52** (F/In2/B unchanged). Full one-command end state: **24** unconnected groups, copper **0/0**, clearance **0** after cleanup.
- **Diagnostics**: `hardware/tools/aon_zone_diagnostic.py`.

### Panels

`mono_panel_*` remain **0/0/0**; generator restores panel PCBs from git at end of `generate_mono_split_boards.py`.
