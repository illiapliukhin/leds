from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from kicad_sch_api import Schematic, get_symbol_cache

from generate_led_driver_schematics import (
    CAPACITOR_FOOTPRINT,
    MATRIX_VARIANTS,
    RESISTOR_FOOTPRINT,
    MatrixVariant,
    add_component,
    add_no_connect,
    add_pin_label,
    configure_symbol_cache,
    deterministic_uuid,
    generate_custom_symbol_library,
)


KICAD_SYMBOL_DIRECTORY = Path(
    os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
)
PLATFORM_LIBRARY_NAME = "PartSignal_Platform"
PLATFORM_LIBRARY_PATH = (
    Path(__file__).resolve().parents[1]
    / "libraries"
    / f"{PLATFORM_LIBRARY_NAME}.kicad_sym"
)
CUSTOM_SYMBOLS = {
    "BQ25185": (
        "https://www.ti.com/lit/ds/symlink/bq25185.pdf",
        "Package_DFN_QFN:"
        "Texas_DLH0010A_WSON-10-1EP_2.2x2mm_P0.4mm_EP0.9x1.5mm",
        (
            ("power_out", "SYS", "1"),
            ("power_in", "BAT", "2"),
            ("open_collector", "STAT2", "3"),
            ("passive", "~{CE}", "4"),
            ("power_in", "GND", "5"),
            ("bidirectional", "TS/MR", "6"),
            ("passive", "ILIM/VSET", "7"),
            ("passive", "ISET", "8"),
            ("open_collector", "STAT1", "9"),
            ("power_in", "IN", "10"),
            ("power_in", "GND", "11"),
        ),
    ),
    "TPS63802DLAR": (
        "https://www.ti.com/lit/ds/symlink/tps63802.pdf",
        "",
        (
            ("input", "EN", "1"),
            ("input", "MODE", "2"),
            ("power_in", "AGND", "3"),
            ("input", "FB", "4"),
            ("open_collector", "PG", "5"),
            ("power_out", "VOUT", "6"),
            ("passive", "L2", "7"),
            ("power_in", "GND", "8"),
            ("passive", "L1", "9"),
            ("power_in", "VIN", "10"),
        ),
    ),
    "BMI270": (
        "https://www.bosch-sensortec.com/media/boschsensortec/"
        "downloads/datasheets/bst-bmi270-ds000.pdf",
        "Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm",
        (
            ("passive", "SDO", "1"),
            ("bidirectional", "ASDx", "2"),
            ("bidirectional", "ASCx", "3"),
            ("bidirectional", "INT1", "4"),
            ("power_in", "VDDIO", "5"),
            ("power_in", "GNDIO", "6"),
            ("power_in", "GND", "7"),
            ("power_in", "VDD", "8"),
            ("bidirectional", "INT2", "9"),
            ("input", "OCSB", "10"),
            ("output", "OSDO", "11"),
            ("input", "CSB", "12"),
            ("input", "SCx", "13"),
            ("bidirectional", "SDx", "14"),
        ),
    ),
    "MAX17048G+T10": (
        "https://www.analog.com/media/en/technical-documentation/"
        "data-sheets/max17048-max17049.pdf",
        "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
        (
            ("passive", "CTG", "1"),
            ("power_in", "CELL", "2"),
            ("power_in", "VDD", "3"),
            ("power_in", "GND", "4"),
            ("open_collector", "~{ALERT}", "5"),
            ("input", "QSTRT", "6"),
            ("input", "SCL", "7"),
            ("bidirectional", "SDA", "8"),
            ("power_in", "GND", "9"),
        ),
    ),
}


@dataclass(frozen=True)
class SheetDefinition:
    filename: str
    title: str
    paper: str


SHEET_DEFINITIONS = (
    SheetDefinition("power.kicad_sch", "Power tree", "A3"),
    SheetDefinition("mcu_usb.kicad_sch", "MCU and native USB", "A3"),
    SheetDefinition(
        "imu_gauge_input.kicad_sch", "IMU, gauge, and input", "A4"
    ),
    SheetDefinition("audio.kicad_sch", "Microphone AFE", "A4"),
)


def format_pin(
    pin_type: str,
    pin_name: str,
    pin_number: str,
    x_position: float,
    y_position: float,
    rotation: int,
) -> str:
    return f"""\
			(pin {pin_type} line
				(at {x_position:.2f} {y_position:.2f} {rotation})
				(length 2.54)
				(name "{pin_name}" (effects (font (size 1.27 1.27))))
				(number "{pin_number}" (effects (font (size 1.27 1.27))))
			)"""


