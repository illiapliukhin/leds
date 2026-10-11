# wire_grid_32x32: 32×32 LEDs on wires (no PCB)

A cube-layer-style grid: 1024 × NCD0603W1 (0603 white) soldered between 0.50 mm enamelled row wires (anodes) and 0.25 mm enamelled column wires (cathodes), 10 mm pitch.
The wiring follows [LED_INTERFACE_STANDARD](../common/LED_INTERFACE_STANDARD.md). The grid connects through `garland_breakout` (option A) or through the WG_TAG tag board to v15 `J_RH1`/`J_CH1` (option B).
The build guide is in Russian: [BUILD.md](BUILD.md). All parameters are in `params.py`; run `./gen_all.sh` to regenerate.

Worst-case row drop at 0.32 A: **A 133 mV, B 81 mV** (limit 350 mV). Estimated cost **≈ $47 (A, without breakout) / ≈ $69 (B)**. EEPROM preset: `mkpanelid.py --preset wire32`.

![overview](renders/grid_overview.png)
![node](renders/node_closeup_iso.png)
