from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from uuid import UUID, uuid5

from kicad_sch_api import Schematic, get_symbol_cache


UUID_NAMESPACE = UUID("c83e8188-39f5-49b6-9487-0c48c02ee084")
KICAD_SYMBOL_DIRECTORY = Path(
    os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
)
STANDARD_DRIVER_LIBRARY = KICAD_SYMBOL_DIRECTORY / "Driver_LED.kicad_sym"
CUSTOM_LIBRARY_NAME = "PartSignal_Wearable"
CUSTOM_LIBRARY_PATH = (
    Path(__file__).resolve().parents[1]
    / "libraries"
    / f"{CUSTOM_LIBRARY_NAME}.kicad_sym"
)
MBI5124_LIBRARY_ID = f"{CUSTOM_LIBRARY_NAME}:MBI5124GP-B"
MBI5124_FOOTPRINT = "Package_SO:SSOP-24_3.9x8.7mm_P0.635mm"
BUFFER_LIBRARY_ID = "74xGxx:SN74LVC1G125DBV"
BUFFER_FOOTPRINT = "Package_TO_SOT_SMD:SOT-23-5"
RESISTOR_FOOTPRINT = "Resistor_SMD:R_0603_1608Metric"
CAPACITOR_FOOTPRINT = "Capacitor_SMD:C_0603_1608Metric"


@dataclass(frozen=True)
class MatrixVariant:
    directory_name: str
    matrix_size: int


@dataclass(frozen=True)
class DriverDefinition:
    reference: str
    function_name: str
    color_name: str
    first_column: int
    position: tuple[float, float]


MATRIX_VARIANTS = (
    MatrixVariant("wearable_20x20", 20),
    MatrixVariant("wearable_28x28", 28),
)

DRIVERS = (
    DriverDefinition("U101", "U_LED_R_A", "R", 1, (50.8, 53.34)),
    DriverDefinition("U102", "U_LED_R_B", "R", 17, (114.3, 53.34)),
    DriverDefinition("U103", "U_LED_G_A", "G", 1, (177.8, 53.34)),
    DriverDefinition("U104", "U_LED_G_B", "G", 17, (50.8, 124.46)),
    DriverDefinition("U105", "U_LED_B_A", "B", 1, (114.3, 124.46)),
    DriverDefinition("U106", "U_LED_B_B", "B", 17, (177.8, 124.46)),
)


def deterministic_uuid(name: str) -> str:
    return str(uuid5(UUID_NAMESPACE, name))


def extract_symbol_expression(library_text: str, symbol_name: str) -> str:
    marker = f'\t(symbol "{symbol_name}"'
    expression_start = library_text.index(marker)
    nesting_depth = 0
    in_string = False
    escaped_character = False

    for character_index in range(expression_start, len(library_text)):
        character = library_text[character_index]

        if in_string:
            if escaped_character:
                escaped_character = False
            elif character == "\\":
                escaped_character = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "(":
            nesting_depth += 1
        elif character == ")":
            nesting_depth -= 1
            if nesting_depth == 0:
                return library_text[expression_start : character_index + 1]

    raise ValueError(f"Unterminated symbol expression: {symbol_name}")


def format_harness_pin(
    pin_type: str,
    pin_name: str,
    pin_number: int,
    x_position: float,
    y_position: float,
    rotation: int,
) -> str:
    return f"""\
\t\t\t(pin {pin_type} line
\t\t\t\t(at {x_position:.2f} {y_position:.2f} {rotation})
\t\t\t\t(length 2.54)
\t\t\t\t(name "{pin_name}"
\t\t\t\t\t(effects
\t\t\t\t\t\t(font
\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(number "{pin_number}"
\t\t\t\t\t(effects
\t\t\t\t\t\t(font
\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)"""


