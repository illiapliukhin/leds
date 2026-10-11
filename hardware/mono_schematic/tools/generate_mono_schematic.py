#!/usr/bin/env python3
"""Generate hierarchical KiCad schematics for mono_electronics from PCB pad nets."""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMATIC_ROOT = REPOSITORY_ROOT / "hardware/mono_schematic"
SHEETS_DIR = SCHEMATIC_ROOT / "sheets"
TOOLS_DIR = SCHEMATIC_ROOT / "tools"

sys.path.insert(0, str(TOOLS_DIR))

from extract_pcb_components import extract_board  # noqa: E402
from kicad_sch_writer import (  # noqa: E402
    pad_sort_key,
    GlobalLabel,
    LibSymbolDef,
    JunctionMarker,
    NoConnectMarker,
    PlacedSymbol,
    SchematicDocument,
    WireSegment,
    build_box_pins,
    new_uuid,
    render_document,
    snap_to_grid,
)


SYMBOL_PIN_CONNECT_MM = 5.08
NET_PAD_COUNT: dict[str, int] = {}  # single-pad nets (FFC spares) get a no-connect flag instead of a label
LABEL_STUB_MM = 6.35


@dataclass(frozen=True)
class SheetSpec:
    name: str
    filename: str
    title: str
    reference_prefixes: tuple[str, ...] = ()
    reference_exact: frozenset[str] = frozenset()


SHEET_SPECS: list[SheetSpec] = [
    SheetSpec(
        "root",
        "mono_electronics.kicad_sch",
        "Mono electronics - hierarchy root",
    ),
    SheetSpec(
        "power",
        "sheets/power.kicad_sch",
        "Power - charger, bucks, LDO, switches, battery",
        reference_exact=frozenset(
            {
                "U_CHG",
                "U_LED_PWR",
                "L_LED",
                "U_LDO",
                "U_LED_LOGIC",
                "U_AUDIO_SW",
                "J_BAT",
                "F_BAT",
                "Q_BAT",
                "R_BATG",
                "U_OVP",
                "D_VBUS",
                "R_ILM",
                "R_EN_TOP",
                "R_EN_BOT",
                "U_GAUGE",
                "C_SYS",
                "C_LED1",
                "C_LED2",
                "C_LDO_IN",
                "C_LDO_OUT",
                "C_CHG_SYS",
                "C_CHG_BAT",
                "C_CHG_IN",
                "R_FB_TOP",
                "R_FB_BOT",
                "R_EN_PD",
                "R_LOGIC_PD",
                "R_QOD",
                "R_AUD_PD",
                "R_ILIM",
                "R_ISET",
                "TH_PCB",
                "R_TH",
                "R_EN_SER",
                "C_EN",
                "C_GAUGE",
                "R_ALRT",
                "C_ASW_IN",
                "C_AUD_SW",
                "C_LL_IN",
                "C_LL1",
                "C_LL2",
            }
        ),
    ),
    SheetSpec(
        "mcu",
        "sheets/mcu.kicad_sch",
        "MCU - ESP32-S3, USB, crystal, boot",
        reference_exact=frozenset(
            {
                "U1",
                "Y1",
                "SW1",
                "J_USB",
                "U_ESD",
                "C_USB1",
                "C_MCU1",
                "C_MCU_A2",
                "C_MCU_A3",
                "C_MCU_CPU",
                "C_MCU_DA1",
                "C_MCU_DA2",
                "C_MCU_RTC",
                "C_MCU_SPI",
                "R_CHIP_PU",
                "C_CHIP_PU",
                "R_BOOT0",
                "R_USB_P",
                "R_USB_N",
                "C_XTAL1",
                "C_XTAL2",
                "TP1",
                "TP2",
                "R_CC1",
                "R_CC2",
                "L_XTAL",
            }
        ),
    ),
    SheetSpec(
        "imu",
        "sheets/imu.kicad_sch",
        "IMU - BMI270",
        reference_exact=frozenset({"U_IMU", "C_IMU_VDD", "C_IMU_VIO", "R_SDA", "R_SCL"}),
    ),
    SheetSpec(
        "led_drive",
        "sheets/led_drive.kicad_sch",
        "LED column drive - MBI5124, buffers, translator, decoders, FFC col",
        reference_prefixes=("U_LED", "U_DEC_", "C_LED1_V", "C_LED2_V", "C_BUF_V", "C_DECA_V", "C_DECB_V", "C_XLAT", "U_ROW_", "U_LED_", "J_COL", "R_EXT", "R_ADDR", "R_EN", "R_XOE", "R_SDI", "R_CLK", "R_LE", "R_OE"),
    ),
    SheetSpec(
        "row_farm",
        "sheets/row_farm.kicad_sch",
        "Row farm - AO3403 x32, FFC row",
        reference_prefixes=("Q_ROW", "R_G", "R_PU", "J_ROW"),
    ),
    SheetSpec(
        "audio",
        "sheets/audio.kicad_sch",
        "Audio - microphone and op-amp",
        reference_exact=frozenset({"MIC1", "U_AUDIO", "C_AUD", "C_MIC", "C_AC", "C_B", "C_GN", "R_B1", "R_B2", "R_F", "R_GN", "R_INB"}),
    ),
    SheetSpec(
        "stacking",
        "sheets/stacking.kicad_sch",
        "Stacking ports N/S/W/E - JST-SH 6P, RS-485 (THVD1406), ESD, termination",
        reference_prefixes=("J_PORT_", "D_N_", "D_S_", "D_E_", "D_W_"),
        reference_exact=frozenset({"U_485", "C_485", "R_TERM", "JP_TERM"}),
    ),
    SheetSpec(
        "led_interface",
        "sheets/led_interface.kicad_sch",
        "LED interface standard v1 - FFC spares: panel ID I2C (33R/100R, PESD3V3S2UT), column-expansion taps (DNP)",
        reference_prefixes=("R_ID_", "D_ID", "R_EXP_"),
    ),
    SheetSpec(
        "install_headers",
        "sheets/install_headers.kicad_sch",
        "Installation-build cable headers (v14, DNP in wearable) - J_RH1/J_CH1 2x20 1.27 mm shrouded keyed box headers (XFCN BH127VS-40P-H49) in parallel with J_ROW1/J_COL1 pin-for-pin, PESD5V0S1BL per LED line",
        reference_prefixes=("J_RH", "J_CH", "D_R0", "D_R1", "D_R2", "D_R3", "D_C0", "D_C1", "D_C2", "D_C3"),
    ),
    SheetSpec(
        "mechanical",
        "sheets/mechanical.kicad_sch",
        "Mechanical - M2.5 plated mounting holes (GND)",
        reference_prefixes=("H",),
    ),
]


