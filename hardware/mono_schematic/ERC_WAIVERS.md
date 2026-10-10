# ERC waivers (mono_electronics schematic)

As of PCB v11 (PR #4, after v10b): **whole-hierarchy ERC = 0 violations** (errors and warnings, `--severity-all`), no waivers needed.

Notes:
- Single-pad nets (unused FFC pins COL_SPARE_33..40, ROW_SPARE_33..40) are drawn with a no-connect flag; the PCB keeps their net names.
- v11b: all references now end in a digit (93 renamed, e.g. `J_ROW` → `J_ROW1`, see `hardware/mono_electronics/REF_RENAME_v11b.json`), so the netlist export no longer reports annotation errors.