def generate_harness_symbol(matrix_size: int) -> str:
    symbol_name = f"LED_DRIVER_ERC_HARNESS_{matrix_size}"
    source_pins = (
        ("output", "LED_SDI"),
        ("output", "LED_CLK"),
        ("output", "LED_LE"),
        ("output", "LED_OE_N"),
        ("power_out", "LED_LOGIC_3V3"),
        ("power_out", "GND"),
    )
    sink_pins = [("input", "LED_SDO_RETURN")]
    sink_pins.extend(
        ("passive", f"COL_{color_name}_{column_number:02d}")
        for color_name in ("R", "G", "B")
        for column_number in range(1, matrix_size + 1)
    )
    maximum_pin_count = max(len(source_pins), len(sink_pins))
    top_y = (maximum_pin_count - 1) * 1.27
    bottom_y = -top_y
    pin_expressions = []

    for pin_index, (pin_type, pin_name) in enumerate(source_pins, start=1):
        pin_expressions.append(
            format_harness_pin(
                pin_type,
                pin_name,
                pin_index,
                -10.16,
                top_y - (pin_index - 1) * 2.54,
                0,
            )
        )

    for sink_index, (pin_type, pin_name) in enumerate(sink_pins, start=1):
        pin_number = len(source_pins) + sink_index
        pin_expressions.append(
            format_harness_pin(
                pin_type,
                pin_name,
                pin_number,
                10.16,
                top_y - (sink_index - 1) * 2.54,
                180,
            )
        )

    joined_pins = "\n".join(pin_expressions)
    return f"""\
\t(symbol "{symbol_name}"
\t\t(exclude_from_sim yes)
\t\t(in_bom no)
\t\t(on_board no)
\t\t(in_pos_files no)
\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t(property "Reference" "H"
\t\t\t(at -7.62 {top_y + 3.81:.2f} 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "{symbol_name}"
\t\t\t(at 7.62 {top_y + 3.81:.2f} 0)
\t\t\t(effects (font (size 1.27 1.27)) (justify right))
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at 0 0 0)
\t\t\t(hide yes)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Datasheet" ""
\t\t\t(at 0 0 0)
\t\t\t(hide yes)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Description" "Non-BOM external harness for standalone LED driver ERC"
\t\t\t(at 0 0 0)
\t\t\t(hide yes)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(symbol "{symbol_name}_0_1"
\t\t\t(rectangle
\t\t\t\t(start -7.62 {top_y + 1.27:.2f})
\t\t\t\t(end 7.62 {bottom_y - 1.27:.2f})
\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t(fill (type background))
\t\t\t)
\t\t)
\t\t(symbol "{symbol_name}_1_1"
{joined_pins}
\t\t)
\t)"""


def generate_custom_symbol_library() -> None:
    source_library_text = STANDARD_DRIVER_LIBRARY.read_text(encoding="utf-8")
    symbol_text = extract_symbol_expression(source_library_text, "MBI5252GP")

    replacements = (
        (
            "https://datasheet.lcsc.com/lcsc/"
            "1809031521_MBI-MBI5252GP-A_C261127.pdf",
            "https://www.lcsc.com/datasheet/C256866.pdf",
        ),
        (
            "16-Channel, 14-bit PWM constant current LED sink driver with "
            "built-in 8K-bit SRAM, 6-bit current gain, LED open detection, SSOP-24",
            "16-channel constant-current LED sink driver with ghosting "
            "elimination, SSOP-24",
        ),
        ("DCLK", "CLK"),
        ("GCLK", "~{OE}"),
        ("MBI5252GP", "MBI5124GP-B"),
    )

    for old_value, new_value in replacements:
        if old_value not in symbol_text:
            raise ValueError(f"Expected source symbol value is missing: {old_value}")
        symbol_text = symbol_text.replace(old_value, new_value)

    library_text = "\n".join(
        (
            "(kicad_symbol_lib",
            "\t(version 20251024)",
            '\t(generator "kicad_symbol_editor")',
            '\t(generator_version "10.0")',
            symbol_text,
            generate_harness_symbol(20),
            generate_harness_symbol(28),
            ")",
            "",
        )
    )
    CUSTOM_LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_LIBRARY_PATH.write_text(library_text, encoding="utf-8")