def generate_symbol_expression(
    symbol_name: str,
    datasheet: str,
    footprint: str,
    pins: tuple[tuple[str, str, str], ...],
) -> str:
    pin_expressions = []
    split_index = (len(pins) + 1) // 2
    for pin_index, (pin_type, pin_name, pin_number) in enumerate(pins):
        left_side = pin_index < split_index
        side_index = pin_index if left_side else pin_index - split_index
        pin_expressions.append(
            format_pin(
                pin_type,
                pin_name,
                pin_number,
                -10.16 if left_side else 10.16,
                7.62 - side_index * 2.54,
                0 if left_side else 180,
            )
        )
    joined_pins = "\n".join(pin_expressions)
    return f"""\
	(symbol "{symbol_name}"
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(property "Reference" "U" (at -7.62 11.43 0)
			(effects (font (size 1.27 1.27)))
		)
		(property "Value" "{symbol_name}" (at 7.62 11.43 0)
			(effects (font (size 1.27 1.27)) (justify right))
		)
		(property "Footprint" "{footprint}" (at 0 0 0)
			(hide yes) (effects (font (size 1.27 1.27)))
		)
		(property "Datasheet" "{datasheet}" (at 0 0 0)
			(hide yes) (effects (font (size 1.27 1.27)))
		)
		(property "Description" "Pin map checked against primary manufacturer datasheet" (at 0 0 0)
			(hide yes) (effects (font (size 1.27 1.27)))
		)
		(symbol "{symbol_name}_0_1"
			(rectangle (start -7.62 10.16) (end 7.62 -10.16)
				(stroke (width 0.254) (type default))
				(fill (type background))
			)
		)
		(symbol "{symbol_name}_1_1"
{joined_pins}
		)
	)"""


def generate_platform_symbol_library() -> None:
    expressions = [
        generate_symbol_expression(symbol_name, datasheet, footprint, pins)
        for symbol_name, (datasheet, footprint, pins) in CUSTOM_SYMBOLS.items()
    ]
    text = "\n".join(
        (
            "(kicad_symbol_lib",
            "\t(version 20251024)",
            '\t(generator "kicad_symbol_editor")',
            '\t(generator_version "10.0")',
            *expressions,
            ")",
            "",
        )
    )
    PLATFORM_LIBRARY_PATH.write_text(text, encoding="utf-8")


def configure_platform_symbol_cache() -> None:
    cache = get_symbol_cache()
    cache.discover_libraries([KICAD_SYMBOL_DIRECTORY])
    if not cache.add_library_path(PLATFORM_LIBRARY_PATH):
        raise RuntimeError(f"Could not register {PLATFORM_LIBRARY_PATH}")
    for symbol_name, (_, _, expected_pins) in CUSTOM_SYMBOLS.items():
        symbol = cache.get_symbol(
            f"{PLATFORM_LIBRARY_NAME}:{symbol_name}"
        )
        if symbol is None:
            raise RuntimeError(f"Generated symbol is not readable: {symbol_name}")
        expected_map = {
            pin_number: pin_name
            for _, pin_name, pin_number in expected_pins
        }
        actual_map = {pin.number: pin.name for pin in symbol.pins}
        if actual_map != expected_map:
            raise ValueError(
                f"{symbol_name} pin map mismatch: "
                f"expected {expected_map}, found {actual_map}"
            )


