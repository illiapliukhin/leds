"""AON_3V3 In1 copper zone north of ROW_*_Y (y < 9.4 mm) + pad dogbones."""

from __future__ import annotations

import pcbnew

from generate_mono_split_boards import (
    FAN_IN_TRACK_WIDTH_MM,
    add_through_via,
    footprint_by_reference,
    get_pad,
    millimeters,
    route_net_polyline,
)
from mono_split_copper_utils import dogbone_via_candidates

AON_IN1_Y_MAX_MM = 9.35
AON_ZONE_VIA_Y_MM = 8.88
AON_STUB_W_MM = 0.25
VIA_D_MM = 0.45
AON_LOCAL_CLEARANCE_MM = 0.20
AON_ZONE_PRIORITY = 2
TRANSLATOR_AON_X_MM = 64.20
TRANSLATOR_AON_Y_MM = 10.15

U1_AON_NORTH = ("2", "3")
U1_AON_EAST = ("46", "55", "56")
U1_AON_WEST = ("20", "29")


def _aon_zone_exists(board: pcbnew.BOARD) -> bool:
    for zone in board.Zones():
        if zone.GetNetname() == "AON_3V3" and zone.GetLayer() == pcbnew.In1_Cu:
            return True
    return False


def add_aon_in1_zone(board: pcbnew.BOARD) -> bool:
    """Solid AON pour on In1 over MCU north pocket (below ROW fan-in Y)."""
    if _aon_zone_exists(board):
        return False
    aon = board.FindNet("AON_3V3")
    if aon is None or aon.GetNetCode() == 0:
        return False
    # In1 pocket: west of translator, north of y=9.70 ROW horizontals.
    outline_mm = [
        (38.80, 3.40),
        (66.80, 3.40),
        (66.80, AON_IN1_Y_MAX_MM),
        (38.80, AON_IN1_Y_MAX_MM),
    ]
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.In1_Cu)
    zone.SetNet(aon)
    zone.SetIsRuleArea(False)
    zone.SetAssignedPriority(AON_ZONE_PRIORITY)
    zone.SetLocalClearance(pcbnew.FromMM(AON_LOCAL_CLEARANCE_MM))
    zone.SetMinThickness(pcbnew.FromMM(0.25))
    outline = zone.Outline()
    outline.NewOutline()
    for x_mm, y_mm in outline_mm:
        outline.Append(pcbnew.VECTOR2I_MM(x_mm, y_mm))
    board.Add(zone)
    return True


def _via_exists(board: pcbnew.BOARD, x_mm: float, y_mm: float, net_name: str, *, tol: float = 0.05) -> bool:
    for item in board.GetTracks():
        if item.GetClass() != "PCB_VIA" or item.GetNetname() != net_name:
            continue
        pos = item.GetPosition()
        vx = pcbnew.ToMM(pos.x)
        vy = pcbnew.ToMM(pos.y)
        if abs(vx - x_mm) <= tol and abs(vy - y_mm) <= tol:
            return True
    return False


def _via_into_zone(board: pcbnew.BOARD, x_mm: float, y_mm: float) -> None:
    if _via_exists(board, x_mm, y_mm, "AON_3V3"):
        return
    aon = board.FindNet("AON_3V3")
    add_through_via(board, aon, x_mm, y_mm, diameter_mm=VIA_D_MM)


def _stub_f_to_zone_y(board: pcbnew.BOARD, x_mm: float, y_start: float, y_end: float = AON_ZONE_VIA_Y_MM) -> None:
    """Eastbound F escape then In2 drop (avoids U1 EP GND on F.Cu)."""
    bus_x = 51.55
    if _via_exists(board, bus_x, y_end, "AON_3V3"):
        return
    aon = board.FindNet("AON_3V3")
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(x_mm, y_start), (bus_x, y_start)],
        AON_STUB_W_MM,
    )
    add_through_via(board, aon, bus_x, y_start, diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(bus_x, y_start), (bus_x, y_end)],
        AON_STUB_W_MM,
    )
    _via_into_zone(board, bus_x, y_end)


def connect_u1_aon_dogbones(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    for pad_num in U1_AON_NORTH:
        pad_x, pad_y = millimeters(get_pad(u1, pad_num).GetPosition())
        _stub_f_to_zone_y(board, pad_x, pad_y)
    # Pads 20/29/46/55/56: legacy post-grid `aon` phase (F/In2 escapes).


def tie_in2_spine_to_zone(board: pcbnew.BOARD) -> None:
    """Drop from existing In2 AON spine into the In1 zone (same-net via only)."""
    _via_into_zone(board, 50.80, AON_ZONE_VIA_Y_MM)


def tie_translator_aon(board: pcbnew.BOARD) -> None:
    """Connect In1 zone to translator AON at (64.2, 10.15) via In2 (ROW horizontals on In1 @ y≈9.7)."""
    _via_into_zone(board, TRANSLATOR_AON_X_MM, AON_ZONE_VIA_Y_MM)


def connect_periphery_aon_stubs(board: pcbnew.BOARD) -> None:
    """North strap/decouple pads tie into zone after pad-20 pull (legacy `aon` phase)."""
    del board


def apply_aon_in1_zone_plan(board: pcbnew.BOARD) -> None:
    add_aon_in1_zone(board)
    connect_u1_aon_dogbones(board)
    connect_periphery_aon_stubs(board)