def configure_symbol_cache() -> None:
    symbol_cache = get_symbol_cache()
    symbol_cache.discover_libraries([KICAD_SYMBOL_DIRECTORY])

    if not symbol_cache.add_library_path(CUSTOM_LIBRARY_PATH):
        raise RuntimeError(f"Could not register symbol library {CUSTOM_LIBRARY_PATH}")

    mbi_symbol = symbol_cache.get_symbol(MBI5124_LIBRARY_ID)
    if mbi_symbol is None:
        raise RuntimeError("Generated MBI5124 symbol is not readable")

    expected_pin_names = {
        "1": "GND",
        "2": "SDI",
        "3": "CLK",
        "4": "LE",
        "21": "~{OE}",
        "22": "SDO",
        "23": "R-EXT",
        "24": "VDD",
    }
    actual_pin_names = {pin.number: pin.name for pin in mbi_symbol.pins}
    for pin_number, expected_pin_name in expected_pin_names.items():
        if actual_pin_names.get(pin_number) != expected_pin_name:
            raise ValueError(
                f"MBI5124 pin {pin_number}: expected {expected_pin_name}, "
                f"found {actual_pin_names.get(pin_number)}"
            )


def add_component(
    schematic: Schematic,
    *,
    generation_key: str,
    library_id: str,
    reference: str,
    value: str,
    position: tuple[float, float],
    footprint: str,
    rotation: float = 0,
    properties: dict[str, str] | None = None,
):
    component = schematic.components.add(
        library_id,
        reference=reference,
        value=value,
        position=position,
        footprint=footprint,
        rotation=rotation,
        component_uuid=deterministic_uuid(f"{generation_key}:component:{reference}"),
        **(properties or {}),
    )
    component._data.pin_uuids = {
        pin.number: deterministic_uuid(
            f"{generation_key}:component:{reference}:pin:{pin.number}"
        )
        for pin in component._data.pins
    }
    return component


def add_pin_label(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    pin_number: str,
    net_name: str,
) -> None:
    schematic.add_label(
        net_name,
        pin=(reference, pin_number),
        uuid=deterministic_uuid(
            f"{generation_key}:label:{reference}:{pin_number}:{net_name}"
        ),
    )


def add_no_connect(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    pin_number: str,
) -> None:
    pin_position = schematic.get_component_pin_position(reference, pin_number)
    if pin_position is None:
        raise ValueError(f"Pin not found for no-connect: {reference}.{pin_number}")

    schematic.no_connects.add(
        pin_position,
        no_connect_uuid=deterministic_uuid(
            f"{generation_key}:no-connect:{reference}:{pin_number}"
        ),
    )


def add_driver_support_components(
    schematic: Schematic,
    generation_key: str,
    driver_index: int,
    driver: DriverDefinition,
) -> None:
    resistor_reference = f"R{100 + driver_index}"
    capacitor_reference = f"C{100 + driver_index}"
    support_x = driver.position[0] - 22.86

    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:R",
        reference=resistor_reference,
        value="1.96k 0.1%",
        position=(support_x, driver.position[1] + 17.78),
        footprint=RESISTOR_FOOTPRINT,
        rotation=90,
        properties={"Function": f"{driver.function_name}_R_EXT"},
    )
    rext_net_name = f"{driver.function_name}_R_EXT"
    add_pin_label(schematic, generation_key, driver.reference, "23", rext_net_name)
    add_pin_label(schematic, generation_key, resistor_reference, "1", rext_net_name)
    add_pin_label(schematic, generation_key, resistor_reference, "2", "GND")

    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:C",
        reference=capacitor_reference,
        value="100nF",
        position=(support_x, driver.position[1] - 17.78),
        footprint=CAPACITOR_FOOTPRINT,
        properties={"Function": f"{driver.function_name}_DECOUPLING"},
    )
    add_pin_label(
        schematic,
        generation_key,
        capacitor_reference,
        "1",
        "LED_LOGIC_3V3",
    )
    add_pin_label(schematic, generation_key, capacitor_reference, "2", "GND")