def assign_sheet(reference: str) -> str:
    # v11b: references got a trailing "1" for KiCad annotation (J_ROW -> J_ROW1); match both forms
    candidates = [reference] + ([reference[:-1]] if reference.endswith("1") else [])
    for candidate in candidates:
        sheet_name = _assign_sheet(candidate)
        if sheet_name:
            return sheet_name
    return "led_drive"


def _assign_sheet(reference: str) -> str | None:
    for sheet in SHEET_SPECS:
        if sheet.name == "root":
            continue
        if reference in sheet.reference_exact:
            return sheet.name
        if any(reference.startswith(prefix) for prefix in sheet.reference_prefixes):
            return sheet.name
    return None


def symbol_key(footprint: str, value: str, pad_numbers: tuple[str, ...]) -> str:
    safe_value = "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
    safe_footprint = "".join(
        character if character.isalnum() or character in "._-" else "_" for character in footprint
    )
    return f"mono_parts:{safe_value}_{safe_footprint}_{len(pad_numbers)}"


def pin_anchor(
    symbol_x_mm: float,
    symbol_y_mm: float,
    pin_side: str,
    y_offset_mm: float,
) -> tuple[float, float]:
    if pin_side == "left":
        x_mm = symbol_x_mm - SYMBOL_PIN_CONNECT_MM
    else:
        x_mm = symbol_x_mm + SYMBOL_PIN_CONNECT_MM
    y_mm = symbol_y_mm + y_offset_mm  # lib Y is up, sheet Y is down
    return x_mm, y_mm


