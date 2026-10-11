# Virtual bench report

    BENCH REPORT  mono_electronics v11c + mono_panel_32x32
    I2C scan       PASS  0x68 BMI270, 0x36 MAX17048 (mocked)
    All on         PASS  rows 32/32  cols 32/32  (32 scans)
    Row walk       PASS  rows 32/32  cols 32/32  (89 scans)
    Column walk    PASS  rows 32/32  cols 32/32  (76 scans)
    Checkerboard   PASS  rows 32/32  cols 32/32  (25 scans)
    [F1] All on    CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [1, 2, 3, 4, 5, 6]..
    [F1] Row walk  CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [1, 2, 3, 4, 5, 6]..
    [F2] Column walk CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [7]
    VERDICT: nominal PASS, faults all caught

## Details

- **All on**: 32 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Row walk**: 89 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Column walk**: 76 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Checkerboard**: 25 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **[F1] All on**: 26 scans, 11648 LED mismatches; rows ok 0; cols ok 0; examples: D218 (ROW_07 x COL_26) dark, expected lit; D214 (ROW_07 x COL_22) dark, expected lit; D70 (ROW_03 x COL_06) dark, expected lit; D803 (ROW_26 x COL_03) dark, expected lit
- **[F1] Row walk**: 76 scans, 3728 LED mismatches; rows ok 0; cols ok 0; examples: D955 (ROW_30 x COL_27) dark, expected lit; D341 (ROW_11 x COL_21) lit, expected dark; D331 (ROW_11 x COL_11) lit, expected dark; D337 (ROW_11 x COL_17) lit, expected dark
- **[F2] Column walk**: 78 scans, 64 LED mismatches; rows ok 0; cols ok 31; examples: D519 (ROW_17 x COL_07) dark, expected lit; D583 (ROW_19 x COL_07) dark, expected lit; D903 (ROW_29 x COL_07) dark, expected lit; D935 (ROW_30 x COL_07) dark, expected lit

Row chain (netlist walk): [('U_DEC_A1', 1, 'ROW_01_Y', 'R_G01', 'Q_ROW01', 'ROW_01_ANODE'), ('U_DEC_A1', 2, 'ROW_02_Y', 'R_G02', 'Q_ROW02', 'ROW_02_ANODE'), ('U_DEC_A1', 3, 'ROW_03_Y', 'R_G03', 'Q_ROW03', 'ROW_03_ANODE'), ('U_DEC_B1', 1, 'ROW_17_Y', 'R_G17', 'Q_ROW17', 'ROW_17_ANODE')]

Column chain: SDI -> U_LED1 -> U_LED2, bit c -> COL_(c+1)
