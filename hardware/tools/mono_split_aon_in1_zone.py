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

AON_IN1_Y_MAX_MM = 14.85
AON_ZONE_VIA_Y_MM = 8.88
AON_STUB_W_MM = 0.25
VIA_D_MM = 0.45
AON_LOCAL_CLEARANCE_MM = 0.20
AON_ZONE_PRIORITY = 2
TRANSLATOR_AON_X_MM = 64.20
TRANSLATOR_AON_Y_MM = 10.15
AON_HUB_X_MM = 50.80
EAST_BUS_X_MM = 51.55
WEST_BUS_X_MM = 40.50
MIN_VIA_HOLE_CENTER_MM = 0.52

U1_AON_NORTH = ("2", "3")
U1_AON_EAST = ("46", "55", "56")
U1_AON_WEST = ("20", "29")

# Main north pocket + IMU north extension (bridged on In1).
MAIN_ZONE_OUTLINE_MM = [
    (36.00, 3.20),
    (67.00, 3.20),
    (67.00, AON_IN1_Y_MAX_MM),
    (36.00, AON_IN1_Y_MAX_MM),
]


def _aon_zone_exists(board: pcbnew.BOARD, *, min_y: float = 0.0) -> bool:
    for zone in list(board.Zones()):
        if zone.GetNetname() != "AON_3V3" or zone.GetLayer() != pcbnew.In1_Cu:
            continue
        outline = zone.Outline()
        if outline.OutlineCount() == 0:
            continue
        shape = outline.COutline(0)
        if shape.PointCount() == 0:
            continue
        point = shape.CPoint(0)
        if pcbnew.ToMM(point.y) >= min_y:
            return True
    return False


def _add_zone_polygon(board: pcbnew.BOARD, outline_mm: list[tuple[float, float]]) -> bool:
    aon = board.FindNet("AON_3V3")
    if aon is None or aon.GetNetCode() == 0:
        return False
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


def remove_aon_in1_zones(board: pcbnew.BOARD) -> int:
    to_remove: list = []
    for zone in list(board.Zones()):
        if zone.GetNetname() == "AON_3V3" and zone.GetLayer() == pcbnew.In1_Cu:
            to_remove.append(zone)
    for zone in to_remove:
        board.Remove(zone)
    return len(to_remove)


def add_aon_in1_zone(board: pcbnew.BOARD) -> bool:
    return _add_zone_polygon(board, MAIN_ZONE_OUTLINE_MM)


def _set_zone_outline(zone: pcbnew.ZONE, outline_mm: list[tuple[float, float]]) -> None:
    outline = zone.Outline()
    while outline.OutlineCount() > 0:
        outline.RemoveOutline(0)
    outline.NewOutline()
    for x_mm, y_mm in outline_mm:
        outline.Append(pcbnew.VECTOR2I_MM(x_mm, y_mm))


def refresh_aon_in1_zones(board: pcbnew.BOARD) -> None:
    aon_zones = [
        zone
        for zone in list(board.Zones())
        if zone.GetNetname() == "AON_3V3" and zone.GetLayer() == pcbnew.In1_Cu
    ]
    if len(aon_zones) == 1:
        _set_zone_outline(aon_zones[0], MAIN_ZONE_OUTLINE_MM)
        return
    remove_aon_in1_zones(board)
    add_aon_in1_zone(board)


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
    if y_mm > AON_IN1_Y_MAX_MM + 0.02:
        return
    if _via_exists(board, x_mm, y_mm, "AON_3V3"):
        return
    aon = board.FindNet("AON_3V3")
    add_through_via(board, aon, x_mm, y_mm, diameter_mm=VIA_D_MM)


def _drop_in2_to_zone_y(
    board: pcbnew.BOARD,
    x_mm: float,
    y_start: float,
    y_end: float = AON_ZONE_VIA_Y_MM,
) -> None:
    if abs(y_start - y_end) < 0.05:
        _via_into_zone(board, x_mm, y_end)
        return
    aon = board.FindNet("AON_3V3")
    if not _via_exists(board, x_mm, y_start, "AON_3V3"):
        add_through_via(board, aon, x_mm, y_start, diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(x_mm, y_start), (x_mm, y_end)],
        AON_STUB_W_MM,
    )
    _via_into_zone(board, x_mm, y_end)