def write_library_tables(output_directory: Path) -> None:
    symbol_libraries = (
        "74xGxx",
        "74xx",
        "Amplifier_Operational",
        "Device",
        "Logic_LevelTranslator",
        "MCU_Espressif",
        "Power_Management",
        "Power_Protection",
        "Regulator_Linear",
        "Transistor_FET",
        "power",
    )
    symbol_lines = [
        "(sym_lib_table",
        (
            '  (lib (name "PartSignal_Wearable")(type "KiCad")'
            '(uri "${KIPRJMOD}/../libraries/'
            'PartSignal_Wearable.kicad_sym")(options "")(descr ""))'
        ),
        (
            '  (lib (name "PartSignal_Platform")(type "KiCad")'
            '(uri "${KIPRJMOD}/../libraries/'
            'PartSignal_Platform.kicad_sym")(options "")(descr ""))'
        ),
    ]
    symbol_lines.extend(
        f'  (lib (name "{name}")(type "KiCad")'
        f'(uri "${{KICAD10_SYMBOL_DIR}}/{name}.kicad_sym")'
        '(options "")(descr ""))'
        for name in symbol_libraries
    )
    symbol_lines.append(")")
    (output_directory / "sym-lib-table").write_text(
        "\n".join(symbol_lines) + "\n", encoding="utf-8"
    )
    footprint_names = (
        "Capacitor_SMD",
        "Crystal",
        "Package_DFN_QFN",
        "Package_LGA",
        "Package_SO",
        "Package_TO_SOT_SMD",
        "Resistor_SMD",
    )
    footprint_lines = ["(fp_lib_table"]
    footprint_lines.extend(
        (
            '  (lib (name "PartSignal_LEDs")(type "KiCad")'
            '(uri "${KIPRJMOD}/../libraries/leds.pretty")'
            '(options "")(descr ""))',
            '  (lib (name "PartSignal_Packages")(type "KiCad")'
            '(uri "${KIPRJMOD}/../libraries/packages.pretty")'
            '(options "")(descr ""))',
        )
    )
    footprint_lines.extend(
        f'  (lib (name "{name}")(type "KiCad")'
        f'(uri "${{KICAD10_FOOTPRINT_DIR}}/{name}.pretty")'
        '(options "")(descr ""))'
        for name in footprint_names
    )
    footprint_lines.append(")")
    (output_directory / "fp-lib-table").write_text(
        "\n".join(footprint_lines) + "\n", encoding="utf-8"
    )


def add_resistor(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    value: str,
    position: tuple[float, float],
    first_net: str,
    second_net: str,
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
    )
    add_pin_label(schematic, generation_key, reference, "1", first_net)
    add_pin_label(schematic, generation_key, reference, "2", second_net)


def add_capacitor(
    schematic: Schematic,
    generation_key: str,
    reference: str,
    value: str,
    position: tuple[float, float],
    first_net: str,
    second_net: str = "GND",
) -> None:
    add_component(
        schematic,
        generation_key=generation_key,
        library_id="Device:C",
        reference=reference,
        value=value,
        position=position,
        footprint=CAPACITOR_FOOTPRINT,
    )
    add_pin_label(schematic, generation_key, reference, "1", first_net)
    add_pin_label(schematic, generation_key, reference, "2", second_net)


def create_sheet(
    variant: MatrixVariant,
    definition: SheetDefinition,
) -> tuple[Schematic, str]:
    generation_key = (
        f"platform:{variant.directory_name}:{definition.filename}"
    )
    schematic = Schematic.create(
        name=f"{variant.directory_name} {definition.title}",
        uuid=deterministic_uuid(f"{generation_key}:schematic"),
        paper=definition.paper,
    )
    schematic.set_title_block(
        title=f"{variant.directory_name} — {definition.title}",
        date="2026-10-07",
        rev="A",
        company="Part Signal",
        comments={
            1: "Generated; edit generate_platform_schematics.py",
            2: "Conditional design: see BOM_FREEZE_STATUS.csv",
        },
    )
    return schematic, generation_key


