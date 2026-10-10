"""Locked GND/AON U1 fanouts before MCU grid dump (must keep generate copper 0/0)."""

from __future__ import annotations

import math

import pcbnew

from generate_mono_split_boards import (
    FAN_IN_TRACK_WIDTH_MM,
    add_through_via,
    footprint_by_reference,
    get_pad,
    millimeters,
    route_net_polyline,
)
from mono_split_aon_in1_zone import refresh_aon_in1_zones
from mono_split_copper_utils import GND_STITCH_TARGETS, dogbone_via_candidates

STUB_W_MM = FAN_IN_TRACK_WIDTH_MM
VIA_D_MM = 0.40
MAX_STUB_MM = 0.55
VIA_CLEARANCE_MM = 0.38

# (via_x, via_y) per U1 AON pad group — tuned for 0/0 on fresh generate_electronics_board.
AON_VIA_23 = (47.85, 5.85)
AON_VIA_556 = (49.44, 6.95)
AON_VIA_20 = (41.65, 9.40)
AON_VIA_29 = (43.40, 14.35)
AON_VIA_46 = (49.44, 12.05)


def _lock_item(item: pcbnew.BOARD_ITEM) -> None:
    item.SetLocked(True)


def _lock_net_items_at(board: pcbnew.BOARD, x_mm: float, y_mm: float, net_name: str) -> None:
    tol = 0.04
    for item in board.GetTracks():
        if item.GetNetname() != net_name:
            continue
        if item.GetClass() == "PCB_VIA":
            vx, vy = millimeters(item.GetPosition())
            if abs(vx - x_mm) <= tol and abs(vy - y_mm) <= tol:
                _lock_item(item)
        elif item.GetClass() == "PCB_TRACK":
            for pt in (millimeters(item.GetStart()), millimeters(item.GetEnd())):
                if abs(pt[0] - x_mm) <= tol and abs(pt[1] - y_mm) <= tol:
                    _lock_item(item)
                    break


