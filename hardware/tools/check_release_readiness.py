import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import pcbnew


@dataclass(frozen=True)
class ReleaseCheck:
    name: str
    passed: bool
    detail: str


VARIANTS = ("wearable_20x20", "wearable_28x28")
EXPECTED_NON_LED_FOOTPRINTS = {
    "wearable_20x20": 169,
    "wearable_28x28": 193,
}
REQUIRED_ROOT_SHEETS = (
    "power.kicad_sch",
    "mcu_usb.kicad_sch",
    "imu_gauge_input.kicad_sch",
    "audio.kicad_sch",
)


def check_bom(repository_root: Path) -> ReleaseCheck:
    status_path = repository_root / "manufacturing" / "BOM_FREEZE_STATUS.csv"
    with status_path.open(encoding="utf-8", newline="") as status_file:
        rows = list(csv.DictReader(status_file))

    blocked_rows = [
        row["Manufacturer Part"]
        for row in rows
        if row["Status"] in {"OPEN", "BLOCKED_DESIGN", "BLOCKED_EXTERNAL"}
    ]
    return ReleaseCheck(
        name="BOM freeze",
        passed=not blocked_rows,
        detail=(
            "all components released"
            if not blocked_rows
            else f"{len(blocked_rows)} blocked items: {', '.join(blocked_rows)}"
        ),
    )


def check_schematic(repository_root: Path, variant: str) -> ReleaseCheck:
    variant_directory = repository_root / "hardware" / variant
    missing_sheets = [
        sheet_name
        for sheet_name in REQUIRED_ROOT_SHEETS
        if not (variant_directory / sheet_name).exists()
    ]
    root_path = variant_directory / f"{variant}.kicad_sch"
    if not root_path.exists():
        missing_sheets.append(root_path.name)

    return ReleaseCheck(
        name=f"{variant} schematic hierarchy",
        passed=not missing_sheets,
        detail=(
            "required hierarchy present"
            if not missing_sheets
            else f"missing: {', '.join(missing_sheets)}"
        ),
    )


def check_board(repository_root: Path, variant: str) -> list[ReleaseCheck]:
    board_path = (
        repository_root / "hardware" / variant / f"{variant}.kicad_pcb"
    )
    board = pcbnew.LoadBoard(str(board_path))
    footprints = list(board.GetFootprints())
    non_led_footprints = [
        footprint
        for footprint in footprints
        if footprint.GetValue() != "MHPA1010RGBDT"
    ]
    unconnected_count = board.GetConnectivity().GetUnconnectedCount(False)
    ground_zones = [
        zone
        for zone in board.Zones()
        if zone.GetLayer() == pcbnew.In1_Cu and zone.GetNetname() == "GND"
    ]
    ground_pads = [
        pad
        for footprint in non_led_footprints
        for pad in footprint.Pads()
        if pad.GetNetname() == "GND"
    ]

    return [
        ReleaseCheck(
            name=f"{variant} backside placement",
            passed=(
                len(non_led_footprints)
                == EXPECTED_NON_LED_FOOTPRINTS[variant]
            ),
            detail=(
                f"{len(non_led_footprints)}/"
                f"{EXPECTED_NON_LED_FOOTPRINTS[variant]} "
                "non-LED footprints"
            ),
        ),
        ReleaseCheck(
            name=f"{variant} connectivity",
            passed=(
                unconnected_count == 0
                and len(non_led_footprints)
                == EXPECTED_NON_LED_FOOTPRINTS[variant]
            ),
            detail=(
                f"{unconnected_count} unconnected matrix items; "
                "full-product connectivity requires backside placement"
            ),
        ),
        ReleaseCheck(
            name=f"{variant} L2 ground plane",
            passed=bool(ground_zones) and bool(ground_pads),
            detail=(
                f"{len(ground_zones)} GND zones and "
                f"{len(ground_pads)} GND component pads on physical L2"
            ),
        ),
    ]


def collect_checks(repository_root: Path) -> list[ReleaseCheck]:
    checks = [check_bom(repository_root)]

    for variant in VARIANTS:
        checks.append(check_schematic(repository_root, variant))
        checks.extend(check_board(repository_root, variant))

    supplier_acceptance_path = (
        repository_root
        / "manufacturing"
        / "supplier"
        / "EDGE_LED_DFM_ACCEPTANCE.pdf"
    )
    checks.append(
        ReleaseCheck(
            name="Supplier DFM acceptance",
            passed=supplier_acceptance_path.exists(),
            detail=(
                "acceptance attached"
                if supplier_acceptance_path.exists()
                else "written edge-LED/reflow acceptance is absent"
            ),
        )
    )
    return checks


def print_report(checks: list[ReleaseCheck]) -> None:
    print("# Manufacturing release readiness")
    print()
    print("| Gate | Result | Detail |")
    print("|---|---|---|")
    for check in checks:
        result = "PASS" if check.passed else "BLOCKED"
        print(f"| {check.name} | {result} | {check.detail} |")


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    checks = collect_checks(repository_root)
    print_report(checks)

    if not all(check.passed for check in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
