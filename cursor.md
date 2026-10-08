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
- Centerline-non-crossing fan-in is not pad clearance. Direct diagonals into a 0.50 mm FFC pad row clip the long axis of neighboring pads; stop the fan above the connector courtyard and drop vertically on each pad centerline.
- A 32-net U-turn on two layers needs three non-overlapping X bands: connector courtyard, 0.55 mm via row, and 0.28 mm front channels. 32 mm of margin is not enough; prove the packed width before freezing the panel outline.
- Matching L-routes on the via layer and nested L-routes on the source layer impose opposite X assignments. Do not mix them on the same via row.
- `pcbnew` `Flip` after a 180° orientation can report 0°; dump pad coordinates instead of trusting the rotation used at placement time.
- 1.0 mm silk cannot label a transistor plus two 0402s in one 7–10 mm cell. Keep the transistor reference on silk and put the dense farm passives on Fab.
- USB-C stacked A/B pads DRC-short unless they share a net. Assign GND/VBUS to the coincident pairs before treating the receptacle as placement-clean.
- A mono pixel is one row net crossed with one column net. Do not tie those nets together. Leave a corridor for BMI270 `IMU_SDA`, `IMU_SCL`, and `IMU_INT1` plus `LED_OE_N`, so motion can blank or rewrite every LED.

