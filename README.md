# leds

LED matrix / wearable LED electronics, firmware and tools.

## Where things live
- **mono_electronics v15 (ESP32-S3 mono LED driver board, PR #4): standalone KiCad project, fab outputs, drawings, renders and docs in [`projects/mono_electronics_v15/`](projects/mono_electronics_v15/).** This is the canonical copy to open and order from.
- Working sources: `hardware/mono_schematic/` (schematic and generator tools), `hardware/mono_electronics/` (board, review docs); fab history in `manufacturing/mono_electronics/` (v11b–v15).
- Interface standard: `hardware/common/LED_INTERFACE_STANDARD.md`.
- Firmware: `firmware/`. Simulators and analysis: `tools/`, `leds_analysis/`.
