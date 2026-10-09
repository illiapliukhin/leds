#!/usr/bin/env python3
"""PathFinder-style single-net route from live board geometry (system Python)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR / "mcu_grid"))
sys.path.insert(0, str(TOOLS_DIR))

from grid import Board  # noqa: E402
from mcu_grid_constants import paths_to_segments  # noqa: E402


def prefer_pad(net_name: str) -> tuple[str, str] | None:
    mapping = {
        "GND": ("U1", "57"),
        "AON_3V3": ("U1", "46"),
        "DEC_A_EN_N": ("U1", "47"),
        "GPIO0_BOOT": ("U1", "5"),
        "USB_D_N_MCU": ("U1", "25"),
        "USB_D_P_MCU": ("U1", "26"),
        "IMU_SDA": ("U1", "13"),
        "IMU_SCL": ("U1", "14"),
        "IMU_INT1": ("U1", "15"),
        "LED_CLK": ("U1", "18"),
        "ROW_A3": ("U1", "38"),
    }
    return mapping.get(net_name)


def main() -> None:
    geometry_path = Path(sys.argv[1])
    net_name = sys.argv[2]
    geometry = json.load(geometry_path.open())
    grid_board = Board(geometry)
    if net_name not in grid_board.nid:
        json.dump({"segs": [], "vias": [], "complete_nets": [], "incomplete_nets": [net_name]}, sys.stdout)
        return
    prefer = prefer_pad(net_name)
    prefer_source = prefer if prefer and prefer in grid_board.padcells else None
    max_joins = 36 if net_name == "GND" else 28
    via_cost = 12.0 if net_name in ("GND", "AON_3V3") else 15.0
    _ok, joins_fail, paths = grid_board.route_net(
        net_name,
        viacost=via_cost,
        layercost=(1.0, 1.0, 1.0, 0.82),
        commit=True,
        prefer_comp_of=prefer_source,
        max_joins=max_joins,
    )
    complete = joins_fail == 0 and bool(paths)
    routed = {net_name: paths} if complete else {}
    segments, vias = paths_to_segments(routed)
    payload = {
        "segs": segments,
        "vias": vias,
        "complete_nets": [net_name] if complete else [],
        "incomplete_nets": [] if complete else [net_name],
        "add_gnd_mesh": False,
    }
    json.dump(payload, sys.stdout)
    print(
        f"one-net {net_name}: joins_fail={joins_fail} segs={len(segments)}",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    main()
