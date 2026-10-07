# Verification acceptance criteria

Status: pre-EVT limits. Values marked `CHARACTERIZE` require physical data
before DVT limits can be frozen.

## Safety and power

| Check | EVT acceptance |
|---|---|
| Short/open inspection | No rail short; no visible assembly damage |
| AON_3V3 | 3.3 V nominal, within selected LDO/data-sheet limits |
| LED_4V1 | 4.099 V nominal; no reset or unstable oscillation at load steps |
| LED channel current | Nominal approximately 9.41 mA; every channel below 10 mA worst-case operating limit |
| USB pre-enumeration input | Hardware limited to 100 mA |
| USB configured input | At or below 500 mA |
| Charge temperature | Hardware window 0–60 °C; firmware charge enable target 0–45 °C |
| PCB derating | Begin near 40 °C; hard limit near 43 °C; LED off near 48 °C, then calibrate to enclosure |
| Low battery | Strong derating near 3.3 V under load; LED off and sleep by 3.15–3.2 V |
| Deep sleep current | Target 30–40 µA for complete device; CHARACTERIZE |

Any uncontrolled heating, cell swelling, repeated reset, reverse current,
back-power, two-row overlap, or charge outside the approved temperature window
is an immediate failure.

## Scan engine

| Check | 20×20 | 28×28 |
|---|---:|---:|
| SPI baseline | 20 MHz | 20 MHz |
| Minimum calculated LSB hold | 3.94 µs | 4.33 µs |
| Target refresh | 175 Hz | 115 Hz |
| Serialized bits per row | 96 | 96 |
| Initial break-before-make | 1.5 µs | 1.5 µs |
| Continuous 1 W global cap | 43% | 31% |

The 1.5 µs dead time is an initial safe value, not a production optimum.
Oscilloscope evidence must show the outgoing PMOS off before the incoming row
conducts. `24 MHz` SPI is prohibited until timing and signal-integrity evidence
is approved.

## Functional

- Every pixel produces red, green, and blue with no open or stuck channel.
- Black frames show no visible ghosting in a dark environment.
- MBI5124 configuration readback succeeds after every switched-domain start.
- USB enumeration, WebUSB, recovery, disconnect, and repeated reconnect pass.
- MSC service mode never exposes a mounted firmware resource filesystem.
- IMU wake works and false-wake rate is characterized.
- Microphone response covers the intended 60 Hz–7 kHz bands without visible
  LED-switching contamination at normal gain.
- Charger, fuel gauge, NTCs, button, and service UART pass.

## Reliability

- EVT unit completes 24 hours of representative operation with no unexplained
  reset, pixel fault, charge fault, or unsafe temperature.
- DVT units complete 72 hours of the released burn-in profile.
- All failures have a traceable unit serial, hardware/firmware revision,
  timestamp, operating state, measurement, root cause, correction, and
  regression result.
