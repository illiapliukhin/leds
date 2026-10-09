# Latest changes

## Mono split boards (PR #4)

- **MCU grid:** default **greedy** sequential router (`mcu_grid_compute.py`, 8 passes). Optional **PathFinder-style** negotiation: `MONO_PATHFINDER=1` → `pathfinder.py` (history cost, rip-up victims, finish pass). **`libastar.so`** pinned from analysis bundle (KiCad 10 headless).
- **Apply policy:** only **`complete_nets`** (`joins_fail==0`) are written to `mono_electronics.kicad_pcb`. **`add_gnd_mesh`** in routes JSON defaults **false** (B.Cu mesh + stitch vias caused copper shorts in DRC).
- **DRC (2026-10-09):** after greedy grid apply — **0 shorts / 0 crossings / 45 unconnected** (matrix baseline without grid: **0/0/71**). PathFinder trial on same geometry closed **19/26** signal nets but same **7** nets remain open (`AON_3V3`, `DEC_*`, `LED_*`, `AUDIO_EN`, `GPIO0_BOOT`, `USB_D_N_MCU`).
- **Still open:** close remaining MCU nets without breaking **0 shorts**; enable GND mesh only after pour/fill is DRC-safe; courtyard/clearance/silk; full **`verify_mono_split_boards.py`**.
- **Post-grid cleanup (2026-10-09):** only **short F.Cu stubs** (≤0.9 mm) with a truly floating endpoint are removed — no coordinate kill-list (fixes **ROW_A3** regression).
- **GND stitch:** **dogbone** only (stub to via off 0402/0603 pad); **no via-in-pad** on passives/ESD/SW1/IMU. VIPPO not required at JLC when dogbone passes DRC gate.
- **Pre-grid fanout:** `mono_split_pre_grid_fanout.py` — opt-in `MONO_PRE_GRID_FANOUT=1` (default **off** until fanout + grid DRC gate is 0/0). Sub-flags: `MONO_FANOUT_U1_AON`, `MONO_FANOUT_U1_GND`, `MONO_FANOUT_PERIPHERY_GND`.
- **PathFinder:** `GND` / `AON_3V3` stay in `GRID_SKIP_NETS` for grid apply (power via fanout + gated post-grid); **ROW_*** nets in `RIP_PROTECT`.
- **DRC snapshot:** copper gate **0/0**; **24** unconnected groups (was 31): `AON_3V3` 14, `DEC_A_EN_N` 2, `GND` 2, IMU×3, `LED_CLK` 1, `ROW_A3` 1, `USB_D_N_MCU` 1.
