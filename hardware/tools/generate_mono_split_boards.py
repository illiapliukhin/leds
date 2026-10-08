from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pcbnew
from mono_split_spec import (
    BRANDING_STRIP_HEIGHT_MM,
    COLUMN_CONNECTOR_FOOTPRINT_NAME,
    ELECTRONICS_HEIGHT_MM,
    ELECTRONICS_WIDTH_MM,
    FFC_PIN_COUNT,
    LED_ANODE_PAD,
    LED_CATHODE_PAD,
    LED_FOOTPRINT_NAME,
    LED_PITCH_MM,
    MATRIX_CHANNEL_COUNT,
    PANEL_MARGIN_MM,
    PANEL_VARIANTS,
    ROW_CONNECTOR_FOOTPRINT_NAME,
    PanelVariant,
    column_connector_pinout,
    column_net_name,
    row_connector_pinout,
    row_net_name,
)


BOARD_THICKNESS_MM = 1.0
EDGE_LINE_WIDTH_MM = 0.05
GUIDE_LINE_WIDTH_MM = 0.05
LED_CENTER_MARK_RADIUS_MM = 0.12
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
ROW_BUS_WIDTH_MM = 0.35
ROW_BUS_OFFSET_MM = 0.90
COLUMN_TRACK_WIDTH_MM = 0.20
STUB_TRACK_WIDTH_MM = 0.20
FAN_IN_TRACK_WIDTH_MM = 0.15
FAN_IN_CHANNEL_PITCH_MM = 0.28
FAN_IN_VIA_PITCH_MM = 0.55
ROW_CONNECTOR_X_MM = 8.0
COLUMN_CONNECTOR_EDGE_OFFSET_MM = 8.3
ROW_FAN_VIA_START_X_MM = 13.2
ROW_FAN_VIA_Y_MM = 16.0
ROW_FAN_CORRIDOR_Y_START_MM = 4.0
COLUMN_FAN_APPROACH_OFFSET_MM = 8.0
CATHODE_VIA_OFFSET_Y_MM = 1.10
LED_ROTATION_DEGREES = 180.0
REPOSITORY_LED_LIBRARY = Path("hardware/libraries/leds.pretty")
REPOSITORY_CONNECTOR_LIBRARY = Path("hardware/libraries/connectors.pretty")
REPOSITORY_ELECTRONICS_LIBRARY = Path("hardware/libraries/electronics.pretty")


@dataclass(frozen=True)
class PlacedPart:
    reference: str
    value: str
    footprint_name: str
    x_mm: float
    y_mm: float
    rotation_degrees: float
    reference_x_mm: float
    reference_y_mm: float
    pad_nets: dict[str, str]


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


def add_track(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    width_mm: float,
) -> None:
    if (
        abs(start_x_mm - end_x_mm) < 0.001
        and abs(start_y_mm - end_y_mm) < 0.001
    ):
        return
    track = pcbnew.PCB_TRACK(board)
    track.SetNet(net)
    track.SetLayer(layer)
    track.SetStart(pcbnew.VECTOR2I_MM(start_x_mm, start_y_mm))
    track.SetEnd(pcbnew.VECTOR2I_MM(end_x_mm, end_y_mm))
    track.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(track)


def add_polyline(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    points_mm: list[tuple[float, float]],
    width_mm: float,
) -> None:
    for start_point, end_point in zip(points_mm, points_mm[1:]):
        add_track(
            board,
            net,
            layer,
            start_point[0],
            start_point[1],
            end_point[0],
            end_point[1],
            width_mm,
        )


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
    via.SetDrill(pcbnew.FromMM(MINIMUM_VIA_DRILL_MM))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)


def create_net(board: pcbnew.BOARD, net_name: str) -> pcbnew.NETINFO_ITEM:
    existing = board.FindNet(net_name)
    if existing is not None and existing.GetNetCode() != 0:
        return existing
    net = pcbnew.NETINFO_ITEM(board, net_name)
    board.Add(net)
    return net


def load_footprint(library_path: Path, footprint_name: str) -> pcbnew.FOOTPRINT:
    footprint = pcbnew.FootprintLoad(str(library_path), footprint_name)
    if footprint is None:
        raise FileNotFoundError(
            f"Unable to load {footprint_name} from {library_path}"
        )
    return footprint


