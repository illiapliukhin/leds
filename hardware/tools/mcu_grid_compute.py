#!/usr/bin/env python3
"""Compute MCU grid routes from dumped geometry (system Python + numpy/scipy)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR / "mcu_grid"))
sys.path.insert(0, str(TOOLS_DIR))

from grid import Board  # noqa: E402
from mcu_grid_constants import MCU_ROUTE_ORDER, paths_to_segments  # noqa: E402


def main() -> None:
    geometry_path = Path(sys.argv[1])
    routes_path = Path(sys.argv[2])
    geometry = json.load(geometry_path.open())
    grid_board = Board(geometry)
    grid_board.newvias = {}
    all_paths: dict[str, list] = {}
    order = list(MCU_ROUTE_ORDER)
    via_cost = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    layer_cost = (1.0, 1.0, 1.0, 0.85)

    max_iterations = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    complete: set[str] = set()
    for pass_index in range(max_iterations):
        failed: list[str] = []
        for net_name in order:
            if net_name in complete:
                continue
            prefer = ("U1", "57") if net_name == "GND" else ("U1", "46") if net_name == "AON_3V3" else None
            prefer_source = prefer if prefer and prefer in grid_board.padcells else None
            _joins_ok, joins_fail, paths = grid_board.route_net(
                net_name,
                viacost=via_cost,
                layercost=layer_cost,
                commit=True,
                prefer_comp_of=prefer_source,
            )
            if paths:
                all_paths.setdefault(net_name, []).extend(paths)
            if joins_fail == 0:
                complete.add(net_name)
            else:
                failed.append(net_name)
        print(
            f"pass {pass_index}: complete {len(complete)}, incomplete {failed}",
            flush=True,
        )
        if not failed:
            break
        order = list(
            dict.fromkeys(failed + [n for n in MCU_ROUTE_ORDER if n not in complete])
        )

    segments, vias = paths_to_segments(all_paths)
    json.dump(
        {
            "segs": segments,
            "vias": vias,
            "complete_nets": sorted(complete),
            "incomplete_nets": sorted(set(all_paths) - complete),
        },
        routes_path.open("w"),
    )
    print(
        f"routes: {len(segments)} segs, {len(vias)} vias, "
        f"complete {len(complete)} / touched {len(all_paths)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
