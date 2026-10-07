# Wearable RGB mechanical input register

Status: EVT input baseline. Dimensions marked `PROVISIONAL` are not production
release dimensions and must not be converted into hard keepouts until the
listed evidence is received.

## Product envelopes

| Input | 20×20 | 28×28 | Status |
|---|---:|---:|---|
| PCB outline | 49.3 × 49.3 mm | 61.2 × 61.2 mm | ROUTING-PROVEN, NOT FROZEN |
| PCB thickness | 1.0 mm | 1.0 mm | EVT BASELINE |
| LED pitch | 2.50 mm | 2.20 mm | ROUTING-PROVEN |
| Battery plan envelope | 32 × 40 mm | 40 × 50 mm | PROVISIONAL |
| Battery thickness | 6 mm target | 6 mm target | PROVISIONAL |
| Product thickness | 10.5–12 mm target | 10.5–12 mm target | PROVISIONAL |

The current PCB outlines are proven for all four matrix edges. They are not
production-frozen because the connector, battery, enclosure, and panel tabs
have not been reconciled in one mechanical assembly.

## Stack budget

| Element | Baseline | Validation |
|---|---:|---|
| Smoked polycarbonate front | 0.6–0.8 mm | Optical EVT |
| LED-to-front spacing | 0.8 / 1.2 / 1.6 mm samples | Optical EVT |
| Black pixel grid | 1.0–1.5 mm | Optical EVT |
| LED package | 0.6 mm | Manufacturer drawing |
| PCB | 1.0 mm | Fabricator stackup |
| Battery | approximately 6 mm | Supplier drawing |
| Rear cover and attachment | 1.0–1.5 mm | Enclosure prototype |

## Connector baseline

`C52209107`, HH `16P TYPE-C (Y385)`, is the traceable EVT candidate:

- USB 2.0, 16 contacts, right-angle surface mount;
- 7.35 mm body length;
- 3 A power rating, 20 V rating;
- rated for 10,000 mating cycles;
- locating posts and a supplier datasheet are available.

Do not assign its footprint or freeze its edge position until the enclosure
cross-section confirms shell height, board-edge setback, insertion clearance,
and retention-tab access. `C52711232` remains unverified and is not an approved
alternate.

The battery interface remains a three-contact `BAT+ / NTC / GND` requirement.
The EVT connector candidate is the active Molex Pico-Lock 1.50 mm set:

- PCB header `504050-0391`, right-angle SMT, positive lock, 3 circuits,
  3.5 A/contact maximum;
- cable housing `504051-0301`;
- three crimp terminals `504052-0098`, 24–28 AWG, 3.0 A/contact maximum;
- 2.0 mm mated height, 30 mating cycles, and −40…+105 °C operating range.

This selection is conditional. Freeze the footprint and wire exit only after
the battery supplier confirms the mating harness, conductor gauge, pin order,
polarity, current derating, and cable bend envelope.

The rear-button EVT candidate is Panasonic `EVPBL2A1F000`: top-push SMD,
2.8 × 1.9 × 0.53 mm, 1.6 N force, 0.15 mm travel, and 300,000-cycle rated
life. Its component-level IP67 rating does not establish enclosure ingress
protection. Placement remains conditional on the rear-cover plunger tolerance
stack and allowable preload.

## Placement constraints

- All LEDs are on the front side; all other components and test pads are on
  the back.
- Keep the battery projection free of the DC/DC converter, LED drivers, hot
  charging components, and tall parts.
- Place USB-C at the center of a side only after its shell opening is defined.
- Keep the IMU in a rigid region away from the inductor, USB edge, button
  plunger, and flexible enclosure features.
- Give the top-port microphone a direct sealed acoustic channel and mesh.
- Preserve the back-silkscreen branding strip or relocate it as a complete
  group.
- Do not place routed tabs or mouse-bite remnants beside edge LEDs.

## Optical experiment

Build the nine combinations of 30%, 40%, and 50% front transmission with
0.8 mm, 1.2 mm, and 1.6 mm LED-to-diffuser spacing. Record:

- luminance and color balance;
- hotspot visibility and inter-pixel crosstalk;
- viewing-angle uniformity;
- surface temperature at the continuous power limit.

No optical stack is approved until this experiment is completed on an
assembled EVT matrix.

## Required evidence before production freeze

1. Battery manufacturer drawing, STEP, PCM/NTC specification, UN38.3 evidence,
   maximum pulse current, and mating connector.
2. USB-C supplier drawing and enclosure cross-section with insertion clearance.
3. `EVPBL2A1F000` drawing and rear-cover plunger tolerance stack.
4. PCB, enclosure, battery, grid, front panel, mesh, and fasteners in one STEP
   assembly with interference checks.
5. Supplier-approved panel rails, routed tabs, fiducials, and depanelization
   method.
6. Optical, acoustic, thermal, and fit-check results from physical EVT units.

## Source documents

- `WEARABLE_RGB_MVP_HANDOFF.md`
- `hardware/common/PCB_ARCHITECTURE.md`
- `hardware/analysis/MATRIX_ROUTING_FEASIBILITY.md`
- `manufacturing/JLCPCB_STANDARD_PCBA_RULES.md`
- HH `16P TYPE-C (Y385)` supplier listing and datasheet, LCSC `C52209107`
- Molex drawings for `504050-0391`, `504051-0301`, and `504052-0098`
- Panasonic `EVPBL2A1F000` product page and `EVPBL` series drawing