def generate_power_sheet(variant: MatrixVariant) -> Schematic:
    definition = SHEET_DEFINITIONS[0]
    schematic, key = create_sheet(variant, definition)
    add_component(
        schematic,
        generation_key=key,
        library_id=f"{PLATFORM_LIBRARY_NAME}:BQ25185",
        reference="U1",
        value="BQ25185",
        position=(45.72, 55.88),
        footprint=CUSTOM_SYMBOLS["BQ25185"][1],
        properties={
            "Function": "CHARGER_POWER_PATH",
            "FootprintStatus": "RELEASED_TI_DLH0010A",
        },
    )
    charger_nets = {
        "1": "SYS",
        "2": "BAT_RAW",
        "3": "CHG_STAT2_N",
        "4": "CHG_CE_N",
        "5": "GND",
        "6": "BAT_NTC",
        "7": "CHG_ILIM_SET",
        "8": "CHG_ISET",
        "9": "CHG_STAT1_N",
        "10": "VBUS_USB",
        "11": "GND",
    }
    for pin_number, net_name in charger_nets.items():
        add_pin_label(schematic, key, "U1", pin_number, net_name)
    add_resistor(
        schematic, key, "R1", "24k", (25.4, 78.74), "CHG_ILIM_SET", "GND"
    )
    add_resistor(
        schematic,
        key,
        "R2",
        "1k" if variant.matrix_size == 20 else "750R",
        (38.1, 78.74),
        "CHG_ISET",
        "GND",
    )
    add_capacitor(schematic, key, "C1", "1uF", (20.32, 43.18), "VBUS_USB")
    add_capacitor(schematic, key, "C2", "10uF", (30.48, 43.18), "SYS")
    add_capacitor(schematic, key, "C3", "1uF", (40.64, 43.18), "BAT_RAW")

    add_component(
        schematic,
        generation_key=key,
        library_id="Regulator_Linear:TPS7A20xxxDBV",
        reference="U2",
        value="TPS7A2033PDBVR",
        position=(96.52, 45.72),
        footprint="Package_TO_SOT_SMD:SOT-23-5",
        properties={"Function": "AON_3V3_LDO"},
    )
    for pin_number, net_name in {
        "1": "SYS",
        "2": "GND",
        "3": "SYS",
        "5": "AON_3V3",
    }.items():
        add_pin_label(schematic, key, "U2", pin_number, net_name)
    add_no_connect(schematic, key, "U2", "4")
    add_capacitor(schematic, key, "C4", "1uF", (83.82, 60.96), "SYS")
    add_capacitor(schematic, key, "C5", "4.7uF", (109.22, 60.96), "AON_3V3")

    add_component(
        schematic,
        generation_key=key,
        library_id=f"{PLATFORM_LIBRARY_NAME}:TPS63802DLAR",
        reference="U3",
        value="TPS63802DLAR",
        position=(157.48, 55.88),
        footprint=CUSTOM_SYMBOLS["TPS63802DLAR"][1],
        properties={
            "Function": "LED_4V1_BUCK_BOOST",
            "FootprintStatus": "BLOCKED_PACKAGE_LAND_PATTERN_RELEASE",
        },
    )
    for pin_number, net_name in {
        "1": "LED_EN",
        "2": "GND",
        "3": "GND",
        "4": "LED_FB",
        "5": "LED_PG_N",
        "6": "LED_4V1",
        "7": "LED_SW2",
        "8": "GND",
        "9": "LED_SW1",
        "10": "SYS",
    }.items():
        add_pin_label(schematic, key, "U3", pin_number, net_name)
    add_component(
        schematic,
        generation_key=key,
        library_id="Device:L",
        reference="L1",
        value="DFE201612E-R47M=P2 0.47uH",
        position=(157.48, 81.28),
        footprint="",
        properties={
            "Function": "LED_BUCK_BOOST_INDUCTOR",
            "FootprintStatus": "BLOCKED_MURATA_LAND_PATTERN_RELEASE",
        },
    )
    add_pin_label(schematic, key, "L1", "1", "LED_SW1")
    add_pin_label(schematic, key, "L1", "2", "LED_SW2")
    add_resistor(
        schematic, key, "R3", "655k 0.1%", (185.42, 48.26), "LED_4V1", "LED_FB"
    )
    add_resistor(
        schematic, key, "R4", "91k 0.1%", (185.42, 63.5), "LED_FB", "GND"
    )
    add_resistor(
        schematic, key, "R5", "100k", (134.62, 73.66), "LED_EN", "GND"
    )
    add_capacitor(schematic, key, "C6", "10uF", (137.16, 43.18), "SYS")
    add_capacitor(schematic, key, "C7", "22uF", (198.12, 45.72), "LED_4V1")
    add_capacitor(schematic, key, "C8", "22uF", (208.28, 45.72), "LED_4V1")

    for switch_index, (reference, enable, output) in enumerate(
        (
            ("U4", "LED_LOGIC_EN", "LED_LOGIC_3V3"),
            ("U5", "AUDIO_EN", "AUDIO_3V3"),
        )
    ):
        add_component(
            schematic,
            generation_key=key,
            library_id="Power_Management:TPS22917DBV",
            reference=reference,
            value="TPS22917DBVR",
            position=(83.82 + switch_index * 63.5, 111.76),
            footprint="Package_TO_SOT_SMD:SOT-23-6",
            properties={"Function": f"{output}_LOAD_SWITCH"},
        )
        for pin_number, net_name in {
            "1": "AON_3V3",
            "2": "GND",
            "3": enable,
            "4": f"{output}_CT",
            "5": f"{output}_QOD",
            "6": output,
        }.items():
            add_pin_label(schematic, key, reference, pin_number, net_name)
        base = 6 + switch_index * 4
        add_resistor(
            schematic,
            key,
            f"R{base}",
            "100k",
            (68.58 + switch_index * 63.5, 132.08),
            enable,
            "GND",
        )
        add_resistor(
            schematic,
            key,
            f"R{base + 1}",
            "1k" if switch_index == 0 else "DNP",
            (81.28 + switch_index * 63.5, 132.08),
            f"{output}_QOD",
            "GND",
        )
        add_capacitor(
            schematic,
            key,
            f"C{9 + switch_index * 2}",
            "1nF",
            (93.98 + switch_index * 63.5, 132.08),
            f"{output}_CT",
        )
        add_capacitor(
            schematic,
            key,
            f"C{10 + switch_index * 2}",
            "10uF",
            (106.68 + switch_index * 63.5, 132.08),
            output,
        )
    power_nets = (
        "GND",
        "VBUS_USB",
        "BAT_RAW",
    )
    for flag_index, net_name in enumerate(power_nets, start=1):
        add_component(
            schematic,
            generation_key=key,
            library_id="power:PWR_FLAG",
            reference=f"#FLG0{flag_index:03d}",
            value="PWR_FLAG",
            position=(25.4 + (flag_index - 1) * 20.32, 154.94),
            footprint="",
            properties={"Function": f"{net_name}_ERC_SOURCE"},
        )
        add_pin_label(
            schematic,
            key,
            f"#FLG0{flag_index:03d}",
            "1",
            net_name,
        )
    return schematic


