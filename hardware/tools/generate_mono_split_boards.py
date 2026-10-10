from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import math
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pcbnew
from mono_split_esp32 import esp32_s3_fn8_pad_nets
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

# ESP32-S3FN8 at 270°: functional GPIOs on the west face, east of the row fan-in
# at x≈37; USB/strap cluster stays west toward ESD.
MCU_X_MM = 46.0
MCU_Y_MM = 10.0
MCU_ROTATION_DEGREES = 270.0
MCU_REFERENCE_X_MM = 54.0
MCU_REFERENCE_Y_MM = 3.0
MCU_GND_IN2_SPINE_X_MM = 26.5
MCU_AON_IN2_SPINE_X_MM = 32.5
MCU_GND_IN2_HOOK_Y_MM = 8.55


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


DECODER_Y_PINS = (
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "13",
    "14",
    "15",
    "16",
    "17",
)


def row_gate_net(row_number: int) -> str:
    return f"ROW_{row_number:02d}_GATE"


def row_select_net(row_number: int) -> str:
    return f"ROW_{row_number:02d}_Y"


def translated_row_net(net_name: str) -> str:
    return f"{net_name}_4V"


def decoder_pad_nets(first_row: int) -> dict[str, str]:
    enable_net = translated_row_net(
        "DEC_A_EN_N" if first_row == 1 else "DEC_B_EN_N"
    )
    nets = {
        "12": "GND",
        "18": enable_net,
        "19": "GND",
        "20": translated_row_net("ROW_A3"),
        "21": translated_row_net("ROW_A2"),
        "22": translated_row_net("ROW_A1"),
        "23": translated_row_net("ROW_A0"),
        "24": "LED_4V1",
    }
    for offset, pin in enumerate(DECODER_Y_PINS):
        nets[pin] = row_select_net(first_row + offset)
    return nets


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
                "A6": "USB_D_P",
                "A7": "USB_D_N",
                "B6": "USB_D_P",
                "B7": "USB_D_N",
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
            {
                "1": "USB_D_P",
                "2": "GND",
                "3": "USB_D_N",
                "4": "GND",
                "5": "GND",
                "6": "USB_D_P",
            },
        ),
        PlacedPart(
            "U1",
            "ESP32-S3FN8",
            "QFN-56-1EP_7x7mm_P0.4mm_EP5.6x5.6mm",
            MCU_X_MM,
            MCU_Y_MM,
            MCU_ROTATION_DEGREES,
            MCU_REFERENCE_X_MM,
            MCU_REFERENCE_Y_MM,
            esp32_s3_fn8_pad_nets(),
        ),
        PlacedPart(
            "Y1",
            "L327S400H11L",
            "Crystal_SMD_3225-4Pin_3.2x2.5mm",
            54.0,
            4.2,
            0.0,
            54.0,
            4.2,
            {
                "1": "XTAL_P",
                "2": "GND",
                "3": "XTAL_N",
                "4": "GND",
            },
        ),
        PlacedPart(
            "U_IMU",
            "BMI270",
            "Bosch_LGA-14_3x2.5mm_P0.5mm",
            62.35,
            4.5,
            0.0,
            70.35,
            4.5,
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
            "Texas_DLH0010A_WSON-10-1EP_2x2mm_P0.4mm_EP0.9x1.5mm",
            18.0,
            42.0,
            0.0,
            18.0,
            36.2,
            {
                # DLH top view: left 1 SYS, 2 BAT, 3 STAT2, 4 /CE, 5 GND.
                # Right, bottom to top: 6 TS/MR, 7 ILIM/VSET, 8 ISET, 9 STAT1, 10 IN.
                # ISET is 600 ohm: 500 mA, the 0.5C point of the 1000 mAh Jauch pack.
                # STAT pins stay open. /CE is held low so charge is enabled.
                # TS/MR is the pack thermistor, not an onboard resistor.
                "1": "SYS",
                "2": "BAT_RAW",
                "4": "GND",
                "5": "GND",
                "6": "TS_MR",
                "7": "ILIM_VSET",
                "8": "ISET",
                "10": "VBUS",
                "11": "GND",
            },
        ),
        PlacedPart(
            "J_BAT",
            "53398-0371",
            "Molex_PicoBlade_53398-0371_1x03-1MP_P1.25mm_Vertical",
            6.8,
            58.0,
            90.0,
            6.8,
            50.5,
            {
                # Jauch LP523450JU drawing, wires leaving the cell: black on
                # top next to the minus mark, yellow in the middle, red on
                # the bottom next to the plus mark. Molex 51021-0300 still
                # numbers pin 1 red BAT+, pin 2 yellow NTC, pin 3 black GND.
                # Rotated so that order is top to bottom on the board.
                "1": "BAT_RAW",
                "2": "TS_MR",
                "3": "GND",
            },
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
            {
                # TPS63802 DLA, top view: 1 EN, 2 MODE, 3 AGND, 4 FB, 5 PG,
                # 6 VOUT, 7 L2, 8 GND, 9 L1, 10 VIN. PG stays open.
                "1": "LED_EN",
                "2": "GND",
                "3": "GND",
                "4": "LED_FB",
                "6": "LED_4V1",
                "7": "SW_L2",
                "8": "GND",
                "9": "SW_L1",
                "10": "SYS",
                "11": "GND",
            },
        ),
        PlacedPart(
            "L_LED",
            "DFE201612E-R47M",
            "L_Murata_DFE201610P",
            42.0,
            48.0,
            0.0,
            47.0,
            41.2,
            {"1": "SW_L2", "2": "SW_L1"},
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
            {
                # TPS7A2033 DBV: 1 IN, 2 GND, 3 EN, 4 N/C, 5 OUT.
                # EN tied to IN. The internal pulldown would hold the LDO off.
                "1": "SYS",
                "2": "GND",
                "3": "SYS",
                "5": "AON_3V3",
            },
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
            {
                # TPS22917 DBV pin table: 1 VIN, 2 GND, 3 ON, 4 CT, 5 QOD, 6 VOUT.
                "1": "AON_3V3",
                "2": "GND",
                "3": "LED_LOGIC_EN",
                "5": "LED_QOD",
                "6": "LED_LOGIC_3V3",
            },
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
            {
                "1": "AON_3V3",
                "2": "GND",
                "3": "AUDIO_EN",
                "6": "AUDIO_3V3",
            },
        ),
        PlacedPart(
            "U_GAUGE",
            "MAX17048",
            "Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm",
            18.0,
            50.0,
            0.0,
            18.0,
            54.2,
            {},
        ),
        PlacedPart(
            "MIC1",
            "MA-HFA381",
            "Knowles_LGA-5_3.5x2.65mm",
            128.0,
            36.0,
            0.0,
            128.0,
            30.5,
            {},
        ),
        PlacedPart(
            "U_AUDIO",
            "TLV9001",
            "SOT-353_SC-70-5",
            128.0,
            46.0,
            0.0,
            136.0,
            46.0,
            {},
        ),
        PlacedPart(
            "SW1",
            "KMR2",
            "SW_Push_1P1T_NO_CK_KMR2",
            6.5,
            10.5,
            0.0,
            14.5,
            10.5,
            {"1": "GPIO0_BOOT", "2": "GND"},
        ),
        PlacedPart(
            "U_ROW_XLAT",
            "SN74LVC8T245",
            "VQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm",
            70.0,
            14.5,
            0.0,
            57.0,
            11.2,
            {
                "1": "AON_3V3",
                "2": "AON_3V3",
                "3": "ROW_A0",
                "4": "ROW_A1",
                "5": "ROW_A2",
                "6": "ROW_A3",
                "7": "DEC_A_EN_N",
                "8": "DEC_B_EN_N",
                "9": "GND",
                "10": "GND",
                "11": "GND",
                "12": "GND",
                "13": "GND",
                "16": translated_row_net("DEC_B_EN_N"),
                "17": translated_row_net("DEC_A_EN_N"),
                "18": translated_row_net("ROW_A3"),
                "19": translated_row_net("ROW_A2"),
                "20": translated_row_net("ROW_A1"),
                "21": translated_row_net("ROW_A0"),
                "22": "ROW_XLAT_OE_N",
                "23": "LED_4V1",
                "24": "LED_4V1",
            },
        ),
        PlacedPart(
            "U_DEC_A",
            "74HC154",
            "TSSOP-24_4.4x7.8mm_P0.65mm",
            86.0,
            14.5,
            0.0,
            86.0,
            8.5,
            decoder_pad_nets(1),
        ),
        PlacedPart(
            "U_DEC_B",
            "74HC154",
            "TSSOP-24_4.4x7.8mm_P0.65mm",
            102.0,
            14.5,
            0.0,
            102.0,
            8.5,
            decoder_pad_nets(17),
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
            {
                "1": "GND",
                "2": "LED_CLK",
                "3": "LED_CLK_PRE",
                "4": "GND",
                "5": "LED_SDI",
                "6": "LED_SDI_PRE",
                "7": "GND",
                "8": "LED_LE_PRE",
                "9": "LED_LE",
                "10": "GND",
                "11": "LED_OE_Y",
                "12": "LED_OE_N",
                "13": "GND",
                "14": "LED_LOGIC_3V3",
            },
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
                "2": "LED_SDI_Y",
                "3": "LED_CLK_Y",
                "4": "LED_LE_Y",
                "21": "LED_OE_Y",
                "22": "LED_SDO",
                "23": "REXT1",
                "24": "LED_LOGIC_3V3",
            },
        ),
        PlacedPart(
            "U_LED2",
            "MBI5124GP-B",
            "SSOP-24_3.9x8.7mm_P0.635mm",
            106.0,
            76.0,
            0.0,
            106.0,
            67.0,
            {
                str(5 + offset): column_net_name(17 + offset)
                for offset in range(16)
            }
            | {
                "1": "GND",
                "2": "LED_SDO",
                "3": "LED_CLK_Y",
                "4": "LED_LE_Y",
                "21": "LED_OE_Y",
                "23": "REXT2",
                "24": "LED_LOGIC_3V3",
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
            {"1": "REXT1", "2": "GND"},
        ),
        PlacedPart(
            "R_EXT2",
            "1.82k",
            "R_0402_1005Metric",
            118.0,
            76.0,
            0.0,
            118.0,
            81.0,
            {"1": "REXT2", "2": "GND"},
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
            {"1": "VBUS", "2": "GND"},
        ),
        PlacedPart(
            "C_MCU1",
            "10u",
            "C_0805_2012Metric",
            40.0,
            15.0,
            0.0,
            40.0,
            15.0,
            {"1": "AON_3V3", "2": "GND"},
        ),
        PlacedPart(
            "R_CHIP_PU",
            "10k",
            "R_0402_1005Metric",
            38.0,
            11.5,
            0.0,
            38.0,
            11.5,
            {"1": "AON_3V3", "2": "CHIP_PU"},
        ),
        PlacedPart(
            "C_CHIP_PU",
            "1u",
            "C_0603_1608Metric",
            31.5,
            14.8,
            0.0,
            31.5,
            14.8,
            {"1": "CHIP_PU", "2": "GND"},
        ),
        PlacedPart(
            "R_BOOT0",
            "10k",
            "R_0402_1005Metric",
            40.0,
            17.5,
            0.0,
            40.0,
            17.5,
            {"1": "AON_3V3", "2": "GPIO0_BOOT"},
        ),
        PlacedPart(
            "R_USB_P",
            "22R",
            "R_0402_1005Metric",
            32.0,
            7.6,
            0.0,
            32.0,
            7.6,
            {"1": "USB_D_P", "2": "USB_D_P_MCU"},
        ),
        PlacedPart(
            "R_USB_N",
            "22R",
            "R_0402_1005Metric",
            35.8,
            9.4,
            0.0,
            35.8,
            9.4,
            {"1": "USB_D_N", "2": "USB_D_N_MCU"},
        ),
        PlacedPart(
            "C_XTAL1",
            "10p",
            "C_0402_1005Metric",
            50.2,
            1.9,
            0.0,
            50.2,
            1.9,
            {"1": "XTAL_P", "2": "GND"},
        ),
        PlacedPart(
            "C_XTAL2",
            "10p",
            "C_0402_1005Metric",
            57.8,
            1.9,
            0.0,
            57.8,
            1.9,
            {"1": "XTAL_N", "2": "GND"},
        ),
        PlacedPart(
            "C_SYS",
            "10u",
            "C_0805_2012Metric",
            39.2,
            43.6,
            0.0,
            39.2,
            43.6,
            {"1": "SYS", "2": "GND"},
        ),
        PlacedPart(
            "C_LED1",
            "22u",
            "C_0805_2012Metric",
            30.2,
            55.0,
            0.0,
            30.2,
            55.0,
            {"1": "LED_4V1", "2": "GND"},
        ),
        PlacedPart(
            "C_LED2",
            "22u",
            "C_0805_2012Metric",
            30.2,
            57.5,
            0.0,
            30.2,
            57.5,
            {"1": "LED_4V1", "2": "GND"},
        ),
        PlacedPart(
            "C_LDO_IN",
            "1u",
            "C_0603_1608Metric",
            28.2,
            59.6,
            0.0,
            28.2,
            59.6,
            {"1": "GND", "2": "SYS"},
        ),
        PlacedPart(
            "C_LDO_OUT",
            "1u",
            "C_0603_1608Metric",
            38.6,
            64.3,
            0.0,
            38.6,
            64.3,
            {"1": "AON_3V3", "2": "GND"},
        ),
        PlacedPart(
            "TH_PCB",
            "NTC10K",
            "R_0402_1005Metric",
            8.0,
            42.0,
            0.0,
            14.0,
            42.0,
            {},
        ),
        PlacedPart(
            "TP1",
            "AON_3V3",
            "R_0402_1005Metric",
            28.0,
            76.0,
            0.0,
            28.0,
            76.0,
            {"1": "AON_3V3", "2": "AON_3V3"},
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
                182.0,
                22.0,
                270.0,
                170.0,
                22.0,
                row_pinout,
            ),
            PlacedPart(
                "J_COL",
                COLUMN_CONNECTOR_FOOTPRINT_NAME,
                COLUMN_CONNECTOR_FOOTPRINT_NAME,
                182.0,
                62.0,
                270.0,
                170.0,
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
        gate_net = row_gate_net(row_number)
        select_net = row_select_net(row_number)
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
                    "1": gate_net,
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
                {"1": gate_net, "2": select_net},
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
                {"1": gate_net, "2": "LED_4V1"},
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
        "LED_LOGIC_EN",
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
    # Safe-reset pulls for the translator. Centers sit above the address
    # escapes; pad 1 faces the signal coming from the left.
    for reference, value, signal_net, rail_net, center_x, center_y in (
        ("R_ADDR0", "100k", "ROW_A0_4V", "GND", 78.0, 1.40),
        ("R_ADDR1", "100k", "ROW_A1_4V", "GND", 80.6, 2.10),
        ("R_ADDR2", "100k", "ROW_A2_4V", "GND", 83.2, 2.80),
        ("R_ADDR3", "100k", "ROW_A3_4V", "GND", 85.8, 3.50),
        ("R_ENA", "47k", "DEC_A_EN_N_4V", "LED_4V1", 88.6, 4.20),
        ("R_ENB", "47k", "DEC_B_EN_N_4V", "LED_4V1", 91.2, 4.90),
        ("R_XOE", "10k", "AON_3V3", "ROW_XLAT_OE_N", 66.2, 2.30),
    ):
        parts.append(
            PlacedPart(
                reference,
                value,
                "R_0402_1005Metric",
                center_x,
                center_y,
                0.0,
                center_x,
                center_y,
                {"1": signal_net, "2": rail_net},
            )
        )
    for reference, value, pad1_net, pad2_net, center_x, center_y in (
        ("R_SDI_PD", "100k", "LED_SDI", "GND", 34.2, 73.2),
        ("R_CLK_PD", "100k", "LED_CLK", "GND", 30.0, 73.2),
        ("R_LE_PD", "100k", "LED_LE", "GND", 40.5, 73.2),
        ("R_OE_PU", "47k", "LED_OE_N", "AON_3V3", 47.2, 73.2),
        ("R_CLK_SER", "22R", "LED_CLK_PRE", "LED_CLK_Y", 70.2, 68.45),
        ("R_SDI_SER", "22R", "LED_SDI_PRE", "LED_SDI_Y", 80.2, 68.95),
        ("R_LE_SER", "22R", "LED_LE_PRE", "LED_LE_Y", 77.2, 71.00),
        ("R_OE_YPU", "47k", "LED_OE_Y", "LED_LOGIC_3V3", 73.5, 73.8),
        ("R_FB_TOP", "681k", "LED_4V1", "LED_FB", 26.8, 50.6),
        ("R_FB_BOT", "91k", "LED_FB", "GND", 24.2, 49.2),
        ("R_EN_PD", "100k", "LED_EN", "GND", 27.2, 45.15),
        ("R_LOGIC_PD", "100k", "LED_LOGIC_EN", "GND", 15.4, 64.6),
        ("R_QOD", "1k", "LED_QOD", "LED_LOGIC_3V3", 25.6, 63.2),
        ("R_AUD_PD", "100k", "AUDIO_EN", "GND", 15.11, 72.5),
        ("R_ILIM", "18k", "ILIM_VSET", "GND", 22.8, 42.6),
        ("R_ISET", "600R", "ISET", "GND", 21.6, 40.6),
    ):
        parts.append(
            PlacedPart(
                reference,
                value,
                "R_0402_1005Metric",
                center_x,
                center_y,
                0.0,
                center_x,
                center_y,
                {"1": pad1_net, "2": pad2_net},
            )
        )
    for reference, value, pad1_net, pad2_net, center_x, center_y in (
        ("C_CHG_SYS", "10u", "GND", "SYS", 14.2, 38.2),
        ("C_CHG_BAT", "10u", "GND", "BAT_RAW", 15.2, 46.3),
        ("C_CHG_IN", "10u", "VBUS", "GND", 23.6, 38.8),
    ):
        parts.append(
            PlacedPart(
                reference,
                value,
                "C_0805_2012Metric",
                center_x,
                center_y,
                0.0,
                center_x,
                center_y,
                {"1": pad1_net, "2": pad2_net},
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
            (
                "R_G",
                "R_PU",
                "R_ADDR",
                "R_EN",
                "R_XOE",
                "R_CLK",
                "R_SDI",
                "R_LE",
                "R_OE",
                "R_FB",
                "R_LOGIC",
                "R_QOD",
                "R_AUD",
                "C_LED",
                "C_SYS",
                "C_LDO",
                "C_CHG",
                "R_ILIM",
                "R_ISET",
            )
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


def footprint_by_reference(
    board: pcbnew.BOARD,
    reference: str,
) -> pcbnew.FOOTPRINT:
    for footprint in board.GetFootprints():
        if footprint.GetReference() == reference:
            return footprint
    raise ValueError(f"Unable to find {reference}")


def route_side_escape(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    pad_x_mm: float,
    pad_y_mm: float,
    escape_x_mm: float,
) -> None:
    add_track(
        board,
        net,
        pcbnew.F_Cu,
        pad_x_mm,
        pad_y_mm,
        escape_x_mm,
        pad_y_mm,
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, escape_x_mm, pad_y_mm)


def route_sorted_fan_in(
    board: pcbnew.BOARD,
    sources: list[tuple[pcbnew.NETINFO_ITEM, float, float, float]],
    destinations: list[tuple[float, float]],
    highway_y0_mm: float,
    entry_x0_mm: float,
    travel_on_source_y: bool,
) -> None:
    order = sorted(range(len(destinations)), key=lambda index: destinations[index][1])
    for sequence, index in enumerate(order):
        net, source_x_mm, source_y_mm, escape_x_mm = sources[index]
        dest_x_mm, dest_y_mm = destinations[index]
        entry_x_mm = entry_x0_mm - sequence * 0.45
        route_side_escape(board, net, source_x_mm, source_y_mm, escape_x_mm)
        if travel_on_source_y:
            travel_y_mm = 83.0 + sequence * 0.45
            add_track(
                board,
                net,
                pcbnew.In2_Cu,
                escape_x_mm,
                source_y_mm,
                escape_x_mm,
                travel_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
            add_through_via(
                board, net, escape_x_mm, travel_y_mm, diameter_mm=0.40
            )
            add_track(
                board,
                net,
                pcbnew.In1_Cu,
                escape_x_mm,
                travel_y_mm,
                entry_x_mm,
                travel_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
            add_through_via(
                board, net, entry_x_mm, travel_y_mm, diameter_mm=0.40
            )
            add_track(
                board,
                net,
                pcbnew.In2_Cu,
                entry_x_mm,
                travel_y_mm,
                entry_x_mm,
                dest_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
        else:
            highway_y_mm = highway_y0_mm + sequence * 0.50
            add_track(
                board,
                net,
                pcbnew.In2_Cu,
                escape_x_mm,
                source_y_mm,
                escape_x_mm,
                highway_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
            add_through_via(
                board, net, escape_x_mm, highway_y_mm, diameter_mm=0.40
            )
            add_track(
                board,
                net,
                pcbnew.In1_Cu,
                escape_x_mm,
                highway_y_mm,
                entry_x_mm,
                highway_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
            add_through_via(
                board, net, entry_x_mm, highway_y_mm, diameter_mm=0.40
            )
            add_track(
                board,
                net,
                pcbnew.In2_Cu,
                entry_x_mm,
                highway_y_mm,
                entry_x_mm,
                dest_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
        add_through_via(board, net, entry_x_mm, dest_y_mm, diameter_mm=0.40)
        add_track(
            board,
            net,
            pcbnew.F_Cu,
            entry_x_mm,
            dest_y_mm,
            dest_x_mm,
            dest_y_mm,
            FAN_IN_TRACK_WIDTH_MM,
        )


def route_electronics_matrix(board: pcbnew.BOARD) -> None:
    row_connector = footprint_by_reference(board, "J_ROW")
    column_connector = footprint_by_reference(board, "J_COL")
    row_sources = []
    row_destinations = []
    for pin_index in range(MATRIX_CHANNEL_COUNT):
        transistor = footprint_by_reference(board, f"Q_ROW{pin_index + 1:02d}")
        drain_x_mm, drain_y_mm = millimeters(get_pad(transistor, "3").GetPosition())
        net = get_pad(transistor, "3").GetNet()
        farm_row = pin_index // 8
        row_sources.append(
            (net, drain_x_mm, drain_y_mm, drain_x_mm - 3.2 - farm_row * 0.4)
        )
        row_destinations.append(
            millimeters(get_pad(row_connector, str(pin_index + 1)).GetPosition())
        )
    route_sorted_fan_in(
        board,
        row_sources,
        row_destinations,
        highway_y0_mm=104.0,
        entry_x0_mm=156.0,
        travel_on_source_y=False,
    )

    column_sources = []
    column_destinations = []
    for pin_index in range(MATRIX_CHANNEL_COUNT):
        driver_name = "U_LED1" if pin_index < 16 else "U_LED2"
        output_index = pin_index if pin_index < 16 else pin_index - 16
        driver_pad = str(5 + output_index)
        driver = footprint_by_reference(board, driver_name)
        pad_x_mm, pad_y_mm = millimeters(get_pad(driver, driver_pad).GetPosition())
        center_x_mm, _ = millimeters(driver.GetPosition())
        side_index = output_index if output_index < 8 else output_index - 8
        if pad_x_mm < center_x_mm:
            outward_mm = 4.0 if driver_name == "U_LED1" else 1.8
            escape_x_mm = pad_x_mm - outward_mm - side_index * 0.40
        else:
            escape_x_mm = pad_x_mm + 1.8 + side_index * 0.40
        net = get_pad(driver, driver_pad).GetNet()
        column_sources.append((net, pad_x_mm, pad_y_mm, escape_x_mm))
        column_destinations.append(
            millimeters(get_pad(column_connector, str(pin_index + 1)).GetPosition())
        )
    route_sorted_fan_in(
        board,
        column_sources,
        column_destinations,
        highway_y0_mm=120.4,
        entry_x0_mm=174.0,
        travel_on_source_y=True,
    )

def route_led_anode_rail(board: pcbnew.BOARD) -> None:
    pads: list[tuple[float, float, float, pcbnew.NETINFO_ITEM]] = []
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if reference.startswith("Q_ROW"):
            via_direction = 1.0
        elif reference.startswith("R_PU"):
            via_direction = -1.0
        else:
            continue
        pad = get_pad(footprint, "2")
        if pad.GetNetname() != "LED_4V1":
            continue
        pad_x_mm, pad_y_mm = millimeters(pad.GetPosition())
        pads.append((pad_x_mm, pad_y_mm, via_direction, pad.GetNet()))
    if not pads:
        return
    net = pads[0][3]
    trunk_x_mm = 140.0
    via_ys: list[float] = []
    for pad_x_mm, pad_y_mm, via_direction, _ in pads:
        via_y_mm = pad_y_mm + via_direction * 1.5
        via_ys.append(via_y_mm)
        add_track(
            board,
            net,
            pcbnew.F_Cu,
            pad_x_mm,
            pad_y_mm,
            pad_x_mm,
            via_y_mm,
            0.20,
        )
        add_through_via(board, net, pad_x_mm, via_y_mm, diameter_mm=0.40)
        add_track(
            board,
            net,
            pcbnew.In1_Cu,
            pad_x_mm,
            via_y_mm,
            trunk_x_mm,
            via_y_mm,
            0.25,
        )
    add_track(
        board,
        net,
        pcbnew.In1_Cu,
        trunk_x_mm,
        min(via_ys),
        trunk_x_mm,
        max(via_ys),
        0.50,
    )


def route_imu_sense(board: pcbnew.BOARD) -> None:
    imu = footprint_by_reference(board, "U_IMU")
    reserve = {}
    for footprint in board.GetFootprints():
        if footprint.GetReference().startswith("RP"):
            pad = get_pad(footprint, "1")
            reserve[pad.GetNetname()] = pad
    routes = (
        ("14", "IMU_SDA", 157.4, 4.15, 100.2, False),
        ("13", "IMU_SCL", 158.45, 4.85, 100.9, False),
        ("4", "IMU_INT1", 159.0, 5.6, 101.6, True),
    )
    for pad_number, net_name, lane_x_mm, top_y_mm, bottom_y_mm, escape_left in routes:
        imu_pad = get_pad(imu, pad_number)
        end_pad = reserve[net_name]
        net = imu_pad.GetNet()
        start_x_mm, start_y_mm = millimeters(imu_pad.GetPosition())
        end_x_mm, end_y_mm = millimeters(end_pad.GetPosition())
        rise_x_mm = start_x_mm - 1.6 if escape_left else start_x_mm
        if escape_left:
            add_track(
                board, net, pcbnew.F_Cu,
                start_x_mm, start_y_mm, rise_x_mm, start_y_mm,
                FAN_IN_TRACK_WIDTH_MM,
            )
        add_track(
            board, net, pcbnew.F_Cu,
            rise_x_mm, start_y_mm, rise_x_mm, top_y_mm,
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, rise_x_mm, top_y_mm, diameter_mm=0.40)
        add_track(
            board, net, pcbnew.In1_Cu,
            rise_x_mm, top_y_mm, lane_x_mm, top_y_mm,
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, lane_x_mm, top_y_mm, diameter_mm=0.40)
        add_track(
            board, net, pcbnew.In2_Cu,
            lane_x_mm, top_y_mm, lane_x_mm, bottom_y_mm,
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, lane_x_mm, bottom_y_mm, diameter_mm=0.40)
        add_track(
            board, net, pcbnew.In1_Cu,
            lane_x_mm, bottom_y_mm, end_x_mm, bottom_y_mm,
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, end_x_mm, bottom_y_mm, diameter_mm=0.40)
        add_track(
            board, net, pcbnew.F_Cu,
            end_x_mm, bottom_y_mm, end_x_mm, end_y_mm,
            FAN_IN_TRACK_WIDTH_MM,
        )


def route_net_polyline(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    points_mm: list[tuple[float, float]],
    width_mm: float,
) -> None:
    net = board.FindNet(net_name)
    add_polyline(board, net, layer, points_mm, width_mm)


def route_reserve_drop(
    board: pcbnew.BOARD,
    net_name: str,
    drop_x_mm: float,
    corridor_y_mm: float,
    pad_x_mm: float,
    bottom_y_mm: float = 97.35,
) -> None:
    net = board.FindNet(net_name)
    add_through_via(board, net, drop_x_mm, corridor_y_mm, diameter_mm=0.40)
    route_net_polyline(
        board,
        net_name,
        pcbnew.In2_Cu,
        [(drop_x_mm, corridor_y_mm), (drop_x_mm, bottom_y_mm)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, drop_x_mm, bottom_y_mm, diameter_mm=0.40)
    if abs(drop_x_mm - pad_x_mm) > 0.01:
        route_net_polyline(
            board,
            net_name,
            pcbnew.In1_Cu,
            [(drop_x_mm, bottom_y_mm), (pad_x_mm, bottom_y_mm)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, net, pad_x_mm, bottom_y_mm, diameter_mm=0.40)
    route_net_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [(pad_x_mm, bottom_y_mm), (pad_x_mm, 98.00)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_pad_escape(
    board: pcbnew.BOARD,
    net_name: str,
    pad_x_mm: float,
    pad_y_mm: float,
    via_x_mm: float,
    corridor_y_mm: float,
) -> None:
    net = board.FindNet(net_name)
    route_net_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [(pad_x_mm, pad_y_mm), (via_x_mm, pad_y_mm)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, via_x_mm, pad_y_mm, diameter_mm=0.40)
    route_net_polyline(
        board,
        net_name,
        pcbnew.In2_Cu,
        [(via_x_mm, pad_y_mm), (via_x_mm, corridor_y_mm)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, via_x_mm, corridor_y_mm, diameter_mm=0.40)


def route_power_and_blank(board: pcbnew.BOARD) -> None:
    # USB signal pads share one X. Tie VBUS and GND on In2 so the verticals
    # do not short the pin column, and keep both vias inside the SMD pads.
    vbus = board.FindNet("VBUS")
    add_through_via(board, vbus, 2.05, 20.45, diameter_mm=0.40)
    add_through_via(board, vbus, 2.05, 15.55, diameter_mm=0.40)
    route_net_polyline(
        board, "VBUS", pcbnew.In2_Cu, [(2.05, 15.55), (2.05, 20.45)], 0.20
    )
    usb_cap = footprint_by_reference(board, "C_USB1")
    cap_vbus_x, cap_vbus_y = millimeters(get_pad(usb_cap, "1").GetPosition())
    add_through_via(board, vbus, cap_vbus_x, cap_vbus_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        "VBUS",
        pcbnew.In2_Cu,
        [(cap_vbus_x, cap_vbus_y), (22.65, cap_vbus_y), (22.65, 23.20)],
        0.20,
    )

    gnd = board.FindNet("GND")
    add_through_via(board, gnd, 2.70, 21.25, diameter_mm=0.40)
    add_through_via(board, gnd, 2.70, 14.75, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In2_Cu, [(2.70, 14.75), (2.70, 21.25)], 0.20
    )
    # Shield slots leave a 0.20 mm copper lip. Ride that lip, outside the drill.
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(2.70, 21.25), (2.70, 21.90), (7.50, 21.90)],
        0.15,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(2.70, 14.75), (2.70, 14.08), (13.20, 14.08)],
        0.15,
    )
    add_through_via(board, gnd, 13.20, 14.08, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In2_Cu, [(13.20, 14.08), (13.20, 80.00)], 0.25
    )
    add_through_via(board, gnd, 13.20, 68.20, diameter_mm=0.40)
    add_through_via(board, gnd, 13.20, 80.00, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In1_Cu, [(13.20, 80.00), (49.49, 80.00)], 0.25
    )
    add_through_via(board, gnd, 49.49, 80.00, diameter_mm=0.40)

    add_through_via(board, gnd, 39.50, 9.012, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [
            (39.50, 9.012),
            (39.50, MCU_GND_IN2_HOOK_Y_MM),
            (MCU_GND_IN2_SPINE_X_MM, MCU_GND_IN2_HOOK_Y_MM),
        ],
        0.15,
    )
    add_through_via(
        board, gnd, MCU_GND_IN2_SPINE_X_MM, MCU_GND_IN2_HOOK_Y_MM, diameter_mm=0.40
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.In2_Cu,
        [
            (MCU_GND_IN2_SPINE_X_MM, MCU_GND_IN2_HOOK_Y_MM),
            (MCU_GND_IN2_SPINE_X_MM, 80.00),
        ],
        0.20,
    )
    add_through_via(board, gnd, MCU_GND_IN2_SPINE_X_MM, 80.00, diameter_mm=0.40)

    for pin_x_mm in (83.40, 103.40):
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(pin_x_mm, 72.507), (pin_x_mm, 68.20)],
            0.20,
        )
        add_through_via(board, gnd, pin_x_mm, 68.20, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In1_Cu, [(13.20, 68.20), (103.40, 68.20)], 0.25
    )

    # AON spine east of U1 (46,10): inner layers only so Freerouting can tie MCU pads.
    aon = board.FindNet("AON_3V3")
    add_through_via(board, aon, MCU_AON_IN2_SPINE_X_MM, 9.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(MCU_AON_IN2_SPINE_X_MM, 9.20), (MCU_AON_IN2_SPINE_X_MM, 76.00)],
        0.20,
    )
    add_through_via(board, aon, MCU_AON_IN2_SPINE_X_MM, 76.00, diameter_mm=0.40)

    # MBI5124GP pin configuration: 2 SDI, 3 CLK, 4 LE, 21 OE, 22 SDO,
    # 23 R-EXT, 24 VDD. A lower pin escapes farther from the body so its
    # stub stays clear of the pin above it.
    route_pad_escape(board, "LED_SDI_Y", 83.40, 73.142, 82.30, 67.55)
    route_pad_escape(board, "LED_CLK_Y", 83.40, 73.778, 81.60, 67.05)
    route_pad_escape(board, "LED_LE_Y", 83.40, 74.412, 80.90, 69.60)
    route_pad_escape(board, "LED_LOGIC_3V3", 88.60, 72.507, 90.20, 70.05)
    route_pad_escape(board, "REXT1", 88.60, 73.142, 90.90, 70.50)
    route_pad_escape(board, "LED_SDO", 88.60, 73.778, 91.60, 70.95)
    route_pad_escape(board, "LED_OE_Y", 88.60, 74.412, 92.30, 71.40)
    route_pad_escape(board, "LED_SDO", 103.40, 73.142, 102.40, 70.95)
    route_pad_escape(board, "LED_CLK_Y", 103.40, 73.778, 101.80, 67.05)
    route_pad_escape(board, "LED_LE_Y", 103.40, 74.412, 101.20, 69.60)
    route_pad_escape(board, "LED_LOGIC_3V3", 108.60, 72.507, 109.70, 70.05)
    route_pad_escape(board, "REXT2", 108.60, 73.142, 110.15, 70.50)
    route_pad_escape(board, "LED_OE_Y", 108.60, 74.412, 111.45, 71.40)
    route_net_polyline(
        board, "LED_LOGIC_3V3", pcbnew.In1_Cu, [(90.20, 70.05), (109.70, 70.05)], 0.15
    )
    route_net_polyline(
        board, "REXT1", pcbnew.In1_Cu, [(69.49, 70.50), (90.90, 70.50)], 0.15
    )
    route_net_polyline(
        board, "REXT2", pcbnew.In1_Cu, [(110.15, 70.50), (117.49, 70.50)], 0.15
    )
    route_net_polyline(
        board, "LED_SDO", pcbnew.In1_Cu, [(91.60, 70.95), (102.40, 70.95)], 0.15
    )
    rext1 = board.FindNet("REXT1")
    add_through_via(board, rext1, 69.49, 70.50, diameter_mm=0.40)
    route_net_polyline(
        board, "REXT1", pcbnew.F_Cu, [(69.49, 70.50), (69.49, 76.00)], 0.15
    )
    rext2 = board.FindNet("REXT2")
    add_through_via(board, rext2, 117.49, 70.50, diameter_mm=0.40)
    route_net_polyline(
        board, "REXT2", pcbnew.F_Cu, [(117.49, 70.50), (117.49, 76.00)], 0.15
    )
    route_reserve_drop(board, "LED_SDI", 36.80, 68.70, 41.49)
    route_reserve_drop(board, "LED_CLK", 32.99, 69.15, 32.99)
    route_reserve_drop(board, "LED_LE", 43.20, 69.60, 49.99)
    route_reserve_drop(board, "LED_OE_N", 48.20, 71.40, 58.49, bottom_y_mm=96.70)
    route_led_buffer(board)
    route_converter_rails(board)


def route_buffer_stub(
    board: pcbnew.BOARD,
    net_name: str,
    pad_x_mm: float,
    pad_y_mm: float,
    escape_x_mm: float,
    corridor_y_mm: float,
) -> None:
    route_net_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [(pad_x_mm, pad_y_mm), (escape_x_mm, pad_y_mm), (escape_x_mm, corridor_y_mm)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(
        board,
        board.FindNet(net_name),
        escape_x_mm,
        corridor_y_mm,
        diameter_mm=0.40,
    )


def route_series_on_corridor(
    board: pcbnew.BOARD,
    pre_net: str,
    y_net: str,
    center_x: float,
    center_y: float,
    corridor_y: float,
) -> None:
    for net_name, pad_x in ((pre_net, center_x - 0.51), (y_net, center_x + 0.51)):
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(pad_x, center_y), (pad_x, corridor_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(
            board, board.FindNet(net_name), pad_x, corridor_y, diameter_mm=0.40
        )


def route_buffer_passives(board: pcbnew.BOARD) -> None:
    route_series_on_corridor(board, "LED_CLK_PRE", "LED_CLK_Y", 70.2, 68.45, 67.05)
    route_series_on_corridor(board, "LED_SDI_PRE", "LED_SDI_Y", 80.2, 68.95, 67.55)
    route_series_on_corridor(board, "LED_LE_PRE", "LED_LE_Y", 77.2, 71.00, 69.60)
    pulls = (
        ("LED_CLK", "GND", 30.0, 69.15),
        ("LED_SDI", "GND", 34.2, 68.70),
        ("LED_LE", "GND", 40.5, 69.60),
        ("LED_OE_N", "AON_3V3", 47.2, 71.40),
    )
    for signal_net, rail_net, center_x, corridor_y in pulls:
        signal_x = center_x - 0.51
        rail_x = center_x + 0.51
        route_net_polyline(
            board,
            signal_net,
            pcbnew.F_Cu,
            [(signal_x, 73.2), (signal_x, corridor_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(
            board, board.FindNet(signal_net), signal_x, corridor_y, diameter_mm=0.40
        )
        if rail_net == "GND":
            route_net_polyline(
                board,
                "GND",
                pcbnew.F_Cu,
                [(rail_x, 73.2), (rail_x, 68.20)],
                0.15,
            )
            add_through_via(
                board, board.FindNet("GND"), rail_x, 68.20, diameter_mm=0.40
            )
        else:
            route_net_polyline(
                board,
                "AON_3V3",
                pcbnew.F_Cu,
                [(rail_x, 73.2), (49.49, 73.2)],
                0.15,
            )
            add_through_via(
                board, board.FindNet("AON_3V3"), 49.49, 73.2, diameter_mm=0.40
            )
    route_net_polyline(
        board,
        "LED_OE_Y",
        pcbnew.F_Cu,
        [(72.99, 73.8), (72.99, 71.40)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, board.FindNet("LED_OE_Y"), 72.99, 71.40, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.F_Cu,
        [(74.01, 73.8), (74.01, 70.05)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(
        board, board.FindNet("LED_LOGIC_3V3"), 74.01, 70.05, diameter_mm=0.40
    )


def route_converter_rails(board: pcbnew.BOARD) -> None:
    # TPS63802 at (34, 48), inductor pad 1 on the left. MODE is tied low.
    route_net_polyline(
        board,
        "SW_L2",
        pcbnew.F_Cu,
        [(35.0125, 48.50), (41.275, 48.50)],
        0.30,
    )
    route_net_polyline(
        board,
        "SW_L1",
        pcbnew.F_Cu,
        [
            (35.0125, 47.50),
            (35.85, 47.50),
            (35.85, 46.50),
            (42.725, 46.50),
            (42.725, 47.20),
        ],
        0.30,
    )
    route_net_polyline(
        board,
        "SYS",
        pcbnew.F_Cu,
        [(35.0125, 47.00), (35.0125, 46.10), (30.40, 46.10)],
        0.25,
    )
    sys_net = board.FindNet("SYS")
    add_through_via(board, sys_net, 30.40, 46.10, diameter_mm=0.40)
    route_net_polyline(
        board, "SYS", pcbnew.In2_Cu, [(30.40, 46.10), (30.40, 61.05)], 0.25
    )
    add_through_via(board, sys_net, 30.40, 61.05, diameter_mm=0.40)
    route_net_polyline(
        board,
        "SYS",
        pcbnew.F_Cu,
        [
            (30.40, 61.05),
            (32.8625, 61.05),
            (31.30, 61.05),
            (31.30, 62.95),
            (32.8625, 62.95),
        ],
        0.20,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(34.00, 48.00), (40.20, 48.00)],
        0.25,
    )
    gnd = board.FindNet("GND")
    add_through_via(board, gnd, 40.20, 48.00, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In2_Cu, [(40.20, 48.00), (40.20, 51.00)], 0.25
    )
    add_through_via(board, gnd, 40.20, 51.00, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.F_Cu, [(40.20, 51.00), (41.00, 51.00)], 0.25
    )
    add_through_via(board, gnd, 41.00, 51.00, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [
            (32.9875, 47.50),
            (24.40, 47.50),
            (24.40, 44.40),
            (23.20, 44.40),
            (23.20, 48.00),
            (32.9875, 48.00),
        ],
        0.20,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(27.71, 45.15), (27.71, 44.40), (13.20, 44.40)],
        0.20,
    )
    add_through_via(board, gnd, 13.20, 44.40, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(24.71, 49.20), (24.71, 51.80), (13.20, 51.80)],
        0.20,
    )
    add_through_via(board, gnd, 13.20, 51.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_FB",
        pcbnew.F_Cu,
        [(32.9875, 48.50), (23.69, 48.50), (23.69, 49.20)],
        0.15,
    )
    route_net_polyline(
        board,
        "LED_FB",
        pcbnew.F_Cu,
        [(27.31, 48.50), (27.31, 50.60)],
        0.15,
    )
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.F_Cu,
        [(35.0125, 49.00), (35.0125, 53.20), (54.00, 53.20), (54.00, 46.90)],
        0.25,
    )
    led_rail = board.FindNet("LED_4V1")
    add_through_via(board, led_rail, 54.00, 46.90, diameter_mm=0.40)
    route_net_polyline(
        board, "LED_4V1", pcbnew.In1_Cu, [(52.71, 46.90), (54.00, 46.90)], 0.25
    )
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.F_Cu,
        [(35.0125, 53.20), (26.29, 53.20), (26.29, 50.60)],
        0.15,
    )
    route_net_polyline(
        board,
        "LED_EN",
        pcbnew.F_Cu,
        [(32.9875, 47.00), (26.69, 47.00), (26.69, 45.15), (25.70, 45.15)],
        0.15,
    )
    led_en = board.FindNet("LED_EN")
    add_through_via(board, led_en, 25.70, 45.15, diameter_mm=0.40)
    route_net_polyline(
        board, "LED_EN", pcbnew.In2_Cu, [(25.70, 45.15), (25.70, 120.20)], 0.15
    )
    add_through_via(board, led_en, 25.70, 120.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_EN",
        pcbnew.In1_Cu,
        [(25.70, 120.20), (126.49, 120.20)],
        0.15,
    )
    add_through_via(board, led_en, 126.49, 120.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_EN",
        pcbnew.F_Cu,
        [(126.49, 120.20), (126.49, 98.00)],
        0.15,
    )
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(18.8625, 61.05), (16.20, 61.05), (16.20, 56.80)],
        0.20,
    )
    aon = board.FindNet("AON_3V3")
    add_through_via(board, aon, 16.20, 56.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(35.1375, 61.05), (36.40, 61.05), (36.40, 56.80)],
        0.20,
    )
    add_through_via(board, aon, 36.40, 56.80, diameter_mm=0.40)
    route_net_polyline(
        board, "AON_3V3", pcbnew.In1_Cu, [(16.20, 56.80), (49.49, 56.80)], 0.20
    )
    add_through_via(board, aon, 49.49, 56.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(18.8625, 69.05), (16.20, 69.05), (16.20, 67.20)],
        0.20,
    )
    add_through_via(board, aon, 16.20, 67.20, diameter_mm=0.40)
    route_net_polyline(
        board, "AON_3V3", pcbnew.In2_Cu, [(16.20, 67.20), (16.20, 56.80)], 0.20
    )
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.F_Cu,
        [(21.1375, 61.05), (27.40, 61.05)],
        0.20,
    )
    logic = board.FindNet("LED_LOGIC_3V3")
    add_through_via(board, logic, 27.40, 61.05, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.In2_Cu,
        [(27.40, 61.05), (27.40, 70.05)],
        0.20,
    )
    add_through_via(board, logic, 27.40, 70.05, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.In1_Cu,
        [(27.40, 70.05), (63.70, 70.05)],
        0.20,
    )
    route_net_polyline(
        board,
        "LED_QOD",
        pcbnew.F_Cu,
        [(21.1375, 62.00), (22.60, 62.00), (22.60, 63.20), (25.09, 63.20)],
        0.15,
    )
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.F_Cu,
        [(26.11, 63.20), (27.40, 63.20)],
        0.15,
    )
    add_through_via(board, logic, 27.40, 63.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(18.8625, 62.00), (20.20, 62.00), (20.20, 65.60), (13.20, 65.60)],
        0.15,
    )
    add_through_via(board, gnd, 13.20, 65.60, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.F_Cu, [(15.91, 64.60), (15.91, 65.60)], 0.15
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(32.8625, 62.00), (31.90, 62.00)],
        0.20,
    )
    add_through_via(board, gnd, 31.90, 62.00, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In2_Cu, [(31.90, 62.00), (31.90, 68.20)], 0.20
    )
    add_through_via(board, gnd, 31.90, 68.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_EN",
        pcbnew.F_Cu,
        [(18.8625, 62.95), (14.89, 62.95), (14.89, 64.60), (14.20, 64.60)],
        0.15,
    )
    logic_en = board.FindNet("LED_LOGIC_EN")
    add_through_via(board, logic_en, 14.20, 64.60, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_EN",
        pcbnew.In2_Cu,
        [(14.20, 64.60), (14.20, 120.80)],
        0.15,
    )
    add_through_via(board, logic_en, 14.20, 120.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_EN",
        pcbnew.In1_Cu,
        [(14.20, 120.80), (134.99, 120.80)],
        0.15,
    )
    add_through_via(board, logic_en, 134.99, 120.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_LOGIC_EN",
        pcbnew.F_Cu,
        [(134.99, 120.80), (134.99, 98.00)],
        0.15,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(18.8625, 70.00), (13.20, 70.00), (13.20, 73.40), (15.62, 73.40)],
        0.20,
    )
    add_through_via(board, gnd, 13.20, 73.40, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.F_Cu, [(15.62, 72.50), (15.62, 73.40)], 0.15
    )
    route_net_polyline(
        board,
        "AUDIO_EN",
        pcbnew.F_Cu,
        [(18.8625, 70.95), (14.60, 70.95), (14.60, 72.50)],
        0.15,
    )
    route_converter_caps(board)
    route_charger(board)


def route_charger(board: pcbnew.BOARD) -> None:
    # BQ25185 DLH at (18, 42). 18 kΩ is 4.2 V and 500 mA input limit.
    # 600 Ω on ISET is 500 mA charge, the 0.5C point of the Jauch 1000 mAh pack.
    # J_BAT is Molex 53398-0371 at (6.8, 58), rotated so the Jauch wire order
    # is top to bottom: pin 3 GND, pin 2 NTC, pin 1 BAT+. No onboard 10 kΩ
    # shares TS/MR with the pack thermistor.
    route_net_polyline(
        board, "VBUS", pcbnew.In2_Cu, [(2.05, 20.45), (2.05, 23.20)], 0.30
    )
    vbus = board.FindNet("VBUS")
    add_through_via(board, vbus, 2.05, 23.20, diameter_mm=0.40)
    route_net_polyline(
        board, "VBUS", pcbnew.In1_Cu, [(2.05, 23.20), (22.65, 23.20)], 0.30
    )
    add_through_via(board, vbus, 22.65, 23.20, diameter_mm=0.40)
    route_net_polyline(
        board, "VBUS", pcbnew.In2_Cu, [(22.65, 23.20), (22.65, 37.60)], 0.30
    )
    add_through_via(board, vbus, 22.65, 37.60, diameter_mm=0.40)
    route_net_polyline(
        board,
        "VBUS",
        pcbnew.F_Cu,
        [(22.65, 37.60), (22.65, 38.80), (18.86, 38.80), (18.86, 41.20)],
        0.30,
    )
    route_net_polyline(
        board,
        "SYS",
        pcbnew.F_Cu,
        [(17.14, 41.20), (15.15, 41.20), (15.15, 38.20)],
        0.30,
    )
    route_net_polyline(
        board,
        "SYS",
        pcbnew.F_Cu,
        [(17.14, 41.20), (17.14, 40.00)],
        0.30,
    )
    sys_net = board.FindNet("SYS")
    add_through_via(board, sys_net, 17.14, 40.00, diameter_mm=0.40)
    route_net_polyline(
        board, "SYS", pcbnew.In1_Cu, [(17.14, 40.00), (30.40, 40.00)], 0.30
    )
    add_through_via(board, sys_net, 30.40, 40.00, diameter_mm=0.40)
    route_net_polyline(
        board, "SYS", pcbnew.In2_Cu, [(30.40, 40.00), (30.40, 46.10)], 0.30
    )
    route_net_polyline(
        board,
        "BAT_RAW",
        pcbnew.F_Cu,
        [(17.14, 41.60), (14.70, 41.60), (14.70, 40.40)],
        0.20,
    )
    bat = board.FindNet("BAT_RAW")
    add_through_via(board, bat, 14.70, 40.40, diameter_mm=0.40)
    route_net_polyline(
        board, "BAT_RAW", pcbnew.In2_Cu, [(14.70, 40.40), (14.70, 45.20)], 0.30
    )
    add_through_via(board, bat, 14.70, 45.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "BAT_RAW",
        pcbnew.F_Cu,
        [(14.70, 45.20), (16.50, 45.20), (16.50, 46.30)],
        0.30,
    )
    route_net_polyline(
        board,
        "ILIM_VSET",
        pcbnew.F_Cu,
        [(18.86, 42.40), (22.29, 42.40), (22.29, 42.60)],
        0.15,
    )
    route_net_polyline(
        board,
        "ISET",
        pcbnew.F_Cu,
        [(18.86, 42.00), (21.09, 42.00), (21.09, 40.60)],
        0.15,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(17.14, 42.40), (16.70, 42.40), (16.70, 42.80), (17.14, 42.80)],
        0.15,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(17.14, 42.80), (16.20, 42.80), (16.20, 43.60), (13.20, 43.60), (24.55, 43.60)],
        0.25,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(23.31, 42.60), (23.31, 43.60)],
        0.20,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(24.55, 38.80), (24.55, 43.60)],
        0.25,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(22.11, 40.60), (23.40, 40.60), (23.40, 43.60)],
        0.15,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(13.25, 38.20), (13.25, 43.60)],
        0.25,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(14.25, 46.30), (13.20, 46.30)],
        0.25,
    )
    add_through_via(board, board.FindNet("GND"), 13.20, 46.30, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(18.00, 42.20), (18.00, 43.60)],
        0.25,
    )
    add_through_via(board, board.FindNet("GND"), 13.20, 43.60, diameter_mm=0.40)
    route_net_polyline(
        board,
        "TS_MR",
        pcbnew.F_Cu,
        [(18.86, 42.80), (19.60, 42.80), (19.60, 43.00)],
        0.15,
    )
    ts_net = board.FindNet("TS_MR")
    add_through_via(board, ts_net, 19.60, 43.00, diameter_mm=0.40)
    route_net_polyline(
        board, "TS_MR", pcbnew.In2_Cu, [(19.60, 43.00), (19.60, 45.00)], 0.15
    )
    add_through_via(board, ts_net, 19.60, 45.00, diameter_mm=0.40)
    # Contacts face the left edge. Top pin is GND, bottom pin is BAT+.
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(5.55, 56.75), (5.55, 56.20), (4.00, 56.20)],
        0.30,
    )
    add_through_via(board, board.FindNet("GND"), 4.00, 56.20, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In2_Cu, [(4.00, 56.20), (13.20, 56.20)], 0.30
    )
    route_net_polyline(
        board,
        "TS_MR",
        pcbnew.F_Cu,
        [(5.55, 58.00), (3.40, 58.00), (3.40, 48.40), (19.60, 48.40), (19.60, 45.00)],
        0.15,
    )
    route_net_polyline(
        board,
        "BAT_RAW",
        pcbnew.F_Cu,
        [(5.55, 59.25), (2.70, 59.25), (2.70, 45.20), (14.70, 45.20)],
        0.40,
    )