def add_mbi5124_chain(
    schematic: Schematic,
    generation_key: str,
    matrix_size: int,
) -> None:
    for driver_index, driver in enumerate(DRIVERS, start=1):
        add_component(
            schematic,
            generation_key=generation_key,
            library_id=MBI5124_LIBRARY_ID,
            reference=driver.reference,
            value="MBI5124GP-B",
            position=driver.position,
            footprint=MBI5124_FOOTPRINT,
            properties={"Function": driver.function_name},
        )

        add_pin_label(schematic, generation_key, driver.reference, "1", "GND")
        add_pin_label(schematic, generation_key, driver.reference, "3", "LED_CLK")
        add_pin_label(schematic, generation_key, driver.reference, "4", "LED_LE")
        add_pin_label(schematic, generation_key, driver.reference, "21", "LED_OE_N")
        add_pin_label(
            schematic,
            generation_key,
            driver.reference,
            "24",
            "LED_LOGIC_3V3",
        )

        serial_input_net = (
            "LED_SDI" if driver_index == 1 else f"LED_CHAIN_{driver_index - 1:02d}"
        )
        serial_output_net = (
            "LED_SDO_FINAL"
            if driver_index == len(DRIVERS)
            else f"LED_CHAIN_{driver_index:02d}"
        )
        add_pin_label(
            schematic,
            generation_key,
            driver.reference,
            "2",
            serial_input_net,
        )
        add_pin_label(
            schematic,
            generation_key,
            driver.reference,
            "22",
            serial_output_net,
        )

        for channel_index in range(16):
            pin_number = str(5 + channel_index)
            column_number = driver.first_column + channel_index
            if column_number <= matrix_size:
                add_pin_label(
                    schematic,
                    generation_key,
                    driver.reference,
                    pin_number,
                    f"COL_{driver.color_name}_{column_number:02d}",
                )
            else:
                add_no_connect(
                    schematic,
                    generation_key,
                    driver.reference,
                    pin_number,
                )

        add_driver_support_components(
            schematic,
            generation_key,
            driver_index,
            driver,
        )


def add_sdo_return_buffer(schematic: Schematic, generation_key: str) -> None:
    buffer_reference = "U107"
    add_component(
        schematic,
        generation_key=generation_key,
        library_id=BUFFER_LIBRARY_ID,
        reference=buffer_reference,
        value="SN74LVC1G125DBVR",
        position=(241.3, 124.46),
        footprint=BUFFER_FOOTPRINT,
        properties={"Function": "U_LED_SDO_BUF"},
    )
    add_pin_label(schematic, generation_key, buffer_reference, "1", "GND")
    add_pin_label(
        schematic,
        generation_key,
        buffer_reference,
        "2",
        "LED_SDO_FINAL",
    )
    add_pin_label(schematic, generation_key, buffer_reference, "3", "GND")
    add_pin_label(
        schematic,
        generation_key,
        buffer_reference,
        "4",
        "LED_SDO_RETURN",
    )
    add_pin_label(
        schematic,
        generation_key,
        buffer_reference,
        "5",
        "LED_LOGIC_3V3",
    )

    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:R",
        reference="R107",
        value="100k",
        position=(266.7, 132.08),
        footprint=RESISTOR_FOOTPRINT,
        properties={"Function": "LED_SDO_RETURN_PULLDOWN"},
    )
    add_pin_label(schematic, generation_key, "R107", "1", "LED_SDO_RETURN")
    add_pin_label(schematic, generation_key, "R107", "2", "GND")

    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:C",
        reference="C107",
        value="100nF",
        position=(266.7, 116.84),
        footprint=CAPACITOR_FOOTPRINT,
        properties={"Function": "U_LED_SDO_BUF_DECOUPLING"},
    )
    add_pin_label(schematic, generation_key, "C107", "1", "LED_LOGIC_3V3")
    add_pin_label(schematic, generation_key, "C107", "2", "GND")


