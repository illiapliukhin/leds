from pathlib import Path

import pcbnew

from generate_edge_routing_probe import (
    INNER_ROW_WIDTH_MM,
    MATRIX_RGB_VIA_DIAMETER_MM,
    OUTER_ROW_WIDTH_MM,
    PROBE_VARIANTS,
    TRANSITION_ROW_WIDTH_MM,
    TRANSITION_SIDE_VIA_X_OFFSET_MM,
    TRANSITION_SIDE_VIA_Y_OFFSET_MM,
    ProbeVariant,
    add_track,
    add_through_via,
    get_led,
    get_pad,
    millimeters,
    route_anode,
    route_rgb_to_back,
    route_rotated_anode,
)
from generate_orientation_boundary_probes import (
    BOTTOM_LEFT_PROFILE,
    NORMAL_PROFILE,
    ROTATED_PROFILE,
    TOP_RIGHT_PROFILE,
    OrientationRoutingProfile,
    get_board_path,
    get_led_reference,
    route_edge_row_transition_rgb,
)


RgbPositionMap = dict[str, tuple[float, float]]


def get_orientation_profile(
    variant: ProbeVariant,
    row_number: int,
    column_number: int,
) -> OrientationRoutingProfile:
    upper_half = row_number <= variant.matrix_size // 2
    if upper_half and column_number >= variant.matrix_size - 1:
        return TOP_RIGHT_PROFILE
    if not upper_half and column_number <= 2:
        return BOTTOM_LEFT_PROFILE
    if upper_half:
        return NORMAL_PROFILE
    return ROTATED_PROFILE


def get_row_bus_spec(
    variant: ProbeVariant,
    row_number: int,
) -> tuple[float, float]:
    row_center_y_mm = (
        0.9 + (row_number - 1) * variant.led_pitch_mm
    )
    transition_rows = (
        variant.matrix_size // 2,
        variant.matrix_size // 2 + 1,
    )
    if row_number == 1:
        return 0.525, OUTER_ROW_WIDTH_MM
    if row_number == variant.matrix_size:
        return variant.board_size_mm - 0.525, OUTER_ROW_WIDTH_MM
    if row_number == transition_rows[0]:
        return row_center_y_mm - 0.385, TRANSITION_ROW_WIDTH_MM
    if row_number == transition_rows[1]:
        return row_center_y_mm + 0.385, TRANSITION_ROW_WIDTH_MM
    return row_center_y_mm, INNER_ROW_WIDTH_MM


def route_regular_rgb(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    profile: OrientationRoutingProfile,
    row_center_y_mm: float,
) -> None:
    footprint.SetOrientationDegrees(profile.orientation_degrees)
    route_rgb_to_back(
        board,
        footprint,
        row_center_y_mm,
        profile.side_pad_offsets,
        profile.central_pad_number,
        profile.vertical_direction,
    )


def route_profiled_anode(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    profile: OrientationRoutingProfile,
    row_bus_y_mm: float,
    row_bus_width_mm: float,
    maximum_via_y_mm: float,
) -> float:
    if profile.vertical_direction > 0:
        return route_anode(
            board,
            footprint,
            row_bus_y_mm,
            row_bus_width_mm,
            profile.anode_via_x_offset_mm,
        )
    return route_rotated_anode(
        board,
        footprint,
        row_bus_y_mm,
        row_bus_width_mm,
        maximum_via_y_mm,
        profile.anode_via_x_offset_mm,
    )


def get_regular_rgb_positions(
    footprint: pcbnew.FOOTPRINT,
    profile: OrientationRoutingProfile,
    row_center_y_mm: float,
) -> RgbPositionMap:
    footprint_center_x_mm, _ = millimeters(footprint.GetPosition())
    return {
        color_name: (
            footprint_center_x_mm + x_offset_mm,
            row_center_y_mm + y_offset_mm,
        )
        for color_name, x_offset_mm, y_offset_mm in profile.trunk_offsets
    }