def route_converter_caps(board: pcbnew.BOARD) -> None:
    # Local ceramics for the buck and the always-on LDO. Charge current stays
    # unset: the pack may be larger than the 300 mA assumption.
    route_net_polyline(
        board,
        "SYS",
        pcbnew.F_Cu,
        [(38.25, 43.60), (38.25, 45.70), (35.0125, 45.70), (35.0125, 46.10)],
        0.25,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(40.15, 43.60), (44.30, 43.60), (44.30, 51.60), (41.00, 51.60)],
        0.25,
    )
    add_through_via(board, board.FindNet("GND"), 41.00, 51.60, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.F_Cu,
        [(29.25, 53.20), (29.25, 57.50)],
        0.30,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(31.15, 57.50), (31.15, 55.00), (41.00, 55.00)],
        0.25,
    )
    add_through_via(board, board.FindNet("GND"), 41.00, 55.00, diameter_mm=0.40)
    route_net_polyline(
        board,
        "SYS",
        pcbnew.F_Cu,
        [(28.975, 59.60), (28.975, 61.05), (32.8625, 61.05)],
        0.20,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(27.425, 59.60), (27.425, 56.20), (13.20, 56.20)],
        0.20,
    )
    add_through_via(board, board.FindNet("GND"), 13.20, 56.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(37.825, 64.30), (37.825, 61.05), (36.40, 61.05)],
        0.20,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(39.375, 64.30), (41.00, 64.30)],
        0.20,
    )
    add_through_via(board, board.FindNet("GND"), 41.00, 64.30, diameter_mm=0.40)


