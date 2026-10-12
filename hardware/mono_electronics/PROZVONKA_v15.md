# mono_electronics v15: continuity check (прозвонка)

Method: each pad's board net is compared with the exported schematic netlist (hardware/mono_schematic/reports/mono_electronics_sch_netlist.xml). Each pad on a multi-pad net must have copper attached (KiCad connectivity engine). KiCad DRC must report 0 unconnected, which proves every net is a single connected cluster.

**Result: 312 parts, 312 PASS, 0 FAIL**

| Ref | Value | Pads | Net = schematic | Copper attached | Result | Notes |
|---|---|---|---|---|---|---|
| C_485 | 100nF | 2 | 2 | 2 | PASS |  |
| C_AC1 | 1u | 2 | 2 | 2 | PASS |  |
| C_ASW_IN1 | 1u | 2 | 2 | 2 | PASS |  |
| C_AUD1 | 100n | 2 | 2 | 2 | PASS |  |
| C_AUD_SW1 | 1u | 2 | 2 | 2 | PASS |  |
| C_B1 | 4.7u | 2 | 2 | 2 | PASS |  |
| C_BUF_V1 | 100n | 2 | 2 | 2 | PASS |  |
| C_CHG_BAT1 | 10u | 2 | 2 | 2 | PASS |  |
| C_CHG_IN1 | 10u | 2 | 2 | 2 | PASS |  |
| C_CHG_SYS1 | 10u | 2 | 2 | 2 | PASS |  |
| C_CHIP_PU1 | 1u | 2 | 2 | 2 | PASS |  |
| C_DECA_V1 | 100n | 2 | 2 | 2 | PASS |  |
| C_DECB_V1 | 100n | 2 | 2 | 2 | PASS |  |
| C_EN1 | 10n | 2 | 2 | 2 | PASS |  |
| C_GAUGE1 | 100n | 2 | 2 | 2 | PASS |  |
| C_GN1 | 4.7u | 2 | 2 | 2 | PASS |  |
| C_IMU_VDD1 | 100n | 2 | 2 | 2 | PASS |  |
| C_IMU_VIO1 | 100n | 2 | 2 | 2 | PASS |  |
| C_LDO_IN1 | 1u | 2 | 2 | 2 | PASS |  |
| C_LDO_OUT1 | 1u | 2 | 2 | 2 | PASS |  |
| C_LED1 | 22u | 2 | 2 | 2 | PASS |  |
| C_LED1_V1 | 100n | 2 | 2 | 2 | PASS |  |
| C_LED2 | 22u | 2 | 2 | 2 | PASS |  |
| C_LED2_V1 | 100n | 2 | 2 | 2 | PASS |  |
| C_LL1 | 1u | 2 | 2 | 2 | PASS |  |
| C_LL2 | 100n | 2 | 2 | 2 | PASS |  |
| C_LL_IN1 | 1u | 2 | 2 | 2 | PASS |  |
| C_MCU1 | 22u | 2 | 2 | 2 | PASS |  |
| C_MCU_A2 | 1u | 2 | 2 | 2 | PASS |  |
| C_MCU_A3 | 100n | 2 | 2 | 2 | PASS |  |
| C_MCU_CPU1 | 100n | 2 | 2 | 2 | PASS |  |
| C_MCU_DA1 | 100n | 2 | 2 | 2 | PASS |  |
| C_MCU_DA2 | 1u | 2 | 2 | 2 | PASS |  |
| C_MCU_RTC1 | 100n | 2 | 2 | 2 | PASS |  |
| C_MCU_SPI1 | 1u | 2 | 2 | 2 | PASS |  |
| C_MIC1 | 100n | 2 | 2 | 2 | PASS |  |
| C_SYS1 | 10u | 2 | 2 | 2 | PASS |  |
| C_USB1 | 100n | 2 | 2 | 2 | PASS |  |
| C_XLAT_A1 | 100n | 2 | 2 | 2 | PASS |  |
| C_XLAT_B1 | 100n | 2 | 2 | 2 | PASS |  |
| C_XTAL1 | 10p | 2 | 2 | 2 | PASS |  |
| C_XTAL2 | 10p | 2 | 2 | 2 | PASS |  |
| D_C01 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C02 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C03 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C04 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C05 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C06 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C07 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C08 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C09 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C10 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C11 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C12 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C13 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C14 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C15 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C16 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C17 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C18 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C19 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C20 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C21 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C22 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C23 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C24 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C25 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C26 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C27 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C28 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C29 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C30 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C31 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_C32 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_E_AB1 | SM712 | 3 | 3 | 3 | PASS |  |
| D_E_SP1 | PESD3V3S2UT | 3 | 3 | 3 | PASS |  |
| D_ID1 | PESD5V0S2BT | 3 | 3 | 3 | PASS |  |
| D_N_AB1 | SM712 | 3 | 3 | 3 | PASS |  |
| D_N_SP1 | PESD3V3S2UT | 3 | 3 | 3 | PASS |  |
| D_R01 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R02 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R03 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R04 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R05 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R06 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R07 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R08 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R09 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R10 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R11 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R12 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R13 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R14 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R15 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R16 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R17 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R18 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R19 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R20 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R21 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R22 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R23 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R24 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R25 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R26 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R27 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R28 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R29 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R30 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R31 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_R32 | PESD5V0S1BL (DNP wearable) | 2 | 2 | 2 | PASS |  |
| D_S_AB1 | SM712 | 3 | 3 | 3 | PASS |  |
| D_S_SP1 | PESD3V3S2UT | 3 | 3 | 3 | PASS |  |
| D_VBUS1 | SMF12A | 2 | 2 | 2 | PASS |  |
| D_W_AB1 | SM712 | 3 | 3 | 3 | PASS |  |
| D_W_SP1 | PESD3V3S2UT | 3 | 3 | 3 | PASS |  |
| FID1 | Fiducial | 0 | 0 | 0 | PASS |  |
| FID2 | Fiducial | 0 | 0 | 0 | PASS |  |
| FID3 | Fiducial | 0 | 0 | 0 | PASS |  |
| F_BAT1 | 0466002.NRHF 2A | 2 | 2 | 2 | PASS |  |
| H1 | M2.5 | 1 | 1 | 1 | PASS |  |
| H2 | M2.5 | 1 | 1 | 1 | PASS |  |
| H3 | M2.5 | 1 | 1 | 1 | PASS |  |
| H4 | M2.5 | 1 | 1 | 1 | PASS |  |
| JP_TERM1 | TERM | 2 | 2 | 2 | PASS |  |
| J_BAT1 | S3B-PH-SM4-TB | 5 | 5 | 5 | PASS |  |
| J_CH1 | BH127VS-40P-H49 2x20 1.27mm box header (DNP wearable) | 40 | 40 | 40 | PASS |  |
| J_COL1 | FFC_40P_050_COL | 42 | 42 | 42 | PASS |  |
| J_PORT_E1 | SM06B-SRSS-TB | 8 | 8 | 8 | PASS |  |
| J_PORT_N1 | SM06B-SRSS-TB | 8 | 8 | 8 | PASS |  |
| J_PORT_S1 | SM06B-SRSS-TB | 8 | 8 | 8 | PASS |  |
| J_PORT_W1 | SM06B-SRSS-TB | 8 | 8 | 8 | PASS |  |
| J_RH1 | BH127VS-40P-H49 2x20 1.27mm box header (DNP wearable) | 40 | 40 | 40 | PASS |  |
| J_ROW1 | FFC_40P_050_ROW | 42 | 42 | 42 | PASS |  |
| J_USB1 | TYPE-C-31-M-12 | 20 | 20 | 20 | PASS |  |
| L_LED1 | DFE201612E-R47M | 2 | 2 | 2 | PASS |  |
| L_XTAL1 | 24nH | 2 | 2 | 2 | PASS |  |
| MIC1 | MA-HFA381-H13-1AF | 6 | 6 | 6 | PASS |  |
| Q_BAT1 | AO3401A | 3 | 3 | 3 | PASS |  |
| Q_ROW01 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW02 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW03 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW04 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW05 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW06 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW07 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW08 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW09 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW10 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW11 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW12 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW13 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW14 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW15 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW16 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW17 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW18 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW19 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW20 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW21 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW22 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW23 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW24 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW25 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW26 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW27 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW28 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW29 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW30 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW31 | AO3403 | 3 | 3 | 3 | PASS |  |
| Q_ROW32 | AO3403 | 3 | 3 | 3 | PASS |  |
| R_ADDR0 | 100k | 2 | 2 | 2 | PASS |  |
| R_ADDR1 | 100k | 2 | 2 | 2 | PASS |  |
| R_ADDR2 | 100k | 2 | 2 | 2 | PASS |  |
| R_ADDR3 | 100k | 2 | 2 | 2 | PASS |  |
| R_ALRT1 | 10k | 2 | 2 | 2 | PASS |  |
| R_AUD_PD1 | 100k | 2 | 2 | 2 | PASS |  |
| R_B1 | 100k | 2 | 2 | 2 | PASS |  |
| R_B2 | 100k | 2 | 2 | 2 | PASS |  |
| R_BATG1 | 10k | 2 | 2 | 2 | PASS |  |
| R_BOOT0 | 10k | 2 | 2 | 2 | PASS |  |
| R_CC1 | 5.1k | 2 | 2 | 2 | PASS |  |
| R_CC2 | 5.1k | 2 | 2 | 2 | PASS |  |
| R_CHIP_PU1 | 10k | 2 | 2 | 2 | PASS |  |
| R_CLK_PD1 | 100k | 2 | 2 | 2 | PASS |  |
| R_CLK_SER1 | 22R | 2 | 2 | 2 | PASS |  |
| R_ENA1 | 47k | 2 | 2 | 2 | PASS |  |
| R_ENB1 | 47k | 2 | 2 | 2 | PASS |  |
| R_EN_BOT1 | 39k | 2 | 2 | 2 | PASS |  |
| R_EN_PD1 | 100k | 2 | 2 | 2 | PASS |  |
| R_EN_SER1 | 100k | 2 | 2 | 2 | PASS |  |
| R_EN_TOP1 | 100k | 2 | 2 | 2 | PASS |  |
| R_EXP_3V1 | 0R DNP | 2 | 2 | 2 | PASS |  |
| R_EXP_CLK1 | 33R DNP | 2 | 2 | 2 | PASS |  |
| R_EXP_LE1 | 33R DNP | 2 | 2 | 2 | PASS |  |
| R_EXP_OE1 | 33R DNP | 2 | 2 | 2 | PASS |  |
| R_EXP_SDI1 | 33R DNP | 2 | 2 | 2 | PASS |  |
| R_EXT1 | 1.82k | 2 | 2 | 2 | PASS |  |
| R_EXT2 | 1.82k | 2 | 2 | 2 | PASS |  |
| R_F1 | 100k | 2 | 2 | 2 | PASS |  |
| R_FB_BOT1 | 91k | 2 | 2 | 2 | PASS |  |
| R_FB_TOP1 | 681k | 2 | 2 | 2 | PASS |  |
| R_G01 | 33R | 2 | 2 | 2 | PASS |  |
| R_G02 | 33R | 2 | 2 | 2 | PASS |  |
| R_G03 | 33R | 2 | 2 | 2 | PASS |  |
| R_G04 | 33R | 2 | 2 | 2 | PASS |  |
| R_G05 | 33R | 2 | 2 | 2 | PASS |  |
| R_G06 | 33R | 2 | 2 | 2 | PASS |  |
| R_G07 | 33R | 2 | 2 | 2 | PASS |  |
| R_G08 | 33R | 2 | 2 | 2 | PASS |  |
| R_G09 | 33R | 2 | 2 | 2 | PASS |  |
| R_G10 | 33R | 2 | 2 | 2 | PASS |  |
| R_G11 | 33R | 2 | 2 | 2 | PASS |  |
| R_G12 | 33R | 2 | 2 | 2 | PASS |  |
| R_G13 | 33R | 2 | 2 | 2 | PASS |  |
| R_G14 | 33R | 2 | 2 | 2 | PASS |  |
| R_G15 | 33R | 2 | 2 | 2 | PASS |  |
| R_G16 | 33R | 2 | 2 | 2 | PASS |  |
| R_G17 | 33R | 2 | 2 | 2 | PASS |  |
| R_G18 | 33R | 2 | 2 | 2 | PASS |  |
| R_G19 | 33R | 2 | 2 | 2 | PASS |  |
| R_G20 | 33R | 2 | 2 | 2 | PASS |  |
| R_G21 | 33R | 2 | 2 | 2 | PASS |  |
| R_G22 | 33R | 2 | 2 | 2 | PASS |  |
| R_G23 | 33R | 2 | 2 | 2 | PASS |  |
| R_G24 | 33R | 2 | 2 | 2 | PASS |  |
| R_G25 | 33R | 2 | 2 | 2 | PASS |  |
| R_G26 | 33R | 2 | 2 | 2 | PASS |  |
| R_G27 | 33R | 2 | 2 | 2 | PASS |  |
| R_G28 | 33R | 2 | 2 | 2 | PASS |  |
| R_G29 | 33R | 2 | 2 | 2 | PASS |  |
| R_G30 | 33R | 2 | 2 | 2 | PASS |  |
| R_G31 | 33R | 2 | 2 | 2 | PASS |  |
| R_G32 | 33R | 2 | 2 | 2 | PASS |  |
| R_GN1 | 2.2k | 2 | 2 | 2 | PASS |  |
| R_ID_3V1 | 100R | 2 | 2 | 2 | PASS |  |
| R_ID_SCL1 | 33R | 2 | 2 | 2 | PASS |  |
| R_ID_SDA1 | 33R | 2 | 2 | 2 | PASS |  |
| R_ILIM1 | 18k | 2 | 2 | 2 | PASS |  |
| R_ILM1 | 2.7k | 2 | 2 | 2 | PASS |  |
| R_INB1 | 100k | 2 | 2 | 2 | PASS |  |
| R_ISET1 | 600R | 2 | 2 | 2 | PASS |  |
| R_LE_PD1 | 100k | 2 | 2 | 2 | PASS |  |
| R_LE_SER1 | 22R | 2 | 2 | 2 | PASS |  |
| R_LOGIC_PD1 | 100k | 2 | 2 | 2 | PASS |  |
| R_OE_PU1 | 47k | 2 | 2 | 2 | PASS |  |
| R_OE_YPU1 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU01 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU02 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU03 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU04 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU05 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU06 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU07 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU08 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU09 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU10 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU11 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU12 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU13 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU14 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU15 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU16 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU17 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU18 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU19 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU20 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU21 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU22 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU23 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU24 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU25 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU26 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU27 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU28 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU29 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU30 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU31 | 47k | 2 | 2 | 2 | PASS |  |
| R_PU32 | 47k | 2 | 2 | 2 | PASS |  |
| R_QOD1 | 1k | 2 | 2 | 2 | PASS |  |
| R_SCL1 | 4.7k | 2 | 2 | 2 | PASS |  |
| R_SDA1 | 4.7k | 2 | 2 | 2 | PASS |  |
| R_SDI_PD1 | 100k | 2 | 2 | 2 | PASS |  |
| R_SDI_SER1 | 22R | 2 | 2 | 2 | PASS |  |
| R_TERM1 | 120R | 2 | 2 | 2 | PASS |  |
| R_TH1 | 10k 1% | 2 | 2 | 2 | PASS |  |
| R_USB_N1 | 22R | 2 | 2 | 2 | PASS |  |
| R_USB_P1 | 22R | 2 | 2 | 2 | PASS |  |
| R_XOE1 | 10k | 2 | 2 | 2 | PASS |  |
| SW1 | KMR2 | 4 | 4 | 4 | PASS |  |
| TH_PCB1 | NTC 10k B3435 | 2 | 2 | 2 | PASS |  |
| TP1 | AON_3V3 | 2 | 2 | 2 | PASS |  |
| TP2 | GND | 2 | 2 | 2 | PASS |  |
| U1 | ESP32-S3FN8 | 57 | 57 | 57 | PASS |  |
| U_485 | THVD1406DR | 8 | 8 | 8 | PASS |  |
| U_AUDIO1 | TLV9001IDCKR | 5 | 5 | 5 | PASS |  |
| U_AUDIO_SW1 | TPS22917 | 6 | 6 | 6 | PASS |  |
| U_CHG1 | BQ25185 | 11 | 11 | 11 | PASS |  |
| U_DEC_A1 | 74HC154 | 24 | 24 | 24 | PASS |  |
| U_DEC_B1 | 74HC154 | 24 | 24 | 24 | PASS |  |
| U_ESD1 | USBLC6-2SC6 | 6 | 6 | 6 | PASS |  |
| U_GAUGE1 | MAX17048G+T10 | 9 | 9 | 9 | PASS |  |
| U_IMU1 | BMI270 | 14 | 14 | 14 | PASS |  |
| U_LDO1 | TLV75733PDBVR | 5 | 5 | 5 | PASS |  |
| U_LED1 | MBI5124GP-B | 24 | 24 | 24 | PASS |  |
| U_LED2 | MBI5124GP-B | 24 | 24 | 24 | PASS |  |
| U_LED_BUF1 | SN74LV125A | 14 | 14 | 14 | PASS |  |
| U_LED_LOGIC1 | TPS22917 | 6 | 6 | 6 | PASS |  |
| U_LED_PWR1 | TPS63802DLAR | 11 | 11 | 11 | PASS |  |
| U_OVP1 | TPS259531DSGR | 9 | 9 | 9 | PASS |  |
| U_ROW_XLAT1 | SN74LVC8T245RHLR | 25 | 25 | 25 | PASS |  |
| Y1 | L327S400H11L | 4 | 4 | 4 | PASS |  |
