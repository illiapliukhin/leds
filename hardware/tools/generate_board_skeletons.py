from collections.abc import Iterator
from dataclasses import dataclass
import math
from pathlib import Path

import pcbnew


@dataclass(frozen=True)
class BoardVariant:
    name: str
    matrix_size: int
    board_size_mm: float
    led_pitch_mm: float
    battery_width_mm: float
    battery_height_mm: float


BOARD_VARIANTS = (
    BoardVariant(
        name="wearable_20x20",
        matrix_size=20,
        board_size_mm=49.3,
        led_pitch_mm=2.5,
        battery_width_mm=32.0,
        battery_height_mm=40.0,
    ),
    BoardVariant(
        name="wearable_28x28",
        matrix_size=28,
        board_size_mm=61.2,
        led_pitch_mm=2.2,
        battery_width_mm=40.0,
        battery_height_mm=50.0,
    ),
)

BOARD_THICKNESS_MM = 1.0
EDGE_LINE_WIDTH_MM = 0.05
GUIDE_LINE_WIDTH_MM = 0.05
LED_CENTER_MARK_RADIUS_MM = 0.12
LED_FOOTPRINT_LIBRARY = "hardware/libraries/leds.pretty"
LED_FOOTPRINT_NAME = "MHPA1010RGBDT"
MINIMUM_COPPER_EDGE_CLEARANCE_MM = 0.3
MINIMUM_COPPER_CLEARANCE_MM = 0.1
MINIMUM_TRACK_WIDTH_MM = 0.1
MINIMUM_VIA_DIAMETER_MM = 0.4
STANDARD_VIA_DIAMETER_MM = 0.45
MINIMUM_VIA_DRILL_MM = 0.2
MINIMUM_VIA_ANNULAR_WIDTH_MM = (
    MINIMUM_VIA_DIAMETER_MM - MINIMUM_VIA_DRILL_MM
) / 2
MINIMUM_HOLE_TO_COPPER_CLEARANCE_MM = 0.2
MINIMUM_SOLDER_MASK_WEB_MM = 0.15
SOLDER_MASK_EXPANSION_MM = 0.0
MINIMUM_SILK_TEXT_HEIGHT_MM = 1.0
MINIMUM_SILK_TEXT_THICKNESS_MM = 0.15
MINIMUM_SILK_CLEARANCE_MM = 0.15


def add_line(
    board: pcbnew.BOARD,
    layer: int,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    width_mm: float,
) -> None:
    line = pcbnew.PCB_SHAPE(board)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetLayer(layer)
    line.SetStart(pcbnew.VECTOR2I_MM(start_x_mm, start_y_mm))
    line.SetEnd(pcbnew.VECTOR2I_MM(end_x_mm, end_y_mm))
    line.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(line)


def add_rectangle(
    board: pcbnew.BOARD,
    layer: int,
    left_mm: float,
    top_mm: float,
    right_mm: float,
    bottom_mm: float,
    width_mm: float,
) -> None:
    add_line(board, layer, left_mm, top_mm, right_mm, top_mm, width_mm)
    add_line(board, layer, right_mm, top_mm, right_mm, bottom_mm, width_mm)
    add_line(board, layer, right_mm, bottom_mm, left_mm, bottom_mm, width_mm)
    add_line(board, layer, left_mm, bottom_mm, left_mm, top_mm, width_mm)


def add_text(
    board: pcbnew.BOARD,
    text_value: str,
    x_mm: float,
    y_mm: float,
    layer: int,
    text_size_mm: float = 1.0,
    mirrored: bool = False,
) -> None:
    text = pcbnew.PCB_TEXT(board)
    text.SetText(text_value)
    text.SetLayer(layer)
    text.SetPosition(pcbnew.VECTOR2I_MM(x_mm, y_mm))
    text.SetTextSize(pcbnew.VECTOR2I_MM(text_size_mm, text_size_mm))
    text.SetTextThickness(pcbnew.FromMM(0.15))
    text.SetMirrored(mirrored)
    board.Add(text)


