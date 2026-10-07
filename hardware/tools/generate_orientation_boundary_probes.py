from dataclasses import dataclass
from pathlib import Path

import pcbnew

from generate_board_skeletons import (
    assign_deterministic_board_uuids,
    create_board,
    get_board_variant,
)
from generate_edge_routing_probe import (
    INNER_ROW_WIDTH_MM,
    MATRIX_RGB_VIA_DIAMETER_MM,
    OUTER_ROW_WIDTH_MM,
    PROBE_VARIANTS,
    TRANSITION_ROW_WIDTH_MM,
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


BOUNDARY_ANODE_VIA_X_OFFSET_MM = 0.45


@dataclass(frozen=True)
class OrientationRoutingProfile:
    orientation_degrees: int
    side_pad_offsets: tuple[tuple[str, float], ...]
    central_pad_number: str
    vertical_direction: float
    anode_via_x_offset_mm: float
    trunk_offsets: tuple[tuple[str, float, float], ...]


NORMAL_PROFILE = OrientationRoutingProfile(
    orientation_degrees=0,
    side_pad_offsets=(("3", -0.375), ("2", 0.375)),
    central_pad_number="4",
    vertical_direction=1.0,
    anode_via_x_offset_mm=BOUNDARY_ANODE_VIA_X_OFFSET_MM,
    trunk_offsets=(
        ("G", -0.375, 0.925),
        ("B", 0.0, 1.275),
        ("R", 0.375, 0.925),
    ),
)

TOP_RIGHT_PROFILE = OrientationRoutingProfile(
    orientation_degrees=90,
    side_pad_offsets=(("3", 0.375), ("4", -0.375)),
    central_pad_number="2",
    vertical_direction=1.0,
    anode_via_x_offset_mm=-BOUNDARY_ANODE_VIA_X_OFFSET_MM,
    trunk_offsets=(
        ("G", 0.375, 0.925),
        ("B", -0.375, 0.925),
        ("R", 0.0, 1.275),
    ),
)

ROTATED_PROFILE = OrientationRoutingProfile(
    orientation_degrees=180,
    side_pad_offsets=(("3", 0.375), ("2", -0.375)),
    central_pad_number="4",
    vertical_direction=-1.0,
    anode_via_x_offset_mm=-BOUNDARY_ANODE_VIA_X_OFFSET_MM,
    trunk_offsets=(
        ("G", 0.375, -0.925),
        ("B", 0.0, -1.275),
        ("R", -0.375, -0.925),
    ),
)

BOTTOM_LEFT_PROFILE = OrientationRoutingProfile(
    orientation_degrees=270,
    side_pad_offsets=(("3", -0.375), ("4", 0.375)),
    central_pad_number="2",
    vertical_direction=-1.0,
    anode_via_x_offset_mm=BOUNDARY_ANODE_VIA_X_OFFSET_MM,
    trunk_offsets=(
        ("G", -0.375, -0.925),
        ("B", 0.375, -0.925),
        ("R", 0.0, -1.275),
    ),
)


def create_skeleton_board(
    repository_root: Path,
    variant: ProbeVariant,
) -> pcbnew.BOARD:
    board_variant = get_board_variant(variant.board_name)
    return create_board(repository_root, board_variant)


def get_led_reference(
    variant: ProbeVariant,
    row_number: int,
    column_number: int,
) -> str:
    reference_number = (
        (row_number - 1) * variant.matrix_size + column_number
    )
    return f"D{reference_number}"


def route_profiled_led(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    profile: OrientationRoutingProfile,
    row_center_y_mm: float,
    row_bus_y_mm: float,
    row_bus_width_mm: float,
    maximum_via_y_mm: float,
) -> float:
    footprint.SetOrientationDegrees(profile.orientation_degrees)
    route_rgb_to_back(
        board,
        footprint,
        row_center_y_mm,
        profile.side_pad_offsets,
        profile.central_pad_number,
        profile.vertical_direction,
    )

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


def generate_column_boundary_probe(
    repository_root: Path,
    variant: ProbeVariant,
    top_right: bool,
) -> Path:
    boundary_name = "top_right" if top_right else "bottom_left"
    output_path = (
        repository_root
        / "hardware"
        / "analysis"
        / (
            f"{variant.board_name}_{boundary_name}"
            "_column_boundary_routing_probe.kicad_pcb"
        )
    )
    board = create_skeleton_board(repository_root, variant)

    if top_right:
        row_numbers = (1, 2)
        column_profiles = (
            (variant.matrix_size - 2, NORMAL_PROFILE),
            (variant.matrix_size - 1, TOP_RIGHT_PROFILE),
        )
        row_bus_specs = (
            (0.525, OUTER_ROW_WIDTH_MM),
            (0.9 + variant.led_pitch_mm, INNER_ROW_WIDTH_MM),
        )
    else:
        row_numbers = (variant.matrix_size - 1, variant.matrix_size)
        column_profiles = (
            (1, BOTTOM_LEFT_PROFILE),
            (2, ROTATED_PROFILE),
        )
        second_last_row_center_y_mm = (
            0.9 + (row_numbers[0] - 1) * variant.led_pitch_mm
        )
        row_bus_specs = (
            (second_last_row_center_y_mm, INNER_ROW_WIDTH_MM),
            (variant.board_size_mm - 0.525, OUTER_ROW_WIDTH_MM),
        )

    row_center_y_values = tuple(
        0.9 + (row_number - 1) * variant.led_pitch_mm
        for row_number in row_numbers
    )
    row_via_extents: dict[int, list[float]] = {}
    for row_number, row_center_y_mm, row_bus_spec in zip(
        row_numbers,
        row_center_y_values,
        row_bus_specs,
        strict=True,
    ):
        row_bus_y_mm, row_bus_width_mm = row_bus_spec
        for column_number, profile in column_profiles:
            footprint = get_led(
                board,
                get_led_reference(variant, row_number, column_number),
            )
            via_x_mm = route_profiled_led(
                board,
                footprint,
                profile,
                row_center_y_mm,
                row_bus_y_mm,
                row_bus_width_mm,
                variant.board_size_mm - 0.525,
            )
            row_via_extents.setdefault(row_number, []).append(via_x_mm)

    for row_number, row_bus_spec in zip(
        row_numbers,
        row_bus_specs,
        strict=True,
    ):
        row_bus_y_mm, row_bus_width_mm = row_bus_spec
        first_column_number = column_profiles[0][0]
        row_net = get_pad(
            get_led(
                board,
                get_led_reference(
                    variant,
                    row_number,
                    first_column_number,
                ),
            ),
            "1",
        ).GetNet()
        row_via_x_values = row_via_extents[row_number]
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

    for column_number, profile in column_profiles:
        column_center_x_mm = (
            0.9 + (column_number - 1) * variant.led_pitch_mm
        )
        for color_name, x_offset_mm, y_offset_mm in profile.trunk_offsets:
            trunk_x_mm = column_center_x_mm + x_offset_mm
            add_track(
                board,
                board.FindNet(f"COL_{color_name}_{column_number:02d}"),
                pcbnew.B_Cu,
                trunk_x_mm,
                row_center_y_values[0] + y_offset_mm,
                trunk_x_mm,
                row_center_y_values[1] + y_offset_mm,
            )

    assign_deterministic_board_uuids(
        board,
        f"orientation-probe:{output_path.stem}",
    )
    pcbnew.SaveBoard(str(output_path), board)
    return output_path


def route_edge_row_transition_rgb(
    board: pcbnew.BOARD,
    upper_footprint: pcbnew.FOOTPRINT,
    lower_footprint: pcbnew.FOOTPRINT,
    top_right: bool,
) -> None:
    upper_center_x_mm, upper_center_y_mm = millimeters(
        upper_footprint.GetPosition()
    )
    lower_center_x_mm, lower_center_y_mm = millimeters(
        lower_footprint.GetPosition()
    )
    if abs(upper_center_x_mm - lower_center_x_mm) > 0.001:
        raise ValueError("Transition LEDs must be in the same column")

    transition_center_y_mm = (
        upper_center_y_mm + lower_center_y_mm
    ) / 2
    upper_via_y_mm = (
        transition_center_y_mm - TRANSITION_SIDE_VIA_Y_OFFSET_MM
    )
    lower_via_y_mm = (
        transition_center_y_mm + TRANSITION_SIDE_VIA_Y_OFFSET_MM
    )
    outer_via_x_offset_mm = 1.05
    upper_central_via_x_offset_mm = 0.1
    lower_central_via_x_offset_mm = 0.5
    upper_central_via_y_mm = transition_center_y_mm - 0.2
    lower_central_via_y_mm = transition_center_y_mm + 0.1

    upper_blue_pad = get_pad(upper_footprint, "4")
    upper_red_pad = get_pad(upper_footprint, "2")
    upper_green_pad = get_pad(upper_footprint, "3")
    lower_blue_pad = get_pad(lower_footprint, "4")
    lower_red_pad = get_pad(lower_footprint, "2")
    lower_green_pad = get_pad(lower_footprint, "3")

    if top_right:
        shared_green_via_x_mm = upper_center_x_mm + 0.4
        transition_vias = (
            (
                upper_blue_pad,
                upper_center_x_mm - outer_via_x_offset_mm,
                upper_via_y_mm,
                False,
            ),
            (
                upper_red_pad,
                upper_center_x_mm - upper_central_via_x_offset_mm,
                upper_central_via_y_mm,
                True,
            ),
            (
                lower_blue_pad,
                upper_center_x_mm - lower_central_via_x_offset_mm,
                lower_central_via_y_mm,
                True,
            ),
            (
                lower_red_pad,
                upper_center_x_mm - outer_via_x_offset_mm,
                lower_via_y_mm,
                False,
            ),
        )
    else:
        shared_green_via_x_mm = upper_center_x_mm - 0.4
        transition_vias = (
            (
                upper_blue_pad,
                upper_center_x_mm + upper_central_via_x_offset_mm,
                upper_central_via_y_mm,
                True,
            ),
            (
                upper_red_pad,
                upper_center_x_mm + outer_via_x_offset_mm,
                upper_via_y_mm,
                False,
            ),
            (
                lower_blue_pad,
                upper_center_x_mm + outer_via_x_offset_mm,
                lower_via_y_mm,
                False,
            ),
            (
                lower_red_pad,
                upper_center_x_mm + lower_central_via_x_offset_mm,
                lower_central_via_y_mm,
                True,
            ),
        )

    via_positions_by_pad_number: dict[int, tuple[float, float]] = {}
    for pad, via_x_mm, via_y_mm, route_through_center in transition_vias:
        pad_x_mm, pad_y_mm = millimeters(pad.GetPosition())
        if route_through_center:
            footprint = pad.GetParent()
            footprint_x_mm, footprint_y_mm = millimeters(
                footprint.GetPosition()
            )
            add_track(
                board,
                pad.GetNet(),
                pcbnew.F_Cu,
                pad_x_mm,
                pad_y_mm,
                footprint_x_mm,
                footprint_y_mm,
            )
            approach_y_mm = via_y_mm + (
                0.18 if via_y_mm > transition_center_y_mm else -0.18
            )
            add_track(
                board,
                pad.GetNet(),
                pcbnew.F_Cu,
                footprint_x_mm,
                footprint_y_mm,
                footprint_x_mm,
                approach_y_mm,
            )
            add_track(
                board,
                pad.GetNet(),
                pcbnew.F_Cu,
                footprint_x_mm,
                approach_y_mm,
                via_x_mm,
                approach_y_mm,
            )
            add_track(
                board,
                pad.GetNet(),
                pcbnew.F_Cu,
                via_x_mm,
                approach_y_mm,
                via_x_mm,
                via_y_mm,
            )
        else:
            add_track(
                board,
                pad.GetNet(),
                pcbnew.F_Cu,
                pad_x_mm,
                pad_y_mm,
                via_x_mm,
                pad_y_mm,
            )
            add_track(
                board,
                pad.GetNet(),
                pcbnew.F_Cu,
                via_x_mm,
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
        via_positions_by_pad_number[id(pad)] = (via_x_mm, via_y_mm)

    shared_green_via_y_mm = transition_center_y_mm
    for green_pad in (upper_green_pad, lower_green_pad):
        pad_x_mm, pad_y_mm = millimeters(green_pad.GetPosition())
        add_track(
            board,
            green_pad.GetNet(),
            pcbnew.F_Cu,
            pad_x_mm,
            pad_y_mm,
            shared_green_via_x_mm,
            shared_green_via_y_mm,
        )
    add_through_via(
        board,
        upper_green_pad.GetNet(),
        shared_green_via_x_mm,
        shared_green_via_y_mm,
        MATRIX_RGB_VIA_DIAMETER_MM,
    )
    add_track(
        board,
        upper_green_pad.GetNet(),
        pcbnew.B_Cu,
        shared_green_via_x_mm,
        shared_green_via_y_mm,
        shared_green_via_x_mm,
        shared_green_via_y_mm + 0.2,
    )

    upper_blue_via = via_positions_by_pad_number[id(upper_blue_pad)]
    lower_blue_via = via_positions_by_pad_number[id(lower_blue_pad)]
    upper_red_via = via_positions_by_pad_number[id(upper_red_pad)]
    lower_red_via = via_positions_by_pad_number[id(lower_red_pad)]
    if top_right:
        crossover_routes = (
            (
                upper_blue_pad.GetNet(),
                pcbnew.In2_Cu,
                (
                    upper_blue_via,
                    (
                        upper_blue_via[0],
                        transition_center_y_mm - 0.5,
                    ),
                    (
                        lower_blue_via[0],
                        transition_center_y_mm - 0.5,
                    ),
                    lower_blue_via,
                ),
            ),
            (
                upper_red_pad.GetNet(),
                pcbnew.B_Cu,
                (
                    upper_red_via,
                    (
                        upper_red_via[0],
                        transition_center_y_mm + 0.5,
                    ),
                    (
                        lower_red_via[0],
                        transition_center_y_mm + 0.5,
                    ),
                    lower_red_via,
                ),
            ),
        )
    else:
        outside_x_mm = upper_center_x_mm + 1.4
        crossover_routes = (
            (
                upper_blue_pad.GetNet(),
                pcbnew.In2_Cu,
                (
                    upper_blue_via,
                    (
                        upper_blue_via[0],
                        transition_center_y_mm - 0.65,
                    ),
                    (outside_x_mm, transition_center_y_mm - 0.65),
                    (outside_x_mm, lower_blue_via[1]),
                    lower_blue_via,
                ),
            ),
            (
                upper_red_pad.GetNet(),
                pcbnew.B_Cu,
                (
                    upper_red_via,
                    (outside_x_mm, upper_red_via[1]),
                    (outside_x_mm, transition_center_y_mm + 0.65),
                    (
                        lower_red_via[0],
                        transition_center_y_mm + 0.65,
                    ),
                    lower_red_via,
                ),
            ),
        )

    for net, layer, route_points in crossover_routes:
        for start_point, end_point in zip(
            route_points,
            route_points[1:],
        ):
            add_track(
                board,
                net,
                layer,
                start_point[0],
                start_point[1],
                end_point[0],
                end_point[1],
            )


def generate_row_boundary_probe(
    repository_root: Path,
    variant: ProbeVariant,
    top_right: bool,
) -> Path:
    boundary_name = "top_right" if top_right else "bottom_left"
    output_path = (
        repository_root
        / "hardware"
        / "analysis"
        / (
            f"{variant.board_name}_{boundary_name}"
            "_row_boundary_routing_probe.kicad_pcb"
        )
    )
    board = create_skeleton_board(repository_root, variant)

    upper_row_number = variant.matrix_size // 2
    lower_row_number = upper_row_number + 1
    if top_right:
        row_profiles = (
            (upper_row_number, TOP_RIGHT_PROFILE),
            (lower_row_number, ROTATED_PROFILE),
        )
        column_numbers = (
            variant.matrix_size - 1,
            variant.matrix_size,
        )
    else:
        row_profiles = (
            (upper_row_number, NORMAL_PROFILE),
            (lower_row_number, BOTTOM_LEFT_PROFILE),
        )
        column_numbers = (1, 2)

    row_via_extents: dict[int, list[float]] = {}
    for column_number in column_numbers:
        upper_footprint = get_led(
            board,
            get_led_reference(
                variant,
                upper_row_number,
                column_number,
            ),
        )
        lower_footprint = get_led(
            board,
            get_led_reference(
                variant,
                lower_row_number,
                column_number,
            ),
        )
        upper_footprint.SetOrientationDegrees(
            row_profiles[0][1].orientation_degrees
        )
        lower_footprint.SetOrientationDegrees(
            row_profiles[1][1].orientation_degrees
        )
        route_edge_row_transition_rgb(
            board,
            upper_footprint,
            lower_footprint,
            top_right,
        )

        for row_number, profile, footprint in (
            (
                upper_row_number,
                row_profiles[0][1],
                upper_footprint,
            ),
            (
                lower_row_number,
                row_profiles[1][1],
                lower_footprint,
            ),
        ):
            row_center_y_mm = (
                0.9 + (row_number - 1) * variant.led_pitch_mm
            )
            if profile.vertical_direction > 0:
                via_x_mm = route_anode(
                    board,
                    footprint,
                    row_center_y_mm,
                    TRANSITION_ROW_WIDTH_MM,
                    profile.anode_via_x_offset_mm,
                )
            else:
                via_x_mm = route_rotated_anode(
                    board,
                    footprint,
                    row_center_y_mm,
                    TRANSITION_ROW_WIDTH_MM,
                    variant.board_size_mm - 0.525,
                    profile.anode_via_x_offset_mm,
                )
            row_via_extents.setdefault(row_number, []).append(via_x_mm)

    for row_number, _ in row_profiles:
        row_center_y_mm = (
            0.9 + (row_number - 1) * variant.led_pitch_mm
        )
        row_net = get_pad(
            get_led(
                board,
                get_led_reference(
                    variant,
                    row_number,
                    column_numbers[0],
                ),
            ),
            "1",
        ).GetNet()
        row_via_x_values = row_via_extents[row_number]
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

    assign_deterministic_board_uuids(
        board,
        f"orientation-probe:{output_path.stem}",
    )
    pcbnew.SaveBoard(str(output_path), board)
    return output_path


if __name__ == "__main__":
    root_path = Path(__file__).resolve().parents[2]
    for probe_variant in PROBE_VARIANTS:
        generated_top_right_path = generate_column_boundary_probe(
            root_path,
            probe_variant,
            top_right=True,
        )
        print(f"Generated {generated_top_right_path}")
        generated_bottom_left_path = generate_column_boundary_probe(
            root_path,
            probe_variant,
            top_right=False,
        )
        print(f"Generated {generated_bottom_left_path}")
        generated_top_right_row_path = generate_row_boundary_probe(
            root_path,
            probe_variant,
            top_right=True,
        )
        print(f"Generated {generated_top_right_row_path}")
        generated_bottom_left_row_path = generate_row_boundary_probe(
            root_path,
            probe_variant,
            top_right=False,
        )
        print(f"Generated {generated_bottom_left_row_path}")
