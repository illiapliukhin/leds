#!/usr/bin/env python3
"""Dump board geometry JSON for mcu_grid_compute (KiCad pcbnew Python)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcu_grid_route import dump_board_geometry  # noqa: E402


def main() -> None:
    board_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    board = pcbnew.LoadBoard(str(board_path))
    geometry = dump_board_geometry(board)
    json.dump(geometry, output_path.open("w"))
    print({key: len(value) for key, value in geometry.items()})


if __name__ == "__main__":
    main()