def add_star(
    board: pcbnew.BOARD,
    center_x_mm: float,
    center_y_mm: float,
    outer_radius_mm: float,
    inner_radius_mm: float,
    layer: int,
) -> None:
    points: list[tuple[float, float]] = []

    for point_index in range(10):
        radius_mm = outer_radius_mm if point_index % 2 == 0 else inner_radius_mm
        angle_radians = math.radians(-90 + point_index * 36)
        points.append(
            (
                center_x_mm + radius_mm * math.cos(angle_radians),
                center_y_mm + radius_mm * math.sin(angle_radians),
            )
        )

    for point_index, start_point in enumerate(points):
        end_point = points[(point_index + 1) % len(points)]
        add_line(
            board,
            layer,
            start_point[0],
            start_point[1],
            end_point[0],
            end_point[1],
            MINIMUM_SILK_TEXT_THICKNESS_MM,
        )


def iter_led_positions(
    variant: BoardVariant,
) -> Iterator[tuple[int, int, float, float]]:
    matrix_span_mm = (variant.matrix_size - 1) * variant.led_pitch_mm
    edge_margin_mm = (variant.board_size_mm - matrix_span_mm) / 2

    for row_index in range(variant.matrix_size):
        center_y_mm = edge_margin_mm + row_index * variant.led_pitch_mm

        for column_index in range(variant.matrix_size):
            center_x_mm = edge_margin_mm + column_index * variant.led_pitch_mm
            yield row_index, column_index, center_x_mm, center_y_mm


def add_led_center_markers(board: pcbnew.BOARD, variant: BoardVariant) -> None:
    for _, _, center_x_mm, center_y_mm in iter_led_positions(variant):
        add_line(
            board,
            pcbnew.User_1,
            center_x_mm - LED_CENTER_MARK_RADIUS_MM,
            center_y_mm,
            center_x_mm + LED_CENTER_MARK_RADIUS_MM,
            center_y_mm,
            GUIDE_LINE_WIDTH_MM,
        )
        add_line(
            board,
            pcbnew.User_1,
            center_x_mm,
            center_y_mm - LED_CENTER_MARK_RADIUS_MM,
            center_x_mm,
            center_y_mm + LED_CENTER_MARK_RADIUS_MM,
            GUIDE_LINE_WIDTH_MM,
        )


def create_net(board: pcbnew.BOARD, net_name: str) -> pcbnew.NETINFO_ITEM:
    net = pcbnew.NETINFO_ITEM(board, net_name)
    board.Add(net)
    return net


def add_led_footprints(
    board: pcbnew.BOARD,
    variant: BoardVariant,
    footprint_library_path: Path,
) -> None:
    row_nets = {
        row_index: create_net(board, f"ROW_{row_index + 1:02d}_ANODE")
        for row_index in range(variant.matrix_size)
    }
    column_nets = {
        (color_name, column_index): create_net(
            board,
            f"COL_{color_name}_{column_index + 1:02d}",
        )
        for color_name in ("R", "G", "B")
        for column_index in range(variant.matrix_size)
    }
    pad_net_keys = {
        "2": "R",
        "3": "G",
        "4": "B",
    }

    for row_index, column_index, center_x_mm, center_y_mm in iter_led_positions(
        variant
    ):
        footprint = pcbnew.FootprintLoad(
            str(footprint_library_path),
            LED_FOOTPRINT_NAME,
        )
        if footprint is None:
            raise FileNotFoundError(
                f"Unable to load {LED_FOOTPRINT_NAME} from "
                f"{footprint_library_path}"
            )

        reference_number = row_index * variant.matrix_size + column_index + 1
        footprint.SetReference(f"D{reference_number}")
        footprint.SetValue("MHPA1010RGBDT")
        footprint.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
        footprint.Reference().SetPosition(
            pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm)
        )
        footprint.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.35, 0.35))
        footprint.Reference().SetTextThickness(pcbnew.FromMM(0.06))
        footprint.Reference().SetLayer(pcbnew.F_Fab)
        footprint.Reference().SetVisible(True)
        footprint.Value().SetVisible(False)

        for pad in footprint.Pads():
            pad_number = pad.GetNumber()
            if pad_number == "1":
                pad.SetNet(row_nets[row_index])
                continue

            color_name = pad_net_keys[pad_number]
            pad.SetNet(column_nets[(color_name, column_index)])

        board.Add(footprint)