def get_standard_transition_positions(
    upper_footprint: pcbnew.FOOTPRINT,
    lower_footprint: pcbnew.FOOTPRINT,
) -> tuple[RgbPositionMap, RgbPositionMap]:
    center_x_mm, upper_center_y_mm = millimeters(
        upper_footprint.GetPosition()
    )
    _, lower_center_y_mm = millimeters(lower_footprint.GetPosition())
    transition_center_y_mm = (
        upper_center_y_mm + lower_center_y_mm
    ) / 2
    lower_via_y_mm = (
        transition_center_y_mm + 0.4
    )
    upper_via_y_mm = transition_center_y_mm - 0.4
    upper_blue_position = millimeters(upper_footprint.GetPosition())
    lower_blue_position = millimeters(lower_footprint.GetPosition())
    return (
        {
            "G": (
                center_x_mm - TRANSITION_SIDE_VIA_X_OFFSET_MM,
                upper_via_y_mm,
            ),
            "R": (
                center_x_mm + TRANSITION_SIDE_VIA_X_OFFSET_MM,
                upper_via_y_mm,
            ),
            "B": upper_blue_position,
        },
        {
            "G": (
                center_x_mm + TRANSITION_SIDE_VIA_X_OFFSET_MM,
                lower_via_y_mm,
            ),
            "R": (
                center_x_mm - TRANSITION_SIDE_VIA_X_OFFSET_MM,
                lower_via_y_mm,
            ),
            "B": lower_blue_position,
        },
    )


