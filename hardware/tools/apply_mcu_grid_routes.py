#!/usr/bin/env python3
"""Apply precomputed MCU grid routes to a .kicad_pcb (KiCad pcbnew Python)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcu_grid_route import apply_grid_routes  # noqa: E402


def main() -> None:
    board_path = Path(sys.argv[1])
    routes_path = Path(sys.argv[2])
    routes = json.load(routes_path.open())
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
    pcbnew.SaveBoard(str(board_path), board)
    print(f"applied to {board_path}")


if __name__ == "__main__":
    main()