def add_battery_guide(board: pcbnew.BOARD, variant: BoardVariant) -> None:
    left_mm = (variant.board_size_mm - variant.battery_width_mm) / 2
    top_mm = (variant.board_size_mm - variant.battery_height_mm) / 2
    right_mm = left_mm + variant.battery_width_mm
    bottom_mm = top_mm + variant.battery_height_mm

    add_rectangle(
        board,
        pcbnew.Dwgs_User,
        left_mm,
        top_mm,
        right_mm,
        bottom_mm,
        GUIDE_LINE_WIDTH_MM,
    )
    add_text(
        board,
        f"PROVISIONAL BATTERY {variant.battery_width_mm:.0f}x{variant.battery_height_mm:.0f} mm",
        variant.board_size_mm / 2,
        top_mm + 1.0,
        pcbnew.Dwgs_User,
        text_size_mm=0.8,
    )


def add_board_branding(board: pcbnew.BOARD, variant: BoardVariant) -> None:
    add_text(
        board,
        "PCB CREATED BY ILLIA PLIUKHIN",
        variant.board_size_mm / 2,
        variant.board_size_mm - 3.2,
        pcbnew.B_SilkS,
        text_size_mm=MINIMUM_SILK_TEXT_HEIGHT_MM,
        mirrored=True,
    )
    add_star(
        board,
        variant.board_size_mm / 2,
        variant.board_size_mm - 1.2,
        outer_radius_mm=0.7,
        inner_radius_mm=0.3,
        layer=pcbnew.B_SilkS,
    )


def configure_board(
    variant: BoardVariant,
    repository_root: Path,
) -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    design_settings = board.GetDesignSettings()
    design_settings.SetBoardThickness(pcbnew.FromMM(BOARD_THICKNESS_MM))
    design_settings.m_MinClearance = pcbnew.FromMM(MINIMUM_COPPER_CLEARANCE_MM)
    design_settings.m_TrackMinWidth = pcbnew.FromMM(MINIMUM_TRACK_WIDTH_MM)
    design_settings.m_ViasMinSize = pcbnew.FromMM(MINIMUM_VIA_DIAMETER_MM)
    design_settings.m_MinThroughDrill = pcbnew.FromMM(MINIMUM_VIA_DRILL_MM)
    design_settings.m_ViasMinAnnularWidth = pcbnew.FromMM(
        MINIMUM_VIA_ANNULAR_WIDTH_MM
    )
    design_settings.m_HoleClearance = pcbnew.FromMM(
        MINIMUM_HOLE_TO_COPPER_CLEARANCE_MM
    )
    design_settings.m_CopperEdgeClearance = pcbnew.FromMM(
        MINIMUM_COPPER_EDGE_CLEARANCE_MM
    )
    design_settings.m_SolderMaskMinWidth = pcbnew.FromMM(
        MINIMUM_SOLDER_MASK_WEB_MM
    )
    design_settings.m_SolderMaskExpansion = pcbnew.FromMM(
        SOLDER_MASK_EXPANSION_MM
    )
    design_settings.m_MinSilkTextHeight = pcbnew.FromMM(
        MINIMUM_SILK_TEXT_HEIGHT_MM
    )
    design_settings.m_MinSilkTextThickness = pcbnew.FromMM(
        MINIMUM_SILK_TEXT_THICKNESS_MM
    )
    design_settings.m_SilkClearance = pcbnew.FromMM(MINIMUM_SILK_CLEARANCE_MM)
    default_netclass = design_settings.m_NetSettings.GetDefaultNetclass()
    default_netclass.SetClearance(pcbnew.FromMM(MINIMUM_COPPER_CLEARANCE_MM))
    default_netclass.SetTrackWidth(pcbnew.FromMM(MINIMUM_TRACK_WIDTH_MM))
    default_netclass.SetViaDiameter(pcbnew.FromMM(STANDARD_VIA_DIAMETER_MM))
    default_netclass.SetViaDrill(pcbnew.FromMM(MINIMUM_VIA_DRILL_MM))

    add_rectangle(
        board,
        pcbnew.Edge_Cuts,
        0.0,
        0.0,
        variant.board_size_mm,
        variant.board_size_mm,
        EDGE_LINE_WIDTH_MM,
    )
    add_led_center_markers(board, variant)
    add_led_footprints(
        board,
        variant,
        repository_root / LED_FOOTPRINT_LIBRARY,
    )
    add_battery_guide(board, variant)
    add_board_branding(board, variant)
    add_text(
        board,
        f"{variant.matrix_size}x{variant.matrix_size} LED CENTERS / {variant.led_pitch_mm:.2f} mm PITCH",
        variant.board_size_mm / 2,
        variant.board_size_mm - 1.0,
        pcbnew.Cmts_User,
        text_size_mm=0.8,
    )

    return board


