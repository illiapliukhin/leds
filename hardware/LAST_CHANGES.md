# Latest changes

## Mono split boards (PR #4)

- **MCU grid:** default **greedy** sequential router (`mcu_grid_compute.py`, 8 passes). Optional **PathFinder-style** negotiation: `MONO_PATHFINDER=1` → `pathfinder.py` (history cost, rip-up victims, finish pass). **`libastar.so`** pinned from analysis bundle (KiCad 10 headless).
- **Apply policy:** only **`complete_nets`** (`joins_fail==0`) are written to `mono_electronics.kicad_pcb`. **`add_gnd_mesh`** in routes JSON defaults **false** (B.Cu mesh + stitch vias caused copper shorts in DRC).
- **DRC (2026-10-09):** after greedy grid apply — **0 shorts / 0 crossings / 45 unconnected** (matrix baseline without grid: **0/0/71**). PathFinder trial on same geometry closed **19/26** signal nets but same **7** nets remain open (`AON_3V3`, `DEC_*`, `LED_*`, `AUDIO_EN`, `GPIO0_BOOT`, `USB_D_N_MCU`).
- **Still open:** close remaining MCU nets without breaking **0 shorts**; enable GND mesh only after pour/fill is DRC-safe; courtyard/clearance/silk; full **`verify_mono_split_boards.py`**.
