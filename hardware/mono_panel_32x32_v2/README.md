# mono_panel_32x32_v2 — 32×32 white 2835 LED panel, 8 mm pitch, 256×256 mm

This is a single-colour matrix panel for `projects/mono_electronics_v15`, following `hardware/common/LED_INTERFACE_STANDARD.md`.
- J_ROW1 and J_COL1 are Hirose FH12-40S-0.5SH on B.Cu, mid-board. Pin 1 is north; the cable exits west when viewed from the back. Use a 40-way 0.5 mm FFC, Type B (pin 1 → pin 1), ≤200 mm.
- J_ROW: 35/36 ID_SDA/SCL, 37 ID_3V3, 33/38/39/40 GND, 34 NC.
- U_ID1 is an M24C02 EEPROM at address 0x50.
- Six M2 NPTH holes, 2.2 mm (use nylon screws/standoffs). Fiducials 3 + 3.
- Edge-to-first-LED distance is 4.0 mm = pitch/2, so panels tile edge-to-edge with a continuous 8 mm pitch.
- See TRADE_STUDY.md for the LED choice and cost.

| Gate (KiCad 10.0.7) | Result |
|---|---|
| ERC (all severities) | 0 |
| DRC (all severities) | 0 |
| Unconnected | 0 |
| Schematic parity | 0 |

Rules (in `.kicad_pro`) and stackup:
- 0.127 mm minimum clearance; tracks ≥0.15 mm; vias 0.6/0.3; edge 0.3 mm.
- Stackup JLC04161H-7628, 1.6 mm, 1 oz outer.
- Every bend is a tangent arc: router output is string-pulled to any-angle straight runs (bilinear distance-field line of sight, 0.15 mm clearance), then filleted; `check_bends.py` audits tangency. GND zones on In2/B.Cu use thermal reliefs (0.3 gap / 0.3 spoke) and are refilled before plotting. 455 GND stitching vias.

## Row drop (docs/analysis.json, from the routed copper)
- Load: 32 LEDs × 10 mA = 0.32 A per row.
- Copper: ρ +20% (60 °C / plating). The bus is modelled as distributed load fed from the worst end.
- Worst case is ROW_01:
  - board ≈ 75 mV (1.0 mm bus ≈ 0.46 Ω/2, plus fan-out and via)
  - plus 200 mm FFC 1.64 Ω/m and 2 contacts ≈ 124 mV
  - **total ≈ 199 mV, under the 350 mV budget.**
- Worst-case headroom: 4.24 − 0.199 − 0.035 (AO3403) − 2.75 V (Vf max) ≈ 1.26 V left for the MBI5124 sink.
- IPC-2221 at ΔT 10 °C: 0.3 mm external ≈ 1.0 A; 1.0 mm bus ≈ 2.4 A; 0.2 mm internal ≈ 0.37 A.
  - These compare against 0.32 A peak / 57 mA RMS (1/32 duty), so heating is negligible.

## Build
- `./build.sh`: schematic → PCB base → maze router → arcs/zones → ERC/DRC/parity.
- `./make_fab.sh`: zone refill, gerbers + drill, `fab/BOM_JLC.csv`, `fab/CPL_JLC.csv`, zip.
- `python3.11 analyze.py`: row-drop analysis.

## JLC
- Upload `fab/mono_panel_32x32_v2_gerbers.zip`: 4 layers, 1.6 mm, impedance stackup JLC04161H-7628.
- PCBA both sides, using BOM_JLC.csv and CPL_JLC.csv.
- Parts: C2843876 ×1024, C202114 ×2, C7562, C1525. All were in stock on 2026-10-12.