def millimeters(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def get_pad(footprint: pcbnew.FOOTPRINT, pad_number: str) -> pcbnew.PAD:
    for pad in footprint.Pads():
        if pad.GetNumber() == pad_number:
            return pad
    raise ValueError(
        f"Unable to find pad {pad_number} in {footprint.GetReference()}"
    )


def apply_design_rules(board: pcbnew.BOARD, copper_layer_count: int) -> None:
    board.SetCopperLayerCount(copper_layer_count)
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


def iter_led_positions(
    variant: PanelVariant,
) -> Iterator[tuple[int, int, float, float]]:
    matrix_span_mm = (variant.matrix_size - 1) * LED_PITCH_MM
    edge_margin_mm = (variant.board_size_mm - matrix_span_mm) / 2
    for row_index in range(variant.matrix_size):
        center_y_mm = edge_margin_mm + row_index * LED_PITCH_MM
        for column_index in range(variant.matrix_size):
            center_x_mm = edge_margin_mm + column_index * LED_PITCH_MM
            yield row_index, column_index, center_x_mm, center_y_mm


def assign_pad_nets(
    footprint: pcbnew.FOOTPRINT,
    net_by_pad: dict[str, pcbnew.NETINFO_ITEM],
) -> None:
    for pad in footprint.Pads():
        net = net_by_pad.get(pad.GetNumber())
        if net is not None:
            pad.SetNet(net)


def add_led_matrix(
    board: pcbnew.BOARD,
    variant: PanelVariant,
    repository_root: Path,
) -> dict[tuple[int, int], pcbnew.FOOTPRINT]:
    library_path = repository_root / REPOSITORY_LED_LIBRARY
    footprints: dict[tuple[int, int], pcbnew.FOOTPRINT] = {}
    row_nets = {
        row_index: create_net(board, row_net_name(row_index + 1))
        for row_index in range(variant.matrix_size)
    }
    column_nets = {
        column_index: create_net(board, column_net_name(column_index + 1))
        for column_index in range(variant.matrix_size)
    }

    for row_index, column_index, center_x_mm, center_y_mm in iter_led_positions(
        variant
    ):
        footprint = load_footprint(library_path, LED_FOOTPRINT_NAME)
        reference_number = row_index * variant.matrix_size + column_index + 1
        footprint.SetReference(f"D{reference_number}")
        footprint.SetValue(LED_FOOTPRINT_NAME)
        footprint.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
        footprint.SetOrientationDegrees(LED_ROTATION_DEGREES)
        footprint.Reference().SetLayer(pcbnew.F_Fab)
        footprint.Reference().SetPosition(
            pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm)
        )
        footprint.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.35, 0.35))
        footprint.Reference().SetTextThickness(pcbnew.FromMM(0.06))
        footprint.Reference().SetVisible(True)
        footprint.Value().SetVisible(False)
        assign_pad_nets(
            footprint,
            {
                LED_ANODE_PAD: row_nets[row_index],
                LED_CATHODE_PAD: column_nets[column_index],
            },
        )
        board.Add(footprint)
        footprints[(row_index, column_index)] = footprint
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

    return footprints


def place_panel_connector(
    board: pcbnew.BOARD,
    repository_root: Path,
    footprint_name: str,
    reference: str,
    x_mm: float,
    y_mm: float,
    rotation_degrees: float,
    pinout: dict[str, str],
    assigned_pins: int,
) -> pcbnew.FOOTPRINT:
    footprint = load_footprint(
        repository_root / REPOSITORY_CONNECTOR_LIBRARY,
        footprint_name,
    )
    footprint.SetReference(reference)
    footprint.SetValue(footprint_name)
    footprint.SetPosition(pcbnew.VECTOR2I_MM(x_mm, y_mm))
    footprint.SetOrientationDegrees(rotation_degrees)
    footprint.Value().SetVisible(False)
    board.Add(footprint)
    footprint.Flip(footprint.GetPosition(), False)
    footprint.Reference().SetTextSize(
        pcbnew.VECTOR2I_MM(
            MINIMUM_SILK_TEXT_HEIGHT_MM,
            MINIMUM_SILK_TEXT_HEIGHT_MM,
        )
    )
    footprint.Reference().SetTextThickness(
        pcbnew.FromMM(MINIMUM_SILK_TEXT_THICKNESS_MM)
    )
    nets = {
        pin_number: create_net(board, net_name)
        for pin_number, net_name in pinout.items()
        if int(pin_number) <= assigned_pins
    }
    assign_pad_nets(footprint, nets)
    return footprint


