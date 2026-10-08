# EVT bring-up and characterization procedure

Run the complete procedure on 20×20 first. Transfer approved corrections to
28×28, recalculate variant limits, and repeat the same procedure.

## Required equipment

- Current-limited programmable supply and protected production-intent battery.
- USB power meter or analyzer with controllable host connection.
- Four-channel oscilloscope, differential probe, current probe or shunt, and
  low-capacitance probes.
- DMM, thermal camera plus contact thermocouples, lux/color meter if available.
- SWD/UART/USB programming fixture and released bring-up firmware.
- Dark box, diffuser/grid samples, acoustic source, and reference microphone.

Record instrument model, asset/calibration ID, firmware version, board serial,
hardware revision, ambient temperature, battery lot, and operator.

## 1. Unpowered inspection

1. Inspect polarity, orientation, solder bridges, tombstones, exposed pads,
   edge damage, USB shell, and matrix alignment at magnification.
2. Measure resistance from every rail to GND and compare all assembled units.
3. Check BAT polarity, NTC identity, USB CC resistors, CHIP_PU, GPIO0, and
   hardware default pulls.
4. Stop on a short, reversed part, damaged cell, or unexplained outlier.

## 2. Current-limited first power

1. Leave the battery disconnected. Apply the minimum qualified SYS/BAT input
   from a current-limited supply with LED and audio domains disabled.
2. Confirm AON_3V3, CHIP_PU, reset behavior, MCU boot, service UART, I²C device
   identities, and quiescent current.
3. Sweep input slowly through the battery range and cycle it abruptly. Confirm
   no switched-domain back-power, chatter, unsafe GPIO, or unintended LED.
4. Repeat from USB with the 100 mA hardware input limit.

## 3. Switched rails and configuration

1. Execute the documented LED start sequence while probing AON_3V3,
   LED_LOGIC_3V3, LED_4V1, `LED_OE_N`, and one row gate.
2. Verify configuration readback for all six MBI5124 devices. A failed readback
   must leave OE high, both decoder banks disabled, translator disabled, and
   LED power off.
3. Measure rail rise/fall, reverse leakage, QOD behavior, overshoot, ripple,
   and inrush at minimum, nominal, and maximum battery voltage.
4. Repeat at cold/room/hot component conditions available in EVT.

## 4. Matrix electrical test

1. Display single red, green, and blue pixels at every matrix position.
2. Run walking columns, walking rows, checkerboards, all-black, primary colors,
   and capped full white.
3. Log opens, shorts, swapped colors, stuck channels, uneven rows, and
   intermittent faults by coordinate.
4. Measure Rext current on every driver and representative first/middle/last
   columns. No channel may exceed the approved 10 mA bound.
5. Measure LED_4V1 at converter, row source, row drain, and farthest pixel.

## 5. Row transition and signal integrity

1. Probe outgoing/incoming PMOS gates, row anodes, `LED_OE_N`, decoder enable,
   latch, and clock using repeated worst-case patterns.
2. Verify outgoing row current reaches the approved off threshold before the
   incoming row conducts.
3. Characterize minimum robust dead time; retain margin over temperature,
   voltage, process spread, and probe uncertainty.
4. Check 20 MHz clock/data/latch setup, hold, overshoot, ringing, and monotonic
   threshold crossings at the first and last driver.
5. Keep 24 MHz disabled unless a separate signed SI/timing report passes.

## 6. USB, charging, and battery

1. Test attach, detach, repeated enumeration, WebUSB transfer, recovery, and
   malformed/interrupted resource transfers.
2. Confirm 100 mA before configuration and no more than 500 mA afterward.
3. Measure charge current, power-path sharing, CE resampling, TS window, NTC
   faults, thermal throttling, termination, recharge, and ship mode.
4. Exercise simultaneous LED load and charging. Firmware must reduce or stop
   charge/brightness before thermal or input limits are exceeded.
5. Compare fuel-gauge SOC with coulomb/runtime observations.

## 7. IMU, audio, sleep, and recovery

1. Validate IMU axes, range, sample rates, motion wake, repeated sleep cycles,
   and false wakes.
2. Sweep the microphone path from 60 Hz to 7 kHz and record gain, clipping,
   noise floor, startup settling, and LED/DC-DC switching spurs.
3. Measure complete-device deep-sleep current after all interfaces settle.
4. Test button wake, USB wake/recovery, watchdog, brownout, and corrupted
   resource fallback.

## 8. Thermal, optical, and endurance

1. Evaluate the nine front-panel transmission/spacing combinations defined in
   `mechanical/MECHANICAL_INPUTS.md`.
2. Run representative and worst approved content at minimum/nominal/maximum
   battery conditions. Log converter, driver, PMOS, charger, battery, PCB, and
   enclosure temperatures.
3. Verify derating and shutdown thresholds without oscillation.
4. Run 24 hours with repeated active, charging, sleep, wake, USB, and animation
   cycles. Capture resets and faults automatically.

## Exit criteria

- Every item in `test/ACCEPTANCE_CRITERIA.md` passes or has an approved,
  non-safety EVT deviation.
- Defects have root causes and regression tests; safety, thermal, USB,
  charging, scan, and assembly blockers require a corrected spin.
- Raw logs, scope captures, thermal images, photos, firmware build ID, and
  signed summary are stored under the unit/revision release record.
