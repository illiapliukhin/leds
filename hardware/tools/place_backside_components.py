from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree

import pcbnew

from generate_board_skeletons import (
    deterministic_kiid,
    save_board_without_project_side_effects,
)


LED_VALUE = "MHPA1010RGBDT"
EDGE_CLEARANCE_MM = 0.35
COMPONENT_GAP_MM = 0.30
REFERENCE_TEXT_HEIGHT_MM = 1.0
REFERENCE_TEXT_THICKNESS_MM = 0.15
REFERENCE_COLUMN_PITCH_MM = 4.6
REFERENCE_ROW_PITCH_MM = 2.0
LOCAL_FOOTPRINT_DIRECTORIES = {
    "PartSignal_Packages": Path(__file__).resolve().parents[1]
    / "libraries"
    / "packages.pretty",
}
KICAD_FOOTPRINT_DIRECTORY = Path(
    os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
)
REGION_PREFERENCES = {
    "power": ("bottom-left", "bottom-right", "left", "right", "top-inner"),
    "mcu": ("top-left", "top-inner", "left", "bottom-left"),
    "imu": ("top-right", "top-inner", "right", "bottom-right"),
    "audio": ("bottom-right", "right", "top-right", "top-inner"),
    "drivers": ("left", "right", "bottom-left", "top-inner"),
    "rows": ("right", "left", "bottom-right", "top-inner", "bottom-left"),
}


@dataclass(frozen=True)
class Rectangle:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class FreeRectangle:
    name: str
    bounds: Rectangle


@dataclass(frozen=True)
class ComponentSpec:
    reference: str
    value: str
    footprint_identifier: str
    width_mm: float
    height_mm: float
    group_name: str

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm


@dataclass(frozen=True)
class Placement:
    x_mm: float
    y_mm: float
    rotation_degrees: int
    width_mm: float
    height_mm: float


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


def split_reference(reference: str) -> tuple[str, int]:
    prefix = "".join(character for character in reference if character.isalpha())
    digits = "".join(character for character in reference if character.isdigit())
    return prefix, int(digits or "0")


def group_for_reference(reference: str) -> str:
    prefix, number = split_reference(reference)
    if prefix == "Q" or number >= 200:
        return "rows"
    if prefix == "Y":
        return "mcu"
    if prefix == "L":
        return "power"
    if prefix == "MIC":
        return "audio"
    if prefix in {"SW", "TH"}:
        return "imu"
    if 100 <= number < 200:
        return "drivers"
    if prefix == "U" and number >= 30:
        return "audio"
    if prefix == "U" and number >= 20:
        return "imu"
    if number >= 40:
        return "audio"
    if number >= 30:
        return "imu"
    if number >= 20 or reference in {"U10", "U11"}:
        return "mcu"
    return "power"


def load_component_specs(
    netlist_path: Path,
) -> tuple[list[ComponentSpec], dict[str, pcbnew.FOOTPRINT]]:
    root = ElementTree.parse(netlist_path).getroot()
    specifications: list[ComponentSpec] = []
    library_footprints: dict[str, pcbnew.FOOTPRINT] = {}
    for component in root.findall("./components/comp"):
        value = component.findtext("value", default="")
        if value == LED_VALUE:
            continue
        reference = component.get("ref", "")
        footprint_identifier = component.findtext("footprint", default="").strip()
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
        specifications.append(
            ComponentSpec(
                reference=reference,
                value=value,
                footprint_identifier=footprint_identifier,
                width_mm=pcbnew.ToMM(bounding_box.GetWidth()),
                height_mm=pcbnew.ToMM(bounding_box.GetHeight()),
                group_name=group_for_reference(reference),
            )
        )
        library_footprints[reference] = footprint
    return specifications, library_footprints


def build_pin_net_map(netlist_path: Path) -> dict[tuple[str, str], str]:
    root = ElementTree.parse(netlist_path).getroot()
    pin_net_map: dict[tuple[str, str], str] = {}
    for net in root.findall("./nets/net"):
        net_name = net.get("name", "").rsplit("/", 1)[-1]
        for node in net.findall("node"):
            pin_net_map[(node.get("ref", ""), node.get("pin", ""))] = net_name
    return pin_net_map


