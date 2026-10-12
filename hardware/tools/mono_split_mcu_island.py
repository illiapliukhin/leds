"""MCU island routing for U1 @ (52, 94) mm, 0° — F.Cu reserve corridor @ y≈85 mm."""

from __future__ import annotations

import pcbnew

from generate_mono_split_boards import (
    FAN_IN_TRACK_WIDTH_MM,
    MCU_GND_SPINE_X_MM,
    RESERVE_BUS_Y_MM,
    add_through_via,
    footprint_by_reference,
    get_pad,
    millimeters,
    reserve_pad_x,
    route_net_polyline,
)

# Staggered eastbound bus on F.Cu (verified clear of row-anode horizontals / verticals).
MCU_CORRIDOR_Y_START_MM = 85.0
MCU_CORRIDOR_Y_STEP_MM = 0.22

MCU_USB_ESCAPE_Y_MM = 87.5
MCU_AON_SPINE_X_MM = 50.80
MCU_AON_SPINE_Y_MM = 76.00


def _corridor_y(lane_index: int) -> float:
    return round(MCU_CORRIDOR_Y_START_MM - lane_index * MCU_CORRIDOR_Y_STEP_MM, 2)


def route_mcu_island_south_stubs(board: pcbnew.BOARD) -> None:
    """Reserve tails stay at y=98 from matrix routing; no extra In1 south columns."""


def _route_f_to_reserve(
    board: pcbnew.BOARD,
    net_name: str,
    start_x: float,
    start_y: float,
    lane_index: int,
) -> None:
    reserve_x = reserve_pad_x(board, net_name)
    bus_y = _corridor_y(lane_index)
    route_net_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [
            (start_x, start_y),
            (start_x, bus_y),
            (reserve_x, bus_y),
            (reserve_x, RESERVE_BUS_Y_MM),
        ],
        FAN_IN_TRACK_WIDTH_MM,
    )


def _u1_pad_to_reserve(
    board: pcbnew.BOARD,
    net_name: str,
    u1_pad: str,
    lane_index: int,
) -> None:
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, u1_pad).GetPosition())
    _route_f_to_reserve(board, net_name, pad_x, pad_y, lane_index)