def power_symbol_pin_anchor(
    symbol_x_mm: float,
    symbol_y_mm: float,
    library_id: str,
) -> tuple[float, float]:
    if library_id == "power:GND":
        return symbol_x_mm - SYMBOL_PIN_CONNECT_MM, symbol_y_mm
    return symbol_x_mm, symbol_y_mm


def add_power_flags(document: SchematicDocument) -> None:
    ground_x, ground_y = snap_to_grid(15.0), snap_to_grid(15.0)
    document.placed_symbols.append(
        PlacedSymbol(
            library_id="power:GND",
            reference="#PWR01",
            value="GND",
            footprint="",
            at_x_mm=ground_x,
            at_y_mm=ground_y,
        )
    )
    ground_pin_x, ground_pin_y = power_symbol_pin_anchor(ground_x, ground_y, "power:GND")
    ground_bus_x = ground_pin_x - LABEL_STUB_MM
    document.wires.append(WireSegment(ground_pin_x, ground_pin_y, ground_bus_x, ground_pin_y))
    document.global_labels.append(GlobalLabel("GND", ground_bus_x, ground_pin_y, 180.0))

    flag_x, flag_y = snap_to_grid(22.0), snap_to_grid(15.0)
    document.placed_symbols.append(
        PlacedSymbol(
            library_id="power:PWR_FLAG",
            reference="#FLG01",
            value="PWR_FLAG",
            footprint="",
            at_x_mm=flag_x,
            at_y_mm=flag_y,
        )
    )
    flag_pin_x, flag_pin_y = power_symbol_pin_anchor(flag_x, flag_y, "power:PWR_FLAG")
    document.wires.append(WireSegment(flag_pin_x, flag_pin_y, ground_bus_x, ground_pin_y))

    vbus_flag_x, vbus_flag_y = snap_to_grid(29.0), snap_to_grid(15.0)
    document.placed_symbols.append(
        PlacedSymbol(
            library_id="power:PWR_FLAG",
            reference="#FLG02",
            value="PWR_FLAG",
            footprint="",
            at_x_mm=vbus_flag_x,
            at_y_mm=vbus_flag_y,
        )
    )
    vbus_pin_x, vbus_pin_y = power_symbol_pin_anchor(vbus_flag_x, vbus_flag_y, "power:PWR_FLAG")
    vbus_label_x = vbus_pin_x + LABEL_STUB_MM
    document.wires.append(WireSegment(vbus_pin_x, vbus_pin_y, vbus_label_x, vbus_pin_y))
    document.global_labels.append(GlobalLabel("VBUS", vbus_label_x, vbus_pin_y, 0.0))


def build_sheet_document(
    sheet_name: str,
    title: str,
    components: list,
    lib_catalog: dict[str, LibSymbolDef],
) -> SchematicDocument:
    document = SchematicDocument(title=title, project_name="mono_electronics")

    origin_x = snap_to_grid(35.56)
    origin_y = snap_to_grid(35.56)
    column_pitch = snap_to_grid(45.72)
    row_pitch = snap_to_grid(55.88)
    columns = 4 if sheet_name != "row_farm" else 5

    for index, component in enumerate(components):
        column = index % columns
        row = index // columns
        symbol_x = snap_to_grid(origin_x + column * column_pitch)
        symbol_y = snap_to_grid(origin_y + row * row_pitch)

        pad_numbers = tuple(sorted(component.pad_nets.keys(), key=pad_sort_key))
        if not pad_numbers:
            pad_numbers = ("1",)
        key = symbol_key(component.footprint, component.value, pad_numbers)
        if key not in lib_catalog:
            pins = build_box_pins(list(pad_numbers), component.pad_nets)
            lib_catalog[key] = LibSymbolDef(
                library_id=key,
                pins=pins,
                reference_prefix=component.reference.rstrip("0123456789") or "U",
            )
        symbol_def = lib_catalog[key]
        placed = PlacedSymbol(
            library_id=key,
            reference=component.reference,
            value=component.value,
            footprint=f"mono_electronics:{component.footprint}",
            at_x_mm=symbol_x,
            at_y_mm=symbol_y,
            pin_numbers=[pin.number for pin in symbol_def.pins],
        )
        document.placed_symbols.append(placed)

        pin_side_by_number = {pin.number: pin.side for pin in symbol_def.pins}
        pin_offset_by_number = {pin.number: pin.y_offset_mm for pin in symbol_def.pins}
        for pad_number in pad_numbers:
            net_name = component.pad_nets.get(pad_number, "")
            side = pin_side_by_number.get(pad_number, "left")
            y_offset = pin_offset_by_number.get(pad_number, 0.0)
            anchor_x, anchor_y = pin_anchor(symbol_x, symbol_y, side, y_offset)
            if net_name and NET_PAD_COUNT.get(net_name, 0) > 1:
                direction = -1.0 if side == "left" else 1.0
                label_x = anchor_x + direction * LABEL_STUB_MM
                label_rotation = 180.0 if side == "left" else 0.0
                document.wires.append(
                    WireSegment(anchor_x, anchor_y, label_x, anchor_y)
                )
                document.junctions.append(JunctionMarker(anchor_x, anchor_y))
                document.junctions.append(JunctionMarker(label_x, anchor_y))
                document.global_labels.append(
                    GlobalLabel(net_name, label_x, anchor_y, label_rotation)
                )
            else:
                document.no_connects.append(NoConnectMarker(anchor_x, anchor_y))

    used_library_ids: list[str] = []
    seen_library_ids: set[str] = set()
    for placed_item in document.placed_symbols:
        if not placed_item.library_id.startswith("mono_parts:"):
            continue
        if placed_item.library_id in seen_library_ids:
            continue
        seen_library_ids.add(placed_item.library_id)
        used_library_ids.append(placed_item.library_id)
    document.lib_symbols = [lib_catalog[library_id] for library_id in used_library_ids]
    return document


