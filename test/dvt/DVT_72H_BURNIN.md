# DVT 72-hour burn-in

Run only after EVT exit criteria and corrective-spin regressions pass.

## Population

- Test 10–20 production-intent units across PCB, assembly, LED, battery, and
  enclosure lots where available.
- Assign immutable serial numbers and record all hardware, firmware, BOM,
  fixture, and supplier lot revisions.
- Keep at least one approved golden unit outside burn-in for fixture checks.

## Automated cycle

Repeat the following profile for 72 hours:

1. 20 minutes representative animations under the continuous power limiter.
2. 5 minutes capped worst-case RGB patterns with thermal derating active.
3. 10 minutes audio-reactive mode with a controlled acoustic stimulus.
4. 10 minutes IMU interaction and wake/sleep cycles.
5. USB attach, enumeration, resource CRC transfer, detach, and recovery check.
6. Charge/load sharing interval followed by battery-only operation.
7. Deep sleep interval with current sampling and button/IMU wake.

Log rail voltage, input/battery current, SOC, all temperatures, reset reason,
USB result, scan/configuration faults, pixel self-test result, and firmware
health counters at least once per minute and at every state transition.

## Inspections

- At 0, 24, 48, and 72 hours run the complete pixel/color, USB, charging,
  sleep-current, IMU, microphone, button, and visual inspection suite.
- Compare luminance/color and current against pre-burn-in measurements.
- Inspect enclosure distortion, diffuser/grid movement, connector retention,
  battery swelling, solder cracking, contamination, and edge-LED damage.

## Pass criteria

- No unsafe temperature, battery anomaly, uncontrolled charge, two-row
  overlap, repeated reset, persistent communication error, or latent short.
- No permanent failed/stuck pixel and no significant unapproved
  luminance/current drift.
- Every transient failure is automatically captured and reproducible or
  explained.
- Factory programming and test produce the same verdict before and after
  burn-in.

Any safety-critical failure rejects the revision until root cause, corrective
action, and full regression are complete. Do not average failures away as a
yield percentage.
