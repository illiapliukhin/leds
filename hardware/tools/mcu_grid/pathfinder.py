"""Negotiated congestion routing (PathFinder-style history + rip-up/reroute)."""

from __future__ import annotations

import random

import numpy as np

from grid import Board, H, W, bump_hist_from_paths, track_radius  # noqa: E402

GRID_SKIP_NETS = frozenset({"GND"})
RIP_PROTECT = frozenset({"XTAL_P", "XTAL_N", "USB_D_P_MCU", "USB_D_N_MCU", "IMU_SDA", "IMU_SCL"})


def _prefer_pad(net_name: str) -> tuple[str, str] | None:
    if net_name == "AON_3V3":
        return ("U1", "46")
    return None


def _via_cost(net_name: str, base: float) -> float:
    if net_name == "AON_3V3":
        return base * 0.50
    return base


def _max_joins(net_name: str) -> int:
    if net_name == "AON_3V3":
        return 28
    return 20


def negotiate(
    geometry: dict,
    net_order: list[str],
    *,
    max_rounds: int = 32,
    via_cost: float = 15.0,
    layer_cost: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.80),
    alpha_present: float = 10.0,
    beta_history: float = 14.0,
    rng: random.Random | None = None,
) -> tuple[dict[str, list], set[str], set[str]]:
    rng = rng or random.Random(42)
    hist = np.zeros((4, H, W), np.float32)
    committed: dict[str, list] = {}
    active = [n for n in net_order if n not in GRID_SKIP_NETS]
    stale_rounds = 0

    for round_index in range(max_rounds):
        if round_index > 4 and stale_rounds >= 2 and len(committed) > 8:
            victims = [n for n in committed if n not in RIP_PROTECT]
            if victims:
                victim = rng.choice(victims)
                committed.pop(victim, None)
                print(f"pf rip victim {victim}", flush=True)

        board = Board(geometry)
        board.recommit_all(committed)
        prev_complete = sum(1 for n in active if board.is_connected(n))

        order = list(active)
        if round_index > 1:
            order = [n for n in order if not board.is_connected(n) or n not in committed]
            order += [n for n in active if n not in order]
        if round_index > 5:
            rng.shuffle(order)

        failed: list[str] = []
        for net_name in order:
            if net_name not in board.nid:
                continue
            if board.is_connected(net_name) and net_name in committed:
                continue

            board.uncommit_net(net_name)
            committed.pop(net_name, None)

            present = board.present_usage(skip_net=net_name)
            cellcost = 1.0 + alpha_present * present + beta_history * hist

            prefer = _prefer_pad(net_name)
            prefer_source = prefer if prefer and prefer in board.padcells else None
            _ok, joins_fail, paths = board.route_net(
                net_name,
                viacost=_via_cost(net_name, via_cost),
                layercost=layer_cost,
                commit=True,
                prefer_comp_of=prefer_source,
                cellcost=cellcost,
                track_r=track_radius(net_name),
                max_joins=_max_joins(net_name),
            )
            if joins_fail == 0 and paths:
                committed[net_name] = paths
            else:
                failed.append(net_name)
                board.uncommit_net(net_name)
                committed.pop(net_name, None)

        bump_hist_from_paths(hist, committed, amount=1.0 + 0.1 * round_index)

        board = Board(geometry)
        board.recommit_all(committed)
        complete = {n for n in active if n in board.nid and board.is_connected(n)}
        incomplete = {n for n in active if n in board.nid and n not in complete}
        new_complete = len(complete)
        stale_rounds = stale_rounds + 1 if new_complete <= prev_complete else 0

        print(
            f"pf round {round_index}: complete {len(complete)}/{len(active)} "
            f"pending {sorted(incomplete)}",
            flush=True,
        )
        if not incomplete:
            break

    board = Board(geometry)
    board.recommit_all(committed)
    complete = {n for n in active if n in board.nid and board.is_connected(n)}
    incomplete = {n for n in active if n in board.nid and n not in complete}
    return committed, complete, incomplete