def route_led_cells(
    board: pcbnew.BOARD,
    variant: PanelVariant,
    led_footprints: dict[tuple[int, int], pcbnew.FOOTPRINT],
) -> tuple[dict[int, tuple[float, float]], dict[int, tuple[float, float]]]:
    row_bus_ends: dict[int, tuple[float, float]] = {}
    column_trunk_ends: dict[int, tuple[float, float]] = {}
    for row_index in range(variant.matrix_size):
        first_led = led_footprints[(row_index, 0)]
        last_led = led_footprints[(row_index, variant.matrix_size - 1)]
        first_center_x_mm, first_center_y_mm = millimeters(
            first_led.GetPosition()
        )
        last_center_x_mm, _ = millimeters(last_led.GetPosition())
        bus_y_mm = first_center_y_mm - ROW_BUS_OFFSET_MM
        row_net = get_pad(first_led, LED_ANODE_PAD).GetNet()
        first_anode_x_mm, first_anode_y_mm = millimeters(
            get_pad(first_led, LED_ANODE_PAD).GetPosition()
        )
        last_anode_x_mm, _ = millimeters(
            get_pad(last_led, LED_ANODE_PAD).GetPosition()
        )
        add_track(
            board,
            row_net,
            pcbnew.F_Cu,
            first_anode_x_mm,
            bus_y_mm,
            last_anode_x_mm,
            bus_y_mm,
            ROW_BUS_WIDTH_MM,
        )
        for column_index in range(variant.matrix_size):
            led = led_footprints[(row_index, column_index)]
            anode_x_mm, anode_y_mm = millimeters(
                get_pad(led, LED_ANODE_PAD).GetPosition()
            )
            add_track(
                board,
                row_net,
                pcbnew.F_Cu,
                anode_x_mm,
                anode_y_mm,
                anode_x_mm,
                bus_y_mm,
                STUB_TRACK_WIDTH_MM,
            )
        escape_x_mm = first_center_x_mm - 1.60
        add_track(
            board,
            row_net,
            pcbnew.F_Cu,
            first_anode_x_mm,
            bus_y_mm,
            escape_x_mm,
            bus_y_mm,
            ROW_BUS_WIDTH_MM,
        )
        row_bus_ends[row_index] = (escape_x_mm, bus_y_mm)

    for column_index in range(variant.matrix_size):
        first_led = led_footprints[(0, column_index)]
        last_led = led_footprints[(variant.matrix_size - 1, column_index)]
        column_net = get_pad(first_led, LED_CATHODE_PAD).GetNet()
        first_via_x_mm = 0.0
        first_via_y_mm = 0.0
        last_via_y_mm = 0.0
        for row_index in range(variant.matrix_size):
            led = led_footprints[(row_index, column_index)]
            cathode_x_mm, cathode_y_mm = millimeters(
                get_pad(led, LED_CATHODE_PAD).GetPosition()
            )
            _, center_y_mm = millimeters(led.GetPosition())
            via_x_mm = cathode_x_mm
            via_y_mm = center_y_mm + CATHODE_VIA_OFFSET_Y_MM
            add_track(
                board,
                column_net,
                pcbnew.F_Cu,
                cathode_x_mm,
                cathode_y_mm,
                via_x_mm,
                via_y_mm,
                STUB_TRACK_WIDTH_MM,
            )
            add_through_via(board, column_net, via_x_mm, via_y_mm)
            if row_index == 0:
                first_via_x_mm = via_x_mm
                first_via_y_mm = via_y_mm
            last_via_y_mm = via_y_mm
        add_track(
            board,
            column_net,
            pcbnew.B_Cu,
            first_via_x_mm,
            first_via_y_mm,
            first_via_x_mm,
            last_via_y_mm,
            COLUMN_TRACK_WIDTH_MM,
        )
        last_center_x_mm, last_center_y_mm = millimeters(last_led.GetPosition())
        escape_y_mm = last_center_y_mm + 1.60
        add_track(
            board,
            column_net,
            pcbnew.B_Cu,
            first_via_x_mm,
            last_via_y_mm,
            first_via_x_mm,
            escape_y_mm,
            COLUMN_TRACK_WIDTH_MM,
        )
        column_trunk_ends[column_index] = (first_via_x_mm, escape_y_mm)

    return row_bus_ends, column_trunk_ends


