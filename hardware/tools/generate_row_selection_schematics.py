from pathlib import Path
import subprocess

from kicad_sch_api import Schematic

from generate_led_driver_schematics import (
    CAPACITOR_FOOTPRINT,
    CUSTOM_LIBRARY_NAME,
    MATRIX_VARIANTS,
    RESISTOR_FOOTPRINT,
    MatrixVariant,
    add_component,
    add_no_connect,
    add_pin_label,
    configure_symbol_cache,
    deterministic_uuid,
    generate_custom_symbol_library,
    write_project_library_tables,
)


TRANSLATOR_LIBRARY_ID = "Logic_LevelTranslator:SN74LVC8T245"
DECODER_LIBRARY_ID = "74xx:74LS154"
PMOS_LIBRARY_ID = "Transistor_FET:Q_PMOS_GSD"
DECODER_FOOTPRINT = "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"
PMOS_FOOTPRINT = "Package_TO_SOT_SMD:SOT-23"
TRANSLATOR_FOOTPRINT = (
    "PartSignal_Packages:"
    "TI_RHL0024A_VQFN-24-1EP_3.5x5.5mm_P0.5mm_EP2.05x4.05mm"
)
DECODER_OUTPUT_PINS = (
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


def add_resistor(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    value: str,
    position: tuple[float, float],
    first_net: str,
    second_net: str,
    function_name: str,
) -> None:
    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:R",
        reference=reference,
        value=value,
        position=position,
        footprint=RESISTOR_FOOTPRINT,
        rotation=90,
        properties={"Function": function_name},
    )
    add_pin_label(schematic, generation_key, reference, "2", first_net)
    add_pin_label(schematic, generation_key, reference, "1", second_net)


def add_capacitor(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    position: tuple[float, float],
    power_net: str,
    function_name: str,
) -> None:
    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:C",
        reference=reference,
        value="100nF",
        position=position,
        footprint=CAPACITOR_FOOTPRINT,
        properties={"Function": function_name},
    )
    add_pin_label(schematic, generation_key, reference, "1", power_net)
    add_pin_label(schematic, generation_key, reference, "2", "GND")


def add_translator(schematic: Schematic, generation_key: str) -> None:
    reference = "U201"
    add_component(
        schematic,
        generation_key=generation_key,
        library_id=TRANSLATOR_LIBRARY_ID,
        reference=reference,
        value="SN74LVC8T245RHLR",
        position=(55.88, 55.88),
        footprint=TRANSLATOR_FOOTPRINT,
        properties={
            "Function": "U_ROW_XLAT",
            "FootprintStatus": "RELEASED_TI_RHL0024A_4225250_REV_C",
        },
    )

    add_pin_label(schematic, generation_key, reference, "1", "AON_3V3")
    add_pin_label(schematic, generation_key, reference, "2", "AON_3V3")
    for address_index in range(4):
        add_pin_label(
            schematic,
            generation_key,
            reference,
            str(3 + address_index),
            f"ROW_A{address_index}",
        )
    add_pin_label(schematic, generation_key, reference, "7", "DEC_A_EN_N")
    add_pin_label(schematic, generation_key, reference, "8", "DEC_B_EN_N")
    add_pin_label(
        schematic,
        generation_key,
        reference,
        "9",
        "ROW_XLAT_A7_UNUSED",
    )
    add_pin_label(
        schematic,
        generation_key,
        reference,
        "10",
        "ROW_XLAT_A8_UNUSED",
    )
    for ground_pin in ("11", "12", "13"):
        add_pin_label(schematic, generation_key, reference, ground_pin, "GND")

    add_no_connect(schematic, generation_key, reference, "14")
    add_no_connect(schematic, generation_key, reference, "15")
    add_pin_label(schematic, generation_key, reference, "16", "DEC_B_EN_4V1_N")
    add_pin_label(schematic, generation_key, reference, "17", "DEC_A_EN_4V1_N")
    for address_index, pin_number in enumerate(("21", "20", "19", "18")):
        add_pin_label(
            schematic,
            generation_key,
            reference,
            pin_number,
            f"ROW_A{address_index}_4V1",
        )
    add_pin_label(schematic, generation_key, reference, "22", "ROW_XLAT_OE_N")
    add_pin_label(schematic, generation_key, reference, "23", "LED_4V1")
    add_pin_label(schematic, generation_key, reference, "24", "LED_4V1")

    add_resistor(
        schematic,
        generation_key,
        "R401",
        "10k",
        (83.82, 33.02),
        "ROW_XLAT_OE_N",
        "AON_3V3",
        "ROW_XLAT_OE_PULLUP",
    )
    for address_index in range(4):
        add_resistor(
            schematic,
            generation_key,
            f"R{402 + address_index}",
            "100k",
            (83.82, 43.18 + address_index * 7.62),
            f"ROW_A{address_index}_4V1",
            "GND",
            f"ROW_A{address_index}_B_SIDE_PULLDOWN",
        )
    for bank_index, bank_name in enumerate(("A", "B")):
        add_resistor(
            schematic,
            generation_key,
            f"R{406 + bank_index}",
            "47k",
            (83.82, 76.2 + bank_index * 7.62),
            f"DEC_{bank_name}_EN_4V1_N",
            "LED_4V1",
            f"DEC_{bank_name}_ENABLE_PULLUP",
        )
    for unused_channel_index in range(2):
        add_resistor(
            schematic,
            generation_key,
            f"R{408 + unused_channel_index}",
            "0R",
            (83.82, 93.98 + unused_channel_index * 7.62),
            f"ROW_XLAT_A{7 + unused_channel_index}_UNUSED",
            "GND",
            f"ROW_XLAT_A{7 + unused_channel_index}_GROUND_LINK",
        )

    add_capacitor(
        schematic,
        generation_key,
        "C201",
        (30.48, 43.18),
        "AON_3V3",
        "ROW_XLAT_VCCA_DECOUPLING",
    )
    add_capacitor(
        schematic,
        generation_key,
        "C202",
        (30.48, 68.58),
        "LED_4V1",
        "ROW_XLAT_VCCB_DECOUPLING",
    )