def route_full_standard_transition_rgb(
    board: pcbnew.BOARD,
    upper_footprint: pcbnew.FOOTPRINT,
    lower_footprint: pcbnew.FOOTPRINT,
) -> None:
    center_x_mm, upper_center_y_mm = millimeters(
        upper_footprint.GetPosition()
    )
    _, lower_center_y_mm = millimeters(lower_footprint.GetPosition())
    transition_center_y_mm = (
        upper_center_y_mm + lower_center_y_mm
    ) / 2
    upper_via_y_mm = transition_center_y_mm - 0.4
    lower_via_y_mm = transition_center_y_mm + 0.4

    upper_green_pad = get_pad(upper_footprint, "3")
    upper_red_pad = get_pad(upper_footprint, "2")
    upper_blue_pad = get_pad(upper_footprint, "4")
    lower_green_pad = get_pad(lower_footprint, "3")
    lower_red_pad = get_pad(lower_footprint, "2")
    lower_blue_pad = get_pad(lower_footprint, "4")
    transition_vias = (
        (
            upper_green_pad,
            center_x_mm - 0.5,
            upper_via_y_mm,
        ),
        (
            upper_red_pad,
            center_x_mm + 0.5,
            upper_via_y_mm,
        ),
        (
            lower_green_pad,
            center_x_mm + 0.5,
            lower_via_y_mm,
        ),
        (
            lower_red_pad,
            center_x_mm - 0.5,
            lower_via_y_mm,
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

    for footprint, blue_pad in (
        (upper_footprint, upper_blue_pad),
        (lower_footprint, lower_blue_pad),
    ):
        pad_x_mm, pad_y_mm = millimeters(blue_pad.GetPosition())
        footprint_x_mm, footprint_y_mm = millimeters(
            footprint.GetPosition()
        )
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
        upper_blue_pad.GetNet(),
        pcbnew.F_Cu,
        center_x_mm,
        upper_center_y_mm,
        center_x_mm,
        lower_center_y_mm,
    )

    crossover_routes = (
        (
            upper_green_pad.GetNet(),
            pcbnew.In2_Cu,
            (
                (center_x_mm - 0.5, upper_via_y_mm),
                (center_x_mm - 0.5, transition_center_y_mm),
                (center_x_mm + 0.5, transition_center_y_mm),
                (center_x_mm + 0.5, lower_via_y_mm),
            ),
        ),
        (
            upper_red_pad.GetNet(),
            pcbnew.B_Cu,
            (
                (center_x_mm + 0.5, upper_via_y_mm),
                (center_x_mm + 0.5, transition_center_y_mm),
                (center_x_mm - 0.5, transition_center_y_mm),
                (center_x_mm - 0.5, lower_via_y_mm),
            ),
        ),
    )
    for net, layer, route_points in crossover_routes:
        for start_position, end_position in zip(
            route_points,
            route_points[1:],
        ):
            add_track(
                board,
                net,
                layer,
                start_position[0],
                start_position[1],
                end_position[0],
                end_position[1],
            )


def get_edge_transition_positions(
    upper_footprint: pcbnew.FOOTPRINT,
    lower_footprint: pcbnew.FOOTPRINT,
    top_right: bool,
) -> tuple[RgbPositionMap, RgbPositionMap]:
    center_x_mm, upper_center_y_mm = millimeters(
        upper_footprint.GetPosition()
    )
    _, lower_center_y_mm = millimeters(lower_footprint.GetPosition())
    transition_center_y_mm = (
        upper_center_y_mm + lower_center_y_mm
    ) / 2
    upper_via_y_mm = (
        transition_center_y_mm - TRANSITION_SIDE_VIA_Y_OFFSET_MM
    )
    lower_via_y_mm = (
        transition_center_y_mm + TRANSITION_SIDE_VIA_Y_OFFSET_MM
    )
    upper_central_y_mm = transition_center_y_mm - 0.2
    lower_central_y_mm = transition_center_y_mm + 0.1
    if top_right:
        return (
            {
                "G": (center_x_mm + 0.4, transition_center_y_mm),
                "B": (center_x_mm - 1.05, upper_via_y_mm),
                "R": (center_x_mm - 0.1, upper_central_y_mm),
            },
            {
                "G": (center_x_mm + 0.4, transition_center_y_mm),
                "B": (center_x_mm - 0.5, lower_central_y_mm),
                "R": (center_x_mm - 1.05, lower_via_y_mm),
            },
        )
    return (
        {
            "G": (center_x_mm - 0.4, transition_center_y_mm),
            "B": (center_x_mm + 0.1, upper_central_y_mm),
            "R": (center_x_mm + 1.05, upper_via_y_mm),
        },
        {
            "G": (center_x_mm - 0.4, transition_center_y_mm),
            "B": (center_x_mm + 1.05, lower_via_y_mm),
            "R": (center_x_mm + 0.5, lower_central_y_mm),
        },
    )


def add_rgb_connection(
    board: pcbnew.BOARD,
    column_number: int,
    color_name: str,
    start_position: tuple[float, float],
    end_position: tuple[float, float],
    layer: int = pcbnew.B_Cu,
) -> None:
    if start_position == end_position:
        return
    add_track(
        board,
        board.FindNet(f"COL_{color_name}_{column_number:02d}"),
        layer,
        start_position[0],
        start_position[1],
        end_position[0],
        end_position[1],
    )


def route_full_matrix(
    repository_root: Path,
    variant: ProbeVariant,
) -> Path:
    output_path = (
        repository_root
        / "hardware"
        / "analysis"
        / f"{variant.board_name}_full_matrix_routing.kicad_pcb"
    )
    board = pcbnew.LoadBoard(str(get_board_path(repository_root, variant)))
    upper_transition_row = variant.matrix_size // 2
    lower_transition_row = upper_transition_row + 1
    transition_positions: dict[
        int,
        tuple[RgbPositionMap, RgbPositionMap],
    ] = {}
    regular_positions: dict[
        tuple[int, int],
        RgbPositionMap,
    ] = {}
    row_via_positions: dict[int, list[float]] = {}

    for row_number in range(1, variant.matrix_size + 1):
        row_center_y_mm = (
            0.9 + (row_number - 1) * variant.led_pitch_mm
        )
        if row_number in (upper_transition_row, lower_transition_row):
            continue
        for column_number in range(1, variant.matrix_size + 1):
            footprint = get_led(
                board,
                get_led_reference(variant, row_number, column_number),
            )
            profile = get_orientation_profile(
                variant,
                row_number,
                column_number,
            )
            route_regular_rgb(
                board,
                footprint,
                profile,
                row_center_y_mm,
            )
            regular_positions[(row_number, column_number)] = (
                get_regular_rgb_positions(
                    footprint,
                    profile,
                    row_center_y_mm,
                )
            )

    for column_number in range(1, variant.matrix_size + 1):
        upper_footprint = get_led(
            board,
            get_led_reference(
                variant,
                upper_transition_row,
                column_number,
            ),
        )
        lower_footprint = get_led(
            board,
            get_led_reference(
                variant,
                lower_transition_row,
                column_number,
            ),
        )
        upper_profile = get_orientation_profile(
            variant,
            upper_transition_row,
            column_number,
        )
        lower_profile = get_orientation_profile(
            variant,
            lower_transition_row,
            column_number,
        )
        upper_footprint.SetOrientationDegrees(
            upper_profile.orientation_degrees
        )
        lower_footprint.SetOrientationDegrees(
            lower_profile.orientation_degrees
        )
        if column_number <= 2:
            route_edge_row_transition_rgb(
                board,
                upper_footprint,
                lower_footprint,
                top_right=False,
            )
            transition_positions[column_number] = (
                get_edge_transition_positions(
                    upper_footprint,
                    lower_footprint,
                    top_right=False,
                )
            )
        elif column_number >= variant.matrix_size - 1:
            route_edge_row_transition_rgb(
                board,
                upper_footprint,
                lower_footprint,
                top_right=True,
            )
            transition_positions[column_number] = (
                get_edge_transition_positions(
                    upper_footprint,
                    lower_footprint,
                    top_right=True,
                )
            )
        else:
            route_full_standard_transition_rgb(
                board,
                upper_footprint,
                lower_footprint,
            )
            transition_positions[column_number] = (
                get_standard_transition_positions(
                    upper_footprint,
                    lower_footprint,
                )
            )

    maximum_via_y_mm = variant.board_size_mm - 0.525
    for row_number in range(1, variant.matrix_size + 1):
        row_bus_y_mm, row_bus_width_mm = get_row_bus_spec(
            variant,
            row_number,
        )
        for column_number in range(1, variant.matrix_size + 1):
            footprint = get_led(
                board,
                get_led_reference(variant, row_number, column_number),
            )
            profile = get_orientation_profile(
                variant,
                row_number,
                column_number,
            )
            via_x_mm = route_profiled_anode(
                board,
                footprint,
                profile,
                row_bus_y_mm,
                row_bus_width_mm,
                maximum_via_y_mm,
            )
            row_via_positions.setdefault(row_number, []).append(via_x_mm)

        first_footprint = get_led(
            board,
            get_led_reference(variant, row_number, 1),
        )
        row_net = get_pad(first_footprint, "1").GetNet()
        add_track(
            board,
            row_net,
            pcbnew.In2_Cu,
            min(row_via_positions[row_number]),
            row_bus_y_mm,
            max(row_via_positions[row_number]),
            row_bus_y_mm,
            row_bus_width_mm,
        )

    for column_number in range(1, variant.matrix_size + 1):
        for row_number in range(1, upper_transition_row - 1):
            upper_positions = regular_positions[
                (row_number, column_number)
            ]
            lower_positions = regular_positions[
                (row_number + 1, column_number)
            ]
            for color_name in ("R", "G", "B"):
                add_rgb_connection(
                    board,
                    column_number,
                    color_name,
                    upper_positions[color_name],
                    lower_positions[color_name],
                )

        for row_number in range(
            lower_transition_row + 1,
            variant.matrix_size,
        ):
            upper_positions = regular_positions[
                (row_number, column_number)
            ]
            lower_positions = regular_positions[
                (row_number + 1, column_number)
            ]
            for color_name in ("R", "G", "B"):
                add_rgb_connection(
                    board,
                    column_number,
                    color_name,
                    upper_positions[color_name],
                    lower_positions[color_name],
                )

        upper_transition_positions, lower_transition_positions = (
            transition_positions[column_number]
        )
        upper_regular_positions = regular_positions[
            (upper_transition_row - 1, column_number)
        ]
        lower_regular_positions = regular_positions[
            (lower_transition_row + 1, column_number)
        ]
        if column_number <= 2 or column_number >= variant.matrix_size - 1:
            transition_colors = (
                ("R", pcbnew.F_Cu),
                ("G", pcbnew.B_Cu),
                ("B", pcbnew.F_Cu),
            )
        else:
            transition_colors = (
                ("R", pcbnew.B_Cu),
                ("G", pcbnew.B_Cu),
                ("B", pcbnew.F_Cu),
            )

        for color_name, layer in transition_colors:
            add_rgb_connection(
                board,
                column_number,
                color_name,
                upper_regular_positions[color_name],
                upper_transition_positions[color_name],
                layer,
            )
            add_rgb_connection(
                board,
                column_number,
                color_name,
                lower_transition_positions[color_name],
                lower_regular_positions[color_name],
                layer,
            )

    pcbnew.SaveBoard(str(output_path), board)
    return output_path


if __name__ == "__main__":
    root_path = Path(__file__).resolve().parents[2]
    for probe_variant in PROBE_VARIANTS:
        generated_path = route_full_matrix(root_path, probe_variant)
        print(f"Generated {generated_path}")
