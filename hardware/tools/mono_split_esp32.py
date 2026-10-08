"""ESP32-S3FN8 pad map and MCU routing for mono_electronics."""

from __future__ import annotations

import pcbnew


def esp32_s3_fn8_pad_nets() -> dict[str, str]:
    """Only name nets that leave the chip on this PCB. Flash/QSPI pads stay unnamed."""
    return {
        "2": "AON_3V3",
        "3": "AON_3V3",
        "4": "CHIP_PU",
        "5": "GPIO0_BOOT",
        "11": "GND",
        "13": "IMU_SDA",
        "14": "IMU_SCL",
        "15": "IMU_INT1",
        "18": "LED_CLK",
        "19": "LED_SDI",
        "20": "AON_3V3",
        "21": "LED_LE",
        "22": "LED_OE_N",
        "23": "ROW_A0",
        "24": "ROW_A1",
        "25": "USB_D_N_MCU",
        "26": "USB_D_P_MCU",
        "27": "ROW_A2",
        "29": "AON_3V3",
        "32": "GND",
        "37": "ROW_XLAT_OE_N",
        "38": "ROW_A3",
        "39": "DEC_A_EN_N",
        "40": "DEC_B_EN_N",
        "41": "LED_EN",
        "42": "LED_LOGIC_EN",
        "44": "GND",
        "45": "GND",
        "46": "AON_3V3",
        "48": "AUDIO_EN",
        "53": "XTAL_N",
        "54": "XTAL_P",
        "55": "AON_3V3",
        "56": "AON_3V3",
        "57": "GND",
    }


def esp32_s3_fn8_pad_to_gpio() -> dict[str, int | None]:
    """QFN pad number → GPIO (None = power/strap pad without GPIO number)."""
    return {
        "4": None,
        "5": 0,
        "13": 8,
        "14": 9,
        "15": 10,
        "18": 13,
        "19": 14,
        "21": 15,
        "22": 16,
        "23": 17,
        "24": 18,
        "25": 19,
        "26": 20,
        "27": 21,
        "37": 47,
        "38": 33,
        "39": 34,
        "40": 35,
        "41": 36,
        "42": 37,
        "48": 42,
    }


def esp32_gpio_pin_map_markdown() -> str:
    return """| GPIO | QFN pad | Net | Role |
|---:|---:|---|---|
| — | 4 | `CHIP_PU` | EN (`R_CHIP_PU` / `C_CHIP_PU`) |
| 0 | 5 | `GPIO0_BOOT` | Boot strap + `SW1` |
| 8 | 13 | `IMU_SDA` | BMI270 I²C |
| 9 | 14 | `IMU_SCL` | BMI270 I²C |
| 10 | 15 | `IMU_INT1` | BMI270 interrupt |
| 13–16 | 18,19,21,22 | `LED_CLK` … `LED_OE_N` | MBI5124 control (via reserve) |
| 17 | 23 | `ROW_A0` | Row address |
| 18 | 24 | `ROW_A1` | Row address |
| 21 | 27 | `ROW_A2` | Row address |
| 33 | 38 | `ROW_A3` | Row address |
| 34 | 39 | `DEC_A_EN_N` | 74HC154 A enable |
| 35 | 40 | `DEC_B_EN_N` | 74HC154 B enable |
| 36 | 41 | `LED_EN` | `TPS63802` enable |
| 37 | 42 | `LED_LOGIC_EN` | LED logic switch |
| 19 | 25 | `USB_D_N_MCU` | Native USB D− (22 Ω) |
| 20 | 26 | `USB_D_P_MCU` | Native USB D+ (22 Ω) |
| 42 | 48 | `AUDIO_EN` | Audio switch |
| 47 | 37 | `ROW_XLAT_OE_N` | Translator `/OE` |
| — | 53–54 | `XTAL_N` / `XTAL_P` | 40 MHz crystal |

**Part:** `ESP32-S3FN8` (in-package **quad** flash). `GPIO19`/`GPIO20` are USB only; row address uses `GPIO17`/`18`/`21`/`33` — no GPIO overlap. `GPIO33`–`GPIO37` are wired on FN8 but are **not** free on octal `-R8`/`-N16R8` modules; this PCB is not drop-in for those without respin/firmware remap. Straps `GPIO0`, `GPIO3`, `GPIO45`, `GPIO46` stay off functional outputs.
"""


