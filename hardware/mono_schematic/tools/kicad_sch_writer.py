"""KiCad 10 s-expression schematic writer (KiCadAI-compatible subset)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal


PinElectricalType = Literal[
    "input",
    "output",
    "bidirectional",
    "tri_state",
    "passive",
    "free",
    "unspecified",
    "power_in",
    "power_out",
    "open_collector",
    "open_emitter",
    "no_connect",
]


def new_uuid() -> str:
    return str(uuid.uuid4())


GRID_MM = 1.27


def snap_to_grid(value_mm: float, grid_mm: float = GRID_MM) -> float:
    return round(value_mm / grid_mm) * grid_mm


def fmt(value: float) -> str:
    snapped = snap_to_grid(value)
    text = f"{snapped:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def fmt_angle(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


@dataclass
class SchPin:
    number: str
    name: str
    electrical_type: PinElectricalType
    side: Literal["left", "right"] = "left"
    y_offset_mm: float = 0.0


@dataclass
class LibSymbolDef:
    library_id: str
    pins: list[SchPin]
    reference_prefix: str = "U"


@dataclass
class PlacedSymbol:
    library_id: str
    reference: str
    value: str
    footprint: str
    at_x_mm: float
    at_y_mm: float
    rotation_deg: float = 0.0
    pin_numbers: list[str] = field(default_factory=list)


@dataclass
class GlobalLabel:
    net_name: str
    at_x_mm: float
    at_y_mm: float
    rotation_deg: float = 0.0


@dataclass
class WireSegment:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float


@dataclass
class NoConnectMarker:
    at_x_mm: float
    at_y_mm: float


@dataclass
class JunctionMarker:
    at_x_mm: float
    at_y_mm: float


@dataclass
class SchematicDocument:
    title: str
    paper: str = "A3"
    lib_symbols: list[LibSymbolDef] = field(default_factory=list)
    placed_symbols: list[PlacedSymbol] = field(default_factory=list)
    wires: list[WireSegment] = field(default_factory=list)
    global_labels: list[GlobalLabel] = field(default_factory=list)
    no_connects: list[NoConnectMarker] = field(default_factory=list)
    junctions: list[JunctionMarker] = field(default_factory=list)
    child_sheets: list[tuple[str, str, float, float]] = field(default_factory=list)
    project_name: str = "mono_electronics"


def power_pin_type(net_name: str) -> PinElectricalType:
    upper = net_name.upper()
    if upper in {"GND", "AGND", "PGND"}:
        return "power_in"
    return "passive"


def pad_sort_key(pad_number: str) -> tuple[int, int | str]:
    if pad_number.isdigit():
        return (0, int(pad_number))
    return (1, pad_number)


def build_box_pins(pad_numbers: list[str], pad_nets: dict[str, str]) -> list[SchPin]:
    sorted_numbers = sorted(pad_numbers, key=pad_sort_key)
    pins: list[SchPin] = []
    pitch_mm = 2.54
    for index, pad_number in enumerate(sorted_numbers):
        side: Literal["left", "right"] = "left" if index % 2 == 0 else "right"
        row = index // 2
        net_name = pad_nets.get(pad_number, "")
        pins.append(
            SchPin(
                number=pad_number,
                name=net_name if net_name else "~",
                electrical_type=power_pin_type(net_name) if net_name else "passive",
                side=side,
                y_offset_mm=row * pitch_mm,
            )
        )
    return pins


def render_lib_pin(pin: SchPin, symbol_width_mm: float = 10.16) -> str:
    x_location = -symbol_width_mm / 2 if pin.side == "left" else symbol_width_mm / 2
    rotation = 0 if pin.side == "left" else 180
    y_location = -pin.y_offset_mm
    return f"""(pin
        {pin.electrical_type}
        line
        (at {fmt(x_location)} {fmt(y_location)} {rotation})
        (length 0)
        (name "{pin.name}")
        (number "{pin.number}")
      )"""


def render_lib_symbol(symbol_def: LibSymbolDef) -> str:
    pin_blocks = [render_lib_pin(pin) for pin in symbol_def.pins]
    joined_pins = "\n      ".join(pin_blocks)
    return f"""(symbol
      "{symbol_def.library_id}"
      {joined_pins}
    )"""


def embedded_power_symbols() -> str:
    return """
    (symbol
      "power:GND"
      (pin
        power_in
        line
        (at -5.08 0.0 180)
        (length 0)
        (name "GND")
        (number "1")
      )
    )
    (symbol
      "power:PWR_FLAG"
      (pin
        power_out
        line
        (at 0 0 0)
        (length 0)
        (hide yes)
        (name "pwr")
        (number "1")
      )
    )""".strip()


def render_property(name: str, value: str, at_x: float, at_y: float, rotation: float, hide: bool = False) -> str:
    hide_line = "\n      (hide yes)" if hide else ""
    return f"""(property
      "{name}"
      "{value}"
      (at {fmt(at_x)} {fmt(at_y)} {fmt_angle(rotation)})
      (effects
        (font
          (size 1.27 1.27)
        )
      ){hide_line}
    )"""


def render_placed_symbol(
    placed: PlacedSymbol,
    project_name: str,
    path_instance: str,
) -> str:
    return f"""(symbol
    (lib_id "{placed.library_id}")
    (at {fmt(placed.at_x_mm)} {fmt(placed.at_y_mm)} {fmt_angle(placed.rotation_deg)})
    (unit 1)
    (body_style 1)
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (in_pos_files yes)
    (dnp no)
    (uuid "{new_uuid()}")
    {render_property("Reference", placed.reference, placed.at_x_mm, placed.at_y_mm, placed.rotation_deg, hide=False)}
    {render_property("Value", placed.value, placed.at_x_mm, placed.at_y_mm, placed.rotation_deg, hide=False)}
    {render_property("Footprint", placed.footprint, placed.at_x_mm, placed.at_y_mm, 0, hide=True)}
    {render_property("Datasheet", "", placed.at_x_mm, placed.at_y_mm, 0, hide=True)}
    {render_placed_pin_lines(placed)}
    (instances
      (project "{project_name}"
        (path "{path_instance}"
          (reference "{placed.reference}")
          (unit 1)
        )
      )
    )
  )"""


def render_placed_pin_lines(placed: PlacedSymbol) -> str:
    if not placed.pin_numbers:
        return ""
    lines = [f'(pin "{pin_number}" (uuid "{new_uuid()}"))' for pin_number in placed.pin_numbers]
    return "\n    ".join(lines)


def render_wire(wire: WireSegment) -> str:
    return f"""(wire
    (pts
      (xy {fmt(wire.x1_mm)} {fmt(wire.y1_mm)})
      (xy {fmt(wire.x2_mm)} {fmt(wire.y2_mm)})
    )
    (stroke
      (width 0)
      (type default)
    )
    (uuid "{new_uuid()}")
  )"""


def render_global_label(label: GlobalLabel) -> str:
    return f"""(label "{label.net_name}"
    (at {fmt(label.at_x_mm)} {fmt(label.at_y_mm)} {fmt_angle(label.rotation_deg)})
    (effects
      (font
        (size 1.27 1.27)
      )
      (justify left bottom)
    )
    (uuid "{new_uuid()}")
  )"""


def render_junction(marker: JunctionMarker) -> str:
    return f"""(junction
    (at {fmt(marker.at_x_mm)} {fmt(marker.at_y_mm)})
    (diameter 0)
    (color 0 0 0 0)
    (uuid "{new_uuid()}")
  )"""


def render_no_connect(marker: NoConnectMarker) -> str:
    return f"""(no_connect
    (at {fmt(marker.at_x_mm)} {fmt(marker.at_y_mm)})
    (uuid "{new_uuid()}")
  )"""


def render_child_sheet(name: str, filename: str, at_x: float, at_y: float) -> str:
    return f"""(sheet
    (at {fmt(at_x)} {fmt(at_y)})
    (size 40 30)
    (fields_autoplaced yes)
    (stroke
      (width 0.1524)
      (type solid)
    )
    (fill
      (type none)
    )
    (uuid "{new_uuid()}")
    (property "Sheetname" "{name}"
      (at {fmt(at_x)} {fmt(at_y - 2)} 0)
      (effects
        (font
          (size 1.27 1.27)
        )
        (justify left bottom)
      )
    )
    (property "Sheetfile" "{filename}"
      (at {fmt(at_x)} {fmt(at_y + 32)} 0)
      (effects
        (font
          (size 1.27 1.27)
        )
        (justify left bottom)
      )
    )
  )"""


def render_document(document: SchematicDocument, path_instance: str = "/") -> str:
    lib_blocks = [render_lib_symbol(item) for item in document.lib_symbols]
    lib_blocks.append(embedded_power_symbols())
    lib_section = "\n    ".join(lib_blocks)

    content_blocks: list[str] = []
    content_blocks.extend(
        render_placed_symbol(item, document.project_name, path_instance)
        for item in document.placed_symbols
    )
    content_blocks.extend(render_wire(item) for item in document.wires)
    content_blocks.extend(render_global_label(item) for item in document.global_labels)
    content_blocks.extend(render_no_connect(item) for item in document.no_connects)
    content_blocks.extend(render_junction(item) for item in document.junctions)
    content_blocks.extend(
        render_child_sheet(name, filename, at_x, at_y)
        for name, filename, at_x, at_y in document.child_sheets
    )
    content_section = "\n  ".join(content_blocks)

    return f"""(kicad_sch
  (version 20260306)
  (generator "mono_schematic")
  (generator_version "1.0")
  (uuid "{new_uuid()}")
  (paper "{document.paper}")
  (title_block
    (title "{document.title}")
    (date "2026-10-10")
    (rev "EVT")
    (comment 1 "Generated from mono_electronics.kicad_pcb pad nets")
    (comment 2 "Cross-check: hardware/mono_schematic/tools/compare_sch_pcb_nets.py")
  )
  (lib_symbols
    {lib_section}
  )
  {content_section}
  (sheet_instances
    (path "{path_instance}"
      (page "1")
    )
  )
)
"""