def add_erc_harness(
    schematic: Schematic,
    generation_key: str,
    matrix_size: int,
) -> None:
    harness_reference = "H1"
    harness_library_id = (
        f"{CUSTOM_LIBRARY_NAME}:LED_DRIVER_ERC_HARNESS_{matrix_size}"
    )
    harness = add_component(
        schematic,
        generation_key=generation_key,
        library_id=harness_library_id,
        reference=harness_reference,
        value=f"LED_DRIVER_ERC_HARNESS_{matrix_size}",
        position=(330.2, 139.7),
        footprint="",
        properties={"Function": "NON_BOM_ERC_HARNESS"},
    )
    harness._data.in_bom = False
    harness._data.on_board = False

    net_names = [
        "LED_SDI",
        "LED_CLK",
        "LED_LE",
        "LED_OE_N",
        "LED_LOGIC_3V3",
        "GND",
        "LED_SDO_RETURN",
    ]
    net_names.extend(
        f"COL_{color_name}_{column_number:02d}"
        for color_name in ("R", "G", "B")
        for column_number in range(1, matrix_size + 1)
    )

    for pin_number, net_name in enumerate(net_names, start=1):
        add_pin_label(
            schematic,
            generation_key,
            harness_reference,
            str(pin_number),
            net_name,
        )


def write_project_library_tables(output_directory: Path) -> None:
    symbol_table = """(sym_lib_table
  (lib (name "PartSignal_Wearable")(type "KiCad")(uri "${KIPRJMOD}/../libraries/PartSignal_Wearable.kicad_sym")(options "")(descr "Part Signal wearable custom symbols"))
  (lib (name "74xGxx")(type "KiCad")(uri "${KICAD10_SYMBOL_DIR}/74xGxx.kicad_sym")(options "")(descr ""))
  (lib (name "Device")(type "KiCad")(uri "${KICAD10_SYMBOL_DIR}/Device.kicad_sym")(options "")(descr ""))
  (lib (name "power")(type "KiCad")(uri "${KICAD10_SYMBOL_DIR}/power.kicad_sym")(options "")(descr ""))
)
"""
    footprint_table = """(fp_lib_table
  (lib (name "Capacitor_SMD")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Capacitor_SMD.pretty")(options "")(descr ""))
  (lib (name "Package_SO")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Package_SO.pretty")(options "")(descr ""))
  (lib (name "Package_TO_SOT_SMD")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Package_TO_SOT_SMD.pretty")(options "")(descr ""))
  (lib (name "Resistor_SMD")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Resistor_SMD.pretty")(options "")(descr ""))
)
"""
    (output_directory / "sym-lib-table").write_text(symbol_table, encoding="utf-8")
    (output_directory / "fp-lib-table").write_text(footprint_table, encoding="utf-8")
    (output_directory / "led_drivers.kicad_pro").write_text("{}\n", encoding="utf-8")


def generate_variant_schematic(repository_root: Path, variant: MatrixVariant) -> Path:
    generation_key = f"led-drivers:{variant.directory_name}"
    output_directory = repository_root / "hardware" / variant.directory_name
    output_path = output_directory / "led_drivers.kicad_sch"
    output_directory.mkdir(parents=True, exist_ok=True)
    write_project_library_tables(output_directory)

    schematic = Schematic.create(
        name=f"{variant.directory_name} LED drivers",
        uuid=deterministic_uuid(f"{generation_key}:schematic"),
        paper="A3",
    )
    schematic.set_title_block(
        title=f"{variant.matrix_size}x{variant.matrix_size} RGB LED drivers",
        date="2026-10-07",
        rev="A",
        company="Part Signal",
        comments={
            1: "Six color-homogeneous MBI5124 drivers",
            2: "Generated; edit hardware/tools/generate_led_driver_schematics.py",
        },
    )

    add_mbi5124_chain(
        schematic,
        generation_key,
        variant.matrix_size,
    )
    add_sdo_return_buffer(schematic, generation_key)
    add_erc_harness(schematic, generation_key, variant.matrix_size)
    schematic.save(output_path)

    subprocess.run(
        ("kicad-cli", "sch", "upgrade", "--force", str(output_path)),
        check=True,
        cwd=output_directory,
    )
    return output_path


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    generate_custom_symbol_library()
    configure_symbol_cache()

    for variant in MATRIX_VARIANTS:
        generated_path = generate_variant_schematic(repository_root, variant)
        print(f"Generated {generated_path}")


if __name__ == "__main__":
    main()
