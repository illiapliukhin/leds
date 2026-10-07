# Matrix routing feasibility

Status: top-left, bottom-right, and normal-to-180-degree orientation-transition routing probes pass KiCad 10 DRC for both matrix pitches. This proves both terminal-row directions and the orientation transition locally, not the completed board.

## Verified artifacts

- `wearable_20x20_edge_routing_probe.kicad_pcb`
- `wearable_20x20_edge_routing_probe_drc.rpt`
- `wearable_28x28_edge_routing_probe.kicad_pcb`
- `wearable_28x28_edge_routing_probe_drc.rpt`
- `wearable_20x20_bottom_right_routing_probe.kicad_pcb`
- `wearable_20x20_bottom_right_routing_probe_drc.rpt`
- `wearable_28x28_bottom_right_routing_probe.kicad_pcb`
- `wearable_28x28_bottom_right_routing_probe_drc.rpt`
- `wearable_20x20_orientation_transition_routing_probe.kicad_pcb`
- `wearable_20x20_orientation_transition_routing_probe_drc.rpt`
- `wearable_28x28_orientation_transition_routing_probe.kicad_pcb`
- `wearable_28x28_orientation_transition_routing_probe_drc.rpt`
- Generator: `hardware/tools/generate_edge_routing_probe.py`

All six DRC reports contain zero geometric violations. They still report 499 unconnected groups because only four LEDs are routed in each probe and no driver electronics exist.

## DRC-proven local pattern

- L1 carries only short LED-pad escape segments.
- Every RGB cathode transitions to L4 with a 0.40/0.20 mm through via.
- L4 carries three 0.10 mm vertical RGB trunks per column.
- Each trunk is offset 0.375 mm from the optical center or runs through the center.
- Every common anode transitions to L3 with a 0.45/0.20 mm through via.
- Interior L3 row buses are 1.20 mm wide.
- The top edge row bus is 0.40 mm wide and centered 0.525 mm from the routed edge.
- Local copper clearance is 0.10 mm.
- Hole-to-copper clearance is 0.20 mm.
- Copper-to-edge clearance is at least 0.30 mm.

The same top-left topology passes at 2.50 mm and 2.20 mm pitch without microvias, blind/buried vias, or via-in-pad.

The bottom-right probe rotates the final two LED rows by 180 degrees and mirrors the escape inward:

- RGB transition vias are above each rotated LED;
- the bottom L3 row bus is 0.40 mm wide and centered 0.525 mm from the edge;
- anode vias escape to the left, including at the rightmost column;
- the same 0.40/0.20 mm RGB and 0.45/0.20 mm anode vias are retained.

The orientation-transition probe uses a normal upper row and a 180-degree lower row. Rotating the footprint reverses the lateral G/R pad order, so three shared RGB vias cannot connect both rows on one copper layer without a crossover. The DRC-proven transition uses:

- one shared blue via per column;
- separate upper and lower G/R vias, for five RGB vias per transition column;
- a local G crossover on L3 and an R crossover on L4;
- a 0.40 mm local neck in each L3 row bus through the transition cell.

The normal 1.20 mm interior row-bus width resumes outside the transition cell. All row buses now use KiCad `In2.Cu`, the physical L3 layer; `In1.Cu` remains reserved for the L2 ground plane.

## Preliminary electrical estimate

Assumptions:

- copper resistivity: 1.724 × 10⁻⁸ Ω·m;
- L3 inner copper: conservative 17.5 µm;
- L4 outer copper: 35 µm;
- row current: 0.60 A for 20×20 and 0.84 A for 28×28;
- current is distributed uniformly along a row and fed from one end;
- one active LED color channel carries 10 mA.

| Case | Approximate conductor resistance | Distributed-load far-end drop |
|---|---:|---:|
| 20×20, 0.40 mm outer row | 0.117 Ω | 35 mV |
| 20×20, 1.20 mm interior row | 0.039 Ω | 12 mV |
| 28×28, 0.40 mm outer row | 0.146 Ω | 61 mV |
| 28×28, 1.20 mm interior row | 0.049 Ω | 21 mV |
| 28×28, 0.10 mm RGB trunk | 0.293 Ω | 2.9 mV at 10 mA |

These are first-order copper-only estimates. PMOS, connector, via, plane-spreading, converter ripple, copper-thickness tolerance, and temperature are excluded. Feed rows from both ends if backside placement permits; otherwise confirm the farthest blue pixel at maximum row current during EVT.

## Density and production impact

The simple repeated topology uses four matrix vias per LED:

- 20×20: 1,600 matrix vias;
- 28×28: 3,136 matrix vias.

This is a conventional through-via process but creates substantial L2 ground-plane perforation and drill count. Before expansion:

1. confirm JLCPCB accepts the repeated 0.40/0.20 mm vias at quoted yield;
2. inspect L2 neck widths and return-current continuity after antipads;
3. reserve L4 vertical channels from backside component pads;
4. test the bottom-left and top-right corners;
5. compare against a lower-via interior pattern only if it remains simpler and DRC-clean.

## Release gate

Do not copy the probe directly into production output until:

- all four corners pass DRC; the orientation transition is already proven locally;
- a complete repeated matrix has zero geometric DRC violations;
- row feeds, driver exits, and backside placement are included;
- L2 plane continuity is reviewed visually and by field-current inspection;
- voltage-drop assumptions are checked against the selected supplier stackup.