def route_row_fan_in(
    board: pcbnew.BOARD,
    starts: list[tuple[pcbnew.NETINFO_ITEM, float, float]],
    connector: pcbnew.FOOTPRINT,
    assigned_pins: int,
) -> None:
    for pin_index in range(assigned_pins):
        net, start_x_mm, start_y_mm = starts[pin_index]
        pad_x_mm, pad_y_mm = millimeters(
            get_pad(connector, str(pin_index + 1)).GetPosition()
        )
        channel_x_mm = start_x_mm - (pin_index + 1) * FAN_IN_CHANNEL_PITCH_MM
        corridor_y_mm = (
            ROW_FAN_CORRIDOR_Y_START_MM + pin_index * FAN_IN_CHANNEL_PITCH_MM
        )
        via_x_mm = ROW_FAN_VIA_START_X_MM + pin_index * FAN_IN_VIA_PITCH_MM
        via_y_mm = ROW_FAN_VIA_Y_MM
        add_polyline(
            board,
            net,
            pcbnew.F_Cu,
            [
                (start_x_mm, start_y_mm),
                (channel_x_mm, start_y_mm),
                (channel_x_mm, corridor_y_mm),
                (via_x_mm, corridor_y_mm),
                (via_x_mm, via_y_mm),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, via_x_mm, via_y_mm)
        add_polyline(
            board,
            net,
            pcbnew.B_Cu,
            [
                (via_x_mm, via_y_mm),
                (via_x_mm, pad_y_mm),
                (pad_x_mm, pad_y_mm),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )


def route_column_fan_in(
    board: pcbnew.BOARD,
    starts: list[tuple[pcbnew.NETINFO_ITEM, float, float]],
    connector: pcbnew.FOOTPRINT,
    assigned_pins: int,
) -> None:
    pad_y_values_mm = [
        millimeters(get_pad(connector, str(pin_index + 1)).GetPosition())[1]
        for pin_index in range(assigned_pins)
    ]
    approach_y_mm = min(pad_y_values_mm) - COLUMN_FAN_APPROACH_OFFSET_MM
    for pin_index in range(assigned_pins):
        net, start_x_mm, start_y_mm = starts[pin_index]
        pad_x_mm, pad_y_mm = millimeters(
            get_pad(connector, str(pin_index + 1)).GetPosition()
        )
        add_polyline(
            board,
            net,
            pcbnew.B_Cu,
            [
                (start_x_mm, start_y_mm),
                (pad_x_mm, approach_y_mm),
                (pad_x_mm, pad_y_mm),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )


def add_panel_branding(board: pcbnew.BOARD, variant: PanelVariant) -> None:
    add_text(
        board,
        "PCB CREATED BY ILLIA PLIUKHIN",
        variant.board_size_mm / 2,
        3.2,
        pcbnew.B_SilkS,
        text_size_mm=MINIMUM_SILK_TEXT_HEIGHT_MM,
        mirrored=True,
    )
    add_star(
        board,
        variant.board_size_mm / 2,
        1.3,
        outer_radius_mm=0.7,
        inner_radius_mm=0.3,
        layer=pcbnew.B_SilkS,
    )
    add_text(
        board,
        (
            f"{variant.matrix_size}x{variant.matrix_size} NCD0603W1 / "
            f"{LED_PITCH_MM:.2f} mm PITCH"
        ),
        variant.board_size_mm / 2,
        variant.board_size_mm - 1.2,
        pcbnew.Cmts_User,
        text_size_mm=0.8,
    )


def generate_panel_board(
    variant: PanelVariant,
    repository_root: Path,
) -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    apply_design_rules(board, copper_layer_count=2)
    add_rectangle(
        board,
        pcbnew.Edge_Cuts,
        0.0,
        0.0,
        variant.board_size_mm,
        variant.board_size_mm,
        EDGE_LINE_WIDTH_MM,
    )
    led_footprints = add_led_matrix(board, variant, repository_root)
    row_connector = place_panel_connector(
        board,
        repository_root,
        ROW_CONNECTOR_FOOTPRINT_NAME,
        "J_ROW",
        ROW_CONNECTOR_X_MM,
        variant.board_size_mm / 2,
        270.0,
        row_connector_pinout(),
        variant.matrix_size,
    )
    column_connector = place_panel_connector(
        board,
        repository_root,
        COLUMN_CONNECTOR_FOOTPRINT_NAME,
        "J_COL",
        variant.board_size_mm / 2,
        variant.board_size_mm - COLUMN_CONNECTOR_EDGE_OFFSET_MM,
        180.0,
        column_connector_pinout(),
        variant.matrix_size,
    )
    row_bus_ends, column_trunk_ends = route_led_cells(
        board,
        variant,
        led_footprints,
    )
    row_starts = []
    for row_index in range(variant.matrix_size):
        first_led = led_footprints[(row_index, 0)]
        net = get_pad(first_led, LED_ANODE_PAD).GetNet()
        row_starts.append((net, *row_bus_ends[row_index]))
    column_starts = []
    for column_index in range(variant.matrix_size):
        last_led = led_footprints[(variant.matrix_size - 1, column_index)]
        net = get_pad(last_led, LED_CATHODE_PAD).GetNet()
        column_starts.append((net, *column_trunk_ends[column_index]))
    route_row_fan_in(
        board,
        row_starts,
        row_connector,
        variant.matrix_size,
    )
    route_column_fan_in(
        board,
        column_starts,
        column_connector,
        variant.matrix_size,
    )
    add_panel_branding(board, variant)
    return board


def electronics_parts() -> list[PlacedPart]:
    parts = [
        PlacedPart(
            "J_USB",
            "USB4105",
            "USB_C_Receptacle_HRO_TYPE-C-31-M-12",
            6.5,
            18.0,
            90.0,
            6.5,
            29.5,
            {
                "A1": "GND",
                "A12": "GND",
                "B1": "GND",
                "B12": "GND",
                "A4": "VBUS",
                "A9": "VBUS",
                "B4": "VBUS",
                "B9": "VBUS",
                "SH": "GND",
            },
        ),
        PlacedPart(
            "U_ESD",
            "USBLC6-2SC6",
            "SOT-23-6",
            16.0,
            12.0,
            0.0,
            16.0,
            8.5,
            {},
        ),
        PlacedPart(
            "U1",
            "ESP32-S3FN8",
            "QFN-56-1EP_7x7mm_P0.4mm_EP5.6x5.6mm",
            28.0,
            20.0,
            0.0,
            28.0,
            12.5,
            {},
        ),
        PlacedPart(
            "Y1",
            "L327S400H11L",
            "Crystal_SMD_3225-4Pin_3.2x2.5mm",
            28.0,
            30.5,
            0.0,
            36.0,
            30.5,
            {},
        ),
        PlacedPart(
            "U_IMU",
            "BMI270",
            "Bosch_LGA-14_3x2.5mm_P0.5mm",
            40.0,
            14.0,
            0.0,
            40.0,
            9.5,
            {
                "4": "IMU_INT1",
                "5": "AON_3V3",
                "6": "GND",
                "7": "GND",
                "8": "AON_3V3",
                "13": "IMU_SCL",
                "14": "IMU_SDA",
            },
        ),
        PlacedPart(
            "U_CHG",
            "BQ25185",
            "Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm",
            18.0,
            42.0,
            0.0,
            18.0,
            37.5,
            {},
        ),
        PlacedPart(
            "J_BAT",
            "BAT_3P",
            "JST_GH_BM03B-GHS-TBT_1x03-1MP_P1.25mm_Vertical",
            8.0,
            58.0,
            180.0,
            8.0,
            64.0,
            {},
        ),
        PlacedPart(
            "U_LED_PWR",
            "TPS63802DLAR",
            "TDFN-10-1EP_2x3mm_P0.5mm_EP0.9x2mm",
            34.0,
            48.0,
            0.0,
            34.0,
            53.5,
            {},
        ),
        PlacedPart(
            "L_LED",
            "DFE201612E-R47M",
            "L_Murata_DFE201610P",
            42.0,
            48.0,
            0.0,
            42.0,
            43.0,
            {},
        ),
        PlacedPart(
            "U_LDO",
            "TPS7A2033",
            "SOT-23-5",
            34.0,
            62.0,
            0.0,
            34.0,
            57.5,
            {},
        ),
        PlacedPart(
            "U_LED_LOGIC",
            "TPS22917",
            "SOT-23-6",
            20.0,
            62.0,
            0.0,
            20.0,
            57.5,
            {},
        ),
        PlacedPart(
            "U_AUDIO_SW",
            "TPS22917",
            "SOT-23-6",
            20.0,
            70.0,
            0.0,
            20.0,
            74.5,
            {},
        ),
        PlacedPart(
            "U_GAUGE",
            "MAX17048",
            "Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm",
            18.0,
            50.0,
            0.0,
            26.0,
            50.0,
            {},
        ),
        PlacedPart(
            "MIC1",
            "MA-HFA381",
            "Knowles_LGA-5_3.5x2.65mm",
            100.0,
            10.0,
            0.0,
            100.0,
            5.5,
            {},
        ),
        PlacedPart(
            "U_AUDIO",
            "TLV9001",
            "SOT-353_SC-70-5",
            100.0,
            18.0,
            0.0,
            107.0,
            18.0,
            {},
        ),
        PlacedPart(
            "SW1",
            "KMR2",
            "SW_Push_1P1T_NO_CK_KMR2",
            124.0,
            76.0,
            0.0,
            124.0,
            71.5,
            {},
        ),
        PlacedPart(
            "U_ROW_XLAT",
            "SN74LVC8T245",
            "VQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm",
            54.0,
            10.0,
            0.0,
            54.0,
            4.5,
            {},
        ),
        PlacedPart(
            "U_DEC_A",
            "74HC154",
            "TSSOP-24_4.4x7.8mm_P0.65mm",
            68.0,
            10.0,
            0.0,
            68.0,
            4.5,
            {},
        ),
        PlacedPart(
            "U_DEC_B",
            "74HC154",
            "TSSOP-24_4.4x7.8mm_P0.65mm",
            82.0,
            10.0,
            0.0,
            82.0,
            4.5,
            {},
        ),
        PlacedPart(
            "U_LED_BUF",
            "SN74LV125A",
            "TSSOP-14_4.4x5mm_P0.65mm",
            62.0,
            76.0,
            0.0,
            62.0,
            70.5,
            {},
        ),
        PlacedPart(
            "U_LED1",
            "MBI5124GP-B",
            "SSOP-24_3.9x8.7mm_P0.635mm",
            86.0,
            76.0,
            0.0,
            86.0,
            67.0,
            {
                str(5 + offset): column_net_name(1 + offset)
                for offset in range(16)
            }
            | {
                "1": "GND",
                "22": "REXT1",
                "23": "LED_LOGIC_3V3",
                "24": "LED_OE_N",
            },
        ),
        PlacedPart(
            "U_LED2",
            "MBI5124GP-B",
            "SSOP-24_3.9x8.7mm_P0.635mm",
            102.0,
            76.0,
            0.0,
            102.0,
            67.0,
            {
                str(5 + offset): column_net_name(17 + offset)
                for offset in range(16)
            }
            | {
                "1": "GND",
                "22": "REXT2",
                "23": "LED_LOGIC_3V3",
                "24": "LED_OE_N",
            },
        ),
        PlacedPart(
            "R_EXT1",
            "1.82k",
            "R_0402_1005Metric",
            70.0,
            76.0,
            0.0,
            70.0,
            81.0,
            {"1": "REXT1"},
        ),
        PlacedPart(
            "R_EXT2",
            "1.82k",
            "R_0402_1005Metric",
            114.0,
            76.0,
            0.0,
            114.0,
            81.0,
            {"1": "REXT2"},
        ),
        PlacedPart(
            "C_USB1",
            "100n",
            "C_0402_1005Metric",
            16.0,
            24.0,
            0.0,
            16.0,
            27.5,
            {},
        ),
        PlacedPart(
            "C_MCU1",
            "10u",
            "C_0805_2012Metric",
            28.0,
            36.0,
            0.0,
            34.5,
            36.0,
            {},
        ),
        PlacedPart(
            "C_LED1",
            "22u",
            "C_0805_2012Metric",
            42.0,
            40.0,
            0.0,
            42.0,
            35.5,
            {},
        ),
        PlacedPart(
            "TH_PCB",
            "NTC10K",
            "R_0402_1005Metric",
            40.0,
            22.0,
            0.0,
            40.0,
            18.5,
            {},
        ),
        PlacedPart(
            "TP1",
            "AON_3V3",
            "R_0402_1005Metric",
            50.0,
            76.0,
            0.0,
            50.0,
            72.5,
            {"1": "AON_3V3"},
        ),
        PlacedPart(
            "TP2",
            "GND",
            "R_0402_1005Metric",
            50.0,
            80.0,
            0.0,
            44.5,
            80.0,
            {"1": "GND"},
        ),
    ]

    row_pinout = row_connector_pinout()
    column_pinout = column_connector_pinout()
    parts.extend(
        [
            PlacedPart(
                "J_ROW",
                ROW_CONNECTOR_FOOTPRINT_NAME,
                ROW_CONNECTOR_FOOTPRINT_NAME,
                152.0,
                22.0,
                270.0,
                140.0,
                22.0,
                row_pinout,
            ),
            PlacedPart(
                "J_COL",
                COLUMN_CONNECTOR_FOOTPRINT_NAME,
                COLUMN_CONNECTOR_FOOTPRINT_NAME,
                152.0,
                62.0,
                270.0,
                140.0,
                62.0,
                column_pinout,
            ),
        ]
    )

    for row_number in range(1, MATRIX_CHANNEL_COUNT + 1):
        farm_index = row_number - 1
        column_index = farm_index % 8
        farm_row_index = farm_index // 8
        origin_x_mm = 48.0 + column_index * 10.0
        origin_y_mm = 26.0 + farm_row_index * 12.0
        drain_net = row_net_name(row_number)
        parts.append(
            PlacedPart(
                f"Q_ROW{row_number:02d}",
                "AO3403",
                "SOT-23",
                origin_x_mm,
                origin_y_mm,
                0.0,
                origin_x_mm - 1.0,
                origin_y_mm - 5.2,
                {
                    "2": "LED_4V1",
                    "3": drain_net,
                },
            )
        )
        parts.append(
            PlacedPart(
                f"R_G{row_number:02d}",
                "33R",
                "R_0402_1005Metric",
                origin_x_mm + 4.2,
                origin_y_mm + 1.6,
                0.0,
                origin_x_mm + 4.2,
                origin_y_mm + 5.2,
                {},
            )
        )
        parts.append(
            PlacedPart(
                f"R_PU{row_number:02d}",
                "47k",
                "R_0402_1005Metric",
                origin_x_mm + 4.2,
                origin_y_mm - 1.6,
                0.0,
                origin_x_mm + 5.5,
                origin_y_mm - 5.2,
                {"2": "LED_4V1"},
            )
        )

    reserve_y_mm = 98.0
    reserve_nets = (
        "IMU_SDA",
        "IMU_SCL",
        "IMU_INT1",
        "LED_CLK",
        "LED_SDI",
        "LED_LE",
        "LED_OE_N",
        "ROW_A0",
        "ROW_A1",
        "ROW_A2",
        "ROW_A3",
        "DEC_A_EN_N",
        "DEC_B_EN_N",
        "ROW_XLAT_OE_N",
        "LED_EN",
    )
    for index, net_name in enumerate(reserve_nets):
        origin_x_mm = 8.0 + index * 8.5
        parts.append(
            PlacedPart(
                f"RP{index + 1:02d}",
                net_name,
                "R_0402_1005Metric",
                origin_x_mm,
                reserve_y_mm,
                0.0,
                origin_x_mm,
                reserve_y_mm - 2.4,
                {"1": net_name},
            )
        )
    return parts


def add_electronics_components(
    board: pcbnew.BOARD,
    repository_root: Path,
) -> None:
    library_path = repository_root / REPOSITORY_ELECTRONICS_LIBRARY
    connector_library_path = repository_root / REPOSITORY_CONNECTOR_LIBRARY
    for part in electronics_parts():
        source_library = (
            connector_library_path
            if part.footprint_name in {
                ROW_CONNECTOR_FOOTPRINT_NAME,
                COLUMN_CONNECTOR_FOOTPRINT_NAME,
            }
            else library_path
        )
        footprint = load_footprint(source_library, part.footprint_name)
        footprint.SetReference(part.reference)
        footprint.SetValue(part.value)
        footprint.SetPosition(pcbnew.VECTOR2I_MM(part.x_mm, part.y_mm))
        footprint.SetOrientationDegrees(part.rotation_degrees)
        footprint.Value().SetVisible(False)
        reference_is_dense_farm_passive = part.reference.startswith(
            ("R_G", "R_PU")
        )
        footprint.Reference().SetLayer(
            pcbnew.F_Fab if reference_is_dense_farm_passive else pcbnew.F_SilkS
        )
        footprint.Reference().SetTextSize(
            pcbnew.VECTOR2I_MM(
                MINIMUM_SILK_TEXT_HEIGHT_MM,
                MINIMUM_SILK_TEXT_HEIGHT_MM,
            )
        )
        footprint.Reference().SetTextThickness(
            pcbnew.FromMM(MINIMUM_SILK_TEXT_THICKNESS_MM)
        )
        footprint.Reference().SetPosition(
            pcbnew.VECTOR2I_MM(part.reference_x_mm, part.reference_y_mm)
        )
        footprint.Reference().SetVisible(True)
        board.Add(footprint)
        nets = {
            pad_number: create_net(board, net_name)
            for pad_number, net_name in part.pad_nets.items()
        }
        assign_pad_nets(footprint, nets)

def generate_electronics_board(repository_root: Path) -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    apply_design_rules(board, copper_layer_count=4)
    add_rectangle(
        board,
        pcbnew.Edge_Cuts,
        0.0,
        0.0,
        ELECTRONICS_WIDTH_MM,
        ELECTRONICS_HEIGHT_MM,
        EDGE_LINE_WIDTH_MM,
    )
    branding_top_mm = ELECTRONICS_HEIGHT_MM - BRANDING_STRIP_HEIGHT_MM
    add_rectangle(
        board,
        pcbnew.Dwgs_User,
        0.5,
        branding_top_mm,
        ELECTRONICS_WIDTH_MM - 0.5,
        ELECTRONICS_HEIGHT_MM - 0.5,
        GUIDE_LINE_WIDTH_MM,
    )
    add_text(
        board,
        "BRANDING KEEPOUT",
        ELECTRONICS_WIDTH_MM / 2,
        branding_top_mm + 1.2,
        pcbnew.Dwgs_User,
        text_size_mm=0.8,
    )
    add_electronics_components(board, repository_root)
    add_rectangle(
        board,
        pcbnew.Dwgs_User,
        4.0,
        84.0,
        ELECTRONICS_WIDTH_MM - 4.0,
        102.0,
        GUIDE_LINE_WIDTH_MM,
    )
    add_text(
        board,
        "SCAN AND IMU SIGNAL RESERVE",
        ELECTRONICS_WIDTH_MM / 2,
        86.2,
        pcbnew.Dwgs_User,
        text_size_mm=0.8,
    )
    add_text(
        board,
        "PCB CREATED BY ILLIA PLIUKHIN",
        ELECTRONICS_WIDTH_MM / 2,
        ELECTRONICS_HEIGHT_MM - 3.4,
        pcbnew.F_SilkS,
        text_size_mm=MINIMUM_SILK_TEXT_HEIGHT_MM,
    )
    add_star(
        board,
        ELECTRONICS_WIDTH_MM / 2,
        ELECTRONICS_HEIGHT_MM - 1.3,
        outer_radius_mm=0.7,
        inner_radius_mm=0.3,
        layer=pcbnew.F_SilkS,
    )
    add_text(
        board,
        "MONO ELECTRONICS / 32 ROW x 32 COL FFC",
        ELECTRONICS_WIDTH_MM / 2,
        2.0,
        pcbnew.Cmts_User,
        text_size_mm=0.8,
    )
    return board


def write_project_file(
    output_directory: Path,
    project_name: str,
    template_path: Path,
    unconnected_is_error: bool,
) -> None:
    project_text = template_path.read_text()
    project_text = project_text.replace(
        '"filename": "wearable_20x20.kicad_pro"',
        f'"filename": "{project_name}.kicad_pro"',
    )
    if not unconnected_is_error:
        project_text = project_text.replace(
            '"unconnected_items": "error"',
            '"unconnected_items": "warning"',
        )
    (output_directory / f"{project_name}.kicad_pro").write_text(project_text)


def generate_boards(repository_root: Path) -> None:
    template_path = (
        repository_root / "hardware/wearable_20x20/wearable_20x20.kicad_pro"
    )
    for variant in PANEL_VARIANTS:
        output_directory = repository_root / "hardware" / variant.name
        output_directory.mkdir(parents=True, exist_ok=True)
        board = generate_panel_board(variant, repository_root)
        pcbnew.SaveBoard(
            str(output_directory / f"{variant.name}.kicad_pcb"),
            board,
        )
        write_project_file(output_directory, variant.name, template_path, True)
        print(f"Generated {output_directory / variant.name}.kicad_pcb")

    electronics_directory = repository_root / "hardware/mono_electronics"
    electronics_directory.mkdir(parents=True, exist_ok=True)
    electronics_board = generate_electronics_board(repository_root)
    pcbnew.SaveBoard(
        str(electronics_directory / "mono_electronics.kicad_pcb"),
        electronics_board,
    )
    write_project_file(
        electronics_directory,
        "mono_electronics",
        template_path,
        False,
    )
    print(f"Generated {electronics_directory / 'mono_electronics.kicad_pcb'}")


if __name__ == "__main__":
    generate_boards(Path(__file__).resolve().parents[2])