def generate_mcu_usb_sheet(variant: MatrixVariant) -> Schematic:
    schematic, key = create_sheet(variant, SHEET_DEFINITIONS[1])
    add_component(
        schematic,
        generation_key=key,
        library_id="MCU_Espressif:ESP32-S3",
        reference="U10",
        value="ESP32-S3FN8",
        position=(91.44, 91.44),
        footprint="Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm",
        properties={
            "Function": "MCU",
            "PinAuditStatus": "CONDITIONAL_SEE_BOM_FREEZE_STATUS",
        },
    )
    pin_nets = {
        "2": "AON_3V3",
        "3": "AON_3V3",
        "4": "CHIP_PU",
        "6": "MIC_ADC",
        "7": "BAT_TS_ADC",
        "9": "PCB_NTC_ADC",
        "10": "PCB_NTC_EXCITE",
        "13": "I2C_SDA",
        "14": "I2C_SCL",
        "15": "IMU_INT1",
        "16": "BUTTON_WAKE_N",
        "17": "GAUGE_ALERT_N",
        "18": "MCU_LED_CLK",
        "19": "MCU_LED_SDI",
        "20": "AON_3V3",
        "21": "MCU_LED_LE",
        "22": "MCU_LED_OE_N",
        "23": "ROW_A0",
        "24": "ROW_A1",
        "25": "USB_MCU_D_N",
        "26": "USB_MCU_D_P",
        "27": "ROW_A2",
        "38": "ROW_A3",
        "39": "DEC_A_EN_N",
        "40": "DEC_B_EN_N",
        "41": "LED_EN",
        "42": "AUDIO_EN",
        "43": "CHG_CE_N",
        "44": "CHG_STAT1_N",
        "45": "CHG_STAT2_N",
        "46": "AON_3V3",
        "47": "CHG_SHIP_N",
        "48": "LED_LOGIC_EN",
        "49": "SERVICE_UART_TX",
        "50": "SERVICE_UART_RX",
        "36": "LED_SDO_RETURN",
        "37": "ROW_XLAT_OE_N",
        "53": "XTAL_N",
        "54": "XTAL_P",
        "55": "AON_3V3",
        "56": "AON_3V3",
        "57": "GND",
    }
    for pin_number, net_name in pin_nets.items():
        add_pin_label(schematic, key, "U10", pin_number, net_name)
    reserved_pins = (
        "1",
        "5",
        "8",
        "11",
        "12",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "51",
        "52",
    )
    for pin_number in reserved_pins:
        add_no_connect(schematic, key, "U10", pin_number)
    add_resistor(
        schematic, key, "R20", "10k", (48.26, 35.56), "CHIP_PU", "AON_3V3"
    )
    add_capacitor(schematic, key, "C20", "1uF", (60.96, 35.56), "CHIP_PU")
    add_component(
        schematic,
        generation_key=key,
        library_id="Device:Crystal",
        reference="Y1",
        value="L327S400H11L 40MHz 10pF",
        position=(147.32, 40.64),
        footprint="",
        properties={
            "Function": "MCU_XTAL_40MHZ",
            "FootprintStatus": "CONDITIONAL_PACKAGE_AUDIT_REQUIRED",
        },
    )
    add_pin_label(schematic, key, "Y1", "1", "XTAL_P")
    add_pin_label(schematic, key, "Y1", "2", "XTAL_N")
    add_component(
        schematic,
        generation_key=key,
        library_id="Power_Protection:USBLC6-2SC6",
        reference="U11",
        value="USBLC6-2SC6",
        position=(177.8, 91.44),
        footprint="Package_TO_SOT_SMD:SOT-23-6",
        properties={"Function": "USB_ESD"},
    )
    for pin_number, net_name in {
        "1": "USB_CONN_D_N",
        "2": "GND",
        "3": "USB_CONN_D_P",
        "4": "USB_CONN_D_P",
        "5": "VBUS_USB",
        "6": "USB_CONN_D_N",
    }.items():
        add_pin_label(schematic, key, "U11", pin_number, net_name)
    add_resistor(
        schematic,
        key,
        "R21",
        "22R",
        (203.2, 81.28),
        "USB_MCU_D_N",
        "USB_CONN_D_N",
    )
    add_resistor(
        schematic,
        key,
        "R22",
        "22R",
        (203.2, 101.6),
        "USB_MCU_D_P",
        "USB_CONN_D_P",
    )
    add_resistor(
        schematic, key, "R23", "5.1k", (228.6, 81.28), "USB_CC1", "GND"
    )
    add_resistor(
        schematic, key, "R24", "5.1k", (228.6, 101.6), "USB_CC2", "GND"
    )
    return schematic