def _segment_distance_mm(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def via_clears_foreign_copper(
    board: pcbnew.BOARD,
    via_x: float,
    via_y: float,
    net_name: str,
    *,
    clearance_mm: float = VIA_CLEARANCE_MM,
) -> bool:
    radius = VIA_D_MM / 2.0 + clearance_mm
    for item in board.GetTracks():
        if item.GetClass() != "PCB_TRACK":
            continue
        foreign_net = item.GetNetname()
        if foreign_net == net_name or not foreign_net:
            continue
        start = millimeters(item.GetStart())
        end = millimeters(item.GetEnd())
        track_half = item.GetWidth() * 1e-6 / 2.0
        if _segment_distance_mm(via_x, via_y, start[0], start[1], end[0], end[1]) < radius + track_half:
            return False
    return True


def _place_locked_via(
    board: pcbnew.BOARD,
    net_name: str,
    points: list[tuple[float, float]],
    via_x: float,
    via_y: float,
) -> bool:
    if not via_clears_foreign_copper(board, via_x, via_y, net_name):
        return False
    net = board.FindNet(net_name)
    if net is None:
        return False
    route_net_polyline(board, net_name, pcbnew.F_Cu, points, STUB_W_MM)
    add_through_via(board, net, via_x, via_y, diameter_mm=VIA_D_MM)
    _lock_net_items_at(board, via_x, via_y, net_name)
    for pt in points:
        _lock_net_items_at(board, pt[0], pt[1], net_name)
    return True


def _fanout_u1_aon(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    pad2 = millimeters(get_pad(u1, "2").GetPosition())
    pad3 = millimeters(get_pad(u1, "3").GetPosition())
    route_net_polyline(board, "AON_3V3", pcbnew.F_Cu, [pad2, pad3], STUB_W_MM)
    _lock_net_items_at(board, pad2[0], pad2[1], "AON_3V3")
    _lock_net_items_at(board, pad3[0], pad3[1], "AON_3V3")
    vx, vy = AON_VIA_23
    _place_locked_via(
        board,
        "AON_3V3",
        [(pad3[0], pad3[1]), (vx, pad3[1]), (vx, vy)],
        vx,
        vy,
    )

    pad55 = millimeters(get_pad(u1, "55").GetPosition())
    pad56 = millimeters(get_pad(u1, "56").GetPosition())
    route_net_polyline(board, "AON_3V3", pcbnew.F_Cu, [pad55, pad56], STUB_W_MM)
    _lock_net_items_at(board, pad55[0], pad55[1], "AON_3V3")
    _lock_net_items_at(board, pad56[0], pad56[1], "AON_3V3")
    vx, vy = AON_VIA_556
    _place_locked_via(
        board,
        "AON_3V3",
        [(pad56[0], pad56[1]), (pad56[0], vy), (vx, vy)],
        vx,
        vy,
    )

    pad20 = millimeters(get_pad(u1, "20").GetPosition())
    vx, vy = AON_VIA_20
    _place_locked_via(
        board,
        "AON_3V3",
        [(pad20[0], pad20[1]), (vx, pad20[1]), (vx, vy)],
        vx,
        vy,
    )

    pad29 = millimeters(get_pad(u1, "29").GetPosition())
    vx, vy = AON_VIA_29
    _place_locked_via(
        board,
        "AON_3V3",
        [(pad29[0], pad29[1]), (pad29[0], vy)],
        vx,
        vy,
    )

    pad46 = millimeters(get_pad(u1, "46").GetPosition())
    vx, vy = AON_VIA_46
    _place_locked_via(
        board,
        "AON_3V3",
        [(pad46[0], pad46[1]), (pad46[0], vy)],
        vx,
        vy,
    )


def _fanout_dogbone_gnd(board: pcbnew.BOARD, ref: str, pad_num: str) -> bool:
    gnd = board.FindNet("GND")
    if gnd is None:
        return False
    footprint = footprint_by_reference(board, ref)
    pad = get_pad(footprint, pad_num)
    if pad.GetNetname() != "GND":
        return False
    pad_x, pad_y = millimeters(pad.GetPosition())
    for via_x, via_y, from_x, from_y in dogbone_via_candidates(pad_x, pad_y, stub_mm=MAX_STUB_MM):
        if not via_clears_foreign_copper(board, via_x, via_y, "GND"):
            continue
        if _place_locked_via(board, "GND", [(from_x, from_y), (via_x, via_y)], via_x, via_y):
            return True
    return False


def _fanout_periphery_gnd(board: pcbnew.BOARD) -> None:
    for ref, pad_num in GND_STITCH_TARGETS:
        _fanout_dogbone_gnd(board, ref, pad_num)


def _fanout_gnd_fixed_fallbacks(board: pcbnew.BOARD) -> None:
    from mono_split_copper_utils import GND_STITCH_FIXED_FALLBACK

    for (ref, pad_num), (via_x, via_y) in GND_STITCH_FIXED_FALLBACK.items():
        footprint = footprint_by_reference(board, ref)
        pad = get_pad(footprint, pad_num)
        if pad.GetNetname() != "GND":
            continue
        pad_x, pad_y = millimeters(pad.GetPosition())
        if not via_clears_foreign_copper(board, via_x, via_y, "GND"):
            continue
        _place_locked_via(board, "GND", [(pad_x, pad_y), (via_x, via_y)], via_x, via_y)


def apply_pre_grid_power_fanout(board: pcbnew.BOARD) -> None:
    import os

    if os.environ.get("MONO_FANOUT_AON_ZONE", "1") == "1":
        refresh_aon_in1_zones(board)
    if os.environ.get("MONO_FANOUT_U1_AON", "1") == "1":
        _fanout_u1_aon(board)
    if os.environ.get("MONO_FANOUT_PERIPHERY_GND", "0") == "1":
        _fanout_periphery_gnd(board)
    if os.environ.get("MONO_FANOUT_GND_FIXED", "0") == "1":
        _fanout_gnd_fixed_fallbacks(board)