def add_decoder(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    bank_name: str,
    position: tuple[float, float],
) -> None:
    add_component(
        schematic,
        generation_key=generation_key,
        library_id=DECODER_LIBRARY_ID,
        reference=reference,
        value="74HC154PW,118",
        position=position,
        footprint=DECODER_FOOTPRINT,
        properties={"Function": f"U_DEC_{bank_name}"},
    )
    add_pin_label(schematic, generation_key, reference, "12", "GND")
    add_pin_label(
        schematic,
        generation_key,
        reference,
        "18",
        f"DEC_{bank_name}_EN_4V1_N",
    )
    add_pin_label(schematic, generation_key, reference, "19", "GND")
    for address_index, pin_number in enumerate(("23", "22", "21", "20")):
        add_pin_label(
            schematic,
            generation_key,
            reference,
            pin_number,
            f"ROW_A{address_index}_4V1",
        )
    add_pin_label(schematic, generation_key, reference, "24", "LED_4V1")


def get_row_component_position(row_number: int) -> tuple[float, float]:
    column_index = (row_number - 1) // 14
    row_in_column = (row_number - 1) % 14
    return (
        116.84 + column_index * 101.6,
        121.92 + row_in_column * 12.7,
    )


def add_row_switch(
    schematic: Schematic,
    generation_key: str,
    row_number: int,
    decoder_reference: str,
    decoder_output_index: int,
) -> None:
    pmos_reference = f"Q{200 + row_number}"
    series_reference = f"R{200 + row_number}"
    pullup_reference = f"R{300 + row_number}"
    decoder_output_net = (
        f"{decoder_reference}_Y{decoder_output_index:02d}_N"
    )
    gate_net = f"ROW_{row_number:02d}_GATE"
    row_net = f"ROW_{row_number:02d}_ANODE"
    pmos_x, pmos_y = get_row_component_position(row_number)

    add_pin_label(
        schematic,
        generation_key,
        decoder_reference,
        DECODER_OUTPUT_PINS[decoder_output_index],
        decoder_output_net,
    )
    add_resistor(
        schematic,
        generation_key,
        series_reference,
        "33R",
        (pmos_x - 17.78, pmos_y),
        decoder_output_net,
        gate_net,
        f"ROW_{row_number:02d}_GATE_SERIES",
    )
    add_resistor(
        schematic,
        generation_key,
        pullup_reference,
        "47k",
        (pmos_x, pmos_y - 7.62),
        gate_net,
        "LED_4V1",
        f"ROW_{row_number:02d}_GATE_PULLUP",
    )
    add_component(
        schematic,
        generation_key=generation_key,
        library_id=PMOS_LIBRARY_ID,
        reference=pmos_reference,
        value="AO3403",
        position=(pmos_x, pmos_y),
        footprint=PMOS_FOOTPRINT,
        properties={"Function": f"Q_ROW{row_number:02d}"},
    )
    add_pin_label(schematic, generation_key, pmos_reference, "1", gate_net)
    add_pin_label(schematic, generation_key, pmos_reference, "2", "LED_4V1")
    add_pin_label(schematic, generation_key, pmos_reference, "3", row_net)


