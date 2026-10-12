# mono_electronics v15b: ESP32-S3 mono LED driver board (standalone KiCad project)

This folder is the self-contained, canonical copy of the v15 mono electronics board (PR #4). Open `mono_electronics.kicad_pro` in KiCad 10. The symbols (`symbols/`), footprints (`footprints/mono_electronics.pretty`) and 3D models (`3dmodels/`, via `${KIPRJMOD}`) are all local. The originals stay in `hardware/mono_schematic/` (schematic) and `hardware/mono_electronics/` (board), and are kept in sync.

## Spec summary
| | |
|---|---|
| Board | 148.0 × 99.5 mm, 4 layers, **1.6 mm JLC04161H-7628** (1 oz outer / 0.5 oz inner, ENIG), top-side assembly only, 4 × M2.5 plated holes, 3 fiducials |
| MCU | ESP32-S3FN8 (QFN-56), 40 MHz crystal, USB-C (HRO TYPE-C-31-M-12) with USBLC6-2SC6 ESD |
| Power in | USB VBUS_CONN → SMF12A TVS → TPS259531 eFuse (5.7 V OVP, R_ILM 2.7 k = 0.78 A) → BQ25185 charger/power path (ILIM 18 k ≈ 0.475 A, ISET 620 R) |
| Battery | 1S Li-ion on JST PH S3B-PH-SM4-TB; 0466002 2 A fuse; AO3401A reverse-battery P-FET; MAX17048 gauge |
| Rails | LED_4V1 = 4.24 V (TPS63802, FB 681k/91k); AON_3V3 (TLV75733P); LED_LOGIC_3V3 / AUDIO_3V3 (TPS22917 switches) |
| LED drive | 2 × MBI5124 (16 ch, 10 mA, Rext 1.82 k), 2 × 74HC154 row decoders, 32 × AO3403 row FETs, SN74LVC8T245 level shift; worst row drop ≈ 107 mV |
| Interfaces | 2 × 40-pin 0.5 mm FFC (Type B cable), installation variant: 2 × 2×20 1.27 mm box headers + 64 × PESD5V0S1BL; 4 × RS-485/sync ports (JST SH 6P, THVD1406); BMI270 IMU; MEMS mic |
| LED interface | See `docs/LED_INTERFACE_STANDARD.md` |

## Contents
- `mono_electronics.kicad_pro / .kicad_sch / .kicad_pcb`, `sheets/` (10 sub-sheets), `symbols/`, `footprints/`, `3dmodels/`, `sym-lib-table`, `fp-lib-table`
- `fab/`: Gerbers and Excellon drill (`fab/gerbers/`), JLCPCB BOM + CPL for the **wearable** and **installation** variants, annotated BOM, `README_FAB.md`, and `mono_electronics_v15_fab.zip` (the upload package)
- `drawings/`: schematic PDF, top assembly drawing PDF
- `renders/`: top / bottom / iso 3D renders
- `docs/`: MFG_AUDIT_v15 (manufacturing-standards audit and fixes), ABSMAX_REVIEW_v13, LED_INTERFACE_STANDARD, REWORK_LOG, LAST_CHANGES, PROZVONKA_v15 (continuity check), ERC_WAIVERS

## Verification (2026-10-12, KiCad 10.0.7 kicad-cli, run from this folder)
- `kicad-cli pcb drc --schematic-parity --severity-all mono_electronics.kicad_pcb`: **0 violations, 0 unconnected, 0 parity issues**. Board min clearance rule 0.127 mm. Zones refilled before plotting.
- `kicad-cli sch erc --severity-all mono_electronics.kicad_sch`: **0**
- Continuity 312/312 footprints (309 schematic parts + 3 board-only fiducials). Nets 224. All trace bends are arcs. No B-side parts.

## Known gaps
- No 3D model for J_BAT1 (JST S3B-PH-SM4-TB): there is none in the KiCad library.
- J_RH1/J_CH1 box header C42462832: stock ~125, so check it before ordering. Thin stock also on MIC1, Y1 and J_BAT1 (see fab/README_FAB.md).
- Check CPL rotations in the JLC preview: the CPL is raw KiCad output, with no JLC offsets applied.
