# mono_split manufacturing outputs

Fab packages for the three mono split boards, produced by `tools/make_fab.sh` (KiCad 10 `kicad-cli`).

## Outputs

| Board | Directory | Status |
|---|---|---|
| `mono_panel_20x20` | `output/mono_panel_20x20/` | **READY** (DRC-clean panel) |
| `mono_panel_32x32` | `output/mono_panel_32x32/` | **READY** |
| `mono_electronics` | `output/mono_electronics_NOT_READY/` | **NOT_READY** (dry run only; do not order) |

Each package contains:

- `gerbers/` — copper/mask/silk/paste (plot params from board)
- `drill/` — Excellon drills
- `positions.csv` — pick-and-place (mm)
- `bom.csv` — JLC-style BOM with LCSC where mapped
- `board.pdf`, `layers.svg` — renders
- `FAB_PACKAGE_STATUS.txt`

## Usage

```bash
source hardware/tools/kicad10_env.sh
manufacturing/mono_split/tools/make_fab.sh
# or single board:
manufacturing/mono_split/tools/make_fab.sh --boards mono_panel_20x20
```

BOM LCSC map: `tools/lcsc_bom_map.json` (extend per `DATASHEET_BOM_FREEZE.md`).

Assembly rules: `manufacturing/JLCPCB_STANDARD_PCBA_RULES.md`.