def _helpers():
    from generate_mono_split_boards import (
        FAN_IN_TRACK_WIDTH_MM,
        add_through_via,
        footprint_by_reference,
        get_pad,
        millimeters,
        route_mcu_side_to_drop,
        route_net_polyline,
    )

    return (
        FAN_IN_TRACK_WIDTH_MM,
        add_through_via,
        footprint_by_reference,
        get_pad,
        millimeters,
        route_mcu_side_to_drop,
        route_net_polyline,
    )


def _route_u1_pad_column_to_spine(
    board: pcbnew.BOARD,
    net_name: str,
    u1_pad: str,
    join_x_mm: float,
    join_y_mm: float,
    *,
    east_offset_mm: float = 0.0,
) -> None:
    """Drop on a dedicated column, then hop to the existing decoder spine on F.Cu."""
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, u1_pad).GetPosition())
    column_x = pad_x + east_offset_mm
    route_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [
            (pad_x, pad_y),
            (column_x, pad_y),
            (column_x, join_y_mm),
            (join_x_mm, join_y_mm),
        ],
        track_width,
    )


def _route_u1_to_power_spine(
    board: pcbnew.BOARD,
    net_name: str,
    u1_pad: str,
    spine_x_mm: float,
    spine_y_mm: float,
    tap_y_mm: float,
) -> None:
    track_width, add_via, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, u1_pad).GetPosition())
    route_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [(pad_x, pad_y), (pad_x, tap_y_mm), (spine_x_mm, tap_y_mm)],
        track_width,
    )
    net = board.FindNet(net_name)
    add_via(board, net, spine_x_mm, tap_y_mm, diameter_mm=0.40)
    route_polyline(
        board,
        net_name,
        pcbnew.In2_Cu,
        [(spine_x_mm, tap_y_mm), (spine_x_mm, spine_y_mm)],
        track_width,
    )


def route_mcu_imu_links(board: pcbnew.BOARD) -> None:
    """Direct F_Cu from ESP32 to BMI270, staying above the IMU reserve fan-in."""
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    imu = footprint_by_reference(board, "U_IMU")
    for u1_pad, imu_pad, net_name, lane_y_mm in (
        ("13", "14", "IMU_SDA", 10.40),
        ("14", "13", "IMU_SCL", 10.12),
        ("15", "4", "IMU_INT1", 9.84),
    ):
        start_x, start_y = millimeters(get_pad(u1, u1_pad).GetPosition())
        end_x, end_y = millimeters(get_pad(imu, imu_pad).GetPosition())
        route_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [
                (start_x, start_y),
                (start_x, lane_y_mm),
                (end_x, lane_y_mm),
                (end_x, end_y),
            ],
            track_width,
        )


def route_mcu_row_address_joins(board: pcbnew.BOARD) -> None:
    """Tie ESP32 GPIOs to existing decoder-address spines (no second hop to U_ROW_XLAT)."""
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    translator = footprint_by_reference(board, "U_ROW_XLAT")
    dec_a_x, _dec_a_y = millimeters(get_pad(translator, "7").GetPosition())
    row_joins = (
        ("ROW_A0", "23", 63.80, 18.70, 0.0),
        ("ROW_A1", "24", 64.40, 19.20, 0.0),
        ("ROW_A2", "27", 65.00, 19.70, 0.0),
        ("ROW_A3", "38", 65.60, 20.20, 0.55),
        ("DEC_A_EN_N", "39", dec_a_x, 20.80, 1.10),
    )
    for net_name, u1_pad, join_x, join_y, east_offset in row_joins:
        _route_u1_pad_column_to_spine(
            board, net_name, u1_pad, join_x, join_y, east_offset_mm=east_offset
        )
    dec_b_pad_x, dec_b_pad_y = millimeters(get_pad(u1, "40").GetPosition())
    dec_b_col = dec_b_pad_x + 1.65
    route_polyline(
        board,
        "DEC_B_EN_N",
        pcbnew.F_Cu,
        [
            (dec_b_pad_x, dec_b_pad_y),
            (dec_b_col, dec_b_pad_y),
            (dec_b_col, 23.70),
            (65.20, 23.70),
            (65.20, 25.35),
        ],
        track_width,
    )


