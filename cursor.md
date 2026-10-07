# Agent Notes

## Repository status

- Initialized as the working repository for the LEDS project.
- The repository currently contains planning, handoff, preliminary BOM, and partial datasheet-freeze documents.
- KiCad 10 boards with 400/784 verified LED footprints and matrix nets, common PCB architecture, generation tools, and engineering-model outputs now exist under `hardware`.
- Schematics, non-LED footprints, driver placement/routing, firmware, mechanical, manufacturing, and test source trees are not complete.

## Verification

- Run the relevant build and test suite after every substantive change.
- Record newly discovered agent mistakes and their prevention rules in this file.
- Do not treat a value below an absolute datasheet maximum as a robust operating target; reserve timing, voltage, current, and thermal margin explicitly.
- Do not freeze a power component from a headline current rating alone; verify the datasheet's exact operating point, derating, passives, layout, and thermal limits.
- Keep confirmed datasheet facts separate from calculations, assumptions, and EVT-only validation items.
- Derive expected fixture and record counts from an explicit specification or stable identifiers; do not guess a row count in an ad-hoc verification script.
- On Windows, avoid locale-dependent non-ASCII literals in scripts piped through PowerShell; use UTF-8 script files, Unicode escapes, or ASCII-stable validation markers.
- Verify KiCad Python layer constants against the installed major version; KiCad 10 uses `Cmts_User`, not the guessed `User_Comments` name.
- A zero-violation DRC on an outline-only board proves file and geometry validity, not electrical correctness; rerun DRC after footprints, nets, zones, and routing are present and label the scope explicitly.
- Do not satisfy dense-board labeling requests with sub-fabrication-limit silkscreen. For JLCPCB use at least 1.0 mm text height, 0.15 mm stroke, and 0.15 mm pad clearance; keep dense matrix references on Fab/assembly layers and physical references for normally spaced components.
- Do not place decorative silkscreen graphics by visual estimate alone; run DRC for graphic-to-text and graphic-to-pad overlap, then reserve the validated branding area from later placement.
- Validate KiCad semantics through `pcbnew` objects where possible; serialized files use native tokens such as `B.SilkS` while the API reports display names such as `B.Silkscreen`, so hard-coded display-name searches are brittle.
- Do not select a PCBA service from PCB fabrication capabilities alone. JLCPCB Economic PCBA is single-sided and does not satisfy this project's two-sided 1.0 mm black-mask ENIG build; use Standard PCBA and verify panel, finish, and assembly constraints together.
- Do not claim a PCB outline is frozen after checking only pad-to-edge clearance. Prove outer-row and outer-column escape routing, including bus width, via geometry, and edge clearance, before freezing the mechanical envelope.
- In KiCad, `m_MinClearance` is only the absolute board minimum; the default netclass can still enforce a larger clearance. Set and validate both, plus hole-to-copper clearance, before interpreting routing-probe DRC results.
- Do not interpret a nonzero `kicad-cli pcb drc --exit-code-violations` result as a geometry failure without reading the report. A partial routing probe can have zero DRC violations while intentionally retaining unrouted groups.
- Do not assume a repeated LED escape that works at the top edge automatically closes at the bottom edge. Prove terminal rows and orientation transitions separately before expanding the complete matrix.
- Map logical stackup names to KiCad layer constants before generating copper. On a four-layer board, `In1.Cu` is physical L2 and `In2.Cu` is physical L3; reserve `In1.Cu` for the ground plane and place row buses on `In2.Cu`.
- Do not assume a 180-degree LED orientation transition can reuse one three-via RGB set. Rotation reverses the lateral G/R pad order, so prove the required crossover and local row-bus neck with DRC at every production pitch.
- Do not mirror a dense corner escape by changing only the anode-via direction. Verify the transformed pad map through `pcbnew`; the opposite corners require 90/270-degree footprints and a different central RGB escape.
- A DRC-clean corner-specific orientation does not prove that it tiles into the full matrix. Test each boundary between 0/90/180/270-degree regions before production expansion.

