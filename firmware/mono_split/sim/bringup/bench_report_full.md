# Virtual bench report

    BENCH REPORT  mono_electronics v11c + mono_panel_32x32_full
    I2C scan       PASS  0x68 BMI270, 0x36 MAX17048 (mocked)
    All on         PASS  rows 32/32  cols 32/32  (24 scans)
    Row walk       PASS  rows 32/32  cols 32/32  (71 scans)
    Column walk    PASS  rows 32/32  cols 32/32  (71 scans)
    Checkerboard   PASS  rows 32/32  cols 32/32  (28 scans)
    [F1] All on    CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [1, 2, 3, 4, 5, 6]..
    [F1] Row walk  CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [1, 2, 3, 4, 5, 6]..
    [F2] Column walk CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [7]
    VERDICT: nominal PASS, faults all caught

## Details

- **All on**: 24 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Row walk**: 71 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Column walk**: 71 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Checkerboard**: 28 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **[F1] All on**: 28 scans, 12544 LED mismatches; rows ok 0; cols ok 0; examples: D1 (ROW_01 x COL_01) dark, expected lit; D2 (ROW_01 x COL_02) dark, expected lit; D3 (ROW_01 x COL_03) dark, expected lit; D4 (ROW_01 x COL_04) dark, expected lit
- **[F1] Row walk**: 62 scans, 3112 LED mismatches; rows ok 0; cols ok 0; examples: D380 (ROW_12 x COL_28) lit, expected dark; D381 (ROW_12 x COL_29) lit, expected dark; D361 (ROW_12 x COL_09) lit, expected dark; D362 (ROW_12 x COL_10) lit, expected dark
- **[F2] Column walk**: 71 scans, 32 LED mismatches; rows ok 0; cols ok 31; examples: D7 (ROW_01 x COL_07) dark, expected lit; D39 (ROW_02 x COL_07) dark, expected lit; D71 (ROW_03 x COL_07) dark, expected lit; D103 (ROW_04 x COL_07) dark, expected lit

Row chain (netlist walk): [('U_DEC_A1', 1, 'ROW_01_Y', 'R_G01', 'Q_ROW01', 'ROW_01_ANODE'), ('U_DEC_A1', 2, 'ROW_02_Y', 'R_G02', 'Q_ROW02', 'ROW_02_ANODE'), ('U_DEC_A1', 3, 'ROW_03_Y', 'R_G03', 'Q_ROW03', 'ROW_03_ANODE'), ('U_DEC_B1', 1, 'ROW_17_Y', 'R_G17', 'Q_ROW17', 'ROW_17_ANODE')]

Column chain: SDI -> U_LED1 -> U_LED2, bit c -> COL_(c+1)
