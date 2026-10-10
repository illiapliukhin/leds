# mono_electronics schematic (generated)

Hierarchical KiCad 10 schematics for **`mono_electronics`**, generated from pad nets on `hardware/mono_electronics/mono_electronics.kicad_pcb` (same references and net names as the PCB).

## Layout

| Path | Purpose |
|---|---|
| `mono_electronics.kicad_pro` | Project (links schematic tree) |
| `mono_electronics.kicad_sch` | Root sheet (hierarchy index) |
| `sheets/*.kicad_sch` | Power, MCU, IMU, LED drive, row farm, reserves, audio |
| `mono_electronics_net_manifest.json` | Reference → pad → net (PCB source) |
| `tools/generate_mono_schematic.py` | Regenerate all `.kicad_sch` files |
| `tools/compare_sch_pcb_nets.py` | Fail if manifest ≠ PCB pad nets |
| `tools/run_erc.sh` | Run `kicad-cli sch erc` on all sheets |
| `ERC_WAIVERS.md` | Intentional ERC exceptions |
| `DESIGN_ISSUES.md` | Reported electrical gaps (PCB not edited here) |

## Commands

```bash
source hardware/tools/kicad10_env.sh
python3.11 hardware/mono_schematic/tools/generate_mono_schematic.py
python3.11 hardware/mono_schematic/tools/compare_sch_pcb_nets.py
hardware/mono_schematic/tools/run_erc.sh
```

Requires KiCad **10.0.x** (`kicad-cli`, `pcbnew` Python). On cloud agents, AppImage is installed under `/workspace/.kicad10/` when missing.
