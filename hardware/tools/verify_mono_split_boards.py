from pathlib import Path
import json
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pcbnew
from mono_split_spec import (
    BRANDING_STRIP_HEIGHT_MM,
    COLUMN_CONNECTOR_FOOTPRINT_NAME,
    ELECTRONICS_HEIGHT_MM,
    FFC_PIN_COUNT,
    LED_FOOTPRINT_NAME,
    PANEL_VARIANTS,
    ROW_CONNECTOR_FOOTPRINT_NAME,
    column_connector_pinout,
    populated_matrix_nets,
    row_connector_pinout,
)


GEOMETRIC_VIOLATION_TYPES = {
    "clearance",
    "copper_edge_clearance",
    "copper_sliver",
    "courtyards_overlap",
    "drill_out_of_range",
    "hole_clearance",
    "invalid_outline",
    "items_not_allowed",
    "malformed_courtyard",
    "shorting_items",
    "silk_over_copper",
    "silk_overlap",
    "solder_mask_bridge",
    "text_on_edge_cuts",
    "track_dangling",
    "track_width",
    "tracks_crossing",
    "via_dangling",
}


def connector_pinout(board: pcbnew.BOARD, reference: str) -> dict[str, str]:
    for footprint in board.GetFootprints():
        if footprint.GetReference() != reference:
            continue
        pinout = {}
        for pad in footprint.Pads():
            pad_number = pad.GetNumber()
            if not pad_number.isdigit():
                continue
            net = pad.GetNet()
            net_name = net.GetNetname() if net is not None else ""
            pinout[pad_number] = net_name
        return pinout
    raise ValueError(f"Unable to find {reference}")


def load_board(path: Path) -> pcbnew.BOARD:
    board = pcbnew.LoadBoard(str(path))
    if board is None:
        raise FileNotFoundError(path)
    return board


def assert_panel_geometry(board: pcbnew.BOARD, matrix_size: int) -> None:
    led_count = sum(
        1
        for footprint in board.GetFootprints()
        if footprint.GetValue() == LED_FOOTPRINT_NAME
    )
    expected = matrix_size * matrix_size
    if led_count != expected:
        raise AssertionError(
            f"expected {expected} LEDs, found {led_count}"
        )

    front_non_led = [
        footprint.GetReference()
        for footprint in board.GetFootprints()
        if footprint.GetValue() != LED_FOOTPRINT_NAME
        and not footprint.IsFlipped()
    ]
    if front_non_led:
        raise AssertionError(
            f"front of LED panel has non-LED parts: {front_non_led}"
        )

    rear_connectors = sorted(
        footprint.GetReference()
        for footprint in board.GetFootprints()
        if footprint.IsFlipped()
    )
    if rear_connectors != ["J_COL", "J_ROW"]:
        raise AssertionError(
            f"expected rear J_ROW and J_COL, found {rear_connectors}"
        )

    if board.GetCopperLayerCount() != 2:
        raise AssertionError("LED panel must be two-layer")


def assert_matching_pinout(
    actual: dict[str, str],
    expected: dict[str, str],
    assigned_pins: int,
    board_name: str,
    connector_name: str,
) -> None:
    for pin_number in range(1, assigned_pins + 1):
        pin = str(pin_number)
        actual_net = actual.get(pin, "")
        expected_net = expected[pin]
        if actual_net != expected_net:
            raise AssertionError(
                f"{board_name} {connector_name} pin {pin}: "
                f"expected {expected_net}, found {actual_net or 'no net'}"
            )


