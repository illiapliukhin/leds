# mono_electronics v13: absolute-maximum review (2026-10-11)

Worst-case rail voltages after the v13 protections:

| Rail | Worst case | Why |
|---|---|---|
| VBUS_CONN (connector side) | ≤ 19.9 V transient, 12 V continuous (bad QC/PD source) | D_VBUS1 SMF12A: VRWM 12 V, VBR 13.3–14.7 V, VC 19.9 V @ 10 A |
| VBUS (after U_OVP1) | ≤ 5.9 V | TPS259531 OV clamp: rising threshold 5.5–5.9 V, output clamp 5.2–5.7 V (datasheet SLVSE57C) |
| SYS | ≤ 4.5 V (VSYS_REG), BAT 4.2 V without VBUS | BQ25185 power path |
| BAT_PACK / BAT_FUSE / BAT_RAW | 4.35 V; reversed pack −4.35 V on BAT_PACK/BAT_FUSE only | Q_BAT1 blocks reverse polarity |
| LED_4V1 | 4.24 V (FB 681k/91k) | TPS63802 |
| AON_3V3 / LED_LOGIC_3V3 | 3.3 V | TLV75733P / TPS22917 |

| Part | Pin / rating | Abs max | Worst case | Result |
|---|---|---|---|---|
| U_OVP1 TPS259531DSGR | IN | 20 V | 19.9 V clamp (D_VBUS1) | OK, 0.1 V margin at full 10 A surge, large margin at 12 V |
| U_OVP1 | EN/UVLO | 7 V | 19.9 × 39/139 = 5.6 V | OK |
| U_OVP1 | IN→OUT current | internal limit | R_ILM1 = 2.7 k (C25885). TPS2595 Eq. 4: I_LIMIT = 2000/R + 0.04 = 0.78 A (0.72–0.84 A) | **Fixed in v13:** 1.78 k gave 1.09–1.24 A, above the BQ25185 1.1 A IN DC abs max. v13c briefly used 1.6 k (1.29 A); that change was reverted in v13d |
| D_VBUS1 SMF12A | VRWM | 12 V | 12 V continuous source | OK, leakage ≤ 2.5 µA; a 5 V-standoff TVS (SMBJ5.0A/SMF5.0A) would avalanche continuously on a 12 V source and burn, which is the failure the simulation found on the USBLC6 |
| U_CHG1 BQ25185 | IN | 25 V | 5.9 V | OK (it would also survive 12 V by itself; its VIN_OVP is 18–19 V) |
| U_CHG1 | IN DC current | 1.1 A | 0.84 A (eFuse limit); 0.5 A steady state (ILIM pin, R_ILIM1 18 k) | OK |
| U_CHG1 | all other pins | 5.5 V | SYS 4.5 V, BAT 4.35 V, TS ≤ 3.3 V | OK |
| U_CHG1 | TJ | 150 °C | linear charge (5 − 3.0 V) × 0.5 A = 1.0 W worst case, plus about 0.1 W SYS path | Internal thermal regulation folds back the charge current. v13 adds 62 mm² of F GND pour and 4 GND vias on the EP return. Still EVT-check the hottest case (empty cell, 5 V input) |
| U_ESD1 USBLC6-2SC6 | VBUS pin | 6 V | 5.9 V | OK; was exposed to VBUS_CONN (12 V) before v13 |
| C_CHG_IN1 10 µF CL21A106KAYNNNE / C_USB1 100 nF CL05B104KO5 | rating | 25 V / 16 V | 5.9 V | OK |
| R_EN_TOP1 100 k 0402 | rating | 50 V | 20 V | OK |
| Q_BAT1 AO3401A | VDS / VGS | −30 V / ±12 V | 4.35 V / −4.35 V | OK; RDS(on) ≈ 60 mΩ at 4.5 V → 72 mV at the 1.2 A peak |
| F_BAT1 0466002.NRHF | 63 V, 50 A interrupt | — | 4.35 V; pack short limited by the pack PCM and cell ESR (< 50 A) | OK |
| J_BAT1 JST S3B-PH-SM4-TB (v13b; was Molex PicoBlade 53398, 1 A) | 2 A/contact, 100 V | — | 1.22 A peak, 0.5 A charge | OK (1.6× margin). The pack PCM is still assumed as primary over-current protection; F_BAT1 is the board backstop |
| U_GAUGE1 MAX17048 | CELL | 6 V | 4.35 V | OK; behind Q_BAT1, so it never sees reverse polarity |
| U_LED_PWR1 TPS63802 | VIN | 6 V (abs) | 4.5 V | OK |
| U_LDO1 TLV75733P | IN | 6.5 V | 4.5 V | OK |
| U_LED_LOGIC1 / U_AUDIO_SW1 TPS22917 | VIN | 6 V | 3.3 V | OK |
| U_ROW_XLAT1 SN74LVC8T245 | VCCA / VCCB | 6.5 V | 3.3 / 4.24 V | OK |
| U_DEC_A1/B1 74HC154 | VCC | 7 V | 4.24 V | OK |
| Q_ROW01–32 AO3403 | VDS / VGS | −30 V / ±12 V | 4.24 V / −4.24 V | OK |
| U_LED1/2 MBI5124 | VDD / OUT | 7 V / 17 V | 3.3 V / 4.24 V | OK |
| U1 ESP32-S3FN8, U_IMU1 BMI270, U_485 THVD1406, U_LED_BUF1 SN74LV125A, U_AUDIO1 TLV9001, MIC1 | VDD | 3.6 V or more | 3.3 V | OK; all I/O stays inside its own rail domain (LED_4V1 only reaches the row FETs/decoders through the LVC8T245) |
| All 0402 1 µF (C106254, 6.3 V X5R) | rating | 6.3 V | SYS 4.5 V | OK (DC-bias derating about −40 %, already in the design) |
| 22 µF 0805 (10 V) on LED_4V1 / AON | rating | 10 V | 4.24 V | OK |
| D_*_SP1 PESD3V3S2UT, D_*_AB1 SM712, D_ID1 PESD5V0S2BT | VRWM | 3.3 / −7…12 / 5 V | 3.3 V / RS-485 bus / 3.3 V I²C | OK |

Changes made by this review: R_ILM1 1.78 k → 2.7 k (C25885). v13c also added an F.Cu GND pour around U_OVP1 (21.5 mm²) and 2 GND thermal vias tied to the EP; that copper is kept. Nothing else is over its abs max.
