from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree

import pcbnew


BOARD_SIZE_MM = 57.0
BATTERY_WIDTH_MM = 32.0
BATTERY_HEIGHT_MM = 40.0
EXPECTED_LED_COUNT = 400
EXPECTED_NON_LED_COUNT = 172
LED_VALUE = "MHPA1010RGBDT"
PRACTICAL_PACKING_EFFICIENCY = 0.85
LOCAL_FOOTPRINT_DIRECTORIES = {
    "PartSignal_LEDs": Path(__file__).resolve().parents[1]
    / "libraries"
    / "leds.pretty",
    "PartSignal_Packages": Path(__file__).resolve().parents[1]
    / "libraries"
    / "packages.pretty",
}
KICAD_FOOTPRINT_DIRECTORY = Path(
    os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
)


@dataclass(frozen=True)
class ComponentEnvelope:
    reference: str
    footprint_identifier: str
    width_mm: float
    height_mm: float

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm


def export_root_netlist(repository_root: Path, output_path: Path) -> None:
    schematic_path = (
        repository_root
        / "hardware"
        / "wearable_20x20"
        / "wearable_20x20.kicad_sch"
    )
    subprocess.run(
        (
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "-o",
            str(output_path),
            str(schematic_path),
        ),
        check=True,
        cwd=schematic_path.parent,
    )


def resolve_footprint_directory(library_name: str) -> Path:
    local_directory = LOCAL_FOOTPRINT_DIRECTORIES.get(library_name)
    if local_directory is not None:
        return local_directory
    return KICAD_FOOTPRINT_DIRECTORY / f"{library_name}.pretty"


def load_component_envelope(
    reference: str,
    footprint_identifier: str,
) -> ComponentEnvelope:
    if ":" not in footprint_identifier:
        raise ValueError(
            f"{reference}: invalid footprint identifier "
            f"{footprint_identifier!r}"
        )

    library_name, footprint_name = footprint_identifier.split(":", 1)
    footprint = pcbnew.FootprintLoad(
        str(resolve_footprint_directory(library_name)),
        footprint_name,
    )
    if footprint is None:
        raise FileNotFoundError(
            f"{reference}: cannot load {footprint_identifier}"
        )

    bounding_box = footprint.GetBoundingBox(False, False)
    return ComponentEnvelope(
        reference=reference,
        footprint_identifier=footprint_identifier,
        width_mm=pcbnew.ToMM(bounding_box.GetWidth()),
        height_mm=pcbnew.ToMM(bounding_box.GetHeight()),
    )


def read_component_envelopes(
    netlist_path: Path,
) -> tuple[int, list[ComponentEnvelope]]:
    root = ElementTree.parse(netlist_path).getroot()
    components = root.findall("./components/comp")
    led_count = sum(
        component.findtext("value", default="") == LED_VALUE
        for component in components
    )
    non_led_envelopes = [
        load_component_envelope(
            component.get("ref", ""),
            component.findtext("footprint", default="").strip(),
        )
        for component in components
        if component.findtext("value", default="") != LED_VALUE
    ]
    return led_count, non_led_envelopes


def verify_component_counts(
    led_count: int,
    non_led_envelopes: list[ComponentEnvelope],
) -> None:
    if led_count != EXPECTED_LED_COUNT:
        raise ValueError(
            f"expected {EXPECTED_LED_COUNT} LEDs, found {led_count}"
        )
    if len(non_led_envelopes) != EXPECTED_NON_LED_COUNT:
        raise ValueError(
            f"expected {EXPECTED_NON_LED_COUNT} non-LED components, "
            f"found {len(non_led_envelopes)}"
        )


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as temporary_directory:
        netlist_path = Path(temporary_directory) / "wearable_20x20.xml"
        export_root_netlist(repository_root, netlist_path)
        led_count, non_led_envelopes = read_component_envelopes(netlist_path)

    verify_component_counts(led_count, non_led_envelopes)
    component_envelope_area_mm2 = sum(
        component.area_mm2 for component in non_led_envelopes
    )
    area_outside_battery_mm2 = (
        BOARD_SIZE_MM * BOARD_SIZE_MM
        - BATTERY_WIDTH_MM * BATTERY_HEIGHT_MM
    )
    utilization_percent = (
        component_envelope_area_mm2 / area_outside_battery_mm2 * 100.0
    )
    theoretical_minimum_side_mm = math.sqrt(
        component_envelope_area_mm2
        + BATTERY_WIDTH_MM * BATTERY_HEIGHT_MM
    )
    practical_minimum_side_mm = math.sqrt(
        component_envelope_area_mm2 / PRACTICAL_PACKING_EFFICIENCY
        + BATTERY_WIDTH_MM * BATTERY_HEIGHT_MM
    )

    print(
        f"20x20: {led_count} LEDs and "
        f"{len(non_led_envelopes)} non-LED components"
    )
    print(
        "Non-LED assembly-envelope area: "
        f"{component_envelope_area_mm2:.1f} mm^2"
    )
    print(
        "Board area outside provisional battery projection: "
        f"{area_outside_battery_mm2:.1f} mm^2"
    )
    print(f"Minimum rectangular-envelope utilization: {utilization_percent:.1f}%")
    print(
        "Theoretical square-side floor at 100% packing: "
        f"{theoretical_minimum_side_mm:.1f} mm"
    )
    print(
        "Square-side baseline at "
        f"{PRACTICAL_PACKING_EFFICIENCY:.0%} packing: "
        f"{practical_minimum_side_mm:.1f} mm"
    )

    if component_envelope_area_mm2 > area_outside_battery_mm2:
        raise ValueError(
            "component-free 32x40 mm battery projection is infeasible: "
            "component envelopes exceed all area outside the projection. "
            f"the outline must be at least "
            f"{theoretical_minimum_side_mm:.1f} mm square even at impossible "
            "100% packing, and approximately "
            f"{practical_minimum_side_mm:.1f} mm at the declared packing "
            "baseline. Freeze a larger outline, split the electronics onto "
            "another PCB, or qualify a revised battery/component stack before "
            "production placement."
        )


if __name__ == "__main__":
    main()