def route_mcu_row_xlat_oe(board: pcbnew.BOARD) -> None:
    _route_u1_pad_column_to_spine(
        board, "ROW_XLAT_OE_N", "37", 69.75, 3.55, east_offset_mm=0.55
    )


def route_mcu_led_reserves(board: pcbnew.BOARD) -> None:
    """In2 eastern spine to reserve pads (clears row fan-in / LED_SDI vs ROW_08_Y)."""
    from generate_mono_split_boards import (
        FAN_IN_TRACK_WIDTH_MM,
        add_through_via,
        footprint_by_reference,
        get_pad,
        millimeters,
        reserve_pad_x,
        route_net_polyline,
    )

    track_width = FAN_IN_TRACK_WIDTH_MM
    u1 = footprint_by_reference(board, "U1")
    hop_x = 34.00
    led_specs = (
        ("LED_CLK", "18", 120.50, 10.95, 97.35),
        ("LED_SDI", "19", 121.25, 10.35, 97.35),
        ("LED_LE", "21", 122.00, 9.75, 97.35),
        ("LED_OE_N", "22", 122.75, 9.15, 96.70),
    )
    for net_name, u1_pad, lane_x, bus_y, rail_y in led_specs:
        pad_x, pad_y = millimeters(get_pad(u1, u1_pad).GetPosition())
        reserve_x = reserve_pad_x(board, net_name)
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(pad_x, pad_y), (pad_x, bus_y), (hop_x, bus_y)],
            track_width,
        )
        net = board.FindNet(net_name)
        add_through_via(board, net, hop_x, bus_y, diameter_mm=0.40)
        route_net_polyline(
            board,
            net_name,
            pcbnew.In2_Cu,
            [
                (hop_x, bus_y),
                (lane_x, bus_y),
                (lane_x, rail_y),
                (reserve_x, rail_y),
            ],
            track_width,
        )
        add_through_via(board, net, reserve_x, rail_y, diameter_mm=0.40)
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(reserve_x, rail_y), (reserve_x, 98.00)],
            track_width,
        )


def route_usb_connector_to_esd(board: pcbnew.BOARD) -> None:
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    usb = footprint_by_reference(board, "J_USB")
    esd = footprint_by_reference(board, "U_ESD")
    for bus_net, usb_pads, esd_pad in (
        ("USB_D_P", ("A6", "B6"), "1"),
        ("USB_D_N", ("A7", "B7"), "3"),
    ):
        esd_x, esd_y = millimeters(get_pad(esd, esd_pad).GetPosition())
        usb_points = [
            millimeters(get_pad(usb, pad_name).GetPosition()) for pad_name in usb_pads
        ]
        merge_x = min(point[0] for point in usb_points) - 0.80
        merge_y = sum(point[1] for point in usb_points) / len(usb_points)
        for usb_x, usb_y in usb_points:
            route_polyline(
                board,
                bus_net,
                pcbnew.F_Cu,
                [(usb_x, usb_y), (merge_x, usb_y), (merge_x, merge_y)],
                track_width,
            )
        route_polyline(
            board,
            bus_net,
            pcbnew.F_Cu,
            [(merge_x, merge_y), (esd_x, esd_y)],
            track_width,
        )


