from dataclasses import dataclass
import math
from pathlib import Path

import pcbnew


@dataclass(frozen=True)
class PadGeometry:
    number: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    has_copper: bool = True
    has_mask: bool = True
    has_paste: bool = True


DLA0010A_NAME = "TI_DLA0010A_VSON-HR-10_2x3mm_P0.5mm"
DLA0010A_PADS = (
    PadGeometry("1", -0.9, -1.0, 0.6, 0.25),
    PadGeometry("2", -0.9, -0.5, 0.6, 0.25),
    PadGeometry("3", -0.9, 0.0, 0.6, 0.25),
    PadGeometry("4", -0.9, 0.5, 0.6, 0.25),
    PadGeometry("5", -0.9, 1.0, 0.6, 0.25),
    PadGeometry("6", 0.75, 1.0, 0.9, 0.25),
    PadGeometry("7", 0.75, 0.5, 0.9, 0.25),
    PadGeometry("8", 0.55, 0.0, 1.3, 0.25, has_paste=False),
    PadGeometry("", 0.175, 0.0, 0.55, 0.25, False, False, True),
    PadGeometry("", 0.925, 0.0, 0.55, 0.25, False, False, True),
    PadGeometry("9", 0.75, -0.5, 0.9, 0.25),
    PadGeometry("10", 0.75, -1.0, 0.9, 0.25),
)


def millimeters(internal_units: int) -> float:
    return pcbnew.ToMM(internal_units)


def assert_close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > 0.000_001:
        raise ValueError(f"{label}: expected {expected}, found {actual}")


def rounded_rectangle_area(
    width_mm: float,
    height_mm: float,
    corner_radius_mm: float,
) -> float:
    square_corner_area_mm2 = 4 * corner_radius_mm**2
    rounded_corner_area_mm2 = math.pi * corner_radius_mm**2
    return (
        width_mm * height_mm
        - square_corner_area_mm2
        + rounded_corner_area_mm2
    )


def verify_pad(pad: pcbnew.PAD, expected: PadGeometry, index: int) -> None:
    position = pad.GetPosition()
    size = pad.GetSize()
    prefix = f"pad[{index}] {expected.number or 'paste-only'}"

    if pad.GetNumber() != expected.number:
        raise ValueError(
            f"{prefix} number: expected {expected.number!r}, "
            f"found {pad.GetNumber()!r}"
        )

    assert_close(millimeters(position.x), expected.x_mm, f"{prefix} x")
    assert_close(millimeters(position.y), expected.y_mm, f"{prefix} y")
    assert_close(millimeters(size.x), expected.width_mm, f"{prefix} width")
    assert_close(millimeters(size.y), expected.height_mm, f"{prefix} height")

    layer_expectations = (
        (pcbnew.F_Cu, expected.has_copper, "F.Cu"),
        (pcbnew.F_Mask, expected.has_mask, "F.Mask"),
        (pcbnew.F_Paste, expected.has_paste, "F.Paste"),
    )
    for layer, expected_presence, layer_name in layer_expectations:
        actual_presence = pad.IsOnLayer(layer)
        if actual_presence != expected_presence:
            raise ValueError(
                f"{prefix} {layer_name}: expected {expected_presence}, "
                f"found {actual_presence}"
            )


def verify_dla0010a(packages_directory: Path) -> None:
    footprint = pcbnew.FootprintLoad(str(packages_directory), DLA0010A_NAME)
    if footprint is None:
        raise FileNotFoundError(f"Unable to load {DLA0010A_NAME}")

    pads = list(footprint.Pads())
    if len(pads) != len(DLA0010A_PADS):
        raise ValueError(
            f"{DLA0010A_NAME}: expected {len(DLA0010A_PADS)} pad objects, "
            f"found {len(pads)}"
        )

    for index, (pad, expected) in enumerate(
        zip(pads, DLA0010A_PADS, strict=True),
        start=1,
    ):
        verify_pad(pad, expected, index)

    paste_area_mm2 = sum(
        rounded_rectangle_area(
            expected.width_mm,
            expected.height_mm,
            0.05,
        )
        for expected in DLA0010A_PADS
        if expected.number == "" and expected.has_paste
    )
    pad_8_area_mm2 = rounded_rectangle_area(1.3, 0.25, 0.05)
    paste_coverage = paste_area_mm2 / pad_8_area_mm2
    if not 0.83 <= paste_coverage <= 0.84:
        raise ValueError(
            f"pad 8 paste coverage: expected 83% to 84%, "
            f"found {paste_coverage:.1%}"
        )

    print(
        f"{DLA0010A_NAME}: 10 electrical pads, "
        f"pad 8 paste coverage {paste_coverage:.1%}"
    )


def main() -> None:
    packages_directory = (
        Path(__file__).resolve().parents[1] / "libraries" / "packages.pretty"
    )
    verify_dla0010a(packages_directory)


if __name__ == "__main__":
    main()