def generate_imu_gauge_sheet(variant: MatrixVariant) -> Schematic:
    schematic, key = create_sheet(variant, SHEET_DEFINITIONS[2])
    add_component(
        schematic,
        generation_key=key,
        library_id=f"{PLATFORM_LIBRARY_NAME}:BMI270",
        reference="U20",
        value="BMI270",
        position=(55.88, 55.88),
        footprint=CUSTOM_SYMBOLS["BMI270"][1],
        properties={
            "Function": "IMU",
            "FootprintStatus": "RELEASED_BOSCH_LGA14",
        },
    )
    for pin_number, net_name in {
        "2": "BMI_ASDX_UNUSED",
        "3": "BMI_ASCX_UNUSED",
        "4": "IMU_INT1",
        "5": "AON_3V3",
        "6": "GND",
        "7": "GND",
        "8": "AON_3V3",
        "9": "IMU_INT2",
        "10": "AON_3V3",
        "12": "AON_3V3",
        "13": "I2C_SCL",
        "14": "I2C_SDA",
    }.items():
        add_pin_label(schematic, key, "U20", pin_number, net_name)
    add_pin_label(schematic, key, "U20", "1", "GND")
    add_no_connect(schematic, key, "U20", "11")
    add_resistor(
        schematic,
        key,
        "R34",
        "0R",
        (68.58, 78.74),
        "BMI_ASDX_UNUSED",
        "GND",
    )
    add_resistor(
        schematic,
        key,
        "R35",
        "0R",
        (81.28, 78.74),
        "BMI_ASCX_UNUSED",
        "GND",
    )
    add_capacitor(schematic, key, "C30", "100nF", (30.48, 78.74), "AON_3V3")
    add_capacitor(schematic, key, "C31", "2.2uF", (43.18, 78.74), "AON_3V3")

    add_component(
        schematic,
        generation_key=key,
        library_id=f"{PLATFORM_LIBRARY_NAME}:MAX17048G+T10",
        reference="U21",
        value="MAX17048G+T10",
        position=(121.92, 55.88),
        footprint=CUSTOM_SYMBOLS["MAX17048G+T10"][1],
        properties={
            "Function": "FUEL_GAUGE",
            "FootprintStatus": "RELEASED_MAXIM_21_0168_90_0065",
        },
    )
    for pin_number, net_name in {
        "1": "GND",
        "2": "BAT_RAW",
        "3": "BAT_RAW",
        "4": "GND",
        "5": "GAUGE_ALERT_N",
        "6": "GND",
        "7": "I2C_SCL",
        "8": "I2C_SDA",
        "9": "GND",
    }.items():
        add_pin_label(schematic, key, "U21", pin_number, net_name)
    add_capacitor(schematic, key, "C32", "100nF", (101.6, 78.74), "BAT_RAW")
    add_resistor(
        schematic, key, "R30", "4.7k", (149.86, 45.72), "I2C_SDA", "AON_3V3"
    )
    add_resistor(
        schematic, key, "R31", "4.7k", (162.56, 45.72), "I2C_SCL", "AON_3V3"
    )
    add_resistor(
        schematic,
        key,
        "R32",
        "10k NTC TBD",
        (149.86, 76.2),
        "PCB_NTC_ADC",
        "GND",
    )
    add_resistor(
        schematic,
        key,
        "R33",
        "10k",
        (162.56, 76.2),
        "PCB_NTC_EXCITE",
        "PCB_NTC_ADC",
    )
    return schematic


