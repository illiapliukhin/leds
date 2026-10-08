from dataclasses import dataclass


FFC_PIN_COUNT = 40
MATRIX_CHANNEL_COUNT = 32
LED_PITCH_MM = 2.54
PANEL_MARGIN_MM = 44.0
ELECTRONICS_WIDTH_MM = 140.0
ELECTRONICS_HEIGHT_MM = 90.0
BRANDING_STRIP_HEIGHT_MM = 6.0
LED_FOOTPRINT_NAME = "NCD0603W1"
ROW_CONNECTOR_FOOTPRINT_NAME = "FFC_40P_050_ROW"
COLUMN_CONNECTOR_FOOTPRINT_NAME = "FFC_40P_050_COL"
LED_CATHODE_PAD = "1"
LED_ANODE_PAD = "2"


@dataclass(frozen=True)
class PanelVariant:
    name: str
    matrix_size: int
    board_size_mm: float


PANEL_VARIANTS = (
    PanelVariant(
        name="mono_panel_20x20",
        matrix_size=20,
        board_size_mm=round((20 - 1) * LED_PITCH_MM + 2 * PANEL_MARGIN_MM, 1),
    ),
    PanelVariant(
        name="mono_panel_32x32",
        matrix_size=32,
        board_size_mm=round((32 - 1) * LED_PITCH_MM + 2 * PANEL_MARGIN_MM, 1),
    ),
)


def row_net_name(row_number: int) -> str:
    if 1 <= row_number <= MATRIX_CHANNEL_COUNT:
        return f"ROW_{row_number:02d}_ANODE"
    if MATRIX_CHANNEL_COUNT < row_number <= FFC_PIN_COUNT:
        return f"ROW_SPARE_{row_number:02d}"
    raise ValueError(f"row number {row_number} is outside 1..{FFC_PIN_COUNT}")


def column_net_name(column_number: int) -> str:
    if 1 <= column_number <= MATRIX_CHANNEL_COUNT:
        return f"COL_{column_number:02d}"
    if MATRIX_CHANNEL_COUNT < column_number <= FFC_PIN_COUNT:
        return f"COL_SPARE_{column_number:02d}"
    raise ValueError(
        f"column number {column_number} is outside 1..{FFC_PIN_COUNT}"
    )


def row_connector_pinout() -> dict[str, str]:
    return {
        str(pin_number): row_net_name(pin_number)
        for pin_number in range(1, FFC_PIN_COUNT + 1)
    }


def column_connector_pinout() -> dict[str, str]:
    return {
        str(pin_number): column_net_name(pin_number)
        for pin_number in range(1, FFC_PIN_COUNT + 1)
    }


def populated_matrix_nets(matrix_size: int) -> tuple[set[str], set[str]]:
    if matrix_size > MATRIX_CHANNEL_COUNT:
        raise ValueError(
            f"matrix {matrix_size} exceeds {MATRIX_CHANNEL_COUNT} driver channels"
        )
    row_nets = {row_net_name(row_number) for row_number in range(1, matrix_size + 1)}
    column_nets = {
        column_net_name(column_number)
        for column_number in range(1, matrix_size + 1)
    }
    return row_nets, column_nets
