"""Short locked GND/AON fanouts before grid geometry dump (stub ≤0.6 mm + via)."""

from __future__ import annotations

import pcbnew

from generate_mono_split_boards import (
    add_through_via,
    footprint_by_reference,
    get_pad,
    millimeters,
    route_net_polyline,
)
from mono_split_copper_utils import dogbone_via_candidates
from mono_split_copper_utils import GND_STITCH_TARGETS

STUB_W_MM = 0.25
VIA_D_MM = 0.45
MAX_STUB_MM = 0.55

# U1 QFN AON pads (short escape before PathFinder).
U1_AON_PADS = ("2", "3", "20", "29", "46", "55", "56")

def _lock_item(item: pcbnew.BOARD_ITEM) -> None:
    item.SetLocked(True)


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
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(from_x, from_y), (via_x, via_y)],
            STUB_W_MM,
        )
        add_through_via(board, gnd, via_x, via_y, diameter_mm=VIA_D_MM)
        _lock_tracks_at(board, via_x, via_y, "GND")
        return True


def _lock_tracks_at(board: pcbnew.BOARD, x_mm: float, y_mm: float, net_name: str) -> None:
    tol = 0.03
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
    return False


def _aon_escape_vector(pad_num: str, pad_x: float, pad_y: float) -> tuple[float, float]:
    u1_cx, u1_cy = 46.0, 10.0
    if pad_num in ("2", "3"):
        return (0.0, -MAX_STUB_MM if pad_y > u1_cy else MAX_STUB_MM)
    if pad_num in ("46", "55", "56"):
        return (MAX_STUB_MM, 0.0)
    if pad_num == "20":
        return (-MAX_STUB_MM, 0.0)
    if pad_num == "29":
        return (0.0, MAX_STUB_MM)
    dx = pad_x - u1_cx
    dy = pad_y - u1_cy
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    return (dx / length * MAX_STUB_MM, dy / length * MAX_STUB_MM)


def _fanout_u1_aon(board: pcbnew.BOARD) -> None:
    aon = board.FindNet("AON_3V3")
    if aon is None:
        return
    u1 = footprint_by_reference(board, "U1")
    for pad_num in U1_AON_PADS:
        pad = get_pad(u1, pad_num)
        pad_x, pad_y = millimeters(pad.GetPosition())
        dx, dy = _aon_escape_vector(pad_num, pad_x, pad_y)
        via_x = round(pad_x + dx, 2)
        via_y = round(pad_y + dy, 2)
        route_net_polyline(
            board,
            "AON_3V3",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (via_x, via_y)],
            STUB_W_MM,
        )
        add_through_via(board, aon, via_x, via_y, diameter_mm=VIA_D_MM)
        _lock_tracks_at(board, via_x, via_y, "AON_3V3")


def _fanout_u1_gnd(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    gnd = board.FindNet("GND")
    if gnd is None:
        return
    ep_x, ep_y = millimeters(get_pad(u1, "57").GetPosition())
    ep_offsets = (
        (-0.55, -0.55),
        (0.55, -0.55),
        (-0.55, 0.55),
        (0.55, 0.55),
    )
    for dx, dy in ep_offsets:
        via_x = round(ep_x + dx, 2)
        via_y = round(ep_y + dy, 2)
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(ep_x, ep_y), (via_x, via_y)],
            STUB_W_MM,
        )
        add_through_via(board, gnd, via_x, via_y, diameter_mm=VIA_D_MM)
        _lock_tracks_at(board, via_x, via_y, "GND")
    for pad in u1.Pads():
        if pad.GetNetname() != "GND":
            continue
        pad_num = pad.GetNumber()
        if pad_num == "57":
            continue
        pad_x, pad_y = millimeters(pad.GetPosition())
        for via_x, via_y, from_x, from_y in dogbone_via_candidates(pad_x, pad_y, stub_mm=MAX_STUB_MM):
            route_net_polyline(
                board,
                "GND",
                pcbnew.F_Cu,
                [(from_x, from_y), (via_x, via_y)],
                STUB_W_MM,
            )
            add_through_via(board, gnd, via_x, via_y, diameter_mm=VIA_D_MM)
            _lock_tracks_at(board, via_x, via_y, "GND")
            break


def _fanout_periphery_gnd(board: pcbnew.BOARD) -> None:
    for ref, pad_num in GND_STITCH_TARGETS:
        _fanout_dogbone_gnd(board, ref, pad_num)


def apply_pre_grid_power_fanout(board: pcbnew.BOARD) -> None:
    import os

    if os.environ.get("MONO_FANOUT_U1_AON", "1") == "1":
        _fanout_u1_aon(board)
    if os.environ.get("MONO_FANOUT_U1_GND", "1") == "1":
        _fanout_u1_gnd(board)
    if os.environ.get("MONO_FANOUT_PERIPHERY_GND", "1") == "1":
        _fanout_periphery_gnd(board)