def validate_board(board: pcbnew.BOARD, variant: BoardVariant) -> None:
    expected_center_marker_segments = variant.matrix_size * variant.matrix_size * 2
    actual_center_marker_segments = sum(
        1 for drawing in board.Drawings() if drawing.GetLayer() == pcbnew.User_1
    )

    if board.GetCopperLayerCount() != 4:
        raise ValueError(f"{variant.name}: expected four copper layers")

    actual_thickness_mm = pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness())
    if abs(actual_thickness_mm - BOARD_THICKNESS_MM) > 0.001:
        raise ValueError(
            f"{variant.name}: expected {BOARD_THICKNESS_MM} mm thickness, "
            f"found {actual_thickness_mm} mm"
        )

    design_settings = board.GetDesignSettings()
    expected_design_rules_mm = {
        "minimum copper clearance": (
            design_settings.m_MinClearance,
            MINIMUM_COPPER_CLEARANCE_MM,
        ),
        "minimum track width": (
            design_settings.m_TrackMinWidth,
            MINIMUM_TRACK_WIDTH_MM,
        ),
        "minimum via diameter": (
            design_settings.m_ViasMinSize,
            MINIMUM_VIA_DIAMETER_MM,
        ),
        "minimum via drill": (
            design_settings.m_MinThroughDrill,
            MINIMUM_VIA_DRILL_MM,
        ),
        "minimum copper-to-edge clearance": (
            design_settings.m_CopperEdgeClearance,
            MINIMUM_COPPER_EDGE_CLEARANCE_MM,
        ),
        "minimum hole-to-copper clearance": (
            design_settings.m_HoleClearance,
            MINIMUM_HOLE_TO_COPPER_CLEARANCE_MM,
        ),
        "minimum solder-mask web": (
            design_settings.m_SolderMaskMinWidth,
            MINIMUM_SOLDER_MASK_WEB_MM,
        ),
        "minimum silkscreen clearance": (
            design_settings.m_SilkClearance,
            MINIMUM_SILK_CLEARANCE_MM,
        ),
    }
    for rule_name, (actual_rule_internal, expected_rule_mm) in (
        expected_design_rules_mm.items()
    ):
        actual_rule_mm = pcbnew.ToMM(actual_rule_internal)
        if abs(actual_rule_mm - expected_rule_mm) > 0.001:
            raise ValueError(
                f"{variant.name}: expected {rule_name} {expected_rule_mm} mm, "
                f"found {actual_rule_mm} mm"
            )

    default_netclass = design_settings.m_NetSettings.GetDefaultNetclass()
    actual_default_clearance_mm = pcbnew.ToMM(default_netclass.GetClearance())
    if abs(actual_default_clearance_mm - MINIMUM_COPPER_CLEARANCE_MM) > 0.001:
        raise ValueError(
            f"{variant.name}: expected default netclass clearance "
            f"{MINIMUM_COPPER_CLEARANCE_MM} mm, found "
            f"{actual_default_clearance_mm} mm"
        )

    if actual_center_marker_segments != expected_center_marker_segments:
        raise ValueError(
            f"{variant.name}: expected {expected_center_marker_segments} center-marker "
            f"segments, found {actual_center_marker_segments}"
        )

    actual_led_count = sum(
        1
        for footprint in board.GetFootprints()
        if footprint.GetValue() == "MHPA1010RGBDT"
    )
    expected_led_count = variant.matrix_size * variant.matrix_size
    if actual_led_count != expected_led_count:
        raise ValueError(
            f"{variant.name}: expected {expected_led_count} LEDs, "
            f"found {actual_led_count}"
        )


def generate_boards(repository_root: Path) -> None:
    for variant in BOARD_VARIANTS:
        output_directory = repository_root / "hardware" / variant.name
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / f"{variant.name}.kicad_pcb"

        board = configure_board(variant, repository_root)
        validate_board(board, variant)
        pcbnew.SaveBoard(str(output_path), board)
        print(f"Generated {output_path}")


if __name__ == "__main__":
    generate_boards(Path(__file__).resolve().parents[2])
