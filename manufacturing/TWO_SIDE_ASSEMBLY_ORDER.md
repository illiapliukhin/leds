# Two-sided assembly and moisture-control baseline

Status: supplier review input. The contract manufacturer must return a written
process and profile before EVT purchase.

## Proposed sequence

1. Bake or dry-pack LEDs according to the manufacturer moisture sensitivity
   requirement and record lot/date exposure.
2. Print and place the back side first: MCU, power, drivers, sensors,
   connectors, passives, and test components.
3. Reflow the back side with the lowest qualified peak and time-above-liquidus
   compatible with all parts.
4. Inspect hidden/thermal-pad joints by the supplier's qualified method.
5. Support the populated back side in a fixture that does not load the battery
   connector, microphone, USB shell, inductor, or exposed packages.
6. Print and place the LED front side.
7. Reflow the LED side. This is the second and final permitted LED reflow.
8. Perform AOI, polarity inspection, opens/shorts test, depanelization, cleaning
   assessment, and controlled repackaging.

## Supplier must confirm

- Actual solder paste alloy, stencil thickness, aperture reductions, peak
  temperature, time above liquidus, ramp rates, and cooling rate.
- Maximum temperature seen by first-side components during second reflow.
- How heavy/tall first-side parts are retained during second reflow.
- LED MSL, floor life, dry storage, bake temperature/time, and lot traceability.
- Exposed-pad paste design and voiding criteria for RHL0024A, charger, and
  DC/DC packages.
- Edge-LED protection during printing, placement, handling, and depanelization.
- Panel support, routed rails, fiducials on both sides, and tab locations.
- AOI access and acceptance criteria for 1.0 mm RGB LED polarity/alignment.

## Prohibited assumptions

- Do not use JLCPCB Economic PCBA; the assembly is two-sided.
- Do not permit a third LED reflow or unrecorded rework heating.
- Do not place mouse bites beside edge LEDs.
- Do not approve the process from generic capability tables alone.
- Do not populate batteries during PCB reflow.
