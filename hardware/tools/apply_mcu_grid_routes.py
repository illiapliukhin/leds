#!/usr/bin/env python3
"""Apply precomputed MCU grid routes to a .kicad_pcb (KiCad pcbnew Python)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcu_grid_route import add_gnd_stitch_vias, add_mcu_gnd_pour_b_cu, apply_grid_routes  # noqa: E402


def main() -> None:
    board_path = Path(sys.argv[1])
    routes_arg = sys.argv[2]
    if routes_arg == "-":
        routes = json.load(sys.stdin)
    else:
        routes = json.load(Path(routes_arg).open())
    board = pcbnew.LoadBoard(str(board_path))
    complete_nets = set(routes.get("complete_nets") or [])
    segments = [
        segment
        for segment in routes["segs"]
        if not complete_nets or segment["net"] in complete_nets
    ]
    vias = [
        via
        for via in routes["vias"]
        if not complete_nets or via["net"] in complete_nets
    ]
    apply_grid_routes(board, segments, vias)
    if routes.get("add_gnd_mesh", True):
        add_gnd_stitch_vias(board)
        add_mcu_gnd_pour_b_cu(board)
    pcbnew.SaveBoard(str(board_path), board)
    print(f"applied to {board_path}")


if __name__ == "__main__":
    main()
