# mono_electronics v8 — continuity check (прозвонка)

Method: every pad's board net compared with the intended net (net manifest from hardware/mono_schematic + documented rework deltas + specs for parts added in rework, including the v8 stacking-port parts). Copper connectivity from the KiCad connectivity engine (each pad with copper attached when its net has >1 pad). KiCad DRC: 0 errors, 0 unconnected.

**Result: 220 parts, 220 PASS, 0 FAIL.**

Single-pad nets: only the 16 unused FFC spare pins (COL_SPARE_33..40, ROW_SPARE_33..40), expected (32×32 matrix on 40-pin FFCs).

v8 U1 pin changes (all documented deltas): GPIO3=PRES_N, GPIO26=PRES_W, GPIO47=PRES_E, GPIO35=PRES_S, GPIO48=FRAME_SYNC, GPIO33=RS485_RX, GPIO34=RS485_TX; ROW_A3 moved GPIO33→GPIO37, ROW_XLAT_OE_N moved GPIO47→GPIO44 (U0RXD, internal boot pull-up keeps the translator disabled during reset).

## IC power / GND / decoupling

| IC | value | GND pads | supply rail: nearest decoupling cap @ pad-to-pad distance |
|---|---|---|---|
| U1 | ESP32-S3FN8 | 1 | AON_3V3:C_MCU_A3@1.3mm |
| U_485 | THVD1406DR | 2 | LED_LOGIC_3V3:C_485@1.6mm |
| U_AUDIO | TLV9001IDCKR | 1 | AUDIO_3V3:C_AUD@1.3mm |
| U_AUDIO_SW | TPS22917 | 1 | AON_3V3:C_ASW_IN@3.8mm; AUDIO_3V3:C_AUD_SW@1.6mm |
| U_CHG | BQ25185 | 3 | BAT_RAW:C_CHG_BAT@4.8mm; SYS:C_CHG_SYS@3.6mm; VBUS:C_CHG_IN@4.5mm |
| U_DEC_A | 74HC154 | 2 | LED_4V1:C_DECA_V@1.5mm |
| U_DEC_B | 74HC154 | 2 | LED_4V1:C_DECB_V@1.5mm |
| U_ESD | USBLC6-2SC6 | 1 | VBUS:C_USB1@12.1mm |
| U_GAUGE | MAX17048G+T10 | 4 | BAT_RAW:C_GAUGE@1.3mm |
| U_IMU | BMI270 | 3 | AON_3V3:C_IMU_VIO@1.1mm |
| U_LDO | TPS7A2033 | 1 | AON_3V3:C_LDO_OUT@4.2mm; SYS:C_LDO_IN@4.1mm |
| U_LED1 | MBI5124GP-B | 1 | LED_LOGIC_3V3:C_LED1_V@1.6mm |
| U_LED2 | MBI5124GP-B | 1 | LED_LOGIC_3V3:C_LED2_V@1.4mm |
| U_LED_BUF | SN74LV125A | 5 | LED_LOGIC_3V3:C_BUF_V@2.6mm |
| U_LED_LOGIC | TPS22917 | 1 | AON_3V3:C_LL_IN@1.5mm; LED_LOGIC_3V3:C_LL1@1.5mm |
| U_LED_PWR | TPS63802DLAR | 4 | LED_4V1:C_LED1@2.2mm; SYS:C_SYS@2.3mm |
| U_ROW_XLAT | SN74LVC8T245RHLR | 6 | AON_3V3:C_XLAT_A@3.0mm; LED_4V1:C_XLAT_B@1.6mm |

U_ESD (USBLC6-2) and the per-port D_x_AB (SM712) / D_x_SP (PESD3V3S2UT) are TVS arrays, no decoupling needed. U_485 (THVD1406) is powered from the switched LED_LOGIC_3V3 rail (off by default).

## Per-part table