def rectangle_from_box(box: pcbnew.BOX2I, margin_mm: float = 0.0) -> Rectangle:
    return Rectangle(
        pcbnew.ToMM(box.GetLeft()) - margin_mm,
        pcbnew.ToMM(box.GetTop()) - margin_mm,
        pcbnew.ToMM(box.GetRight()) + margin_mm,
        pcbnew.ToMM(box.GetBottom()) + margin_mm,
    )


def via_field_bounds(board: pcbnew.BOARD) -> Rectangle:
    bounds: pcbnew.BOX2I | None = None
    for item in board.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        via_bounds = item.GetBoundingBox()
        if bounds is None:
            bounds = via_bounds
        else:
            bounds.Merge(via_bounds)
    if bounds is None:
        raise ValueError("matrix via field is absent")
    return rectangle_from_box(bounds)


def branding_bounds(board: pcbnew.BOARD) -> Rectangle | None:
    bounds: pcbnew.BOX2I | None = None
    for drawing in board.Drawings():
        if drawing.GetLayer() != pcbnew.B_SilkS:
            continue
        drawing_bounds = drawing.GetBoundingBox()
        if bounds is None:
            bounds = drawing_bounds
        else:
            bounds.Merge(drawing_bounds)
    if bounds is None:
        return None
    return rectangle_from_box(bounds, margin_mm=0.2)