def _north_pad_outward_to_zone(board: pcbnew.BOARD, pad_x: float, pad_y: float) -> None:
    """North-face AON: escape +X (away from EP/USB on F), same as east dogbone."""
    _east_pad_outward_to_zone(board, pad_x, pad_y)


def _east_pad_outward_to_zone(board: pcbnew.BOARD, pad_x: float, pad_y: float) -> None:
    """East-face pads: escape +X, then In2 drop into zone row at y=8.88."""
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad_x, pad_y), (EAST_BUS_X_MM, pad_y)],
        AON_STUB_W_MM,
    )
    if pad_y <= AON_IN1_Y_MAX_MM - 0.05:
        _via_into_zone(board, EAST_BUS_X_MM, pad_y)
    else:
        _drop_in2_to_zone_y(board, EAST_BUS_X_MM, pad_y)


def connect_u1_aon_dogbone_pad(board: pcbnew.BOARD, pad_num: str) -> None:
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, pad_num).GetPosition())
    if pad_num in U1_AON_NORTH:
        _north_pad_outward_to_zone(board, pad_x, pad_y)
    elif pad_num in U1_AON_EAST:
        _east_pad_outward_to_zone(board, pad_x, pad_y)


def connect_u1_aon_dogbones(board: pcbnew.BOARD) -> None:
    for pad_num in U1_AON_NORTH + U1_AON_EAST:
        connect_u1_aon_dogbone_pad(board, pad_num)


def connect_pad20_periphery(board: pcbnew.BOARD) -> None:
    """Pad 20 → R_CHIP_PU → C_MCU1, then west bus into zone at y=8.88."""
    u1 = footprint_by_reference(board, "U1")
    pad20_x, pad20_y = millimeters(get_pad(u1, "20").GetPosition())
    r_chip = footprint_by_reference(board, "R_CHIP_PU")
    pull_x, pull_y = millimeters(get_pad(r_chip, "1").GetPosition())
    cap = footprint_by_reference(board, "C_MCU1")
    cap_aon_x, cap_aon_y = millimeters(get_pad(cap, "1").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad20_x, pad20_y), (pull_x, pad20_y), (pull_x, pull_y), (cap_aon_x, cap_aon_y)],
        AON_STUB_W_MM,
    )
    stub_y = 10.60
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(cap_aon_x, cap_aon_y), (cap_aon_x, stub_y), (WEST_BUS_X_MM, stub_y)],
        AON_STUB_W_MM,
    )
    pad29_x, pad29_y = millimeters(get_pad(u1, "29").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad29_x, pad29_y), (pad29_x, stub_y), (WEST_BUS_X_MM, stub_y)],
        AON_STUB_W_MM,
    )
    _drop_in2_to_zone_y(board, WEST_BUS_X_MM, stub_y)


def tie_imu_aon_pads(board: pcbnew.BOARD) -> None:
    """IMU VDD/VDDIO pads → In1 zone row via In2 (pads at y≈5.25)."""
    imu = footprint_by_reference(board, "U_IMU")
    for pad_num in ("5", "8"):
        pad_x, pad_y = millimeters(get_pad(imu, pad_num).GetPosition())
        route_net_polyline(
            board,
            "AON_3V3",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (pad_x, 6.20)],
            AON_STUB_W_MM,
        )
        _drop_in2_to_zone_y(board, pad_x, 6.20)


def tie_translator_aon(board: pcbnew.BOARD) -> None:
    """Translator AON at y=10.15: In2 drop from zone row (avoids In1 ROW @ y≈9.7)."""
    _via_into_zone(board, TRANSLATOR_AON_X_MM, AON_ZONE_VIA_Y_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(TRANSLATOR_AON_X_MM, AON_ZONE_VIA_Y_MM), (TRANSLATOR_AON_X_MM, TRANSLATOR_AON_Y_MM)],
        AON_STUB_W_MM,
    )
    aon = board.FindNet("AON_3V3")
    if not _via_exists(board, TRANSLATOR_AON_X_MM, TRANSLATOR_AON_Y_MM, "AON_3V3"):
        add_through_via(board, aon, TRANSLATOR_AON_X_MM, TRANSLATOR_AON_Y_MM, diameter_mm=VIA_D_MM)


