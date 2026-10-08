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


def esp32_gpio_pin_map_markdown() -> str:
    return """| GPIO | QFN pad | Net | Role |
|---:|---:|---|---|
| — | 4 | `CHIP_PU` | EN (`R_CHIP_PU` / `C_CHIP_PU`) |
| 0 | 5 | `GPIO0_BOOT` | Boot strap + `SW1` |
| 8–10 | 13–15 | `IMU_SDA` / `IMU_SCL` / `IMU_INT1` | BMI270 |
| 13–16 | 18–22 | `LED_CLK` … `LED_OE_N` | MBI5124 control (via reserve) |
| 17–21,33 | 23–24,27,38 | `ROW_A0`…`ROW_A3` | Row translator A-side |
| 34–35 | 39–40 | `DEC_A_EN_N` / `DEC_B_EN_N` | 74HC154 enables |
| 36–37 | 41–42 | `LED_EN` / `LED_LOGIC_EN` | Power switches |
| 19–20 | 25–26 | `USB_D_N_MCU` / `USB_D_P_MCU` | Native USB (22 Ω) |
| 42 | 48 | `AUDIO_EN` | Audio switch |
| 47 | 37 | `ROW_XLAT_OE_N` | Translator `/OE` |
| — | 53–54 | `XTAL_P` / `XTAL_N` | 40 MHz crystal |
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


def _route_u1_elbow_to_join(
    board: pcbnew.BOARD,
    net_name: str,
    u1_pad: str,
    join_x_mm: float,
    join_y_mm: float,
    elbow_x_mm: float,
) -> None:
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, u1_pad).GetPosition())
    route_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [
            (pad_x, pad_y),
            (elbow_x_mm, pad_y),
            (elbow_x_mm, join_y_mm),
            (join_x_mm, join_y_mm),
        ],
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
        ("13", "14", "IMU_SDA", 10.35),
        ("14", "13", "IMU_SCL", 10.05),
        ("15", "4", "IMU_INT1", 9.75),
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
    _, _, footprint_by_reference, get_pad, millimeters, _, _ = _helpers()
    translator = footprint_by_reference(board, "U_ROW_XLAT")
    dec_a_x, _dec_a_y = millimeters(get_pad(translator, "7").GetPosition())
    row_joins = (
        ("ROW_A0", "23", 63.80, 18.70, 34.20),
        ("ROW_A1", "24", 64.40, 19.20, 34.75),
        ("ROW_A2", "27", 65.00, 19.70, 35.30),
        ("ROW_A3", "38", 65.60, 20.20, 35.85),
        ("DEC_A_EN_N", "39", dec_a_x, 20.80, 36.40),
        ("DEC_B_EN_N", "40", 65.20, 25.35, 36.95),
    )
    for net_name, u1_pad, join_x, join_y, elbow_x in row_joins:
        _route_u1_elbow_to_join(board, net_name, u1_pad, join_x, join_y, elbow_x)


def route_mcu_row_xlat_oe(board: pcbnew.BOARD) -> None:
    track_width, _, footprint_by_reference, get_pad, millimeters, _, route_polyline = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, "37").GetPosition())
    route_polyline(
        board,
        "ROW_XLAT_OE_N",
        pcbnew.F_Cu,
        [
            (pad_x, pad_y),
            (39.50, pad_y),
            (39.50, 2.20),
            (69.75, 2.20),
            (69.75, 3.55),
        ],
        track_width,
    )


def route_mcu_led_drops(board: pcbnew.BOARD) -> None:
    """Reuse the same reserve-drop spines as the LV125A buffer stubs."""
    _, _, footprint_by_reference, get_pad, millimeters, route_side_to_drop, _ = (
        _helpers()
    )
    u1 = footprint_by_reference(board, "U1")
    led_drops = (
        ("LED_CLK", "18", 57.00, 26.50, 32.99, 97.35),
        ("LED_SDI", "19", 58.20, 27.20, 36.80, 97.35),
        ("LED_LE", "21", 59.40, 27.90, 43.20, 97.35),
        ("LED_OE_N", "22", 60.60, 28.60, 48.20, 96.70),
    )
    for net_name, u1_pad, spine_x, via_y, drop_x, bottom_y in led_drops:
        pad_x, pad_y = millimeters(get_pad(u1, u1_pad).GetPosition())
        route_side_to_drop(
            board,
            net_name,
            pad_x,
            pad_y,
            spine_x,
            via_y,
            drop_x,
            bottom_y,
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
        ("USB_D_P_MCU", "26", "6", "R_USB_P", "USB_D_P", 12.85),
        ("USB_D_N_MCU", "25", "3", "R_USB_N", "USB_D_N", 11.25),
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
                (mcu_x - 0.55, mcu_y),
                (mcu_x - 0.55, route_y_mm),
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
    route_polyline(
        board,
        "GPIO0_BOOT",
        pcbnew.F_Cu,
        [
            (boot_x - 0.55, boot_y),
            (18.20, boot_y),
            (18.20, 82.00),
            (sw_x, 82.00),
            (sw_x, sw_y),
        ],
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
        route_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(cap_gnd_x, cap_gnd_y), (cap_gnd_x, 19.40), (32.40, 19.40)],
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


def route_mcu_enable_joins(board: pcbnew.BOARD) -> None:
    _route_u1_elbow_to_join(board, "LED_EN", "41", 25.70, 45.15, 33.50)
    _route_u1_elbow_to_join(board, "LED_LOGIC_EN", "42", 14.20, 64.60, 33.00)
    _route_u1_elbow_to_join(board, "AUDIO_EN", "48", 14.60, 72.50, 32.50)


def route_esp32_mcu(board: pcbnew.BOARD) -> None:
    route_mcu_power_stitch(board)
    route_mcu_strap_passives(board)
    route_mcu_reset_and_clock(board)
    route_usb_connector_to_esd(board)
    route_mcu_usb(board)
    route_mcu_imu_links(board)
    route_mcu_row_address_joins(board)
    route_mcu_row_xlat_oe(board)
    route_mcu_led_drops(board)
    route_mcu_enable_joins(board)