| Ref | Value | Intended-net source | Pads | Pads with net | Result | Notes |
|---|---|---|---|---|---|---|
| C_485 | 100nF | rework spec | 2 | 2 | PASS |  |
| C_AC | 1u | rework spec | 2 | 2 | PASS |  |
| C_ASW_IN | 1u | rework spec | 2 | 2 | PASS |  |
| C_AUD | 100n | rework spec | 2 | 2 | PASS |  |
| C_AUD_SW | 1u | rework spec | 2 | 2 | PASS |  |
| C_B | 4.7u | rework spec | 2 | 2 | PASS |  |
| C_BUF_V | 100n | rework spec | 2 | 2 | PASS |  |
| C_CHG_BAT | 10u | manifest | 2 | 2 | PASS |  |
| C_CHG_IN | 10u | manifest | 2 | 2 | PASS |  |
| C_CHG_SYS | 10u | manifest | 2 | 2 | PASS |  |
| C_CHIP_PU | 1u | rework spec | 2 | 2 | PASS |  |
| C_DECA_V | 100n | rework spec | 2 | 2 | PASS |  |
| C_DECB_V | 100n | rework spec | 2 | 2 | PASS |  |
| C_GAUGE | 100n | rework spec | 2 | 2 | PASS |  |
| C_GN | 4.7u | rework spec | 2 | 2 | PASS |  |
| C_IMU_VDD | 100n | rework spec | 2 | 2 | PASS |  |
| C_IMU_VIO | 100n | rework spec | 2 | 2 | PASS |  |
| C_LDO_IN | 1u | manifest | 2 | 2 | PASS |  |
| C_LDO_OUT | 1u | manifest | 2 | 2 | PASS |  |
| C_LED1 | 22u | manifest | 2 | 2 | PASS |  |
| C_LED1_V | 100n | rework spec | 2 | 2 | PASS |  |
| C_LED2 | 22u | manifest | 2 | 2 | PASS |  |
| C_LED2_V | 100n | rework spec | 2 | 2 | PASS |  |
| C_LL1 | 1u | rework spec | 2 | 2 | PASS |  |
| C_LL2 | 100n | rework spec | 2 | 2 | PASS |  |
| C_LL_IN | 1u | rework spec | 2 | 2 | PASS |  |
| C_MCU1 | 10u | manifest | 2 | 2 | PASS |  |
| C_MCU_A2 | 1u | rework spec | 2 | 2 | PASS |  |
| C_MCU_A3 | 100n | rework spec | 2 | 2 | PASS |  |
| C_MCU_CPU | 100n | rework spec | 2 | 2 | PASS |  |
| C_MCU_DA1 | 100n | rework spec | 2 | 2 | PASS |  |
| C_MCU_DA2 | 1u | rework spec | 2 | 2 | PASS |  |
| C_MCU_RTC | 100n | rework spec | 2 | 2 | PASS |  |
| C_MCU_SPI | 1u | rework spec | 2 | 2 | PASS |  |
| C_MIC | 100n | rework spec | 2 | 2 | PASS |  |
| C_SYS | 10u | manifest | 2 | 2 | PASS |  |
| C_USB1 | 100n | manifest | 2 | 2 | PASS |  |
| C_XLAT_A | 100n | rework spec | 2 | 2 | PASS |  |
| C_XLAT_B | 100n | rework spec | 2 | 2 | PASS |  |
| C_XTAL1 | 10p | manifest | 2 | 2 | PASS |  |
| C_XTAL2 | 10p | manifest | 2 | 2 | PASS |  |
| D_E_AB | SM712 | rework spec | 3 | 3 | PASS |  |
| D_E_SP | PESD3V3S2UT | rework spec | 3 | 3 | PASS |  |
| D_N_AB | SM712 | rework spec | 3 | 3 | PASS |  |
| D_N_SP | PESD3V3S2UT | rework spec | 3 | 3 | PASS |  |
| D_S_AB | SM712 | rework spec | 3 | 3 | PASS |  |
| D_S_SP | PESD3V3S2UT | rework spec | 3 | 3 | PASS |  |
| D_W_AB | SM712 | rework spec | 3 | 3 | PASS |  |
| D_W_SP | PESD3V3S2UT | rework spec | 3 | 3 | PASS |  |
| JP_TERM | TERM | rework spec | 2 | 2 | PASS |  |
| J_BAT | 53398-0371 | manifest | 5 | 3 | PASS |  |
| J_COL | FFC_40P_050_COL | manifest | 42 | 40 | PASS |  |
| J_PORT_E | SM06B-SRSS-TB | rework spec | 8 | 8 | PASS |  |
| J_PORT_N | SM06B-SRSS-TB | rework spec | 8 | 8 | PASS |  |
| J_PORT_S | SM06B-SRSS-TB | rework spec | 8 | 8 | PASS |  |
| J_PORT_W | SM06B-SRSS-TB | rework spec | 8 | 8 | PASS |  |
| J_ROW | FFC_40P_050_ROW | manifest | 42 | 40 | PASS |  |
| J_USB | USB4105 | manifest | 20 | 18 | PASS |  |
| L_LED | DFE201612E-R47M | manifest | 2 | 2 | PASS |  |
| L_XTAL | 24nH | rework spec | 2 | 2 | PASS |  |
| MIC1 | MA-HFA381-H13-1AF | rework spec | 6 | 6 | PASS |  |
| Q_ROW01 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW02 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW03 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW04 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW05 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW06 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW07 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW08 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW09 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW10 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW11 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW12 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW13 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW14 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW15 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW16 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW17 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW18 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW19 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW20 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW21 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW22 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW23 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW24 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW25 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW26 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW27 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW28 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW29 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW30 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW31 | AO3403 | manifest | 3 | 3 | PASS |  |
| Q_ROW32 | AO3403 | manifest | 3 | 3 | PASS |  |
| R_ADDR0 | 100k | manifest | 2 | 2 | PASS |  |
| R_ADDR1 | 100k | manifest | 2 | 2 | PASS |  |
| R_ADDR2 | 100k | manifest | 2 | 2 | PASS |  |
| R_ADDR3 | 100k | manifest | 2 | 2 | PASS |  |
| R_ALRT | 10k | rework spec | 2 | 2 | PASS |  |
| R_AUD_PD | 100k | manifest | 2 | 2 | PASS |  |
| R_B1 | 100k | rework spec | 2 | 2 | PASS |  |
| R_B2 | 100k | rework spec | 2 | 2 | PASS |  |
| R_BOOT0 | 10k | manifest | 2 | 2 | PASS |  |
| R_CC1 | 5.1k | rework spec | 2 | 2 | PASS |  |
| R_CC2 | 5.1k | rework spec | 2 | 2 | PASS |  |
| R_CHIP_PU | 10k | rework spec | 2 | 2 | PASS |  |
| R_CLK_PD | 100k | rework spec | 2 | 2 | PASS |  |
| R_CLK_SER | 22R | manifest | 2 | 2 | PASS |  |
| R_ENA | 47k | manifest | 2 | 2 | PASS |  |
| R_ENB | 47k | manifest | 2 | 2 | PASS |  |
| R_EN_PD | 100k | manifest | 2 | 2 | PASS |  |
| R_EXT1 | 1.82k | manifest | 2 | 2 | PASS |  |
| R_EXT2 | 1.82k | manifest | 2 | 2 | PASS |  |
| R_F | 100k | rework spec | 2 | 2 | PASS |  |
| R_FB_BOT | 91k | manifest | 2 | 2 | PASS |  |
| R_FB_TOP | 681k | manifest | 2 | 2 | PASS |  |
| R_G01 | 33R | manifest | 2 | 2 | PASS |  |
| R_G02 | 33R | manifest | 2 | 2 | PASS |  |
| R_G03 | 33R | manifest | 2 | 2 | PASS |  |
| R_G04 | 33R | manifest | 2 | 2 | PASS |  |
| R_G05 | 33R | manifest | 2 | 2 | PASS |  |
| R_G06 | 33R | manifest | 2 | 2 | PASS |  |
| R_G07 | 33R | manifest | 2 | 2 | PASS |  |
| R_G08 | 33R | manifest | 2 | 2 | PASS |  |
| R_G09 | 33R | manifest | 2 | 2 | PASS |  |
| R_G10 | 33R | manifest | 2 | 2 | PASS |  |
| R_G11 | 33R | manifest | 2 | 2 | PASS |  |
| R_G12 | 33R | manifest | 2 | 2 | PASS |  |
| R_G13 | 33R | manifest | 2 | 2 | PASS |  |
| R_G14 | 33R | manifest | 2 | 2 | PASS |  |
| R_G15 | 33R | manifest | 2 | 2 | PASS |  |
| R_G16 | 33R | manifest | 2 | 2 | PASS |  |
| R_G17 | 33R | manifest | 2 | 2 | PASS |  |
| R_G18 | 33R | manifest | 2 | 2 | PASS |  |
| R_G19 | 33R | manifest | 2 | 2 | PASS |  |
| R_G20 | 33R | manifest | 2 | 2 | PASS |  |
| R_G21 | 33R | manifest | 2 | 2 | PASS |  |
| R_G22 | 33R | manifest | 2 | 2 | PASS |  |
| R_G23 | 33R | manifest | 2 | 2 | PASS |  |
| R_G24 | 33R | manifest | 2 | 2 | PASS |  |
| R_G25 | 33R | manifest | 2 | 2 | PASS |  |
| R_G26 | 33R | manifest | 2 | 2 | PASS |  |
| R_G27 | 33R | manifest | 2 | 2 | PASS |  |
| R_G28 | 33R | manifest | 2 | 2 | PASS |  |
| R_G29 | 33R | manifest | 2 | 2 | PASS |  |
| R_G30 | 33R | manifest | 2 | 2 | PASS |  |
| R_G31 | 33R | manifest | 2 | 2 | PASS |  |
| R_G32 | 33R | manifest | 2 | 2 | PASS |  |
| R_GN | 2.2k | rework spec | 2 | 2 | PASS |  |
| R_ILIM | 18k | manifest | 2 | 2 | PASS |  |
| R_INB | 100k | rework spec | 2 | 2 | PASS |  |
| R_ISET | 600R | manifest | 2 | 2 | PASS |  |
| R_LE_PD | 100k | manifest | 2 | 2 | PASS |  |
| R_LE_SER | 22R | manifest | 2 | 2 | PASS |  |
| R_LOGIC_PD | 100k | manifest | 2 | 2 | PASS |  |
| R_OE_PU | 47k | manifest | 2 | 2 | PASS |  |
| R_OE_YPU | 47k | manifest | 2 | 2 | PASS |  |
| R_PU01 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU02 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU03 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU04 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU05 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU06 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU07 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU08 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU09 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU10 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU11 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU12 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU13 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU14 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU15 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU16 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU17 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU18 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU19 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU20 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU21 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU22 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU23 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU24 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU25 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU26 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU27 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU28 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU29 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU30 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU31 | 47k | manifest | 2 | 2 | PASS |  |
| R_PU32 | 47k | manifest | 2 | 2 | PASS |  |
| R_QOD | 1k | manifest | 2 | 2 | PASS |  |
| R_SCL | 4.7k | rework spec | 2 | 2 | PASS |  |
| R_SDA | 4.7k | rework spec | 2 | 2 | PASS |  |
| R_SDI_PD | 100k | rework spec | 2 | 2 | PASS |  |
| R_SDI_SER | 22R | manifest | 2 | 2 | PASS |  |
| R_TERM | 120R | rework spec | 2 | 2 | PASS |  |
| R_TH | 10k 1% | rework spec | 2 | 2 | PASS |  |
| R_USB_N | 22R | manifest | 2 | 2 | PASS |  |
| R_USB_P | 22R | manifest | 2 | 2 | PASS |  |
| R_XOE | 10k | manifest | 2 | 2 | PASS |  |
| SW1 | KMR2 | manifest | 4 | 4 | PASS |  |
| TH_PCB | NTC 10k B3435 | rework spec | 2 | 2 | PASS |  |
| TP1 | AON_3V3 | manifest | 2 | 2 | PASS |  |
| TP2 | GND | manifest | 2 | 1 | PASS |  |
| U1 | ESP32-S3FN8 | manifest | 57 | 41 | PASS |  |
| U_485 | THVD1406DR | rework spec | 8 | 8 | PASS |  |
| U_AUDIO | TLV9001IDCKR | rework spec | 5 | 5 | PASS |  |
| U_AUDIO_SW | TPS22917 | manifest | 6 | 4 | PASS |  |
| U_CHG | BQ25185 | manifest | 11 | 9 | PASS |  |
| U_DEC_A | 74HC154 | manifest | 24 | 24 | PASS |  |
| U_DEC_B | 74HC154 | manifest | 24 | 24 | PASS |  |
| U_ESD | USBLC6-2SC6 | manifest | 6 | 6 | PASS |  |
| U_GAUGE | MAX17048G+T10 | rework spec | 9 | 9 | PASS |  |
| U_IMU | BMI270 | manifest | 14 | 9 | PASS |  |
| U_LDO | TPS7A2033 | manifest | 5 | 4 | PASS |  |
| U_LED1 | MBI5124GP-B | manifest | 24 | 24 | PASS |  |
| U_LED2 | MBI5124GP-B | manifest | 24 | 23 | PASS |  |
| U_LED_BUF | SN74LV125A | manifest | 14 | 14 | PASS |  |
| U_LED_LOGIC | TPS22917 | manifest | 6 | 5 | PASS |  |
| U_LED_PWR | TPS63802DLAR | manifest | 11 | 10 | PASS |  |
| U_ROW_XLAT | SN74LVC8T245RHLR | rework spec | 25 | 23 | PASS |  |
| Y1 | L327S400H11L | manifest | 4 | 4 | PASS |  |
