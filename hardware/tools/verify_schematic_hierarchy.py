from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree


@dataclass(frozen=True)
class Variant:
    name: str
    led_count: int
    matrix_size: int


VARIANTS = (
    Variant("wearable_20x20", 400, 20),
    Variant("wearable_28x28", 784, 28),
)


def export_netlist(repository_root: Path, variant: Variant, output_path: Path) -> None:
    schematic_path = (
        repository_root
        / "hardware"
        / variant.name
        / f"{variant.name}.kicad_sch"
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


def build_pin_net_map(root: ElementTree.Element) -> dict[tuple[str, str], str]:
    pin_net_map: dict[tuple[str, str], str] = {}
    for net in root.findall("./nets/net"):
        net_name = net.get("name", "")
        for node in net.findall("node"):
            reference = node.get("ref", "")
            pin_number = node.get("pin", "")
            pin_net_map[(reference, pin_number)] = net_name
    return pin_net_map


def assert_net_suffix(
    pin_net_map: dict[tuple[str, str], str],
    reference: str,
    pin_number: str,
    expected_suffix: str,
) -> None:
    actual_net = pin_net_map.get((reference, pin_number))
    if actual_net is None or not actual_net.endswith(f"/{expected_suffix}"):
        raise ValueError(
            f"{reference}.{pin_number}: expected {expected_suffix}, "
            f"found {actual_net}"
        )


def verify_variant(netlist_path: Path, variant: Variant) -> None:
    root = ElementTree.parse(netlist_path).getroot()
    components = root.findall("./components/comp")
    component_values = {
        component.findtext("value", default="")
        for component in components
    }
    if any("ERC_HARNESS" in value for value in component_values):
        raise ValueError(f"{variant.name}: root netlist contains an ERC harness")

    led_count = sum(
        1
        for component in components
        if component.findtext("value") == "MHPA1010RGBDT"
    )
    if led_count != variant.led_count:
        raise ValueError(
            f"{variant.name}: expected {variant.led_count} LEDs, found {led_count}"
        )

    pin_net_map = build_pin_net_map(root)
    critical_pin_nets = {
        ("U10", "18"): "MCU_LED_CLK",
        ("U10", "19"): "MCU_LED_SDI",
        ("U10", "21"): "MCU_LED_LE",
        ("U10", "22"): "MCU_LED_OE_N",
        ("U10", "25"): "USB_MCU_D_N",
        ("U10", "26"): "USB_MCU_D_P",
        ("U10", "36"): "LED_SDO_RETURN",
        ("U10", "37"): "ROW_XLAT_OE_N",
        ("U10", "47"): "CHG_SHIP_N",
        ("U10", "48"): "LED_LOGIC_EN",
        ("U21", "2"): "BAT_RAW",
        ("U21", "3"): "BAT_RAW",
        ("U30", "1"): "MIC_AFE_OUT",
        ("U30", "3"): "MIC_AFE_IN",
        ("U30", "4"): "MIC_AFE_FB",
        ("U100", "2"): "MCU_LED_CLK",
        ("U100", "5"): "MCU_LED_SDI",
        ("U100", "9"): "MCU_LED_LE",
        ("U100", "12"): "MCU_LED_OE_N",
    }
    for (reference, pin_number), net_suffix in critical_pin_nets.items():
        assert_net_suffix(pin_net_map, reference, pin_number, net_suffix)

    for row_number in range(1, variant.matrix_size + 1):
        row_net = f"ROW_{row_number:02d}_ANODE"
        if not any(
            net_name.endswith(f"/{row_net}")
            for net_name in pin_net_map.values()
        ):
            raise ValueError(f"{variant.name}: missing {row_net}")

    for color_name in ("R", "G", "B"):
        for column_number in range(1, variant.matrix_size + 1):
            column_net = f"COL_{color_name}_{column_number:02d}"
            if not any(
                net_name.endswith(f"/{column_net}")
                for net_name in pin_net_map.values()
            ):
                raise ValueError(f"{variant.name}: missing {column_net}")

    print(
        f"{variant.name}: {len(components)} components, "
        f"{len(root.findall('./nets/net'))} nets, {led_count} LEDs"
    )


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        for variant in VARIANTS:
            netlist_path = temporary_path / f"{variant.name}.net.xml"
            export_netlist(repository_root, variant, netlist_path)
            verify_variant(netlist_path, variant)


if __name__ == "__main__":
    main()