def tie_in2_spine_to_zone(board: pcbnew.BOARD) -> None:
    """Join legacy In2 spine at x=50.8 into zone row (single hub via)."""
    _via_into_zone(board, AON_HUB_X_MM, AON_ZONE_VIA_Y_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(AON_HUB_X_MM, AON_ZONE_VIA_Y_MM), (AON_HUB_X_MM, 9.20)],
        AON_STUB_W_MM,
    )


def dedupe_aon_hub_vias(board: pcbnew.BOARD) -> int:
    """Remove stacked AON vias closer than hole-to-hole rules (e.g. 50.8 @ 8.88 and 9.20)."""
    removed = 0
    vias = [item for item in board.GetTracks() if item.GetClass() == "PCB_VIA" and item.GetNetname() == "AON_3V3"]
    keep_at_hub = (AON_HUB_X_MM, AON_ZONE_VIA_Y_MM)
    for via in list(vias):
        pos = via.GetPosition()
        vx, vy = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
        if abs(vx - AON_HUB_X_MM) > 0.15:
            continue
        if abs(vy - AON_ZONE_VIA_Y_MM) < 0.08:
            continue
        if abs(vy - keep_at_hub[1]) < MIN_VIA_HOLE_CENTER_MM:
            board.Remove(via)
            removed += 1
    return removed


def tie_distant_aon_ldo(board: pcbnew.BOARD) -> None:
    aon = board.FindNet("AON_3V3")
    ldo = footprint_by_reference(board, "C_LDO_OUT")
    ldo_x, ldo_y = millimeters(get_pad(ldo, "1").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(ldo_x, ldo_y), (36.40, ldo_y)],
        AON_STUB_W_MM,
    )
    if not _via_exists(board, 36.40, ldo_y, "AON_3V3"):
        add_through_via(board, aon, 36.40, ldo_y, diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(36.40, ldo_y), (36.40, 56.80)],
        AON_STUB_W_MM,
    )


def tie_distant_aon_roe(board: pcbnew.BOARD) -> None:
    aon = board.FindNet("AON_3V3")
    roe = footprint_by_reference(board, "R_OE_PU")
    roe_x, roe_y = millimeters(get_pad(roe, "2").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(roe_x, roe_y), (49.49, roe_y)],
        AON_STUB_W_MM,
    )
    if not _via_exists(board, 49.49, roe_y, "AON_3V3"):
        add_through_via(board, aon, 49.49, roe_y, diameter_mm=VIA_D_MM)


def tie_distant_aon_tp(board: pcbnew.BOARD) -> None:
    aon = board.FindNet("AON_3V3")
    tp = footprint_by_reference(board, "TP1")
    tp_x, tp_y = millimeters(get_pad(tp, "1").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(tp_x, tp_y), (16.20, tp_y)],
        AON_STUB_W_MM,
    )
    if not _via_exists(board, 16.20, tp_y, "AON_3V3"):
        add_through_via(board, aon, 16.20, tp_y, diameter_mm=VIA_D_MM)


def tie_distant_aon_loads(board: pcbnew.BOARD) -> None:
    tie_distant_aon_ldo(board)
    tie_distant_aon_roe(board)
    tie_distant_aon_tp(board)


def connect_periphery_aon_stubs(board: pcbnew.BOARD) -> None:
    connect_pad20_periphery(board)


def apply_aon_in1_zone_plan(board: pcbnew.BOARD) -> None:
    add_aon_in1_zone(board)
    dedupe_aon_hub_vias(board)
    connect_u1_aon_dogbones(board)
    connect_periphery_aon_stubs(board)
    tie_in2_spine_to_zone(board)
    tie_translator_aon(board)
    dedupe_aon_hub_vias(board)