def add_row_banks(
    schematic: Schematic,
    generation_key: str,
    variant: MatrixVariant,
) -> None:
    add_decoder(
        schematic,
        generation_key,
        reference="U202",
        bank_name="A",
        position=(127.0, 55.88),
    )
    add_decoder(
        schematic,
        generation_key,
        reference="U203",
        bank_name="B",
        position=(193.04, 55.88),
    )
    add_capacitor(
        schematic,
        generation_key,
        "C203",
        (152.4, 33.02),
        "LED_4V1",
        "DEC_A_DECOUPLING",
    )
    add_capacitor(
        schematic,
        generation_key,
        "C204",
        (218.44, 33.02),
        "LED_4V1",
        "DEC_B_DECOUPLING",
    )

    for row_number in range(1, variant.matrix_size + 1):
        if row_number <= 16:
            decoder_reference = "U202"
            decoder_output_index = row_number - 1
        else:
            decoder_reference = "U203"
            decoder_output_index = row_number - 17
        add_row_switch(
            schematic,
            generation_key,
            row_number,
            decoder_reference,
            decoder_output_index,
        )

    first_unused_output = max(0, variant.matrix_size - 16)
    for output_index in range(first_unused_output, 16):
        add_no_connect(
            schematic,
            generation_key,
            "U203",
            DECODER_OUTPUT_PINS[output_index],
        )


def add_erc_harness(
    schematic: Schematic,
    generation_key: str,
    variant: MatrixVariant,
) -> None:
    reference = "H2"
    library_id = (
        f"{CUSTOM_LIBRARY_NAME}:ROW_SELECTOR_ERC_HARNESS_{variant.matrix_size}"
    )
    harness = add_component(
        schematic,
        generation_key=generation_key,
        library_id=library_id,
        reference=reference,
        value=f"ROW_SELECTOR_ERC_HARNESS_{variant.matrix_size}",
        position=(304.8, 101.6),
        footprint="",
        properties={"Function": "NON_BOM_ERC_HARNESS"},
    )
    harness._data.in_bom = False
    harness._data.on_board = False

    net_names = [f"ROW_A{address_index}" for address_index in range(4)]
    net_names.extend(
        (
            "DEC_A_EN_N",
            "DEC_B_EN_N",
            "ROW_XLAT_OE_N",
            "AON_3V3",
            "LED_4V1",
            "GND",
        )
    )
    net_names.extend(
        f"ROW_{row_number:02d}_ANODE"
        for row_number in range(1, variant.matrix_size + 1)
    )
    for pin_number, net_name in enumerate(net_names, start=1):
        add_pin_label(
            schematic,
            generation_key,
            reference,
            str(pin_number),
            net_name,
        )


def generate_variant_row_selection(
    repository_root: Path,
    variant: MatrixVariant,
) -> Path:
    generation_key = f"row-selection:{variant.directory_name}"
    output_directory = repository_root / "hardware" / variant.directory_name
    output_path = output_directory / "row_selection.kicad_sch"
    output_directory.mkdir(parents=True, exist_ok=True)
    write_project_library_tables(output_directory, project_name="row_selection")

    schematic = Schematic.create(
        name=f"{variant.directory_name} row selection",
        uuid=deterministic_uuid(f"{generation_key}:schematic"),
        paper="A2",
    )
    schematic.set_title_block(
        title=f"{variant.matrix_size}-row high-side selector",
        date="2026-10-07",
        rev="A",
        company="Part Signal",
        comments={
            1: "SN74LVC8T245 + dual 74HC154 + AO3403",
            2: "Generated; edit hardware/tools/generate_row_selection_schematics.py",
        },
    )
    add_translator(schematic, generation_key)
    add_row_banks(schematic, generation_key, variant)
    add_erc_harness(schematic, generation_key, variant)
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
        generated_path = generate_variant_row_selection(
            repository_root,
            variant,
        )
        print(f"Generated {generated_path}")


if __name__ == "__main__":
    main()
