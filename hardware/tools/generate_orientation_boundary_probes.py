from dataclasses import dataclass
from pathlib import Path

import pcbnew

from generate_edge_routing_probe import (
    INNER_ROW_WIDTH_MM,
    OUTER_ROW_WIDTH_MM,
    PROBE_VARIANTS,
    ProbeVariant,
    add_track,
    get_led,
    get_pad,
    route_anode,
    route_rgb_to_back,
    route_rotated_anode,
)


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
    anode_via_x_offset_mm=0.54,
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
    anode_via_x_offset_mm=-0.54,
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
    anode_via_x_offset_mm=-0.54,
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
    anode_via_x_offset_mm=0.54,
    trunk_offsets=(
        ("G", -0.375, -0.925),
        ("B", 0.375, -0.925),
        ("R", 0.0, -1.275),
    ),
)


def get_board_path(repository_root: Path, variant: ProbeVariant) -> Path:
    return (
        repository_root
        / "hardware"
        / variant.board_name
        / f"{variant.board_name}.kicad_pcb"
    )


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
    board = pcbnew.LoadBoard(str(get_board_path(repository_root, variant)))

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