def add_region(
    regions: list[FreeRectangle],
    name: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> None:
    if x1 - x0 < 1.0 or y1 - y0 < 1.0:
        return
    regions.append(FreeRectangle(name, Rectangle(x0, y0, x1, y1)))


def build_regions(
    board_size_mm: float,
    via_bounds: Rectangle,
    branding: Rectangle | None,
) -> list[FreeRectangle]:
    edge = EDGE_CLEARANCE_MM
    outer = board_size_mm - edge
    regions: list[FreeRectangle] = []
    midpoint = board_size_mm / 2
    add_region(regions, "bottom-left", edge, edge, midpoint, via_bounds.y0)
    add_region(regions, "bottom-right", midpoint, edge, outer, via_bounds.y0)
    add_region(regions, "left", edge, via_bounds.y0, via_bounds.x0, via_bounds.y1)
    add_region(regions, "right", via_bounds.x1, via_bounds.y0, outer, via_bounds.y1)
    if branding is None:
        add_region(regions, "top-inner", edge, via_bounds.y1, outer, outer)
        return regions

    add_region(
        regions,
        "top-inner",
        edge,
        via_bounds.y1,
        outer,
        branding.y0,
    )
    add_region(regions, "top-left", edge, branding.y0, branding.x0, outer)
    add_region(regions, "top-right", branding.x1, branding.y0, outer, outer)
    return regions


def contains_rectangle(outer: Rectangle, inner: Rectangle) -> bool:
    return (
        outer.x0 <= inner.x0 + 0.001
        and outer.y0 <= inner.y0 + 0.001
        and outer.x1 >= inner.x1 - 0.001
        and outer.y1 >= inner.y1 - 0.001
    )


def rectangles_intersect(first: Rectangle, second: Rectangle) -> bool:
    return not (
        first.x1 <= second.x0 + 0.001
        or second.x1 <= first.x0 + 0.001
        or first.y1 <= second.y0 + 0.001
        or second.y1 <= first.y0 + 0.001
    )


def prune_free_rectangles(
    rectangles: list[FreeRectangle],
) -> list[FreeRectangle]:
    useful = [
        rectangle
        for rectangle in rectangles
        if rectangle.bounds.width >= 0.9 and rectangle.bounds.height >= 0.9
    ]
    return [
        rectangle
        for rectangle in useful
        if not any(
            other is not rectangle and contains_rectangle(other.bounds, rectangle.bounds)
            for other in useful
        )
    ]


def split_free_rectangles(
    rectangles: list[FreeRectangle],
    occupied: Rectangle,
) -> list[FreeRectangle]:
    split_rectangles: list[FreeRectangle] = []
    for rectangle in rectangles:
        bounds = rectangle.bounds
        if not rectangles_intersect(bounds, occupied):
            split_rectangles.append(rectangle)
            continue
        if occupied.x0 > bounds.x0:
            split_rectangles.append(
                FreeRectangle(
                    rectangle.name,
                    Rectangle(bounds.x0, bounds.y0, occupied.x0, bounds.y1),
                )
            )
        if occupied.x1 < bounds.x1:
            split_rectangles.append(
                FreeRectangle(
                    rectangle.name,
                    Rectangle(occupied.x1, bounds.y0, bounds.x1, bounds.y1),
                )
            )
        if occupied.y0 > bounds.y0:
            split_rectangles.append(
                FreeRectangle(
                    rectangle.name,
                    Rectangle(bounds.x0, bounds.y0, bounds.x1, occupied.y0),
                )
            )
        if occupied.y1 < bounds.y1:
            split_rectangles.append(
                FreeRectangle(
                    rectangle.name,
                    Rectangle(bounds.x0, occupied.y1, bounds.x1, bounds.y1),
                )
            )
    return prune_free_rectangles(split_rectangles)


def place_components(
    components: list[ComponentSpec],
    regions: list[FreeRectangle],
) -> dict[str, Placement]:
    free_rectangles = list(regions)
    placements: dict[str, Placement] = {}
    ordered_components = sorted(
        components,
        key=lambda component: (
            -component.area_mm2,
            component.group_name,
            split_reference(component.reference),
        ),
    )
    for component in ordered_components:
        preferred_names = REGION_PREFERENCES[component.group_name]
        best_candidate = None
        best_score = None
        for free_rectangle in free_rectangles:
            options = [(component.width_mm, component.height_mm, 0)]
            if abs(component.width_mm - component.height_mm) > 0.01:
                options.append((component.height_mm, component.width_mm, 90))
            for width_mm, height_mm, rotation_degrees in options:
                bounds = free_rectangle.bounds
                if width_mm > bounds.width or height_mm > bounds.height:
                    continue
                region_rank = (
                    preferred_names.index(free_rectangle.name)
                    if free_rectangle.name in preferred_names
                    else len(preferred_names)
                )
                score = (
                    region_rank,
                    min(bounds.width - width_mm, bounds.height - height_mm),
                    max(bounds.width - width_mm, bounds.height - height_mm),
                    bounds.y0,
                    bounds.x0,
                    rotation_degrees,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best_candidate = (
                        free_rectangle,
                        width_mm,
                        height_mm,
                        rotation_degrees,
                    )
        if best_candidate is None:
            raise ValueError(
                f"no via-free placement remains for {component.reference}"
            )
        free_rectangle, width_mm, height_mm, rotation_degrees = best_candidate
        origin_x = free_rectangle.bounds.x0
        origin_y = free_rectangle.bounds.y0
        placements[component.reference] = Placement(
            origin_x,
            origin_y,
            rotation_degrees,
            width_mm,
            height_mm,
        )
        free_rectangles = split_free_rectangles(
            free_rectangles,
            Rectangle(
                origin_x,
                origin_y,
                origin_x + width_mm + COMPONENT_GAP_MM,
                origin_y + height_mm + COMPONENT_GAP_MM,
            ),
        )
    return placements


def get_or_create_net(board: pcbnew.BOARD, net_name: str) -> pcbnew.NETINFO_ITEM:
    existing_net = board.FindNet(net_name)
    if existing_net is not None:
        return existing_net
    net = pcbnew.NETINFO_ITEM(board, net_name)
    net.SetUuid(deterministic_kiid(f"backside-net:{net_name}"))
    board.Add(net)
    return net


def assign_footprint_identity(footprint: pcbnew.FOOTPRINT, reference: str) -> None:
    identity = f"backside:{reference}"
    footprint.SetUuid(deterministic_kiid(identity))
    for field_index, field in enumerate(footprint.GetFields()):
        field.SetUuid(deterministic_kiid(f"{identity}:field:{field_index}"))
    for pad_index, pad in enumerate(footprint.Pads()):
        pad.SetUuid(deterministic_kiid(f"{identity}:pad:{pad_index}"))
    for graphic_index, graphic in enumerate(footprint.GraphicalItems()):
        graphic.SetUuid(deterministic_kiid(f"{identity}:graphic:{graphic_index}"))


def configure_reference(
    footprint: pcbnew.FOOTPRINT,
    reference_position: pcbnew.VECTOR2I,
) -> None:
    reference = footprint.Reference()
    reference.SetLayer(pcbnew.B_SilkS)
    reference.SetVisible(True)
    reference.SetTextSize(
        pcbnew.VECTOR2I_MM(REFERENCE_TEXT_HEIGHT_MM, REFERENCE_TEXT_HEIGHT_MM)
    )
    reference.SetTextThickness(pcbnew.FromMM(REFERENCE_TEXT_THICKNESS_MM))
    reference.SetMirrored(True)
    reference.SetTextAngleDegrees(0)
    reference.SetPosition(reference_position)
    footprint.Value().SetVisible(False)


def reference_positions(
    references: list[str],
    board_size_mm: float,
) -> dict[str, pcbnew.VECTOR2I]:
    columns = 9
    grid_width = (columns - 1) * REFERENCE_COLUMN_PITCH_MM
    grid_height = (
        (len(references) + columns - 1) // columns - 1
    ) * REFERENCE_ROW_PITCH_MM
    origin_x = (board_size_mm - grid_width) / 2
    origin_y = (board_size_mm - grid_height) / 2
    positions: dict[str, pcbnew.VECTOR2I] = {}
    for index, reference in enumerate(sorted(references, key=split_reference)):
        column = index % columns
        row = index // columns
        positions[reference] = pcbnew.VECTOR2I_MM(
            origin_x + column * REFERENCE_COLUMN_PITCH_MM,
            origin_y + row * REFERENCE_ROW_PITCH_MM,
        )
    return positions


def align_footprint_bounds(
    footprint: pcbnew.FOOTPRINT,
    origin_x_mm: float,
    origin_y_mm: float,
) -> None:
    bounds = footprint.GetBoundingBox(False, False)
    minimum_y = min(bounds.GetTop(), bounds.GetBottom())
    footprint.Move(
        pcbnew.VECTOR2I(
            pcbnew.FromMM(origin_x_mm) - bounds.GetLeft(),
            pcbnew.FromMM(origin_y_mm) - minimum_y,
        )
    )


def move_silk_circles_off_pads(footprint: pcbnew.FOOTPRINT) -> None:
    for graphic in footprint.GraphicalItems():
        if graphic.GetLayer() != pcbnew.B_SilkS or not isinstance(graphic, pcbnew.PCB_SHAPE):
            continue
        if graphic.GetShape() != pcbnew.SHAPE_T_CIRCLE:
            continue
        center = graphic.GetStart()
        covering_pad = next(
            (pad for pad in footprint.Pads() if pad.HitTest(center)),
            None,
        )
        if covering_pad is None:
            continue
        offset_x = center.x - footprint.GetPosition().x
        offset_y = center.y - footprint.GetPosition().y
        offset_length = (offset_x * offset_x + offset_y * offset_y) ** 0.5
        if offset_length < 1:
            direction_x, direction_y = -1.0, 0.0
        else:
            direction_x = offset_x / offset_length
            direction_y = offset_y / offset_length
        pad_radius = max(covering_pad.GetSize().x, covering_pad.GetSize().y) / 2
        circle_radius = abs(graphic.GetEnd().x - graphic.GetStart().x)
        shift = pad_radius + circle_radius + pcbnew.FromMM(0.35)
        graphic.Move(
            pcbnew.VECTOR2I(int(direction_x * shift), int(direction_y * shift))
        )


def install_component(
    board: pcbnew.BOARD,
    component: ComponentSpec,
    placement: Placement,
    pin_net_map: dict[tuple[str, str], str],
    reference_position: pcbnew.VECTOR2I,
    library_footprint: pcbnew.FOOTPRINT,
) -> None:
    footprint = pcbnew.Cast_to_FOOTPRINT(library_footprint.Duplicate(False))
    footprint.SetReference(component.reference)
    footprint.SetValue(component.value)
    board.Add(footprint)
    footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    footprint.SetOrientationDegrees(placement.rotation_degrees)
    align_footprint_bounds(footprint, placement.x_mm, placement.y_mm)
    move_silk_circles_off_pads(footprint)
    for pad in footprint.Pads():
        net_name = pin_net_map.get((component.reference, pad.GetNumber()))
        if net_name is not None:
            pad.SetNet(get_or_create_net(board, net_name))
    configure_reference(footprint, reference_position)
    assign_footprint_identity(footprint, component.reference)


def rectangles_overlap(first: Rectangle, second: Rectangle, gap_mm: float) -> bool:
    return not (
        first.x1 + gap_mm <= second.x0
        or second.x1 + gap_mm <= first.x0
        or first.y1 + gap_mm <= second.y0
        or second.y1 + gap_mm <= first.y0
    )


def validate_placement(
    board: pcbnew.BOARD,
    via_bounds: Rectangle,
    board_bounds: Rectangle,
    branding: Rectangle | None,
) -> None:
    footprints = [
        footprint
        for footprint in board.GetFootprints()
        if footprint.GetValue() != LED_VALUE
    ]
    if len(footprints) != 172:
        raise ValueError(f"expected 172 backside footprints, found {len(footprints)}")
    envelopes: list[tuple[str, Rectangle]] = []
    for footprint in footprints:
        if footprint.GetLayer() != pcbnew.B_Cu:
            raise ValueError(f"{footprint.GetReference()} is not on the back layer")
        bounds = rectangle_from_box(footprint.GetBoundingBox(False, False))
        if rectangles_overlap(bounds, via_bounds, 0.0):
            raise ValueError(f"{footprint.GetReference()} intersects the via field")
        if (
            bounds.x0 < board_bounds.x0
            or bounds.y0 < board_bounds.y0
            or bounds.x1 > board_bounds.x1
            or bounds.y1 > board_bounds.y1
        ):
            raise ValueError(f"{footprint.GetReference()} crosses the board edge")
        if branding is not None and rectangles_overlap(bounds, branding, 0.0):
            raise ValueError(f"{footprint.GetReference()} covers the branding")
        envelopes.append((footprint.GetReference(), bounds))
    for index, (reference, bounds) in enumerate(envelopes):
        for other_reference, other_bounds in envelopes[index + 1 :]:
            if rectangles_overlap(bounds, other_bounds, 0.0):
                raise ValueError(f"{reference} overlaps {other_reference}")


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    board_path = (
        repository_root
        / "hardware"
        / "wearable_20x20"
        / "wearable_20x20.kicad_pcb"
    )
    matrix_path = (
        repository_root
        / "hardware"
        / "analysis"
        / "wearable_20x20_full_matrix_routing.kicad_pcb"
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        netlist_path = Path(temporary_directory) / "wearable_20x20.xml"
        export_root_netlist(repository_root, netlist_path)
        components, library_footprints = load_component_specs(netlist_path)
        pin_net_map = build_pin_net_map(netlist_path)

    board = pcbnew.LoadBoard(str(matrix_path))
    board_bounds = board.GetBoardEdgesBoundingBox()
    board_size_mm = pcbnew.ToMM(board_bounds.GetWidth())
    via_bounds = via_field_bounds(board)
    regions = build_regions(board_size_mm, via_bounds, branding_bounds(board))
    placements = place_components(components, regions)
    positions = reference_positions(
        [component.reference for component in components],
        board_size_mm,
    )
    for component in sorted(components, key=lambda item: split_reference(item.reference)):
        install_component(
            board,
            component,
            placements[component.reference],
            pin_net_map,
            positions[component.reference],
            library_footprints[component.reference],
        )
    validate_placement(
        board,
        via_bounds,
        Rectangle(
            EDGE_CLEARANCE_MM,
            EDGE_CLEARANCE_MM,
            board_size_mm - EDGE_CLEARANCE_MM,
            board_size_mm - EDGE_CLEARANCE_MM,
        ),
        branding_bounds(board),
    )
    save_board_without_project_side_effects(board_path, board)
    print(
        f"Placed {len(components)} backside components outside the "
        f"{via_bounds.width:.2f} mm via field."
    )


if __name__ == "__main__":
    main()
