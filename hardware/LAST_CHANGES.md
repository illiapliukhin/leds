# Latest changes

## Mono schematic + fab tooling (2026-10-10)

- **`hardware/mono_schematic/`** — programmatic KiCad 10 hierarchical schematic for `mono_electronics` (181 refs, pad nets from committed PCB). Regenerate: `python3.11 hardware/mono_schematic/tools/generate_mono_schematic.py`. Cross-check: `compare_sch_pcb_nets.py` (181/181 match). ERC: `tools/run_erc.sh` (see `ERC_WAIVERS.md`). Design report: `DESIGN_ISSUES.md`.
- **`manufacturing/mono_split/`** — `tools/make_fab.sh` → Gerbers, drill, CPL (`positions.csv`), BOM CSV, PDF/SVG. Committed **READY** packages for `mono_panel_20x20` and `mono_panel_32x32`; `mono_electronics` dry-run only (`output/mono_electronics_NOT_READY/`, gitignored).

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
