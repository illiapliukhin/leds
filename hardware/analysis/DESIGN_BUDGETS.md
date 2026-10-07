# Pre-layout electrical and thermal budgets

Status: analytical screening baseline. These budgets constrain layout and EVT;
they do not replace supplier models, oscilloscope data, or enclosure thermal
measurements.

## LED and scan

| Budget | 20×20 | 28×28 |
|---|---:|---:|
| Peak active-row current | 0.565 A | 0.791 A |
| Peak LED_4V1 power | 2.315 W | 3.241 W |
| Battery current at 3.15 V, 90% efficiency | 0.817 A | 1.143 A |
| TPS63802 loss at assumed 90% | 0.257 W | 0.360 W |
| Datasheet open-board junction rise screening | 20.8 °C | 29.2 °C |
| AO3403 drop at 200 mΩ bound | 113 mV | 158 mV |
| Calculated LSB hold at baseline timing | 3.94 µs | 4.33 µs |
| Global cap for 1 W LED rail | 43.2% | 30.9% |

The converter loss and temperature use a constant efficiency and data-sheet
`RθJA`; they are deliberately not enclosure predictions. The battery,
connector, power path, converter, planes, and decoupling must support the peak
load step even when average brightness is capped.

## Matrix copper

Using 17.5 µm inner copper, 35 µm outer copper, and a one-ended uniformly
distributed row load:

| Path | Estimated far-end drop |
|---|---:|
| 20×20, 0.40 mm outer row | 35 mV |
| 20×20, 1.20 mm interior row | 12 mV |
| 28×28, 0.40 mm outer row | 61 mV |
| 28×28, 1.20 mm interior row | 21 mV |
| 28×28, 0.10 mm RGB trunk at 10 mA | 2.9 mV |

These estimates exclude vias, PMOS, plane spreading, temperature, ripple, and
copper tolerance. Feed rows from both ends where backside placement permits.

## Charging and USB

- The hardware starts at the 100 mA USB input limit and may switch to 500 mA
  only after successful configuration and BQ25185 CE resampling.
- A 5 V / 500 mA host supplies at most 2.5 W before cable, charger, and
  regulator losses. Maximum LED load and full-rate charging cannot coexist.
- First-order linear-charger dissipation at a 3.15 V cell is approximately
  0.56 W at 300 mA and 0.74 W at 400 mA before system-load interactions.
  Therefore charge throttling based on charger/PCB/battery temperature is
  mandatory.
- The hardware TS window targets 0–60 °C. Firmware should allow charging only
  around 0–45 °C until physical correlation is complete.
- USB D−/D+ use 22–33 Ω source-series footprints next to the ESP32-S3 and a
  short, length-matched, impedance-controlled route over uninterrupted GND.
  The final trace geometry must come from the quoted fabricator stackup.

## Capacitor and inductor constraints

- TPS63802 input: 10 µF nominal with at least 4 µF effective after voltage,
  tolerance, temperature, and ageing.
- TPS63802 output: 2×22 µF nominal with at least 7 µF effective total.
- Inductor: 0.47 µH, `DFE201612E-R47M=P2`, 5.5 A saturation, 4.5 A thermal
  current, 26 mΩ maximum DCR.
- Place the converter loop and switch node tightly; route feedback Kelvin-style
  and isolate it from USB, crystal, IMU, microphone, and ADC nets.

## Firmware limits for EVT

1. Baseline SPI is 20 MHz; 24 MHz remains disabled.
2. Initial row dead time is 1.5 µs and may only be reduced from measured
   outgoing/incoming gate and row-current waveforms with margin.
3. Start continuous global caps at 43% for 20×20 and 31% for 28×28.
4. Begin PCB thermal derating near 40 °C, hard-limit near 43 °C, and turn the
   LED rail off near 48 °C; calibrate these against skin/enclosure temperature.
5. Derate strongly around 3.3 V under load and turn LED power off by
   3.15–3.2 V.
6. Reduce or suspend charging during high LED load or thermal rise.

## Required validation

- TPS63802 startup, load-step droop/overshoot, efficiency, current limit, and
  hot enclosure temperature at minimum battery.
- BQ25185 input limit, charge current, TS faults, power-path sharing, and
  thermal throttling.
- AO3403 hot drop and turn-off/on spread; translated decoder timing and
  back-power during arbitrary ramps.
- First/middle/farthest pixel voltage and current for each color.
- USB eye/signal quality sufficient for reliable repeated enumeration and
  transfer on production stackup.