def route_mcu_usb(board: pcbnew.BOARD) -> None:
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    esd = footprint_by_reference(board, "U_ESD")
    for mcu_net, mcu_pad, esd_pad, series_ref, bus_net, route_y_mm in (
        ("USB_D_P_MCU", "26", "6", "R_USB_P", "USB_D_P", 13.35),
        ("USB_D_N_MCU", "25", "3", "R_USB_N", "USB_D_N", 12.75),
    ):
        mcu_x, mcu_y = millimeters(get_pad(u1, mcu_pad).GetPosition())
        esd_x, esd_y = millimeters(get_pad(esd, esd_pad).GetPosition())
        series = footprint_by_reference(board, series_ref)
        series_in_x, series_in_y = millimeters(get_pad(series, "1").GetPosition())
        series_out_x, series_out_y = millimeters(get_pad(series, "2").GetPosition())
        route_polyline(
            board,
            mcu_net,
            pcbnew.F_Cu,
            [
                (mcu_x, mcu_y),
                (mcu_x, route_y_mm),
                (series_out_x, route_y_mm),
                (series_out_x, series_out_y),
            ],
            track_width,
        )
        route_polyline(
            board,
            bus_net,
            pcbnew.F_Cu,
            [(series_in_x, series_in_y), (esd_x, esd_y)],
            track_width,
        )


def route_mcu_strap_passives(board: pcbnew.BOARD) -> None:
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    chip_pu_x, chip_pu_y = millimeters(get_pad(u1, "4").GetPosition())
    boot_x, boot_y = millimeters(get_pad(u1, "5").GetPosition())
    r_chip = footprint_by_reference(board, "R_CHIP_PU")
    c_chip = footprint_by_reference(board, "C_CHIP_PU")
    r_boot = footprint_by_reference(board, "R_BOOT0")
    r_chip_pu_x, r_chip_pu_y = millimeters(get_pad(r_chip, "2").GetPosition())
    c_chip_pu_x, c_chip_pu_y = millimeters(get_pad(c_chip, "1").GetPosition())
    r_boot_boot_x, r_boot_boot_y = millimeters(get_pad(r_boot, "2").GetPosition())
    route_polyline(
        board,
        "CHIP_PU",
        pcbnew.F_Cu,
        [
            (chip_pu_x, chip_pu_y),
            (chip_pu_x - 0.55, chip_pu_y),
            (22.40, chip_pu_y),
            (22.40, r_chip_pu_y),
            (r_chip_pu_x, r_chip_pu_y),
            (c_chip_pu_x, c_chip_pu_y),
        ],
        track_width,
    )
    route_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.F_Cu,
        [
            (boot_x, boot_y),
            (boot_x - 0.55, boot_y),
            (r_boot_boot_x, boot_y),
            (r_boot_boot_x, r_boot_boot_y),
        ],
        track_width,
    )


def route_mcu_reset_and_clock(board: pcbnew.BOARD) -> None:
    track_width, add_via, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    y1 = footprint_by_reference(board, "Y1")
    sw = footprint_by_reference(board, "SW1")
    boot_x, boot_y = millimeters(get_pad(u1, "5").GetPosition())
    sw_x, sw_y = millimeters(get_pad(sw, "1").GetPosition())
    boot_net = board.FindNet("GPIO0_BOOT")
    route_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.F_Cu,
        [(boot_x - 0.55, boot_y), (15.50, boot_y)],
        track_width,
    )
    add_via(board, boot_net, 15.50, boot_y, diameter_mm=0.40)
    route_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.In2_Cu,
        [(15.50, boot_y), (15.50, 82.00)],
        track_width,
    )
    add_via(board, boot_net, 15.50, 82.00, diameter_mm=0.40)
    route_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.F_Cu,
        [(15.50, 82.00), (sw_x, 82.00), (sw_x, sw_y)],
        track_width,
    )
    xtal_p_x, xtal_p_y = millimeters(get_pad(u1, "54").GetPosition())
    xtal_n_x, xtal_n_y = millimeters(get_pad(u1, "53").GetPosition())
    cry_p_x, cry_p_y = millimeters(get_pad(y1, "1").GetPosition())
    cry_n_x, cry_n_y = millimeters(get_pad(y1, "3").GetPosition())
    route_polyline(
        board,
        "XTAL_P",
        pcbnew.F_Cu,
        [(xtal_p_x, xtal_p_y), (xtal_p_x, cry_p_y), (cry_p_x, cry_p_y)],
        track_width,
    )
    route_polyline(
        board,
        "XTAL_N",
        pcbnew.F_Cu,
        [(xtal_n_x, xtal_n_y), (xtal_n_x, cry_n_y), (cry_n_x, cry_n_y)],
        track_width,
    )
    for net_name, cap_ref, cry_pad in (
        ("XTAL_P", "C_XTAL1", "1"),
        ("XTAL_N", "C_XTAL2", "3"),
    ):
        cap = footprint_by_reference(board, cap_ref)
        cap_signal_x, cap_signal_y = millimeters(get_pad(cap, "1").GetPosition())
        cap_gnd_x, cap_gnd_y = millimeters(get_pad(cap, "2").GetPosition())
        cry_x, cry_y = millimeters(get_pad(y1, cry_pad).GetPosition())
        route_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(cry_x, cry_y), (cap_signal_x, cap_signal_y)],
            track_width,
        )
        y1 = footprint_by_reference(board, "Y1")
        gnd_x, gnd_y = millimeters(get_pad(y1, "2").GetPosition())
        route_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(cap_gnd_x, cap_gnd_y), (gnd_x, cap_gnd_y), (gnd_x, gnd_y)],
            track_width,
        )


