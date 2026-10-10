# Latest changes

## Mono split boards (PR #4) — reproducibility pass (2026-10-09)

### Reproduce command (KiCad 10 AppImage + system Python deps)

```bash
cd /workspace
source hardware/tools/kicad10_env.sh
# System Python (not AppImage): numpy, scipy, matplotlib for mcu_grid_compute
env -u PYTHONHOME -u PYTHONPATH \
  /workspace/.kicad10/squashfs-root/usr/bin/python3.11 \
  hardware/tools/generate_mono_split_boards.py
```

Optional env:

- `MONO_RECOMPUTE_ROUTES=1` — force PathFinder/greedy recompute (default: compute each run).
- `MONO_POST_GRID_PHASES=gnd,aon_zone,aon,grid_one,cleanup` — default post-grid sequence (grid_one only commits when copper stays 0/0).
- `MONO_PRE_GRID_FANOUT=1` — locked GND/AON stubs before geometry dump (default **off**; fanout before grid currently breaks DRC gate — do not enable until geometry is reconciled).

### Pipeline changes

- **Post-grid phases** no longer roll back the whole phase when one sub-step fails; `aon` / `aon_zone` / `grid_one` commit per-step via `_try_signal_step` (monotonic unconnected/clearance vs phase start, 0/0 copper).
- **Aggregate post-grid gate** in `mcu_grid_route.py`: revert only on copper shorts/crossings, or if unconnected/clearance regress vs pre-post-grid snapshot (not on partial copper shorts from a single phase).
- **Cleanup**: dangling F.Cu stubs removed one-at-a-time with monotonic gate; zone refill before gate metrics.
- **AON In1 zone**: north pads use outward (−Y) dogbones; zone ties include In2 spine + translator; skip duplicate `aon_north` / `aon_in2` when zone present.
- **GND stitch**: baseline-validated fixed via fallbacks for `C_USB1:2`, `U_ESD:5`, `C_MCU1:2`, `U_IMU:6/7` when dogbone search finds nothing.
- **Grid merge**: greedy supplement for PathFinder rip-up victims (`merge_greedy_one_at_a_time` + rip-recovery set).

### DRC targets

- **Committed board (this pass)**: `MONO_POST_GRID=0` grid **37** → **`gnd` + `aon_zone`** → **23** unconnected, copper **0/0/0** (`AON_3V3` **13**, `GND` **3**). `hole_to_hole` at hub **50.8 mm** removed via `dedupe_aon_hub_vias`; pad **2** dogbone disabled (F escape shorts USB/GND).
- **Diagnostics**: `hardware/tools/aon_zone_diagnostic.py` — U1 AON pads, vias, In1 zone outline after refill.
- **Next**: per-pad east dogbones **46/55/56**, `pad20` chain, distant AON (LDO/TP), remaining **GND** stitches without ROW shorts, PathFinder for **DEC_A_EN_N** / **USB_D_N_MCU** / **IMU** / **LED_CLK** / **ROW_A3**.

### Panels

Both `mono_panel_*` remain **0/0/0**; generator still restores panel PCBs from git at end of `generate_mono_split_boards.py`.
