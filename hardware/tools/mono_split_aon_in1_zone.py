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


def _via_into_zone(board: pcbnew.BOARD, x_mm: float, y_mm: float) -> None:
    aon = board.FindNet("AON_3V3")
    add_through_via(board, aon, x_mm, y_mm, diameter_mm=VIA_D_MM)


def _stub_f_to_zone_y(board: pcbnew.BOARD, x_mm: float, y_start: float, y_end: float = AON_ZONE_VIA_Y_MM) -> None:
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(x_mm, y_start), (x_mm, y_end)],
        AON_STUB_W_MM,
    )
    _via_into_zone(board, x_mm, y_end)


def connect_u1_aon_dogbones(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    east_col_x = 50.55
    for pad_num in U1_AON_NORTH:
        pad_x, pad_y = millimeters(get_pad(u1, pad_num).GetPosition())
        _stub_f_to_zone_y(board, pad_x, pad_y)
    for pad_num in U1_AON_EAST:
        pad_x, pad_y = millimeters(get_pad(u1, pad_num).GetPosition())
        route_net_polyline(
            board,
            "AON_3V3",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (east_col_x, pad_y), (east_col_x, AON_ZONE_VIA_Y_MM)],
            AON_STUB_W_MM,
        )
        _via_into_zone(board, east_col_x, AON_ZONE_VIA_Y_MM)
    pad20_x, pad20_y = millimeters(get_pad(u1, "20").GetPosition())
    r_chip = footprint_by_reference(board, "R_CHIP_PU")
    pull_x, pull_y = millimeters(get_pad(r_chip, "1").GetPosition())
    cap_x, cap_y = millimeters(get_pad(footprint_by_reference(board, "C_MCU1"), "1").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad20_x, pad20_y), (pull_x, pad20_y), (pull_x, pull_y), (cap_x, cap_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    _via_into_zone(board, cap_x, min(cap_y + 0.45, AON_ZONE_VIA_Y_MM))
    pad29_x, pad29_y = millimeters(get_pad(u1, "29").GetPosition())
    _stub_f_to_zone_y(board, pad29_x, pad29_y)


def tie_in2_spine_to_zone(board: pcbnew.BOARD) -> None:
    """Join existing In2 AON spine (50.8, 9.2) into the In1 zone at y=8.88."""
    spine_x = 50.80
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(spine_x, 9.20), (spine_x, AON_ZONE_VIA_Y_MM)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    _via_into_zone(board, spine_x, AON_ZONE_VIA_Y_MM)


def tie_translator_aon(board: pcbnew.BOARD) -> None:
    """In2 riser to translator bus at (64.2, 10.15) — ROW lines stay at y=9.70 on In1."""
    aon = board.FindNet("AON_3V3")
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(TRANSLATOR_AON_X_MM, AON_ZONE_VIA_Y_MM), (TRANSLATOR_AON_X_MM, TRANSLATOR_AON_Y_MM)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, aon, TRANSLATOR_AON_X_MM, AON_ZONE_VIA_Y_MM, diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(50.80, TRANSLATOR_AON_Y_MM), (TRANSLATOR_AON_X_MM, TRANSLATOR_AON_Y_MM)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def connect_periphery_aon_stubs(board: pcbnew.BOARD) -> None:
    """Dogbone north decoupling / strap pads into the In1 zone."""
    targets = (
        ("R_BOOT0", "1"),
        ("R_CHIP_PU", "1"),
        ("C_CHIP_PU", "1"),
        ("C_MCU1", "1"),
    )
    for ref, pad_num in targets:
        fp = footprint_by_reference(board, ref)
        pad = get_pad(fp, pad_num)
        if pad.GetNetname() != "AON_3V3":
            continue
        pad_x, pad_y = millimeters(pad.GetPosition())
        if pad_y > AON_IN1_Y_MAX_MM + 0.5:
            continue
        for via_x, via_y, from_x, from_y in dogbone_via_candidates(pad_x, pad_y, stub_mm=0.45):
            if via_y > AON_IN1_Y_MAX_MM:
                continue
            route_net_polyline(
                board,
                "AON_3V3",
                pcbnew.F_Cu,
                [(from_x, from_y), (via_x, via_y)],
                AON_STUB_W_MM,
            )
            _via_into_zone(board, via_x, via_y)
            break


def apply_aon_in1_zone_plan(board: pcbnew.BOARD) -> None:
    add_aon_in1_zone(board)
    connect_u1_aon_dogbones(board)
    connect_periphery_aon_stubs(board)
    tie_in2_spine_to_zone(board)
    tie_translator_aon(board)
