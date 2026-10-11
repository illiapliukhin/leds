# mono_panel_32x32_lattice — see-through LED-cube layer

Pin- and net-compatible drop-in for `mono_panel_32x32`: same two Hirose FH12-40S-0.5SH receptacles on B.Cu (LCSC C202114), same pinout (`J_ROW` pin n = `ROW_nn_ANODE`, `J_COL` pin n = `COL_nn`, pins 33–40 NC), same LED net mapping (`Dn`, n = 32(r−1)+c, pad 2 = `ROW_rr_ANODE`, pad 1 = `COL_cc`), same LED part (NationStar NCD0603W1, LCSC C84265), same cable (2 × 40P 0.5 mm FFC **Type B**, pin 1 → pin 1; checked from pad geometry by `cable.py --panel lattice`).

Everything here is generated: `gen_lattice.py` (KiCad 10 pcbnew) → `analyze.py` → `make_fab.sh` → `render_cube.py`.

## Mechanics
- FR-4, **0.8 mm**, 2 layers, 1 oz. (JLC also offers 0.6/0.4 mm; 0.8 kept for stiffness on a ~200 mm lattice. 0.6 mm works electrically.)
- Board **198.0 × 210.3 mm** including the connector tab. LED pitch **5.2 mm** in X and Y, unchanged from the 166.7 mm voxel pitch (32 × 5.2 = 166.4 mm). The frame adds the size: the side frames carry the 16 row feeds per side and the south frame carries the row and column bands.
- Lattice: horizontal (row) bars **1.0 mm**, vertical (column) bars **1.3 mm**. Windows 3.9 × 4.2 mm with R0.5 corners, 1089 internal Edge.Cuts cutouts (33 × 33: the outer ring also opens into the frame).
- **Open area: 60.6 % of the lattice field** (59.8 % per 5.2 mm cell); 42.5 % of the whole board including the solid frame and tab.
- Holes: 4 × M2.5 (2.7 mm NPTH) in the corners for stacking spacers; 4 × 2.2 mm NPTH (2 in the top frame, 2 in the bottom frame, at centre ±50 mm) for cube alignment rods / M2. For cubic voxels at 5.2 mm layer pitch, use **4.4 mm spacers** (5.2 − 0.8 board).
- Connector tab: south edge, both receptacles on B.Cu, both cables exit south (J_ROW left, J_COL right), so every layer of a stacked cube brings its FFCs out on the same side.

## LED choice: 0603 (NCD0603W1), not 0402
- Same part, Vf and brightness at 10 mA as the flat panel, so the board firmware, gamma and current settings carry over unchanged. Same JLC part, so no new BOM line.
- Side visibility in a cube: the 0603 package is 0.8 mm wide with a larger clear epoxy body than 0402, which gives more light at grazing angles when the layers are viewed edge-on.
- Cost: the vertical bar has to be 1.3 mm (0.8 mm pad + 2 × 0.25 mm copper-to-edge) instead of about 1.1 mm. That costs about 3 points of open area. 0402 would give about 63–64 %.
- Placement: the LED lies along the vertical bar, with the anode pad centred on the node and on the row bus. The cathode pad is 1.55 mm south, then a 0.3/0.5 mm via 2.6 mm below the node drops to the column bus on B.Cu.

## Routing
- F.Cu: row bus 0.5 mm on each horizontal bar. Rows 1–16 exit west and rows 17–32 exit east. They run down the side frames as 0.6 mm feeds, **twinned on B.Cu** (via at each end), then along a 16-slot 0.6 mm south row band. They drop through one via each onto a 0.2 mm B.Cu stub to the J_ROW pad. West and east bundles share slots. The side frames are planar (outermost = topmost row = bottom slot).
- B.Cu: column bus 0.4 mm on each vertical bar, then a 19-slot 0.25 mm south column band (planar left/right bundles) straight onto the J_COL pads.
- Copper to routed edge **0.25 mm** everywhere. JLC minimum is 0.20; DRC rule 0.20, and a probe at 0.26 confirms 0.25 is the true minimum.

## Row current (0.32 A) and IR drop
- IPC-2152/2221, external 1 oz, ΔT 10 °C: 0.32 A needs ≥ 0.06 mm. Every row conductor is ≥ 0.2 mm (the bars 0.5, the feeds 0.6), so current capacity is not the limit; IR drop is.
- One 0.5 mm row bus over 166 mm is 164 mΩ. With 32 equal 10.2 mA taps fed from one end, the far LED sees 26 mV.
- Worst row (row 1, longest feed): **82 mV at 20 °C** (56 mV feed + 26 mV bar), 95 mV at 60 °C copper. This meets the ≤ 0.1 V target. Without the B.Cu twin in the side frames it would be about 107 mV. Best row: 71 mV.
- Per-row effective panel resistance is in `analysis.json` (`row_R_eff_ohm`). The bring-up sim uses it for the drop readout with `--panel lattice`.

## DRC / JLC checks
- `kicad-cli pcb drc`: **0 errors, 0 warnings, 0 unconnected** (`drc_all.json`).
- Internal cutouts: smallest window 3.9 mm (JLC NPTH route min 1.0 mm), internal corner R0.5 (fits a 1.0 mm router bit), smallest web 1.0 mm, copper to cutout 0.25 mm (min 0.20). Vias 0.3/0.5 mm (JLC standard, no small-via surcharge). Min track/space 0.2/0.15 mm.
- **Routing-fee flag:** about 16.7 m of routed cutout per board, about 403 m/m². That is above JLC's 120 m/m² threshold, so expect a routing surcharge on the quote.

## Fab
`mono_panel_32x32_lattice_fab.zip`: Gerbers (Protel names, no X2), Excellon PTH/NPTH plus maps, `BOM_…_JLCPCB.csv` (NCD0603W1 × 1024 C84265, FH12-40S-0.5SH × 2 C202114), and `CPL_…csv` (LEDs Top, FFCs Bottom). The FFCs are on B.Cu: either order double-sided PCBA or hand-solder the two receptacles and assemble the top side only.

## Renders (`renders/`)
- `lattice_top.png`: KiCad top render.
- `lattice_3d_transparent.png`: KiCad perspective render, transparent background (see-through windows).
- `lattice_top_lit.png`: mock with a lit pattern. `lattice_sim_bg.png` is the bring-up sim background.
- `lattice_cube_stack_6.png`, `lattice_cube_stack_8.png`, `lattice_cube_stack_6_closeup.png`: 6 or 8 layers at 5.2 mm (cubic voxels) with a lit wave surface (PIL mock from the real geometry).

## Bring-up sim
`firmware/mono_split/sim/bringup/bringup.py --panel lattice` loads this `.kicad_pcb`. It is re-dumped to `panel_lattice.json` with `pdump.py` when the board is newer. It traces J_ROW/J_COL → LED nets the same way and shows the lattice with lit LEDs. Report: `bench_report_lattice.md`, screenshots `png/bringup_lattice_*.png`.
