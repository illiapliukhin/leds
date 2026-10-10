# ERC waivers (mono_electronics schematic)

As of PCB v11 (PR #4, after v10b): **whole-hierarchy ERC = 0 violations** (errors and warnings, `--severity-all`), no waivers needed.

Notes:
- Single-pad nets (unused FFC pins COL_SPARE_33..40, ROW_SPARE_33..40) are drawn with a no-connect flag; the PCB keeps their net names.
- `kicad-cli sch export netlist` prints "schematic has annotation errors": PCB references such as `J_ROW`, `U_LED_BUF`, `H1` are kept verbatim (no numeric suffix on some), which KiCad's annotator flags. Netlist content is complete.