def write_project_file() -> None:
    source_pro = REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pro"
    project_text = source_pro.read_text(encoding="utf-8")
    project_text = project_text.replace(
        '"top_level_sheets": []',
        '"top_level_sheets": [\n      {\n        "filename": "mono_electronics.kicad_sch",\n        '
        '"name": "mono_electronics",\n        "uuid": "c1a2b3c4-d5e6-7890-abcd-ef1234567890"\n      }\n    ]',
    )
    (SCHEMATIC_ROOT / "mono_electronics.kicad_pro").write_text(project_text, encoding="utf-8")


def write_libraries(lib_catalog: dict[str, LibSymbolDef]) -> None:
    """Symbol libs (mono_parts + power) and a footprint lib exported from the PCB, so ERC can resolve links."""
    import re
    from kicad_sch_writer import render_lib_symbol, embedded_power_symbols
    blocks = []
    for key in sorted(lib_catalog):
        text = render_lib_symbol(lib_catalog[key]).replace(f'"{key}"', '"' + key.split(":", 1)[1] + '"', 1)
        blocks.append(text)
    header = '(kicad_symbol_lib\n  (version 20241209)\n  (generator "mono_schematic")\n  (generator_version "1.0")\n'
    (SCHEMATIC_ROOT / "symbols").mkdir(exist_ok=True)
    (SCHEMATIC_ROOT / "symbols/mono_parts.kicad_sym").write_text(header + "\n".join("  " + b for b in blocks) + "\n)\n", encoding="utf-8")
    power = embedded_power_symbols().replace('"power:GND"', '"GND"', 1).replace('"power:PWR_FLAG"', '"PWR_FLAG"', 1)
    (SCHEMATIC_ROOT / "symbols/power.kicad_sym").write_text(header + power + "\n)\n", encoding="utf-8")
    (SCHEMATIC_ROOT / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "mono_parts")(type "KiCad")(uri "${KIPRJMOD}/symbols/mono_parts.kicad_sym")(options "")(descr "Generated mono_electronics symbols"))\n'
        '  (lib (name "power")(type "KiCad")(uri "${KIPRJMOD}/symbols/power.kicad_sym")(options "")(descr "GND / PWR_FLAG"))\n)\n', encoding="utf-8")
    (SCHEMATIC_ROOT / "fp-lib-table").write_text(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "mono_electronics")(type "KiCad")(uri "${KIPRJMOD}/footprints/mono_electronics.pretty")(options "")(descr "Footprints exported from mono_electronics.kicad_pcb"))\n)\n', encoding="utf-8")
    pretty = SCHEMATIC_ROOT / "footprints/mono_electronics.pretty"
    pretty.mkdir(parents=True, exist_ok=True)
    text = (REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pcb").read_text(encoding="utf-8")
    blocks = {}
    pos = 0
    while True:
        k = text.find("\n\t(footprint \"", pos)
        if k < 0:
            break
        depth = 0; m = k + 2
        while True:
            ch = text[m]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            elif ch == '"':
                m = text.index('"', m + 1)
                while text[m - 1] == "\\":
                    m = text.index('"', m + 1)
            m += 1
        block = text[k + 2:m + 1]; pos = m
        name = re.match(r'\(footprint "([^"]+)"', block).group(1)
        at = re.search(r'\n\t\t\(at [-\d.]+ [-\d.]+(?: ([-\d.]+))?\)', block)
        rot = float(at.group(1) or 0) if at else 0.0
        if name in blocks and blocks[name][0] == 0.0:
            continue
        if name in blocks and rot != 0.0:
            continue
        blocks[name] = (rot, block)
    for name, (rot, block) in blocks.items():
        b = re.sub(r'\n\t\t\(at [-\d.]+ [-\d.]+(?: [-\d.]+)?\)', "\n\t\t(at 0 0)", block, count=1)
        b = re.sub(r'\(net \d+ "[^"]*"\)|\(net "[^"]*"\)', "", b)
        b = re.sub(r'\n\t\t\(uuid "[^"]*"\)', "", b, count=1)
        b = b.replace('(footprint "' + name + '"', '(footprint "' + name + '"\n\t\t(version 20241229)\n\t\t(generator "mono_schematic")', 1)
        (pretty / (name + ".kicad_mod")).write_text(b.replace("\n\t", "\n") + "\n", encoding="utf-8")

def main() -> None:
    board_path = REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pcb"
    footprints = extract_board(board_path)
    manifest_payload = [
        {
            "reference": footprint.reference,
            "value": footprint.value,
            "footprint": footprint.footprint,
            "pad_nets": footprint.pad_nets,
        }
        for footprint in footprints
    ]
    (SCHEMATIC_ROOT / "mono_electronics_net_manifest.json").write_text(
        json.dumps(manifest_payload, indent=2),
        encoding="utf-8",
    )
    for footprint in footprints:
        for net_name in footprint.pad_nets.values():
            NET_PAD_COUNT[net_name] = NET_PAD_COUNT.get(net_name, 0) + 1
    by_sheet: dict[str, list] = defaultdict(list)
    for footprint in footprints:
        by_sheet[assign_sheet(footprint.reference)].append(footprint)

    lib_catalog: dict[str, LibSymbolDef] = {}
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)

    root_doc = SchematicDocument(
        title="Mono electronics - sheet index",
        project_name="mono_electronics",
        paper="A4",
    )
    add_power_flags(root_doc)
    x_origin = 30.0
    for index, sheet in enumerate(SHEET_SPECS):
        if sheet.name == "root":
            continue
        root_doc.child_sheets.append(
            (sheet.name, sheet.filename, x_origin + index * 45.0, 60.0)
        )

    root_doc.lib_symbols = []
    (SCHEMATIC_ROOT / "mono_electronics.kicad_sch").write_text(
        render_document(root_doc, path_instance="/"),
        encoding="utf-8",
    )

    for sheet in SHEET_SPECS:
        if sheet.name == "root":
            continue
        components = sorted(by_sheet.get(sheet.name, []), key=lambda item: item.reference)
        document = build_sheet_document(sheet.name, sheet.title, components, lib_catalog)
        output_path = SCHEMATIC_ROOT / sheet.filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        path_instance = f"/{new_uuid()}"
        output_path.write_text(
            render_document(document, path_instance=path_instance),
            encoding="utf-8",
        )

    catalog_path = SCHEMATIC_ROOT / "generated_symbol_catalog.json"
    catalog_path.write_text(
        json.dumps(sorted(lib_catalog.keys()), indent=2),
        encoding="utf-8",
    )
    write_project_file()
    write_libraries(lib_catalog)
    print(f"Wrote schematic hierarchy under {SCHEMATIC_ROOT}")


if __name__ == "__main__":
    main()