def route_led_buffer(board: pcbnew.BOARD) -> None:
    buffer = footprint_by_reference(board, "U_LED_BUF")
    # Left pins step outward and climb. A lower pin stays closer to the body
    # so its stub does not cross the vertical of the pin above it.
    # Top pin escapes closest to the body. Every lower stub stops outside it,
    # and every vertical climbs, so the stubs do not cross.
    left_stubs = (
        ("2", 53.35, 69.15),
        ("3", 52.80, 67.05),
        ("5", 52.25, 68.70),
        ("6", 51.70, 67.55),
    )
    right_stubs = (
        ("12", 66.80, 71.40),
        ("11", 67.40, 71.40),
        ("9", 68.00, 69.60),
        ("8", 68.60, 69.60),
    )
    for pin, escape_x, corridor_y in left_stubs + right_stubs:
        pad_x, pad_y = millimeters(get_pad(buffer, pin).GetPosition())
        route_buffer_stub(
            board,
            get_pad(buffer, pin).GetNetname(),
            pad_x,
            pad_y,
            escape_x,
            corridor_y,
        )
    vcc_x, vcc_y = millimeters(get_pad(buffer, "14").GetPosition())
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.F_Cu,
        [(vcc_x, vcc_y), (vcc_x, 73.30), (63.70, 73.30), (63.70, 70.05)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(
        board, board.FindNet("LED_LOGIC_3V3"), 63.70, 70.05, diameter_mm=0.40
    )
    pin1_x, pin1_y = millimeters(get_pad(buffer, "1").GetPosition())
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(pin1_x, pin1_y), (53.90, pin1_y), (53.90, 68.20)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, board.FindNet("GND"), 53.90, 68.20, diameter_mm=0.40)
    ground = board.FindNet("GND")
    for pin, escape_x in (("4", 57.90), ("7", 57.30)):
        pad_x, pad_y = millimeters(get_pad(buffer, pin).GetPosition())
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (escape_x, pad_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, ground, escape_x, pad_y, diameter_mm=0.40)
        add_through_via(board, ground, escape_x, 78.80, diameter_mm=0.40)
        route_net_polyline(
            board,
            "GND",
            pcbnew.In2_Cu,
            [(escape_x, pad_y), (escape_x, 78.80)],
            0.15,
        )
    route_net_polyline(
        board,
        "GND",
        pcbnew.In1_Cu,
        [(57.90, 78.80), (46.50, 78.80), (57.30, 78.80)],
        0.15,
    )
    add_through_via(board, ground, 46.50, 78.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(46.50, 78.80), (46.50, 81.30)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, ground, 46.50, 81.30, diameter_mm=0.40)
    pin13_x, pin13_y = millimeters(get_pad(buffer, "13").GetPosition())
    pin10_x, pin10_y = millimeters(get_pad(buffer, "10").GetPosition())
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [
            (pin13_x, pin13_y),
            (63.40, pin13_y),
            (63.40, 78.40),
            (72.40, 78.40),
            (72.40, 81.30),
        ],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(pin10_x, pin10_y), (63.40, pin10_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, board.FindNet("GND"), 72.40, 81.30, diameter_mm=0.40)
    route_net_polyline(
        board, "LED_SDI", pcbnew.In1_Cu, [(33.69, 68.70), (52.25, 68.70)], 0.15
    )
    route_net_polyline(
        board, "LED_SDI_PRE", pcbnew.In1_Cu, [(51.70, 67.55), (79.69, 67.55)], 0.15
    )
    route_net_polyline(
        board, "LED_SDI_Y", pcbnew.In1_Cu, [(80.71, 67.55), (82.30, 67.55)], 0.15
    )
    route_net_polyline(
        board, "LED_CLK", pcbnew.In1_Cu, [(29.49, 69.15), (53.35, 69.15)], 0.15
    )
    route_net_polyline(
        board, "LED_CLK_PRE", pcbnew.In1_Cu, [(52.80, 67.05), (69.69, 67.05)], 0.15
    )
    route_net_polyline(
        board, "LED_CLK_Y", pcbnew.In1_Cu, [(70.71, 67.05), (101.80, 67.05)], 0.15
    )
    route_net_polyline(
        board, "LED_LE_PRE", pcbnew.In1_Cu, [(68.60, 69.60), (76.69, 69.60)], 0.15
    )
    route_net_polyline(
        board, "LED_LE_Y", pcbnew.In1_Cu, [(77.71, 69.60), (101.20, 69.60)], 0.15
    )
    route_net_polyline(
        board, "LED_LE", pcbnew.In1_Cu, [(39.99, 69.60), (68.00, 69.60)], 0.15
    )
    route_net_polyline(
        board, "LED_OE_Y", pcbnew.In1_Cu, [(67.40, 71.40), (111.45, 71.40)], 0.15
    )
    route_net_polyline(
        board, "LED_OE_N", pcbnew.In1_Cu, [(46.69, 71.40), (66.80, 71.40)], 0.15
    )
    route_buffer_passives(board)
    route_net_polyline(
        board,
        "LED_LOGIC_3V3",
        pcbnew.In1_Cu,
        [(63.70, 70.05), (90.20, 70.05)],
        0.15,
    )


