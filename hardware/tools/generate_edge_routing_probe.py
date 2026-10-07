from dataclasses import dataclass
from pathlib import Path

import pcbnew


@dataclass(frozen=True)
class ProbeVariant:
    board_name: str
    matrix_size: int
    board_size_mm: float
    led_pitch_mm: float


PROBE_VARIANTS = (
    ProbeVariant("wearable_20x20", 20, 49.3, 2.5),
    ProbeVariant("wearable_28x28", 28, 61.2, 2.2),
)

TRACK_WIDTH_MM = 0.1
OUTER_ROW_WIDTH_MM = 0.4
INNER_ROW_WIDTH_MM = 1.2
TRANSITION_ROW_WIDTH_MM = 0.4
STANDARD_VIA_DIAMETER_MM = 0.45
MATRIX_RGB_VIA_DIAMETER_MM = 0.4
VIA_DRILL_MM = 0.2
TRANSITION_SIDE_VIA_X_OFFSET_MM = 0.5
TRANSITION_SIDE_VIA_Y_OFFSET_MM = 0.3
TRANSITION_CROSSOVER_X_OFFSET_MM = 0.9
TRANSITION_CROSSOVER_Y_OFFSET_MM = 0.75


def add_track(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    width_mm: float = TRACK_WIDTH_MM,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetNet(net)
    track.SetLayer(layer)
    track.SetStart(pcbnew.VECTOR2I_MM(start_x_mm, start_y_mm))
    track.SetEnd(pcbnew.VECTOR2I_MM(end_x_mm, end_y_mm))
    track.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(track)


def add_through_via(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    x_mm: float,
    y_mm: float,
    diameter_mm: float = STANDARD_VIA_DIAMETER_MM,
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetNet(net)
    via.SetPosition(pcbnew.VECTOR2I_MM(x_mm, y_mm))
    via.SetWidth(pcbnew.FromMM(diameter_mm))
    via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)


def get_led(board: pcbnew.BOARD, reference: str) -> pcbnew.FOOTPRINT:
    for footprint in board.GetFootprints():
        if footprint.GetReference() == reference:
            return footprint

    raise ValueError(f"Unable to find {reference}")


def get_pad(footprint: pcbnew.FOOTPRINT, pad_number: str) -> pcbnew.PAD:
    for pad in footprint.Pads():
        if pad.GetNumber() == pad_number:
            return pad

    raise ValueError(
        f"Unable to find pad {pad_number} in {footprint.GetReference()}"
    )


def millimeters(position_internal: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position_internal.x), pcbnew.ToMM(position_internal.y)


def route_rgb_to_back(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    row_center_y_mm: float,
) -> None:
    green_pad = get_pad(footprint, "3")
    blue_pad = get_pad(footprint, "4")
    red_pad = get_pad(footprint, "2")

    green_pad_x_mm, green_pad_y_mm = millimeters(green_pad.GetPosition())
    blue_pad_x_mm, blue_pad_y_mm = millimeters(blue_pad.GetPosition())
    red_pad_x_mm, red_pad_y_mm = millimeters(red_pad.GetPosition())

    footprint_center_x_mm, _ = millimeters(footprint.GetPosition())
    green_via_x_mm = footprint_center_x_mm - 0.375
    green_via_y_mm = row_center_y_mm + 0.925
    blue_via_x_mm = footprint_center_x_mm
    blue_via_y_mm = row_center_y_mm + 1.275
    red_via_x_mm = footprint_center_x_mm + 0.375
    red_via_y_mm = row_center_y_mm + 0.925

    add_track(
        board,
        green_pad.GetNet(),
        pcbnew.F_Cu,
        green_pad_x_mm,
        green_pad_y_mm,
        green_via_x_mm,
        green_via_y_mm,
    )
    add_through_via(
        board,
        green_pad.GetNet(),
        green_via_x_mm,
        green_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )

    add_track(
        board,
        red_pad.GetNet(),
        pcbnew.F_Cu,
        red_pad_x_mm,
        red_pad_y_mm,
        red_via_x_mm,
        red_via_y_mm,
    )
    add_through_via(
        board,
        red_pad.GetNet(),
        red_via_x_mm,
        red_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )

    add_track(
        board,
        blue_pad.GetNet(),
        pcbnew.F_Cu,
        blue_pad_x_mm,
        blue_pad_y_mm,
        footprint_center_x_mm,
        row_center_y_mm,
    )
    add_track(
        board,
        blue_pad.GetNet(),
        pcbnew.F_Cu,
        footprint_center_x_mm,
        row_center_y_mm,
        blue_via_x_mm,
        blue_via_y_mm,
    )
    add_through_via(
        board,
        blue_pad.GetNet(),
        blue_via_x_mm,
        blue_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )


def route_rotated_rgb_to_back(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    row_center_y_mm: float,
) -> None:
    green_pad = get_pad(footprint, "3")
    blue_pad = get_pad(footprint, "4")
    red_pad = get_pad(footprint, "2")

    green_pad_x_mm, green_pad_y_mm = millimeters(green_pad.GetPosition())
    blue_pad_x_mm, blue_pad_y_mm = millimeters(blue_pad.GetPosition())
    red_pad_x_mm, red_pad_y_mm = millimeters(red_pad.GetPosition())

    footprint_center_x_mm, _ = millimeters(footprint.GetPosition())
    green_via_x_mm = footprint_center_x_mm + 0.375
    green_via_y_mm = row_center_y_mm - 0.925
    blue_via_x_mm = footprint_center_x_mm
    blue_via_y_mm = row_center_y_mm - 1.275
    red_via_x_mm = footprint_center_x_mm - 0.375
    red_via_y_mm = row_center_y_mm - 0.925

    add_track(
        board,
        green_pad.GetNet(),
        pcbnew.F_Cu,
        green_pad_x_mm,
        green_pad_y_mm,
        green_via_x_mm,
        green_via_y_mm,
    )
    add_through_via(
        board,
        green_pad.GetNet(),
        green_via_x_mm,
        green_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )

    add_track(
        board,
        red_pad.GetNet(),
        pcbnew.F_Cu,
        red_pad_x_mm,
        red_pad_y_mm,
        red_via_x_mm,
        red_via_y_mm,
    )
    add_through_via(
        board,
        red_pad.GetNet(),
        red_via_x_mm,
        red_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )

    add_track(
        board,
        blue_pad.GetNet(),
        pcbnew.F_Cu,
        blue_pad_x_mm,
        blue_pad_y_mm,
        footprint_center_x_mm,
        row_center_y_mm,
    )
    add_track(
        board,
        blue_pad.GetNet(),
        pcbnew.F_Cu,
        footprint_center_x_mm,
        row_center_y_mm,
        blue_via_x_mm,
        blue_via_y_mm,
    )
    add_through_via(
        board,
        blue_pad.GetNet(),
        blue_via_x_mm,
        blue_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )


def route_orientation_transition_rgb(
    board: pcbnew.BOARD,
    normal_footprint: pcbnew.FOOTPRINT,
    rotated_footprint: pcbnew.FOOTPRINT,
) -> None:
    normal_center_x_mm, normal_center_y_mm = millimeters(
        normal_footprint.GetPosition()
    )
    rotated_center_x_mm, rotated_center_y_mm = millimeters(
        rotated_footprint.GetPosition()
    )
    if abs(normal_center_x_mm - rotated_center_x_mm) > 0.001:
        raise ValueError("Transition LEDs must be in the same column")

    transition_center_y_mm = (
        normal_center_y_mm + rotated_center_y_mm
    ) / 2
    normal_via_y_mm = (
        transition_center_y_mm - TRANSITION_SIDE_VIA_Y_OFFSET_MM
    )
    rotated_via_y_mm = (
        transition_center_y_mm + TRANSITION_SIDE_VIA_Y_OFFSET_MM
    )

    normal_green_pad = get_pad(normal_footprint, "3")
    normal_red_pad = get_pad(normal_footprint, "2")
    normal_blue_pad = get_pad(normal_footprint, "4")
    rotated_green_pad = get_pad(rotated_footprint, "3")
    rotated_red_pad = get_pad(rotated_footprint, "2")
    rotated_blue_pad = get_pad(rotated_footprint, "4")

    transition_vias = (
        (
            normal_green_pad,
            normal_center_x_mm - TRANSITION_SIDE_VIA_X_OFFSET_MM,
            normal_via_y_mm,
        ),
        (
            normal_red_pad,
            normal_center_x_mm + TRANSITION_SIDE_VIA_X_OFFSET_MM,
            normal_via_y_mm,
        ),
        (
            rotated_green_pad,
            normal_center_x_mm + TRANSITION_SIDE_VIA_X_OFFSET_MM,
            rotated_via_y_mm,
        ),
        (
            rotated_red_pad,
            normal_center_x_mm - TRANSITION_SIDE_VIA_X_OFFSET_MM,
            rotated_via_y_mm,
        ),
    )
    for pad, via_x_mm, via_y_mm in transition_vias:
        pad_x_mm, pad_y_mm = millimeters(pad.GetPosition())
        add_track(
            board,
            pad.GetNet(),
            pcbnew.F_Cu,
            pad_x_mm,
            pad_y_mm,
            via_x_mm,
            via_y_mm,
        )
        add_through_via(
            board,
            pad.GetNet(),
            via_x_mm,
            via_y_mm,
            MATRIX_RGB_VIA_DIAMETER_MM,
        )

    shared_blue_via_x_mm = normal_center_x_mm
    shared_blue_via_y_mm = transition_center_y_mm
    for footprint, blue_pad in (
        (normal_footprint, normal_blue_pad),
        (rotated_footprint, rotated_blue_pad),
    ):
        pad_x_mm, pad_y_mm = millimeters(blue_pad.GetPosition())
        footprint_x_mm, footprint_y_mm = millimeters(footprint.GetPosition())
        add_track(
            board,
            blue_pad.GetNet(),
            pcbnew.F_Cu,
            pad_x_mm,
            pad_y_mm,
            footprint_x_mm,
            footprint_y_mm,
        )
        add_track(
            board,
            blue_pad.GetNet(),
            pcbnew.F_Cu,
            footprint_x_mm,
            footprint_y_mm,
            shared_blue_via_x_mm,
            shared_blue_via_y_mm,
        )

    add_through_via(
        board,
        normal_blue_pad.GetNet(),
        shared_blue_via_x_mm,
        shared_blue_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )
    add_track(
        board,
        normal_blue_pad.GetNet(),
        pcbnew.B_Cu,
        shared_blue_via_x_mm,
        shared_blue_via_y_mm,
        shared_blue_via_x_mm,
        shared_blue_via_y_mm + 0.2,
    )

    crossover_y_mm = (
        transition_center_y_mm + TRANSITION_CROSSOVER_Y_OFFSET_MM
    )
    crossover_routes = (
        (
            normal_green_pad.GetNet(),
            pcbnew.In2_Cu,
            normal_center_x_mm - TRANSITION_SIDE_VIA_X_OFFSET_MM,
            normal_center_x_mm - TRANSITION_CROSSOVER_X_OFFSET_MM,
            normal_center_x_mm + TRANSITION_SIDE_VIA_X_OFFSET_MM,
        ),
        (
            normal_red_pad.GetNet(),
            pcbnew.B_Cu,
            normal_center_x_mm + TRANSITION_SIDE_VIA_X_OFFSET_MM,
            normal_center_x_mm + TRANSITION_CROSSOVER_X_OFFSET_MM,
            normal_center_x_mm - TRANSITION_SIDE_VIA_X_OFFSET_MM,
        ),
    )
    for net, layer, start_x_mm, outside_x_mm, end_x_mm in crossover_routes:
        add_track(
            board,
            net,
            layer,
            start_x_mm,
            normal_via_y_mm,
            outside_x_mm,
            normal_via_y_mm,
        )
        add_track(
            board,
            net,
            layer,
            outside_x_mm,
            normal_via_y_mm,
            outside_x_mm,
            crossover_y_mm,
        )
        add_track(
            board,
            net,
            layer,
            outside_x_mm,
            crossover_y_mm,
            end_x_mm,
            crossover_y_mm,
        )
        add_track(
            board,
            net,
            layer,
            end_x_mm,
            crossover_y_mm,
            end_x_mm,
            rotated_via_y_mm,
        )


def route_anode(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    row_bus_y_mm: float,
    row_bus_width_mm: float,
) -> float:
    anode_pad = get_pad(footprint, "1")
    anode_pad_x_mm, anode_pad_y_mm = millimeters(anode_pad.GetPosition())
    via_x_mm = anode_pad_x_mm + 0.54
    via_y_mm = max(anode_pad_y_mm, 0.525)

    add_track(
        board,
        anode_pad.GetNet(),
        pcbnew.F_Cu,
        anode_pad_x_mm,
        anode_pad_y_mm,
        via_x_mm,
        via_y_mm,
    )
    add_through_via(board, anode_pad.GetNet(), via_x_mm, via_y_mm)
    if abs(via_y_mm - row_bus_y_mm) > 0.001:
        add_track(
            board,
            anode_pad.GetNet(),
            pcbnew.In2_Cu,
            via_x_mm,
            via_y_mm,
            via_x_mm,
            row_bus_y_mm,
            row_bus_width_mm,
        )

    return via_x_mm


def route_rotated_anode(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    row_bus_y_mm: float,
    row_bus_width_mm: float,
    maximum_via_y_mm: float,
) -> float:
    anode_pad = get_pad(footprint, "1")
    anode_pad_x_mm, anode_pad_y_mm = millimeters(anode_pad.GetPosition())
    via_x_mm = anode_pad_x_mm - 0.54
    via_y_mm = min(anode_pad_y_mm, maximum_via_y_mm)

    add_track(
        board,
        anode_pad.GetNet(),
        pcbnew.F_Cu,
        anode_pad_x_mm,
        anode_pad_y_mm,
        via_x_mm,
        via_y_mm,
    )
    add_through_via(board, anode_pad.GetNet(), via_x_mm, via_y_mm)
    if abs(via_y_mm - row_bus_y_mm) > 0.001:
        add_track(
            board,
            anode_pad.GetNet(),
            pcbnew.In2_Cu,
            via_x_mm,
            via_y_mm,
            via_x_mm,
            row_bus_y_mm,
            row_bus_width_mm,
        )

    return via_x_mm


def generate_probe(
    repository_root: Path,
    variant: ProbeVariant,
) -> Path:
    source_path = (
        repository_root
        / "hardware"
        / variant.board_name
        / f"{variant.board_name}.kicad_pcb"
    )
    output_path = (
        repository_root
        / "hardware"
        / "analysis"
        / f"{variant.board_name}_edge_routing_probe.kicad_pcb"
    )
    board = pcbnew.LoadBoard(str(source_path))

    first_row_center_y_mm = 0.9
    second_row_center_y_mm = first_row_center_y_mm + variant.led_pitch_mm
    second_column_center_x_mm = 0.9 + variant.led_pitch_mm
    second_row_first_reference = f"D{variant.matrix_size + 1}"
    second_row_second_reference = f"D{variant.matrix_size + 2}"
    routed_leds = (
        ("D1", first_row_center_y_mm, 0.525, OUTER_ROW_WIDTH_MM),
        ("D2", first_row_center_y_mm, 0.525, OUTER_ROW_WIDTH_MM),
        (
            second_row_first_reference,
            second_row_center_y_mm,
            second_row_center_y_mm,
            INNER_ROW_WIDTH_MM,
        ),
        (
            second_row_second_reference,
            second_row_center_y_mm,
            second_row_center_y_mm,
            INNER_ROW_WIDTH_MM,
        ),
    )

    row_via_extents: dict[str, list[float]] = {}
    for reference, row_center_y_mm, row_bus_y_mm, row_bus_width_mm in routed_leds:
        footprint = get_led(board, reference)
        route_rgb_to_back(board, footprint, row_center_y_mm)

        via_x_mm = route_anode(
            board,
            footprint,
            row_bus_y_mm,
            row_bus_width_mm,
        )
        row_key = str(row_center_y_mm)
        row_via_extents.setdefault(row_key, []).append(via_x_mm)

    for row_center_y_mm, row_bus_y_mm, row_bus_width_mm, row_reference in (
        (first_row_center_y_mm, 0.525, OUTER_ROW_WIDTH_MM, "D1"),
        (
            second_row_center_y_mm,
            second_row_center_y_mm,
            INNER_ROW_WIDTH_MM,
            second_row_first_reference,
        ),
    ):
        row_net = get_pad(get_led(board, row_reference), "1").GetNet()
        row_via_x_values = row_via_extents[str(row_center_y_mm)]
        add_track(
            board,
            row_net,
            pcbnew.In2_Cu,
            min(row_via_x_values),
            row_bus_y_mm,
            max(row_via_x_values),
            row_bus_y_mm,
            row_bus_width_mm,
        )

    for column_number, column_center_x_mm in (
        (1, 0.9),
        (2, second_column_center_x_mm),
    ):
        for color_name, x_offset_mm, y_offset_mm in (
            ("G", -0.375, 0.925),
            ("B", 0.0, 1.275),
            ("R", 0.375, 0.925),
        ):
            trunk_x_mm = column_center_x_mm + x_offset_mm
            start_y_mm = first_row_center_y_mm + y_offset_mm
            end_y_mm = second_row_center_y_mm + y_offset_mm
            add_track(
                board,
                board.FindNet(f"COL_{color_name}_{column_number:02d}"),
                pcbnew.B_Cu,
                trunk_x_mm,
                start_y_mm,
                trunk_x_mm,
                end_y_mm,
            )

    pcbnew.SaveBoard(str(output_path), board)
    return output_path


def generate_bottom_right_probe(
    repository_root: Path,
    variant: ProbeVariant,
) -> Path:
    source_path = (
        repository_root
        / "hardware"
        / variant.board_name
        / f"{variant.board_name}.kicad_pcb"
    )
    output_path = (
        repository_root
        / "hardware"
        / "analysis"
        / f"{variant.board_name}_bottom_right_routing_probe.kicad_pcb"
    )
    board = pcbnew.LoadBoard(str(source_path))

    second_last_row_number = variant.matrix_size - 1
    last_row_number = variant.matrix_size
    second_last_column_number = variant.matrix_size - 1
    last_column_number = variant.matrix_size
    second_last_row_center_y_mm = (
        0.9 + (second_last_row_number - 1) * variant.led_pitch_mm
    )
    last_row_center_y_mm = (
        0.9 + (last_row_number - 1) * variant.led_pitch_mm
    )
    second_last_column_center_x_mm = (
        0.9 + (second_last_column_number - 1) * variant.led_pitch_mm
    )
    last_column_center_x_mm = (
        0.9 + (last_column_number - 1) * variant.led_pitch_mm
    )

    routed_leds: list[tuple[str, float, float, float]] = []
    for row_number, row_center_y_mm, row_bus_y_mm, row_bus_width_mm in (
        (
            second_last_row_number,
            second_last_row_center_y_mm,
            second_last_row_center_y_mm,
            INNER_ROW_WIDTH_MM,
        ),
        (
            last_row_number,
            last_row_center_y_mm,
            variant.board_size_mm - 0.525,
            OUTER_ROW_WIDTH_MM,
        ),
    ):
        for column_number in (
            second_last_column_number,
            last_column_number,
        ):
            reference_number = (
                (row_number - 1) * variant.matrix_size + column_number
            )
            routed_leds.append(
                (
                    f"D{reference_number}",
                    row_center_y_mm,
                    row_bus_y_mm,
                    row_bus_width_mm,
                )
            )

    row_via_extents: dict[str, list[float]] = {}
    for reference, row_center_y_mm, row_bus_y_mm, row_bus_width_mm in routed_leds:
        footprint = get_led(board, reference)
        footprint.SetOrientationDegrees(180)
        route_rotated_rgb_to_back(board, footprint, row_center_y_mm)
        via_x_mm = route_rotated_anode(
            board,
            footprint,
            row_bus_y_mm,
            row_bus_width_mm,
            variant.board_size_mm - 0.525,
        )
        row_key = str(row_center_y_mm)
        row_via_extents.setdefault(row_key, []).append(via_x_mm)

    for row_number, row_center_y_mm, row_bus_y_mm, row_bus_width_mm in (
        (
            second_last_row_number,
            second_last_row_center_y_mm,
            second_last_row_center_y_mm,
            INNER_ROW_WIDTH_MM,
        ),
        (
            last_row_number,
            last_row_center_y_mm,
            variant.board_size_mm - 0.525,
            OUTER_ROW_WIDTH_MM,
        ),
    ):
        first_reference_number = (
            (row_number - 1) * variant.matrix_size
            + second_last_column_number
        )
        row_net = get_pad(
            get_led(board, f"D{first_reference_number}"),
            "1",
        ).GetNet()
        row_via_x_values = row_via_extents[str(row_center_y_mm)]
        add_track(
            board,
            row_net,
            pcbnew.In2_Cu,
            min(row_via_x_values),
            row_bus_y_mm,
            max(row_via_x_values),
            row_bus_y_mm,
            row_bus_width_mm,
        )

    for column_number, column_center_x_mm in (
        (second_last_column_number, second_last_column_center_x_mm),
        (last_column_number, last_column_center_x_mm),
    ):
        for color_name, x_offset_mm, y_offset_mm in (
            ("G", 0.375, -0.925),
            ("B", 0.0, -1.275),
            ("R", -0.375, -0.925),
        ):
            trunk_x_mm = column_center_x_mm + x_offset_mm
            start_y_mm = second_last_row_center_y_mm + y_offset_mm
            end_y_mm = last_row_center_y_mm + y_offset_mm
            add_track(
                board,
                board.FindNet(f"COL_{color_name}_{column_number:02d}"),
                pcbnew.B_Cu,
                trunk_x_mm,
                start_y_mm,
                trunk_x_mm,
                end_y_mm,
            )

    pcbnew.SaveBoard(str(output_path), board)
    return output_path


def generate_orientation_transition_probe(
    repository_root: Path,
    variant: ProbeVariant,
) -> Path:
    source_path = (
        repository_root
        / "hardware"
        / variant.board_name
        / f"{variant.board_name}.kicad_pcb"
    )
    output_path = (
        repository_root
        / "hardware"
        / "analysis"
        / (
            f"{variant.board_name}"
            "_orientation_transition_routing_probe.kicad_pcb"
        )
    )
    board = pcbnew.LoadBoard(str(source_path))

    normal_row_number = variant.matrix_size // 2
    rotated_row_number = normal_row_number + 1
    column_numbers = (2, 3)
    normal_row_center_y_mm = (
        0.9 + (normal_row_number - 1) * variant.led_pitch_mm
    )
    rotated_row_center_y_mm = (
        0.9 + (rotated_row_number - 1) * variant.led_pitch_mm
    )
    normal_row_via_x_values: list[float] = []
    rotated_row_via_x_values: list[float] = []

    for column_number in column_numbers:
        normal_reference_number = (
            (normal_row_number - 1) * variant.matrix_size + column_number
        )
        rotated_reference_number = (
            (rotated_row_number - 1) * variant.matrix_size + column_number
        )
        normal_footprint = get_led(board, f"D{normal_reference_number}")
        rotated_footprint = get_led(board, f"D{rotated_reference_number}")
        rotated_footprint.SetOrientationDegrees(180)

        route_orientation_transition_rgb(
            board,
            normal_footprint,
            rotated_footprint,
        )
        normal_row_via_x_values.append(
            route_anode(
                board,
                normal_footprint,
                normal_row_center_y_mm,
                TRANSITION_ROW_WIDTH_MM,
            )
        )
        rotated_row_via_x_values.append(
            route_rotated_anode(
                board,
                rotated_footprint,
                rotated_row_center_y_mm,
                TRANSITION_ROW_WIDTH_MM,
                variant.board_size_mm - 0.525,
            )
        )

    for row_number, row_center_y_mm, row_via_x_values in (
        (
            normal_row_number,
            normal_row_center_y_mm,
            normal_row_via_x_values,
        ),
        (
            rotated_row_number,
            rotated_row_center_y_mm,
            rotated_row_via_x_values,
        ),
    ):
        first_reference_number = (
            (row_number - 1) * variant.matrix_size + column_numbers[0]
        )
        row_net = get_pad(
            get_led(board, f"D{first_reference_number}"),
            "1",
        ).GetNet()
        add_track(
            board,
            row_net,
            pcbnew.In2_Cu,
            min(row_via_x_values),
            row_center_y_mm,
            max(row_via_x_values),
            row_center_y_mm,
            TRANSITION_ROW_WIDTH_MM,
        )

    pcbnew.SaveBoard(str(output_path), board)
    return output_path


if __name__ == "__main__":
    root_path = Path(__file__).resolve().parents[2]
    for probe_variant in PROBE_VARIANTS:
        generated_top_left_path = generate_probe(root_path, probe_variant)
        print(f"Generated {generated_top_left_path}")
        generated_bottom_right_path = generate_bottom_right_probe(
            root_path,
            probe_variant,
        )
        print(f"Generated {generated_bottom_right_path}")
        generated_transition_path = generate_orientation_transition_probe(
            root_path,
            probe_variant,
        )
        print(f"Generated {generated_transition_path}")
