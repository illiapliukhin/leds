# Virtual bench report

    BENCH REPORT  mono_electronics v11c + mono_panel_32x32_lattice
    I2C scan       PASS  0x68 BMI270, 0x36 MAX17048 (mocked)
    All on         PASS  rows 32/32  cols 32/32  (25 scans)
    Row walk       PASS  rows 32/32  cols 32/32  (72 scans)
    Column walk    PASS  rows 32/32  cols 32/32  (72 scans)
    Checkerboard   PASS  rows 32/32  cols 32/32  (28 scans)
    [F1] All on    CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [1, 2, 3, 4, 5, 6]..
    [F1] Row walk  CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [1, 2, 3, 4, 5, 6]..
    [F2] Column walk CAUGHT  bad rows [1, 2, 3, 4, 5, 6]..  bad cols [7]
    VERDICT: nominal PASS, faults all caught

## Details

- **All on**: 25 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Row walk**: 72 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Column walk**: 72 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **Checkerboard**: 28 scans, 0 LED mismatches; rows ok 32; cols ok 32; examples: -
- **[F1] All on**: 28 scans, 12544 LED mismatches; rows ok 0; cols ok 0; examples: D247 (ROW_08 x COL_23) dark, expected lit; D248 (ROW_08 x COL_24) dark, expected lit; D249 (ROW_08 x COL_25) dark, expected lit; D250 (ROW_08 x COL_26) dark, expected lit
- **[F1] Row walk**: 62 scans, 3064 LED mismatches; rows ok 0; cols ok 0; examples: D329 (ROW_11 x COL_09) lit, expected dark; D330 (ROW_11 x COL_10) lit, expected dark; D331 (ROW_11 x COL_11) lit, expected dark; D332 (ROW_11 x COL_12) lit, expected dark
- **[F2] Column walk**: 72 scans, 64 LED mismatches; rows ok 0; cols ok 31; examples: D7 (ROW_01 x COL_07) dark, expected lit; D39 (ROW_02 x COL_07) dark, expected lit; D71 (ROW_03 x COL_07) dark, expected lit; D103 (ROW_04 x COL_07) dark, expected lit

Row chain (netlist walk): [('U_DEC_A1', 1, 'ROW_01_Y', 'R_G01', 'Q_ROW01', 'ROW_01_ANODE'), ('U_DEC_A1', 2, 'ROW_02_Y', 'R_G02', 'Q_ROW02', 'ROW_02_ANODE'), ('U_DEC_A1', 3, 'ROW_03_Y', 'R_G03', 'Q_ROW03', 'ROW_03_ANODE'), ('U_DEC_B1', 1, 'ROW_17_Y', 'R_G17', 'Q_ROW17', 'ROW_17_ANODE')]

Column chain: SDI -> U_LED1 -> U_LED2, bit c -> COL_(c+1)
