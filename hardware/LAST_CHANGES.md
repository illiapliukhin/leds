# Latest changes

## Mono split boards (PR #4) — stabilization pass

- **Committed baseline:** `mono_electronics.kicad_pcb` at **24 unconnected**, copper **0/0** (run #7 / `c57bed5a` geometry).
- **Default pipeline:** `MONO_POST_GRID_PHASES=cleanup,gnd,aon` (no `aon_zone` / `grid_one` / full-board rollback). Each post-grid phase commits only if **`monotonic_gate_allows`** (0/0 copper, unconnected and clearance must not increase vs phase start). Post-grid as a whole reverts if the aggregate step fails monotonic vs pre-post-grid snapshot.
- **Grid merge:** greedy supplements merged **one net at a time** (`merge_greedy_one_at_a_time`) so e.g. `LED_CLK` can land without failing the whole borrow set.
- **PathFinder `RIP_PROTECT`:** back to ROW + USB/IMU skip set (removed LED/GPIO extras that blocked rip-up and dropped PF completeness).
- **GND stitch:** per-via trial must reduce unconnected without raising clearance or copper violations (still tuning for **clearance=1** fresh boards; baseline board uses prior stitches).
- **PR hygiene:** `hardware/.gitignore` drops `drc*.json`, `*.ses`, nogrid trial boards, and regenerated `mcu_geom` / `mcu_routes*.json`.
- **Clean generate (current):** full `generate_mono_split_boards.py` with defaults reaches ~**37** unconnected (0/0, clearance **1**) after grid + gated post-grid; **24** from a single generate is blocked until GND/AON steps pass monotonic on that geometry (AON In1 zone remains opt-in).