def run_drc(board_path: Path, output_json_path: Path) -> dict:
    command = [
        "kicad-cli",
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-error",
        "--severity-warning",
        "--output",
        str(output_json_path),
        str(board_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if not output_json_path.exists():
        raise RuntimeError(
            f"DRC did not write {output_json_path}: {completed.stderr}"
        )
    return json.loads(output_json_path.read_text())


def geometric_violations(report: dict) -> list[dict]:
    violations = []
    for violation in report.get("violations", []):
        if violation.get("type") in GEOMETRIC_VIOLATION_TYPES:
            violations.append(violation)
    return violations


def verify_repository(repository_root: Path) -> None:
    expected_row = row_connector_pinout()
    expected_column = column_connector_pinout()
    electronics_path = (
        repository_root / "hardware/mono_electronics/mono_electronics.kicad_pcb"
    )
    electronics_board = load_board(electronics_path)
    electronics_row = connector_pinout(electronics_board, "J_ROW")
    electronics_column = connector_pinout(electronics_board, "J_COL")
    assert_matching_pinout(
        electronics_row,
        expected_row,
        FFC_PIN_COUNT,
        "mono_electronics",
        "J_ROW",
    )
    assert_matching_pinout(
        electronics_column,
        expected_column,
        FFC_PIN_COUNT,
        "mono_electronics",
        "J_COL",
    )
    if electronics_board.GetCopperLayerCount() != 4:
        raise AssertionError("electronics board must be four-layer")

    branding_keepout_mm = ELECTRONICS_HEIGHT_MM - BRANDING_STRIP_HEIGHT_MM
    branding_hits = [
        footprint.GetReference()
        for footprint in electronics_board.GetFootprints()
        if pcbnew.ToMM(footprint.GetPosition().y) > branding_keepout_mm
    ]
    if branding_hits:
        raise AssertionError(
            f"parts overlap branding strip: {branding_hits}"
        )

    for variant in PANEL_VARIANTS:
        board_path = (
            repository_root
            / "hardware"
            / variant.name
            / f"{variant.name}.kicad_pcb"
        )
        board = load_board(board_path)
        assert_panel_geometry(board, variant.matrix_size)
        row_pinout = connector_pinout(board, "J_ROW")
        column_pinout_actual = connector_pinout(board, "J_COL")
        assert_matching_pinout(
            row_pinout,
            expected_row,
            variant.matrix_size,
            variant.name,
            "J_ROW",
        )
        assert_matching_pinout(
            column_pinout_actual,
            expected_column,
            variant.matrix_size,
            variant.name,
            "J_COL",
        )
        populated_rows, populated_columns = populated_matrix_nets(
            variant.matrix_size
        )
        for pin_number in range(variant.matrix_size + 1, FFC_PIN_COUNT + 1):
            row_net = row_pinout.get(str(pin_number), "")
            column_net = column_pinout_actual.get(str(pin_number), "")
            if row_net in populated_rows:
                raise AssertionError(
                    f"{variant.name} J_ROW pin {pin_number} reused {row_net}"
                )
            if column_net in populated_columns:
                raise AssertionError(
                    f"{variant.name} J_COL pin {pin_number} reused {column_net}"
                )

        drc_json_path = board_path.with_name("drc.json")
        report = run_drc(board_path, drc_json_path)
        geometry_failures = geometric_violations(report)
        unconnected = [
            violation
            for violation in report.get("violations", [])
            if violation.get("type") == "unconnected_items"
        ]
        if geometry_failures:
            raise AssertionError(
                f"{variant.name} geometric DRC failed: "
                f"{geometry_failures[0]['type']} "
                f"{geometry_failures[0].get('description')}"
            )
        if unconnected:
            raise AssertionError(
                f"{variant.name} has {len(unconnected)} unconnected groups"
            )
        print(
            f"{variant.name}: pinout match, {variant.matrix_size ** 2} LEDs, "
            "DRC clean"
        )

    electronics_drc_path = electronics_path.with_name("drc.json")
    electronics_report = run_drc(electronics_path, electronics_drc_path)
    electronics_geometry = geometric_violations(electronics_report)
    if electronics_geometry:
        raise AssertionError(
            "mono_electronics geometric DRC failed: "
            f"{electronics_geometry[0]['type']} "
            f"{electronics_geometry[0].get('description')}"
        )
    unconnected_count = sum(
        1
        for violation in electronics_report.get("violations", [])
        if violation.get("type") == "unconnected_items"
    )
    print(
        "mono_electronics: pinout match, geometric DRC clean, "
        f"{unconnected_count} unconnected groups expected before routing"
    )


if __name__ == "__main__":
    verify_repository(Path(__file__).resolve().parents[2])
