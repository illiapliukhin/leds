# Manufacturing release checklist

No package may be labelled `EVT-ORDER-READY` or `PRODUCTION-RELEASED` unless
every item in the corresponding gate is checked and the evidence path is
recorded.

## Design identity

- [ ] Product variant and hardware revision are immutable.
- [ ] Git commit, schematic revision, PCB revision, BOM revision, CPL revision,
      firmware revision, and fixture revision are recorded in the release
      manifest.
- [ ] All `OPEN`, `BLOCKED_DESIGN`, and `BLOCKED_EXTERNAL` BOM entries are
      closed or covered by a signed EVT deviation.
- [ ] Approved alternates have explicit manufacturer part numbers and
      footprint/pin/function compatibility evidence.

## Electrical release

- [ ] Root hierarchical schematic exists and contains power, MCU/USB,
      IMU/gauge/input, audio, LED drivers, matrix, and row selection.
- [ ] Non-BOM ERC harnesses are absent from the root product netlist.
- [ ] Strict ERC reports zero errors and zero warnings.
- [ ] XML netlist semantic checks pass for rails, GPIO assignments, all rows,
      all RGB columns, driver chain, and configuration readback.
- [ ] Independent pin and footprint audit is signed for every critical IC.
- [ ] Power, current, voltage-drop, scan timing, thermal, and USB constraints
      are attached to the release.

## PCB release

- [ ] Backside placement includes every BOM item and readable reference.
- [ ] Matrix routing, row feeds, RGB exits, USB, crystal, power, I²C, audio,
      and test points are complete.
- [ ] L2 is a continuous GND plane with reviewed antipad necks and return paths.
- [ ] Final DRC reports zero violations and zero unconnected items without
      unexplained exclusions.
- [ ] Differential impedance uses the quoted production stackup.
- [ ] Paste, mask web, polarity, thermal pad, courtyard, and component-to-edge
      checks are complete at 1:1 scale.

## Mechanical and optical release

- [ ] Exact battery, battery connector, USB-C, button, NTC, mesh, front panel,
      and grid manufacturer parts are selected.
- [ ] One STEP assembly passes interference and tolerance checks.
- [ ] USB insertion, battery wire exit, button travel, microphone seal, and
      service access are validated.
- [ ] Optical sample selection is backed by EVT measurements.
- [ ] Enclosure surface temperature is within the approved user-contact limit.

## Fabrication and assembly

- [ ] Gerber, drill, IPC netlist, BOM, CPL, schematic PDF, assembly drawings,
      STEP, panel drawing, polarity drawing, and test instructions are present.
- [ ] Gerber and drill viewers were checked independently.
- [ ] JLCPCB Standard PCBA DFM has no unresolved findings.
- [ ] Written edge-LED and repeated 0.40/0.20 mm via acceptance is attached.
- [ ] Panel rails, fiducials, tooling holes, routed tabs, and depanelization are
      approved.
- [ ] Front/back reflow order, profile, LED moisture sensitivity, storage, and
      bake process are approved.
- [ ] BOM stock, lifecycle, MOQ, and alternates were refreshed immediately
      before order.

## EVT order gate

- [ ] All electrical, PCB, and fabrication items above are complete.
- [ ] Release package validation script passes.
- [ ] Bring-up firmware and current-limited power procedure are released.
- [ ] Fixture drawing and blank measurement logs are released.
- [ ] Five 20×20 PCBs and at least two assembled units are quoted.

## DVT/MVP release gate

- [ ] EVT defect log contains no open safety, thermal, USB, charging, scan, or
      assembly blocker.
- [ ] Corrective spin regression results are attached.
- [ ] 28×28 transfer EVT passes its variant-specific limits.
- [ ] Ten to twenty DVT units pass the 72-hour burn-in procedure.
- [ ] Factory programming/test limits, golden unit, calibration, traceability,
      and result retention are validated on production fixtures.
- [ ] Yield and rework data meet the release target.
- [ ] Final release is signed by electrical, mechanical, firmware, test, and
      manufacturing owners.

## Current project state

The current repository is not `EVT-ORDER-READY`. Matrix routing and the row
translator footprint are verified, but root schematics, backside
placement/routing, exact battery/mechanical selections, supplier DFM, firmware,
and physical EVT/DVT evidence remain release blockers.