def route_mcu_power_gnd(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    c_mcu = footprint_by_reference(board, "C_MCU1")
    cap_x, cap_y = millimeters(get_pad(c_mcu, "1").GetPosition())
    aon = board.FindNet("AON_3V3")
    gnd = board.FindNet("GND")
    aon_bus_y = 86.5
    for pad_number in ("2", "3", "20", "29", "46", "55", "56"):
        pad_x, pad_y = millimeters(get_pad(u1, pad_number).GetPosition())
        add_through_via(board, aon, pad_x, pad_y, diameter_mm=0.40)
        route_net_polyline(
            board,
            "AON_3V3",
            pcbnew.In1_Cu,
            [(pad_x, pad_y), (pad_x, aon_bus_y), (cap_x, aon_bus_y), (cap_x, cap_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
    add_through_via(board, aon, cap_x, cap_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In1_Cu,
        [
            (cap_x, cap_y),
            (MCU_AON_SPINE_X_MM, cap_y),
            (MCU_AON_SPINE_X_MM, MCU_AON_SPINE_Y_MM),
        ],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, aon, MCU_AON_SPINE_X_MM, MCU_AON_SPINE_Y_MM, diameter_mm=0.40)
    ep_x, ep_y = millimeters(get_pad(u1, "57").GetPosition())
    add_through_via(board, gnd, ep_x, ep_y, diameter_mm=0.40)
    for pad_number in ("11", "32", "44", "45", "57"):
        pad_x, pad_y = millimeters(get_pad(u1, pad_number).GetPosition())
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (MCU_GND_SPINE_X_MM, pad_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, gnd, MCU_GND_SPINE_X_MM, pad_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.In1_Cu,
        [(MCU_GND_SPINE_X_MM, 88.00), (MCU_GND_SPINE_X_MM, 125.00)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, gnd, MCU_GND_SPINE_X_MM, 125.00, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.In2_Cu,
        [(MCU_GND_SPINE_X_MM, 125.00), (MCU_GND_SPINE_X_MM, 80.00)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_mcu_straps(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    r_chip = footprint_by_reference(board, "R_CHIP_PU")
    c_chip = footprint_by_reference(board, "C_CHIP_PU")
    r_boot = footprint_by_reference(board, "R_BOOT0")
    sw = footprint_by_reference(board, "SW1")
    chip_pu_x, chip_pu_y = millimeters(get_pad(u1, "4").GetPosition())
    boot_x, boot_y = millimeters(get_pad(u1, "5").GetPosition())
    r_chip_2 = millimeters(get_pad(r_chip, "2").GetPosition())
    c_chip_1 = millimeters(get_pad(c_chip, "1").GetPosition())
    r_boot_2 = millimeters(get_pad(r_boot, "2").GetPosition())
    r_boot_1 = millimeters(get_pad(r_boot, "1").GetPosition())
    r_chip_1 = millimeters(get_pad(r_chip, "1").GetPosition())
    c_chip_2 = millimeters(get_pad(c_chip, "2").GetPosition())
    sw_x, sw_y = millimeters(get_pad(sw, "1").GetPosition())
    bus_y = r_chip_2[1]
    route_net_polyline(
        board,
        "CHIP_PU",
        pcbnew.F_Cu,
        [
            (chip_pu_x, chip_pu_y),
            (chip_pu_x, bus_y),
            (r_chip_2[0], bus_y),
            (r_chip_2[0], r_chip_2[1]),
            (c_chip_1[0], c_chip_1[1]),
        ],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.F_Cu,
        [
            (boot_x, boot_y),
            (r_boot_2[0], boot_y),
            (r_boot_2[0], r_boot_2[1]),
        ],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(r_chip_1[0], r_chip_1[1]), (r_chip_1[0], r_boot_1[1]), (r_boot_1[0], r_boot_1[1])],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(c_chip_2[0], c_chip_2[1]), (MCU_GND_SPINE_X_MM, c_chip_2[1])],
        FAN_IN_TRACK_WIDTH_MM,
    )
    gnd = board.FindNet("GND")
    add_through_via(board, gnd, MCU_GND_SPINE_X_MM, c_chip_2[1], diameter_mm=0.40)
    route_net_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.F_Cu,
        [(r_boot_2[0], r_boot_2[1]), (sw_x, r_boot_2[1]), (sw_x, sw_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_mcu_xtal(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    y1 = footprint_by_reference(board, "Y1")
    xtal_p = millimeters(get_pad(u1, "54").GetPosition())
    xtal_n = millimeters(get_pad(u1, "53").GetPosition())
    cry_p = millimeters(get_pad(y1, "1").GetPosition())
    cry_n = millimeters(get_pad(y1, "3").GetPosition())
    route_net_polyline(
        board, "XTAL_P", pcbnew.F_Cu, [xtal_p, cry_p], FAN_IN_TRACK_WIDTH_MM
    )
    route_net_polyline(
        board, "XTAL_N", pcbnew.F_Cu, [xtal_n, cry_n], FAN_IN_TRACK_WIDTH_MM
    )
    cap1 = footprint_by_reference(board, "C_XTAL1")
    cap2 = footprint_by_reference(board, "C_XTAL2")
    cap1_sig = millimeters(get_pad(cap1, "1").GetPosition())
    cap2_sig = millimeters(get_pad(cap2, "1").GetPosition())
    cap1_gnd = millimeters(get_pad(cap1, "2").GetPosition())
    cap2_gnd = millimeters(get_pad(cap2, "2").GetPosition())
    gnd2 = millimeters(get_pad(y1, "2").GetPosition())
    gnd4 = millimeters(get_pad(y1, "4").GetPosition())
    route_net_polyline(
        board, "XTAL_P", pcbnew.F_Cu, [cry_p, cap1_sig], FAN_IN_TRACK_WIDTH_MM
    )
    route_net_polyline(
        board, "XTAL_N", pcbnew.F_Cu, [cry_n, cap2_sig], FAN_IN_TRACK_WIDTH_MM
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [cap1_gnd, (cap1_gnd[0], gnd2[1]), gnd2],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [cap2_gnd, (cap2_gnd[0], gnd4[1]), gnd4],
        FAN_IN_TRACK_WIDTH_MM,
    )
    gnd = board.FindNet("GND")
    add_through_via(board, gnd, gnd2[0], gnd2[1], diameter_mm=0.40)


def route_mcu_imu_local(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    imu = footprint_by_reference(board, "U_IMU")
    for u1_pad, imu_pad, net_name in (
        ("13", "14", "IMU_SDA"),
        ("14", "13", "IMU_SCL"),
        ("15", "4", "IMU_INT1"),
    ):
        start = millimeters(get_pad(u1, u1_pad).GetPosition())
        end = millimeters(get_pad(imu, imu_pad).GetPosition())
        mid_y = (start[1] + end[1]) / 2.0
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [start, (start[0], mid_y), (end[0], mid_y), end],
            FAN_IN_TRACK_WIDTH_MM,
        )


def route_mcu_usb(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    esd = footprint_by_reference(board, "U_ESD")
    for mcu_pad, esd_pad, series_ref, bus_net in (
        ("26", "6", "R_USB_P", "USB_D_P"),
        ("25", "3", "R_USB_N", "USB_D_N"),
    ):
        mcu_net = "USB_D_P_MCU" if mcu_pad == "26" else "USB_D_N_MCU"
        mcu_xy = millimeters(get_pad(u1, mcu_pad).GetPosition())
        esd_xy = millimeters(get_pad(esd, esd_pad).GetPosition())
        series = footprint_by_reference(board, series_ref)
        s_in = millimeters(get_pad(series, "1").GetPosition())
        s_out = millimeters(get_pad(series, "2").GetPosition())
        route_net_polyline(
            board,
            mcu_net,
            pcbnew.F_Cu,
            [mcu_xy, s_out],
            FAN_IN_TRACK_WIDTH_MM,
        )
        net = board.FindNet(bus_net)
        add_through_via(board, net, s_in[0], s_in[1], diameter_mm=0.40)
        route_net_polyline(
            board,
            bus_net,
            pcbnew.In2_Cu,
            [s_in, (s_in[0], esd_xy[1]), esd_xy],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, esd_xy[0], esd_xy[1], diameter_mm=0.40)


def route_mcu_signal_reserves(board: pcbnew.BOARD) -> None:
    specs = (
        ("IMU_SDA", "13"),
        ("IMU_SCL", "14"),
        ("IMU_INT1", "15"),
        ("LED_CLK", "18"),
        ("LED_SDI", "19"),
        ("LED_LE", "21"),
        ("LED_OE_N", "22"),
        ("ROW_A0", "23"),
        ("ROW_A1", "24"),
        ("ROW_A2", "27"),
        ("ROW_A3", "38"),
        ("DEC_A_EN_N", "39"),
        ("DEC_B_EN_N", "40"),
        ("ROW_XLAT_OE_N", "37"),
        ("LED_EN", "41"),
        ("LED_LOGIC_EN", "42"),
    )
    for index, (net_name, u1_pad) in enumerate(specs):
        _u1_pad_to_reserve(board, net_name, u1_pad, index)


def route_mcu_enables(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    px, py = millimeters(get_pad(u1, "48").GetPosition())
    target = footprint_by_reference(board, "U_AUDIO_SW")
    tx, ty = millimeters(get_pad(target, "3").GetPosition())
    bus_y = _corridor_y(18)
    route_net_polyline(
        board,
        "AUDIO_EN",
        pcbnew.F_Cu,
        [(px, py), (px, bus_y), (tx, bus_y), (tx, ty)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_mcu_island(board: pcbnew.BOARD) -> None:
    route_mcu_power_gnd(board)
    route_mcu_straps(board)
    route_mcu_xtal(board)
    route_mcu_usb(board)
    route_mcu_imu_local(board)
    route_mcu_signal_reserves(board)
    route_mcu_enables(board)