def route_gate_cells(board: pcbnew.BOARD) -> None:
    for row_number in range(1, MATRIX_CHANNEL_COUNT + 1):
        transistor = footprint_by_reference(board, f"Q_ROW{row_number:02d}")
        series = footprint_by_reference(board, f"R_G{row_number:02d}")
        pull_up = footprint_by_reference(board, f"R_PU{row_number:02d}")
        gate_x, gate_y = millimeters(get_pad(transistor, "1").GetPosition())
        pull_x, pull_y = millimeters(get_pad(pull_up, "1").GetPosition())
        series_x, series_y = millimeters(get_pad(series, "1").GetPosition())
        net_name = row_gate_net(row_number)
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(gate_x, gate_y), (gate_x, pull_y), (pull_x, pull_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(pull_x, pull_y), (series_x, series_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )


def spaced_coordinates(
    start_mm: float,
    count: int,
    step_mm: float,
    skip: tuple[float, float] | None = None,
) -> list[float]:
    coordinates = []
    cursor_mm = start_mm
    while len(coordinates) < count:
        if skip is not None and skip[0] <= cursor_mm <= skip[1]:
            cursor_mm = skip[1] + step_mm
            continue
        coordinates.append(round(cursor_mm, 2))
        cursor_mm += step_mm
    return coordinates


def assign_select_escapes(outputs: list[dict]) -> None:
    buckets: dict[str, list[dict]] = {
        "a_left": [],
        "a_pin13": [],
        "a_jog": [],
        "b_left": [],
        "b_native": [],
        "b_jog": [],
    }
    for output in outputs:
        row_number = output["row"]
        if row_number <= 11:
            buckets["a_left"].append(output)
        elif row_number == 12:
            buckets["a_pin13"].append(output)
        elif row_number <= 16:
            buckets["a_jog"].append(output)
        elif row_number <= 27:
            buckets["b_left"].append(output)
        elif row_number == 28:
            buckets["b_native"].append(output)
        else:
            buckets["b_jog"].append(output)
    for output in buckets["a_left"]:
        output["jog"] = False
    for output in buckets["a_pin13"]:
        output["jog"] = False
        output["escape_x"] = round(output["pad_x"] + 1.25, 2)
    for output in buckets["b_left"]:
        output["jog"] = False
    for output in buckets["b_native"]:
        output["jog"] = False
    buckets["a_left"].sort(key=lambda item: item["pad_y"])
    for rank, output in enumerate(buckets["a_left"]):
        output["escape_x"] = round(81.70 - rank * 0.48, 2)
    buckets["a_jog"].sort(key=lambda item: item["pad_y"])
    for rank, output in enumerate(buckets["a_jog"]):
        output["jog"] = True
        output["escape_x"] = round(92.35 - rank * 0.55, 2)
        output["entry_y"] = round(20.55 + rank * 0.42, 2)
    buckets["b_left"].sort(key=lambda item: item["pad_y"])
    for rank, output in enumerate(buckets["b_left"]):
        output["escape_x"] = round(97.90 - rank * 0.42, 2)
    for output in buckets["b_native"]:
        output["escape_x"] = round(output["pad_x"] + 1.25, 2)
    for output in outputs:
        if output["row"] == 1:
            output["jog"] = True
            output["entry_y"] = 9.70
    buckets["b_jog"].sort(key=lambda item: item["pad_y"])
    for rank, output in enumerate(buckets["b_jog"]):
        output["jog"] = True
        output["escape_x"] = round(108.40 - rank * 0.55, 2)
        output["entry_y"] = round(18.55 + (3 - rank) * 0.42, 2)


def row_select_fan_layer(row_number: int) -> int:
    # ROW_02..12 decoder→comb on In2 frees In1 under U1; ROW_01 jog stays on In1.
    if 2 <= row_number <= 11:
        return pcbnew.In2_Cu
    return pcbnew.In1_Cu


def park_select_output(board: pcbnew.BOARD, output: dict) -> None:
    net_name = output["net"]
    pad_x = output["pad_x"]
    pad_y = output["pad_y"]
    escape_x = output["escape_x"]
    fan_layer = row_select_fan_layer(output["row"])
    if output["jog"]:
        entry_y = output["entry_y"]
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(pad_x, pad_y), (escape_x, pad_y), (escape_x, entry_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
    else:
        entry_y = pad_y
        output["entry_y"] = entry_y
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [(pad_x, pad_y), (escape_x, pad_y)],
            FAN_IN_TRACK_WIDTH_MM,
        )
    net = board.FindNet(net_name)
    add_through_via(board, net, escape_x, entry_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        net_name,
        fan_layer,
        [(escape_x, entry_y), (output["comb_x"], entry_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def finish_select_output(board: pcbnew.BOARD, output: dict) -> None:
    net = board.FindNet(output["net"])
    comb_x = output["comb_x"]
    entry_y = output["entry_y"]
    travel_y = output["travel_y"]
    approach_x = output["approach_x"]
    target_x = output["target_x"]
    target_y = output["target_y"]
    add_through_via(board, net, comb_x, entry_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        output["net"],
        pcbnew.In2_Cu,
        [(comb_x, entry_y), (comb_x, travel_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, comb_x, travel_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        output["net"],
        pcbnew.In1_Cu,
        [(comb_x, travel_y), (approach_x, travel_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, approach_x, travel_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        output["net"],
        pcbnew.In2_Cu,
        [(approach_x, travel_y), (approach_x, target_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, approach_x, target_y, diameter_mm=0.40)
    route_net_polyline(
        board,
        output["net"],
        pcbnew.F_Cu,
        [(approach_x, target_y), (target_x, target_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_row_select(board: pcbnew.BOARD) -> None:
    route_gate_cells(board)
    outputs = []
    for row_number in range(1, MATRIX_CHANNEL_COUNT + 1):
        bank_row = (row_number - 1) % 16
        decoder_name = "U_DEC_A" if row_number <= 16 else "U_DEC_B"
        decoder = footprint_by_reference(board, decoder_name)
        pad = get_pad(decoder, DECODER_Y_PINS[bank_row])
        pad_x, pad_y = millimeters(pad.GetPosition())
        series = footprint_by_reference(board, f"R_G{row_number:02d}")
        target_x, target_y = millimeters(get_pad(series, "2").GetPosition())
        farm_index = row_number - 1
        column_index = farm_index % 8
        farm_row = farm_index // 8
        outputs.append(
            {
                "row": row_number,
                "net": row_select_net(row_number),
                "pad_x": pad_x,
                "pad_y": pad_y,
                "left": pad_x < millimeters(decoder.GetPosition())[0],
                "bank": decoder_name,
                "target_x": target_x,
                "target_y": target_y,
                "approach_x": 48.0 + column_index * 10.0 + 5.55,
                "farm_row": farm_row,
                "column": column_index,
            }
        )

    travel_by_row = (
        [23.50, 23.95, 24.40, 24.85, 29.10, 29.55, 30.00, 30.45],
        [35.50, 35.95, 36.40, 36.85, 41.05, 41.50, 41.95, 42.40],
        [47.50, 47.95, 48.40, 48.85, 53.05, 53.50, 53.95, 54.40],
        [59.50, 59.95, 60.40, 60.85, 65.10, 65.55, 66.00, 66.45],
    )
    left_outputs = [item for item in outputs if item["row"] <= 12]
    right_outputs = [item for item in outputs if item["row"] > 12]
    left_comb = spaced_coordinates(33.40, len(left_outputs), 0.48)
    right_comb = spaced_coordinates(
        125.20, len(right_outputs), 0.50, skip=(127.35, 128.90)
    )
    for output, comb_x in zip(left_outputs, left_comb):
        output["comb_x"] = comb_x
    for output, comb_x in zip(right_outputs, right_comb):
        output["comb_x"] = comb_x
    assign_select_escapes(outputs)
    for output in outputs:
        output["travel_y"] = travel_by_row[output["farm_row"]][output["column"]]
        park_select_output(board, output)
        finish_select_output(board, output)


def route_reserve_tail(
    board: pcbnew.BOARD,
    net_name: str,
    drop_x_mm: float,
    top_y_mm: float,
    bottom_y_mm: float,
) -> None:
    net = board.FindNet(net_name)
    add_through_via(board, net, drop_x_mm, top_y_mm, diameter_mm=0.40)
    route_net_polyline(
        board,
        net_name,
        pcbnew.In2_Cu,
        [(drop_x_mm, top_y_mm), (drop_x_mm, bottom_y_mm)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, net, drop_x_mm, bottom_y_mm, diameter_mm=0.40)
    reserve_x = reserve_pad_x(board, net_name)
    route_net_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [
            (drop_x_mm, bottom_y_mm),
            (reserve_x, bottom_y_mm),
            (reserve_x, 98.00),
        ],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_mcu_side_to_drop(
    board: pcbnew.BOARD,
    net_name: str,
    pad_x_mm: float,
    pad_y_mm: float,
    spine_x_mm: float,
    via_y_mm: float,
    drop_x_mm: float,
    bottom_y_mm: float,
) -> None:
    route_net_polyline(
        board,
        net_name,
        pcbnew.F_Cu,
        [(pad_x_mm, pad_y_mm), (spine_x_mm, pad_y_mm), (spine_x_mm, via_y_mm)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    if abs(spine_x_mm - drop_x_mm) > 0.01:
        net = board.FindNet(net_name)
        route_net_polyline(
            board,
            net_name,
            pcbnew.In1_Cu,
            [
                (min(spine_x_mm, drop_x_mm), via_y_mm),
                (max(spine_x_mm, drop_x_mm), via_y_mm),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )
    route_reserve_tail(board, net_name, drop_x_mm, via_y_mm, bottom_y_mm)


def route_translator_power(board: pcbnew.BOARD) -> None:
    translator = footprint_by_reference(board, "U_ROW_XLAT")
    vcca_x, vcca_y = millimeters(get_pad(translator, "1").GetPosition())
    dir_x, dir_y = millimeters(get_pad(translator, "2").GetPosition())
    oe_x, oe_y = millimeters(get_pad(translator, "22").GetPosition())
    vccb_x, vccb_y = millimeters(get_pad(translator, "24").GetPosition())
    vccb_pair_x, vccb_pair_y = millimeters(get_pad(translator, "23").GetPosition())
    aon_spine_x = 64.20
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [
            (dir_x, dir_y),
            (vcca_x, vcca_y),
            (aon_spine_x, vcca_y),
            (aon_spine_x, 10.15),
        ],
        0.15,
    )
    aon = board.FindNet("AON_3V3")
    add_through_via(board, aon, aon_spine_x, 10.15, diameter_mm=0.40)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In1_Cu,
        [(aon_spine_x, 10.15), (49.49, 10.15)],
        0.20,
    )
    # Join the east MCU spine into the translator AON bus on In2 (In1 crosses ROW_01_Y @ y≈9.7).
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(MCU_AON_IN2_SPINE_X_MM, 9.20), (MCU_AON_IN2_SPINE_X_MM, 10.15)],
        0.20,
    )
    add_through_via(board, aon, MCU_AON_IN2_SPINE_X_MM, 10.15, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.F_Cu,
        [
            (vccb_pair_x, vccb_pair_y),
            (vccb_x, vccb_y),
            (vccb_x, 8.80),
        ],
        0.15,
    )
    led_rail = board.FindNet("LED_4V1")
    add_through_via(board, led_rail, vccb_x, 8.80, diameter_mm=0.40)
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.In1_Cu,
        [(vccb_x, 8.80), (89.50, 8.80)],
        0.20,
    )
    ground_bus_y = 17.15
    ground_xs = []
    for pin in ("9", "10", "11", "12"):
        pad_x, pad_y = millimeters(get_pad(translator, pin).GetPosition())
        ground_xs.append(pad_x)
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(pad_x, pad_y), (pad_x, ground_bus_y)],
            0.15,
        )
    pin13_x, pin13_y = millimeters(get_pad(translator, "13").GetPosition())
    ground_xs.append(pin13_x)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(pin13_x, pin13_y), (pin13_x, ground_bus_y)],
        0.15,
    )
    ground_xs.append(73.40)
    ordered_ground_xs = sorted(ground_xs)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(x_mm, ground_bus_y) for x_mm in ordered_ground_xs],
        0.15,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(73.40, ground_bus_y), (73.40, 18.075)],
        0.15,
    )
    route_net_polyline(
        board,
        "ROW_XLAT_OE_N",
        pcbnew.F_Cu,
        [(oe_x, oe_y), (oe_x, 3.35)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    oe_drop_x = 116.40
    oe = board.FindNet("ROW_XLAT_OE_N")
    add_through_via(board, oe, oe_x, 3.35, diameter_mm=0.40)
    route_net_polyline(
        board,
        "ROW_XLAT_OE_N",
        pcbnew.In1_Cu,
        [(oe_x, 3.35), (oe_drop_x, 3.35)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, oe, oe_drop_x, 3.55, diameter_mm=0.40)
    route_net_polyline(
        board,
        "ROW_XLAT_OE_N",
        pcbnew.In2_Cu,
        [(oe_drop_x, 3.35), (oe_drop_x, 97.35)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, oe, oe_drop_x, 97.35, diameter_mm=0.40)
    reserve_x = reserve_pad_x(board, "ROW_XLAT_OE_N")
    route_net_polyline(
        board,
        "ROW_XLAT_OE_N",
        pcbnew.F_Cu,
        [(oe_drop_x, 97.35), (reserve_x, 97.35), (reserve_x, 98.00)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_translator_bias(board: pcbnew.BOARD) -> None:
    # Each address vertical stops at its own height. The upper stub is the
    # leftmost net, so the stubs below it never cross that vertical.
    address_pulls = (
        ("ROW_A0_4V", 70.25, 6.20, 78.0, 1.40),
        ("ROW_A1_4V", 70.75, 6.60, 80.6, 2.10),
        ("ROW_A2_4V", 71.25, 7.00, 83.2, 2.80),
        ("ROW_A3_4V", 72.70, 7.40, 85.8, 3.50),
    )
    for net_name, reach_x, entry_y, center_x, center_y in address_pulls:
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [
                (reach_x, entry_y),
                (reach_x, center_y),
                (center_x - 0.51, center_y),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )
    ground_x = 87.20
    ground_ys = []
    for _, _, _, center_x, center_y in address_pulls:
        ground_ys.append(center_y)
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(center_x + 0.51, center_y), (ground_x, center_y)],
            0.15,
        )
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(ground_x, min(ground_ys)), (ground_x, max(ground_ys)), (ground_x, 1.15)],
        0.15,
    )
    ground = board.FindNet("GND")
    add_through_via(board, ground, ground_x, 1.15, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.In1_Cu,
        [(ground_x, 1.15), (39.40, 1.15)],
        0.20,
    )
    add_through_via(board, ground, 39.40, 1.15, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.In2_Cu,
        [(39.40, 1.15), (39.40, 11.20)],
        0.20,
    )
    add_through_via(board, ground, 39.40, 11.20, diameter_mm=0.40)
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [
            (39.35, 11.20),
            (39.35, MCU_GND_IN2_HOOK_Y_MM),
            (MCU_GND_IN2_SPINE_X_MM, MCU_GND_IN2_HOOK_Y_MM),
        ],
        0.15,
    )
    route_net_polyline(
        board,
        "DEC_A_EN_N_4V",
        pcbnew.F_Cu,
        [(73.35, 7.80), (73.35, 4.20), (88.6 - 0.51, 4.20)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "DEC_B_EN_N_4V",
        pcbnew.F_Cu,
        [(74.00, 8.25), (74.00, 4.90), (91.2 - 0.51, 4.90)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    led_drop_x = 93.80
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.F_Cu,
        [
            (88.6 + 0.51, 4.20),
            (88.6 + 0.51, 0.80),
            (led_drop_x, 0.80),
            (led_drop_x, 8.80),
            (89.50, 8.80),
        ],
        0.15,
    )
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.F_Cu,
        [(91.2 + 0.51, 4.90), (led_drop_x, 4.90)],
        0.15,
    )
    route_net_polyline(
        board,
        "ROW_XLAT_OE_N",
        pcbnew.F_Cu,
        [(69.75, 3.55), (69.75, 2.30), (66.2 + 0.51, 2.30)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(66.2 - 0.51, 2.30), (64.20, 2.30), (64.20, 10.15)],
        0.15,
    )


def route_decoder_address(board: pcbnew.BOARD) -> None:
    # B pins reach the decoder on the 4 V net above the row-select field.
    # Right-hand B pins step outward; the upper pin stays closest to the body.
    address_pins = (
        ("ROW_A0", "23", "21", 6.20, 70.25, 66.30, 98.80),
        ("ROW_A1", "22", "20", 6.60, 70.75, 71.80, 99.30),
        ("ROW_A2", "21", "19", 7.00, 71.25, 51.20, 99.75),
        ("ROW_A3", "20", "18", 7.40, 72.70, 59.20, 102.30),
        ("DEC_A_EN_N", "18", "17", 7.80, 73.35, 61.40, 102.80),
        ("DEC_B_EN_N", "18", "16", 8.25, 74.00, 119.40, 103.30),
    )
    # MCU-side spines stay left of the ROW_A0 drop at x=66.30. The upper pin
    # escapes furthest left so its vertical does not cross the stubs below it.
    mcu_spines = {
        "ROW_A0": (63.80, 18.70),
        "ROW_A1": (64.40, 19.20),
        "ROW_A2": (65.00, 19.70),
        "ROW_A3": (65.60, 20.20),
        "DEC_A_EN_N": (None, 20.80),
        "DEC_B_EN_N": (65.20, 25.35),
    }
    a_pins = {
        "ROW_A0": "3",
        "ROW_A1": "4",
        "ROW_A2": "5",
        "ROW_A3": "6",
        "DEC_A_EN_N": "7",
        "DEC_B_EN_N": "8",
    }
    translator = footprint_by_reference(board, "U_ROW_XLAT")
    inward_mm = {
        "ROW_A0": 1.05,
        "ROW_A1": 1.55,
        "ROW_A2": 2.05,
        "ROW_A3": 2.55,
        "DEC_A_EN_N": 3.55,
        "DEC_B_EN_N": 3.55,
    }
    for logical_name, pin, b_pin, entry_y, reach_x, drop_x, bottom_y in address_pins:
        net_name = translated_row_net(logical_name)
        decoders = ("U_DEC_A", "U_DEC_B")
        if logical_name == "DEC_A_EN_N":
            decoders = ("U_DEC_A",)
        elif logical_name == "DEC_B_EN_N":
            decoders = ("U_DEC_B",)
        escape_points = []
        for decoder_name in decoders:
            decoder = footprint_by_reference(board, decoder_name)
            pad_x, pad_y = millimeters(get_pad(decoder, pin).GetPosition())
            escape_x = round(pad_x - inward_mm[logical_name], 2)
            route_net_polyline(
                board,
                net_name,
                pcbnew.F_Cu,
                [(pad_x, pad_y), (escape_x, pad_y), (escape_x, entry_y)],
                FAN_IN_TRACK_WIDTH_MM,
            )
            net = board.FindNet(net_name)
            add_through_via(board, net, escape_x, entry_y, diameter_mm=0.40)
            escape_points.append(escape_x)
        b_x, b_y = millimeters(get_pad(translator, b_pin).GetPosition())
        if abs(b_x - reach_x) < 0.01:
            b_points = [(b_x, b_y), (reach_x, entry_y)]
        else:
            b_points = [(b_x, b_y), (reach_x, b_y), (reach_x, entry_y)]
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            b_points,
            FAN_IN_TRACK_WIDTH_MM,
        )
        net = board.FindNet(net_name)
        add_through_via(board, net, reach_x, entry_y, diameter_mm=0.40)
        route_net_polyline(
            board,
            net_name,
            pcbnew.In1_Cu,
            [
                (min(escape_points + [reach_x]), entry_y),
                (max(escape_points + [reach_x]), entry_y),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )
        a_x, a_y = millimeters(get_pad(translator, a_pins[logical_name]).GetPosition())
        spine_x, via_y = mcu_spines[logical_name]
        if logical_name == "DEC_B_EN_N":
            route_net_polyline(
                board,
                logical_name,
                pcbnew.F_Cu,
                [
                    (a_x, a_y),
                    (a_x, 23.70),
                    (spine_x, 23.70),
                    (spine_x, via_y),
                ],
                FAN_IN_TRACK_WIDTH_MM,
            )
            net = board.FindNet(logical_name)
            add_through_via(board, net, spine_x, via_y, diameter_mm=0.40)
            route_net_polyline(
                board,
                logical_name,
                pcbnew.In1_Cu,
                [(spine_x, via_y), (drop_x, via_y)],
                FAN_IN_TRACK_WIDTH_MM,
            )
            route_reserve_tail(board, logical_name, drop_x, via_y, bottom_y)
            continue
        if spine_x is None:
            spine_x = a_x
        route_mcu_side_to_drop(
            board,
            logical_name,
            a_x,
            a_y,
            spine_x,
            via_y,
            drop_x,
            bottom_y,
        )


def reserve_pad_x(board: pcbnew.BOARD, net_name: str) -> float:
    for footprint in board.GetFootprints():
        if not footprint.GetReference().startswith("RP"):
            continue
        pad = get_pad(footprint, "1")
        if pad.GetNetname() == net_name:
            return millimeters(pad.GetPosition())[0]
    raise ValueError(f"Unable to find reserve pad for {net_name}")


def route_decoder_rails(board: pcbnew.BOARD) -> None:
    gnd_escape_x = []
    for decoder_name, vcc_escape_x, gnd_escape, enable_escape in (
        ("U_DEC_A", 89.50, 73.40, 93.05),
        ("U_DEC_B", 109.20, 98.20, 110.20),
    ):
        decoder = footprint_by_reference(board, decoder_name)
        vcc_x, vcc_y = millimeters(get_pad(decoder, "24").GetPosition())
        gnd_x, gnd_y = millimeters(get_pad(decoder, "12").GetPosition())
        enable_x, enable_y = millimeters(get_pad(decoder, "19").GetPosition())
        route_net_polyline(
            board,
            "LED_4V1",
            pcbnew.F_Cu,
            [(vcc_x, vcc_y), (vcc_escape_x, vcc_y), (vcc_escape_x, 8.80)],
            0.20,
        )
        add_through_via(
            board, board.FindNet("LED_4V1"), vcc_escape_x, 8.80, diameter_mm=0.40
        )
        route_net_polyline(
            board,
            "LED_4V1",
            pcbnew.In2_Cu,
            [(vcc_escape_x, 8.80), (vcc_escape_x, 32.40)],
            0.20,
        )
        add_through_via(
            board, board.FindNet("LED_4V1"), vcc_escape_x, 32.40, diameter_mm=0.40
        )
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(gnd_x, gnd_y), (gnd_escape, gnd_y), (gnd_escape, 22.35)],
            FAN_IN_TRACK_WIDTH_MM,
        )
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [
                (enable_x, enable_y),
                (enable_escape, enable_y),
                (enable_escape, 22.35),
            ],
            FAN_IN_TRACK_WIDTH_MM,
        )
        add_through_via(board, board.FindNet("GND"), gnd_escape, 22.35, diameter_mm=0.40)
        add_through_via(
            board, board.FindNet("GND"), enable_escape, 22.35, diameter_mm=0.40
        )
        gnd_escape_x.extend((gnd_escape, enable_escape))
    route_net_polyline(
        board,
        "LED_4V1",
        pcbnew.In1_Cu,
        [(89.50, 32.40), (140.00, 32.40)],
        0.25,
    )
    route_net_polyline(
        board,
        "GND",
        pcbnew.In1_Cu,
        [(max(gnd_escape_x), 22.35), (13.20, 22.35)],
        0.25,
    )
    gnd = board.FindNet("GND")
    add_through_via(board, gnd, 13.20, 22.35, diameter_mm=0.40)


def route_rext_return(board: pcbnew.BOARD) -> None:
    gnd = board.FindNet("GND")
    add_through_via(board, gnd, 13.20, 81.30, diameter_mm=0.40)
    route_net_polyline(
        board, "GND", pcbnew.In2_Cu, [(13.20, 80.00), (13.20, 81.30)], 0.25
    )
    return_x = []
    for reference in ("R_EXT1", "R_EXT2"):
        resistor = footprint_by_reference(board, reference)
        pad_x, pad_y = millimeters(get_pad(resistor, "2").GetPosition())
        return_x.append(pad_x)
        add_through_via(board, gnd, pad_x, 81.30, diameter_mm=0.40)
        route_net_polyline(
            board,
            "GND",
            pcbnew.F_Cu,
            [(pad_x, 81.30), (pad_x, pad_y)],
            0.20,
        )
    route_net_polyline(
        board,
        "GND",
        pcbnew.In1_Cu,
        [(13.20, 81.30), (max(return_x), 81.30)],
        0.25,
    )


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
    add_rectangle(
        board,
        pcbnew.Dwgs_User,
        56.0,
        3.0,
        148.0,
        13.0,
        GUIDE_LINE_WIDTH_MM,
    )
    add_text(
        board,
        "MCU PIN ESCAPE",
        100.0,
        5.2,
        pcbnew.Dwgs_User,
        text_size_mm=0.8,
    )
    route_electronics_matrix(board)
    route_led_anode_rail(board)
    route_imu_sense(board)
    route_power_and_blank(board)
    route_row_select(board)
    route_decoder_address(board)
    route_decoder_rails(board)
    route_translator_power(board)
    route_translator_bias(board)
    route_rext_return(board)
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
        pcbnew.Cmts_User,
        text_size_mm=MINIMUM_SILK_TEXT_HEIGHT_MM,
    )
    add_star(
        board,
        ELECTRONICS_WIDTH_MM / 2,
        ELECTRONICS_HEIGHT_MM - 1.3,
        outer_radius_mm=0.7,
        inner_radius_mm=0.3,
        layer=pcbnew.Cmts_User,
    )
    add_text(
        board,
        "MONO ELECTRONICS / 32 ROW x 32 COL FFC",
        ELECTRONICS_WIDTH_MM / 2,
        2.0,
        pcbnew.Cmts_User,
        text_size_mm=0.8,
    )
    if __import__("os").environ.get("MONO_BOOT_PREGRID", "0") == "1":
        from mono_split_esp32 import route_mcu_boot_switch, route_mcu_strap_passives

        route_mcu_strap_passives(board)
        route_mcu_boot_switch(board)
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
    electronics_pcb_path = electronics_directory / "mono_electronics.kicad_pcb"
    print(f"Generated {electronics_pcb_path}")
    if __import__("os").environ.get("MONO_APPLY_MCU_GRID", "1") == "1":
        from mcu_grid_route import run_mcu_grid_pipeline

        run_mcu_grid_pipeline(electronics_pcb_path)
        print(f"MCU grid routes applied to {electronics_pcb_path}")

    for variant in PANEL_VARIANTS:
        panel_path = repository_root / "hardware" / variant.name / f"{variant.name}.kicad_pcb"
        subprocess.run(
            ["git", "checkout", "--", str(panel_path.relative_to(repository_root))],
            cwd=repository_root,
            check=False,
        )


if __name__ == "__main__":
    generate_boards(Path(__file__).resolve().parents[2])