def generate_audio_sheet(variant: MatrixVariant) -> Schematic:
    schematic, key = create_sheet(variant, SHEET_DEFINITIONS[3])
    add_component(
        schematic,
        generation_key=key,
        library_id="Amplifier_Operational:TLV9001IDCK",
        reference="U30",
        value="TLV9001IDCKR",
        position=(91.44, 60.96),
        footprint="Package_TO_SOT_SMD:SOT-353_SC-70-5",
        properties={"Function": "MICROPHONE_AFE"},
    )
    for pin_number, net_name in {
        "1": "MIC_AFE_OUT",
        "2": "GND",
        "3": "MIC_AFE_IN",
        "4": "MIC_AFE_FB",
        "5": "AUDIO_3V3",
    }.items():
        add_pin_label(schematic, key, "U30", pin_number, net_name)
    add_resistor(
        schematic, key, "R40", "100R", (30.48, 38.1), "AUDIO_3V3", "MIC_VDD"
    )
    add_capacitor(schematic, key, "C40", "1uF", (43.18, 38.1), "MIC_VDD")
    add_capacitor(schematic, key, "C41", "100nF", (55.88, 38.1), "MIC_VDD")
    add_capacitor(
        schematic,
        key,
        "C42",
        "1uF",
        (55.88, 60.96),
        "MIC_RAW",
        "MIC_AFE_IN",
    )
    add_resistor(
        schematic, key, "R41", "47k", (68.58, 78.74), "AUDIO_3V3", "MIC_BIAS"
    )
    add_resistor(
        schematic, key, "R42", "47k", (81.28, 78.74), "MIC_BIAS", "GND"
    )
    add_capacitor(schematic, key, "C43", "100nF", (93.98, 78.74), "MIC_BIAS")
    add_resistor(
        schematic,
        key,
        "R46",
        "100k",
        (106.68, 78.74),
        "MIC_AFE_IN",
        "MIC_BIAS",
    )
    add_resistor(
        schematic, key, "R43", "10k", (119.38, 50.8), "MIC_AFE_FB", "MIC_BIAS"
    )
    add_resistor(
        schematic,
        key,
        "R44",
        "200k",
        (132.08, 50.8),
        "MIC_AFE_OUT",
        "MIC_AFE_FB",
    )
    add_capacitor(
        schematic,
        key,
        "C44",
        "100pF",
        (132.08, 71.12),
        "MIC_AFE_OUT",
        "MIC_AFE_FB",
    )
    add_resistor(
        schematic, key, "R45", "1k", (157.48, 60.96), "MIC_AFE_OUT", "MIC_ADC"
    )
    add_capacitor(schematic, key, "C45", "22nF", (172.72, 76.2), "MIC_ADC")
    add_capacitor(schematic, key, "C46", "100nF", (106.68, 38.1), "AUDIO_3V3")
    return schematic


def save_sheet(
    output_directory: Path,
    filename: str,
    schematic: Schematic,
) -> Path:
    output_path = output_directory / filename
    schematic.save(output_path)
    subprocess.run(
        ("kicad-cli", "sch", "upgrade", "--force", str(output_path)),
        check=True,
        cwd=output_directory,
    )
    return output_path


