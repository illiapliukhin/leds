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

## v11 sync (PR #4, PCB after v10b)

- Regenerated from the hand-routed PCB on the `cursor/esp32-gpio-route-mono-9adf` branch: 224 parts on 9 sheets (power, mcu, imu, led_drive, row_farm, audio, **stacking** — ports/RS-485/ESD/termination, **mechanical** — H1–H4; the reserves sheet is gone with the reserve pads).
- Generator fixes: pin anchors were mirrored in Y (only the first pin pair landed on a wire), labels were local (sheet-scoped) instead of global, 2-pad parts shared pin names from another net, per-sheet duplicate PWR_FLAGs, lib tables used `${KIPROJECT}` (now `${KIPRJMOD}`), and footprint links pointed nowhere (now `footprints/mono_electronics.pretty`, exported from the PCB).
- `tools/compare_sch_netlist.py`: real check — the netlist exported from the schematic by `kicad-cli` vs. PCB pad nets, compared as connectivity groups. Result: 224/224 refs, **0 pin differences**. ERC (whole hierarchy, all severities): **0**.
