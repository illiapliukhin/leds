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
- `MONO_POST_GRID_PHASES=gnd,aon_zone,aon` — default post-grid sequence (`cleanup` opt-in; disabled by default while stub removal is stabilized).
- `MONO_PRE_GRID_FANOUT=1` — locked GND/AON stubs before geometry dump (default **off**; fanout before grid currently breaks DRC gate — do not enable until geometry is reconciled).

### Pipeline changes

- **Post-grid phases** no longer roll back the whole phase when one sub-step fails; `aon` / `aon_zone` / `grid_one` commit per-step via `_try_signal_step` (monotonic unconnected/clearance vs phase start, 0/0 copper).
- **Aggregate post-grid gate** in `mcu_grid_route.py`: revert only on copper shorts/crossings, or if unconnected/clearance regress vs pre-post-grid snapshot (not on partial copper shorts from a single phase).
- **Cleanup**: dangling F.Cu stubs removed one-at-a-time with monotonic gate; zone refill before gate metrics.
- **AON In1 zone**: north pads use outward (−Y) dogbones; zone ties include In2 spine + translator; skip duplicate `aon_north` / `aon_in2` when zone present.
- **GND stitch**: baseline-validated fixed via fallbacks for `C_USB1:2`, `U_ESD:5`, `C_MCU1:2`, `U_IMU:6/7` when dogbone search finds nothing.
- **Grid merge**: greedy supplement for PathFinder rip-up victims (`merge_greedy_one_at_a_time` + rip-recovery set).

### DRC targets

- **Reproducible generate output (this pass)**: grid **37** unconnected → post-grid **`gnd,aon_zone,aon`** → **28** unconnected, copper **0/0** (committed `mono_electronics.kicad_pcb` matches this pipeline trial).
- **Previous hand baseline (run #7)**: **24** unconnected — not yet matched by a single generate; gap is mostly **GND** (6 vs 2 groups) and **AON** (15 vs 14). Next: dogbones, fixed GND fallbacks that pass monotonic on filled zones, `aon_pad20`/`pad46`, `DEC_A_EN_N`, `ROW_A3`.

### Panels

Both `mono_panel_*` remain **0/0/0**; generator still restores panel PCBs from git at end of `generate_mono_split_boards.py`.
