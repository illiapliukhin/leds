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
- Derive the edge-orientation map from physical pad and outline constraints before routing its boundaries. A nominally symmetric orientation pair can place the anode escape outside the board; the proven edge row pairs are 90°→180° on the right and 0°→270° on the left.
- Do not route dense transition fan-out or crossovers as unchecked direct diagonals. Use explicit orthogonal corridors and run DRC at the tightest production pitch; tracks can clear their endpoint pads while still crossing an intermediate pad or through via.
- Normalize KiCad orientation values modulo 360 in semantic checks. `pcbnew` may report a 270-degree footprint as -90 degrees even though the saved orientation is correct.
- Do not move long transition-to-trunk continuations onto `F.Cu` as a layer-only fix. On the complete matrix they can cross LED fan-out and anode escapes even when the isolated transition is clean; redesign the transition and its neighboring corridors together.
- A full-matrix edge transition needs separate lower L4 corridors for the outer dogleg and the inner color trunk. Route the outer path orthogonally at the transition boundary and move the inner trunk to its regular X coordinate before they converge.
- In KiCad 10 Python checks, call `PCB_VIA.GetWidth(layer)` with an explicit copper layer. Calling `GetWidth()` without a layer emits one assertion per via and obscures otherwise valid semantic-test output.
- Do not infer that an LED-driver configuration register is per-channel from a color table. The MBI5124 has one 16-bit pre-charge configuration per IC, so color-specific settings require color-homogeneous driver assignments unless Macroblock documents a mixed-color mode.
- Do not select a nominal current at or above a datasheet operating-range boundary. Combine resistor tolerance with both IC-to-IC and channel-to-channel maximum errors; omitting the MBI5124 ±2.5% channel error made 1.91 kΩ appear safe when its combined worst case exceeded 10 mA.
- Do not specify mandatory configuration readback without reserving the complete physical return path. Include an MCU input, switched-domain isolation with specified `Ioff`, a deterministic MCU-side default level, decoupling, and the connection from the final device in the serial chain.
- When deriving a generated symbol with ordered text substitutions, replace specific metadata strings before broad part-name substitutions. A broad `MBI5252GP` replacement changed the source datasheet URL and made the later exact URL replacement fail.
- Use fail-fast shell execution for multi-stage verification commands. Without `set -e`, a failed Python assertion was masked by later successful commands and the shell returned exit code zero.
- Run all KiCad CLI schematic commands sequentially, including ERC and exports. Parallel `kicad-cli` processes share an instance lock directory and emit invalid-lock warnings; this mistake recurred when row-selector ERC was parallelized after the narrower export-only rule had already been recorded.
- Verify generated connectivity through the exported XML netlist when symbols are rotated. `kicad-sch-api` pin-based label placement on a 90-degree two-pin resistor connects labels to the opposite serialized pin numbers, so compensate the requested endpoints explicitly. Simply removing rotation caused vertically stacked resistor endpoints to overlap and merge unrelated labels.
- This environment does not provide a `python` alias. Invoke repository
  generators with `python3` after checking the setup status.
- In KiCad 10 Python checks, `CONNECTIVITY_DATA.GetUnconnectedCount` requires
  the `visibleOnly` boolean argument; pass `False` for a complete board check.
- Model multifunction strap pins by their use in the selected interface.
  BMI270 `SDO` is an SPI output but an I²C address strap in this design; marking
  it output caused a false output-to-power-output ERC error when tied to GND.
- Do not assign a multi-pad crystal footprint to a generic two-pin symbol.
  Verify the manufacturer terminal table and model signal pins plus grounded
  case pads explicitly; `L327S400H11L` requires signals on pins 1/3 and GND on
  pins 2/4.
- When counting KiCad DRC categories in a text report, match category headers
  at the start of a line. Counting `[` characters also counts bracketed net
  names such as `[GND]` in violation details and produces false failures.
- Do not derive a footprint from search-result synthesis or extracted dimension
  tables alone; packaging dimensions can be mistaken for land-pattern
  dimensions. Inspect the primary drawing and its graphical dimension arrows
  before encoding pad geometry.
- Do not let an analysis generator use the mutable production PCB as its input.
  Build probes and repeated routing from a clean skeleton so reruns cannot
  duplicate copper or erase later backside placement. This applies to every
  probe generator, not only the full-matrix generator; the legacy edge probe
  path duplicated vias after production promotion until it was converted too.
- KiCad assigns fresh internal UUIDs to newly created board items unless the
  generator sets them explicitly. Do not use whole-file hashes as a
  reproducibility gate until board, footprint, pad, graphic, track, via, and
  zone UUIDs are deterministic.
- `pcbnew.SaveBoard` can create or rewrite a sibling `.kicad_pro`. Generated
  analysis boards must be saved in a temporary directory and copied back as
  `.kicad_pcb` only, so verification cannot mutate project metadata.
- Do not begin dense backside placement from a nominal battery rectangle
  without an area-feasibility check. Sum the actual non-text footprint
  envelopes from the root netlist and compare them with the available board
  area; the 20×20 design has approximately 1673 mm² of non-LED envelopes but
  only approximately 1150 mm² outside its provisional 32×40 mm battery
  projection, so a component-free projection cannot be claimed.
- Do not replace measured footprint-envelope area with a guessed average area
  per component. The resulting side-rail zoning understated 20×20 placement
  demand by more than 2×. Also do not treat all area outside the battery
  rectangle as placeable: the through-via LED field leaves only a border, and
  the measured via-to-via gap is 0.10 mm. Blind vias can turn the matrix back
  side into placement area; a larger outline is the through-via alternative.
- `FOOTPRINT.Flip` segfaults before `board.Add`. Align placement to
  `GetBoundingBox(False, False)`, because the footprint anchor is not the
  courtyard center. Force reference text angle to 0 after rotation, and keep
  footprint envelopes at least 0.30 mm apart so 0.15 mm silk clearance holds.
  Do not batch-remove footprints from one materialized footprint list; the
  proxies dangle. Regenerate backside placement from the matrix artifact.
- Do not change a generated board outline while routing generators still use
  hard-coded LED margins or edge-bus coordinates. Derive LED centers and outer
  row buses from board size, matrix size, and pitch, then rerun every topology
  and DRC gate before promoting the resized board.
- Do not route the border across `F.Cu`. LED pads and solder-mask webs sit
  there; keep escapes on `B.Cu` and `In2.Cu`, and keep `In1.Cu` free for the
  ground plane. Commit orthogonal runs, not one segment per grid step and not
  a single diagonal between Manhattan endpoints.
- Choose a pad escape toward the nearest courtyard edge. The larger offset
  from the footprint center sends a top-row end pin sideways through the
  neighboring pins. Block every other courtyard on `B.Cu` so one escape cannot
  seal the rest of the package.
- Do not treat a pad bounding box as copper. KiCad 10 roundrect pads leave the
  box corner empty, so a track that stops there dangles and does not reduce
  the ratsnest. Start and stop on an inset of the pad, then extend to the
  pad center.
- Keep new via centers at least one via diameter plus 0.10 mm apart, with an
  extra half grid step. Stamping only the via diameter lets neighboring vias
  land 0.05 mm inside the clearance rule.
- Do not move all six MBI5124 packages into the low-Y border to create escape
  channels. That strip already holds about 474 mm² of other envelopes, and the
  side columns freed by the move are narrower than the displaced parts. The
  90° drivers still have eight outputs on a short edge whose neighbor gap
  fits one track.

