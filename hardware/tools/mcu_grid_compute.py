#!/usr/bin/env python3
"""Compute MCU grid routes from dumped geometry (system Python + numpy/scipy)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR / "mcu_grid"))
sys.path.insert(0, str(TOOLS_DIR))

from grid import Board  # noqa: E402
from mcu_grid_constants import MCU_ROUTE_ORDER, paths_to_segments  # noqa: E402


def _prefer_pad(net_name: str) -> tuple[str, str] | None:
    if net_name == "GND":
        return ("U1", "57")
    if net_name == "AON_3V3":
        return ("U1", "46")
    if net_name == "DEC_A_EN_N":
        return ("U1", "47")
    if net_name == "GPIO0_BOOT":
        return ("U1", "5")
    if net_name == "USB_D_N_MCU":
        return ("U1", "25")
    return None


def run_greedy(
    geometry: dict,
    *,
    max_iterations: int,
    via_cost: float,
) -> tuple[dict[str, list], set[str], set[str]]:
    layer_cost = (1.0, 1.0, 1.0, 0.82)
    grid_board = Board(geometry)
    all_paths: dict[str, list] = {}
    complete: set[str] = set()
    order = [n for n in MCU_ROUTE_ORDER if n not in ("GND", "AON_3V3")]
    for pass_index in range(max_iterations):
        failed: list[str] = []
        for net_name in order:
            if net_name in complete:
                continue
            prefer = _prefer_pad(net_name)
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
            f"greedy pass {pass_index}: complete {len(complete)}, incomplete {failed}",
            flush=True,
        )
        if not failed:
            break
        skip_power = ("GND", "AON_3V3")
        order = list(
            dict.fromkeys(
                failed + [n for n in MCU_ROUTE_ORDER if n not in complete and n not in skip_power]
            )
        )
    incomplete = {n for n in MCU_ROUTE_ORDER if n not in complete and n not in ("GND", "AON_3V3")}
    return all_paths, complete, incomplete


def run_pathfinder(
    geometry: dict,
    *,
    max_rounds: int,
    via_cost: float,
) -> tuple[dict[str, list], set[str], set[str]]:
    from pathfinder import negotiate

    return negotiate(geometry, list(MCU_ROUTE_ORDER), max_rounds=max_rounds, via_cost=via_cost)


def main() -> None:
    geometry_path = Path(sys.argv[1])
    routes_path = Path(sys.argv[2])
    geometry = json.load(geometry_path.open())
    via_cost = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    max_iterations = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    use_pathfinder = os.environ.get("MONO_PATHFINDER", "1") != "0"

    if use_pathfinder:
        all_paths, complete, incomplete = run_pathfinder(
            geometry, max_rounds=max_iterations, via_cost=via_cost
        )
    else:
        all_paths, complete, incomplete = run_greedy(
            geometry, max_iterations=max_iterations, via_cost=via_cost
        )

    routed_paths = {net_name: paths for net_name, paths in all_paths.items() if net_name in complete}
    segments, vias = paths_to_segments(routed_paths)
    engine = "pathfinder" if use_pathfinder else "greedy"
    json.dump(
        {
            "segs": segments,
            "vias": vias,
            "complete_nets": sorted(complete),
            "incomplete_nets": sorted(incomplete),
            "add_gnd_mesh": False,
            "route_engine": engine,
        },
        routes_path.open("w"),
    )
    print(
        f"routes: {len(segments)} segs, {len(vias)} vias, "
        f"complete {len(complete)} / order {len(MCU_ROUTE_ORDER)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