def route_mcu_power_stitch(board: pcbnew.BOARD) -> None:
    track_width, add_via, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    decouple = footprint_by_reference(board, "C_MCU1")
    cap_x, cap_y = millimeters(get_pad(decouple, "1").GetPosition())
    for pad_number in ("2", "3"):
        pad_x, pad_y = millimeters(get_pad(u1, pad_number).GetPosition())
        route_polyline(
            board,
            "AON_3V3",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (cap_x, pad_y), (cap_x, cap_y)],
            track_width,
        )
    gnd = board.FindNet("GND")
    ep_x, ep_y = millimeters(get_pad(u1, "57").GetPosition())
    add_via(board, gnd, ep_x + 0.55, ep_y, diameter_mm=0.40)


def route_mcu_strap_power_gnd(board: pcbnew.BOARD) -> None:
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    r_boot = footprint_by_reference(board, "R_BOOT0")
    r_chip = footprint_by_reference(board, "R_CHIP_PU")
    c_chip = footprint_by_reference(board, "C_CHIP_PU")
    aon_x, aon_y = millimeters(get_pad(r_boot, "1").GetPosition())
    aon_pull_x, aon_pull_y = millimeters(get_pad(r_chip, "1").GetPosition())
    gnd_x, gnd_y = millimeters(get_pad(c_chip, "2").GetPosition())
    route_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(aon_pull_x, aon_pull_y), (22.40, aon_pull_y), (22.40, aon_y), (aon_x, aon_y)],
        track_width,
    )
    route_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(gnd_x, gnd_y), (22.40, gnd_y), (22.40, 23.80), (24.71, 23.80)],
        track_width,
    )


def route_mcu_enable_joins(board: pcbnew.BOARD) -> None:
    _route_u1_to_power_spine(board, "LED_EN", "41", 25.70, 45.15, 9.60)
    _route_u1_to_power_spine(board, "LED_LOGIC_EN", "42", 14.20, 64.60, 9.20)
    _route_u1_to_power_spine(board, "AUDIO_EN", "48", 14.60, 72.50, 8.80)


def route_esp32_mcu(board: pcbnew.BOARD) -> None:
    route_mcu_power_stitch(board)
    route_mcu_strap_passives(board)
    route_mcu_strap_power_gnd(board)
    route_mcu_reset_and_clock(board)
    route_usb_connector_to_esd(board)
    route_mcu_usb(board)
    route_mcu_imu_links(board)
    route_mcu_row_address_joins(board)
    route_mcu_row_xlat_oe(board)
    route_mcu_led_reserves(board)
    route_mcu_enable_joins(board)