def generate_root(
    output_directory: Path,
    variant: MatrixVariant,
) -> Path:
    key = f"platform-root:{variant.directory_name}"
    schematic = Schematic.create(
        name=f"{variant.directory_name} root",
        uuid=deterministic_uuid(f"{key}:schematic"),
        paper="A0",
    )
    schematic.set_title_block(
        title=f"{variant.matrix_size}x{variant.matrix_size} wearable",
        date="2026-10-07",
        rev="A",
        company="Part Signal",
        comments={
            1: "Harness-free generated product hierarchy",
            2: "Conditional design: unresolved BOM items remain blocked",
        },
    )
    child_sheets = (
        ("Power", "power.kicad_sch"),
        ("MCU_USB", "mcu_usb.kicad_sch"),
        ("IMU_Gauge_Input", "imu_gauge_input.kicad_sch"),
        ("Audio", "audio.kicad_sch"),
        ("LED_Drivers", "led_drivers.kicad_sch"),
        ("Row_Selection", "row_selection.kicad_sch"),
        ("LED_Matrix", "led_matrix.kicad_sch"),
    )
    child_entries = []
    all_net_names: set[str] = set()
    for sheet_name, filename in child_sheets:
        child = Schematic.load(output_directory / filename)
        net_names = {label.text for label in child.hierarchical_labels}
        child_entries.append((sheet_name, filename, net_names))
        all_net_names.update(net_names)
    ordered_net_names = sorted(all_net_names)
    net_offsets = {
        net_name: (net_index + 1) * 2.54
        for net_index, net_name in enumerate(ordered_net_names)
    }
    common_sheet_height = (len(ordered_net_names) + 2) * 2.54
    net_positions: dict[str, list[tuple[float, float]]] = {}
    for sheet_index, (sheet_name, filename, net_names) in enumerate(
        child_entries
    ):
        sheet_x = 20.32 + sheet_index * 160.02
        sheet_y = 20.32
        sheet_height = common_sheet_height
        sheet_uuid = schematic.add_sheet(
            sheet_name,
            filename,
            position=(sheet_x, sheet_y),
            size=(137.16, sheet_height),
            page_number=str(sheet_index + 2),
            uuid=deterministic_uuid(f"{key}:sheet:{filename}"),
        )
        for net_name in sorted(net_names):
            offset = net_offsets[net_name]
            schematic.add_sheet_pin(
                sheet_uuid,
                net_name,
                "passive",
                "left",
                offset,
                uuid=deterministic_uuid(
                    f"{key}:sheet:{filename}:pin:{net_name}"
                ),
            )
            pin_position = (sheet_x, sheet_y + sheet_height - offset)
            net_positions.setdefault(net_name, []).append(pin_position)

    for net_name, positions in sorted(net_positions.items()):
        first_position = positions[0]
        if len(positions) == 1:
            schematic.no_connects.add(
                first_position,
                no_connect_uuid=deterministic_uuid(
                    f"{key}:root-no-connect:{net_name}"
                ),
            )
            continue
        start = min(positions, key=lambda point: point[0])
        end = max(positions, key=lambda point: point[0])
        wire_uuid = schematic.wires.add(
            start=start,
            end=end,
            uuid=deterministic_uuid(f"{key}:root-wire:{net_name}"),
        )
        schematic._sync_wires_to_data()
        schematic._format_sync_manager.mark_dirty(
            "wire", "add", {"uuid": wire_uuid}
        )
        schematic._modified = True
    output_path = output_directory / f"{variant.directory_name}.kicad_sch"
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
    generate_platform_symbol_library()
    configure_symbol_cache()
    configure_platform_symbol_cache()
    for variant in MATRIX_VARIANTS:
        output_directory = (
            repository_root / "hardware" / variant.directory_name
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        write_library_tables(output_directory)
        generators = (
            generate_power_sheet,
            generate_mcu_usb_sheet,
            generate_imu_gauge_sheet,
            generate_audio_sheet,
        )
        for definition, generator in zip(SHEET_DEFINITIONS, generators):
            output_path = save_sheet(
                output_directory,
                definition.filename,
                generator(variant),
            )
            print(f"Generated {output_path}")
        root_path = generate_root(output_directory, variant)
        print(f"Generated {root_path}")


if __name__ == "__main__":
    main()
