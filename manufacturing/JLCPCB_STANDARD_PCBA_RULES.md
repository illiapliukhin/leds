# JLCPCB Standard PCBA production rules

Status: project rules for EVT quoting and DFM. Recheck JLCPCB capabilities immediately before every order.

## Assembly service decision

JLCPCB Economic PCBA is not compatible with this product:

- Economic PCBA supports single-sided placement only.
- The product requires LEDs on the front and all other components on the back.
- The requested 1.0 mm, black solder mask, ENIG combination is not available through the Economic flow.

Use JLCPCB Standard PCBA for EVT and MVP quotations. Keep PCBWay as the comparison supplier.

Primary sources:

- https://jlcpcb.com/capabilities/pcb-assembly-capabilities
- https://jlcpcb.com/capabilities/pcb-capabilities
- https://jlcpcb.com/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order
- https://jlcpcb.com/help/article/jlcpcb-surface-finish

## Project fabrication rules

| Feature | JLCPCB hard capability | Project rule |
|---|---:|---:|
| Outer-layer trace/space | 0.09/0.09 mm for applicable 4-layer service | 0.10/0.10 mm only inside matrix escape; 0.127/0.127 mm elsewhere |
| Standard signal via | 0.15 mm drill / 0.25 mm pad minimum | 0.20 mm finished drill / 0.45 mm pad |
| Local matrix RGB via | 0.15 mm drill / 0.25 mm pad minimum | 0.20 mm finished drill / 0.40 mm pad |
| Power via | Depends on drill class | 0.30 mm finished drill / 0.60 mm pad |
| Hole to unrelated copper | Depends on feature class | 0.20 mm |
| Copper to routed edge | 0.20 mm | 0.30 mm; target 0.50 mm near tabs or stressed edges |
| Copper to V-cut | 0.40 mm | V-cut prohibited near edge LEDs |
| Black solder-mask web | 0.13 mm threshold | 0.15 mm minimum |
| Silkscreen stroke | 0.15 mm | 0.15 mm minimum; 0.18 mm preferred |
| Silkscreen text height | 1.0 mm | 1.0 mm minimum; 1.2 mm preferred |
| Silkscreen to pad | 0.15 mm | 0.20 mm preferred |
| Nominal board thickness | 1.0 mm | 1.0 mm, expect approximately ±10% |
| Surface finish | ENIG available in Standard flow | ENIG, confirm selected gold-thickness option |

All matrix vias should be tented unless assembly review requires otherwise. No via-in-pad, blind via, buried via, or microvia is allowed without an explicit cost/yield review.

## Matrix-specific rules

- `MHPA1010RGBDT` pad gap is 0.34 mm.
- Use 1:1 solder-mask openings initially. Any expansion must preserve at least 0.15 mm black-mask web.
- Local matrix escape may use 0.10 mm tracks with 0.10 mm clearance.
- Use 0.45/0.20 mm anode vias and 1.20 mm inner-layer row buses where geometry permits.
- The 2.20 mm matrix may use 0.40/0.20 mm RGB transition vias only inside the repeated, DRC-verified escape cell. Do not use them as the general signal-via default.
- L2 remains a continuous ground plane except for through-via antipads.
- Outer rows and columns require a dedicated edge escape. Do not apply the interior-cell routing pattern beyond the outline.
- Edge LEDs violate the generic 2.5 mm body-to-finished-edge assembly recommendation. Obtain written JLCPCB engineering acceptance and use routed panel rails to protect components during depanelization.

## Standard PCBA panel

- Minimum finished panel: 70 × 70 mm.
- Add at least 5 mm breakaway rails.
- Use three or four global fiducials on both assembly sides.
- Fiducial copper: 1.0 mm diameter.
- Fiducial solder-mask opening: 2.0 mm diameter.
- Keep each fiducial and its keepout at least 3.35 mm from the panel edge.
- Use 2.0 mm tooling holes when controlling the panel internally; otherwise allow JLCPCB to panelize and add tooling.
- Do not place edge LEDs next to mouse-bite remnants. Use routed tabs positioned between optical cells or supplier-controlled rails.

## Silkscreen and identification

- Physical non-matrix component references must remain readable after assembly.
- Dense LED references belong on `F.Fab` and assembly drawings.
- Physical matrix identification should use row/column markers rather than sub-minimum text.
- Preserve `PCB CREATED BY ILLIA PLIUKHIN` and the star on `B.SilkS`.
- Reserve the complete branding group from backside placement and test pads.

## Required order gates

1. ERC and routed-board DRC pass with no unexplained exclusions.
2. Solder-mask web and paste apertures reviewed at 1:1 scale.
3. Gerber and drill files visually inspected.
4. JLCPCB DFM result reviewed, including edge-LED acceptance.
5. Two-sided reflow order and LED moisture/bake requirements documented.
6. Panel rails, fiducials, tooling, tab positions, and depanelization method approved.
7. BOM stock and alternates refreshed.
8. Assembly drawing, centroid file, polarity drawing, and factory-test procedure released together.
