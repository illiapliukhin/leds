from dataclasses import dataclass
from pathlib import Path

import pcbnew


@dataclass(frozen=True)
class GroundPlaneSpecification:
    variant: str
    board_size_mm: float
    edge_inset_mm: float
    clearance_mm: float
    minimum_thickness_mm: float
    expected_matrix_vias: int
    minimum_copper_coverage: float


SPECIFICATION = GroundPlaneSpecification(
    variant="wearable_20x20",
    board_size_mm=49.3,
    edge_inset_mm=0.3,
    clearance_mm=0.1,
    minimum_thickness_mm=0.1,
    expected_matrix_vias=1_564,
    minimum_copper_coverage=0.65,
)


def get_or_create_ground_net(board: pcbnew.BOARD) -> pcbnew.NETINFO_ITEM:
    ground_net = board.FindNet("GND")
    if ground_net is not None:
        return ground_net

    ground_net = pcbnew.NETINFO_ITEM(board, "GND")
    board.Add(ground_net)
    return ground_net


def remove_existing_l2_ground_zones(board: pcbnew.BOARD) -> None:
    for zone in list(board.Zones()):
        if zone.GetLayer() == pcbnew.In1_Cu and zone.GetNetname() == "GND":
            board.Remove(zone)


def add_rectangular_ground_zone(
    board: pcbnew.BOARD,
    specification: GroundPlaneSpecification,
) -> pcbnew.ZONE:
    ground_net = get_or_create_ground_net(board)
    remove_existing_l2_ground_zones(board)

    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.In1_Cu)
    zone.SetNet(ground_net)
    zone.SetLocalClearance(pcbnew.FromMM(specification.clearance_mm))
    zone.SetMinThickness(
        pcbnew.FromMM(specification.minimum_thickness_mm)
    )

    minimum_coordinate = specification.edge_inset_mm
    maximum_coordinate = (
        specification.board_size_mm - specification.edge_inset_mm
    )
    outline = zone.Outline()
    outline.NewOutline()
    for x_coordinate, y_coordinate in (
        (minimum_coordinate, minimum_coordinate),
        (maximum_coordinate, minimum_coordinate),
        (maximum_coordinate, maximum_coordinate),
        (minimum_coordinate, maximum_coordinate),
    ):
        outline.Append(
            pcbnew.VECTOR2I_MM(x_coordinate, y_coordinate)
        )

    board.Add(zone)
    return zone


def square_internal_units_to_square_millimeters(area: float) -> float:
    return area / 1_000_000_000_000


def verify_ground_plane(
    board: pcbnew.BOARD,
    zone: pcbnew.ZONE,
    specification: GroundPlaneSpecification,
) -> tuple[float, float]:
    via_count = sum(
        1
        for track in board.GetTracks()
        if isinstance(track, pcbnew.PCB_VIA)
    )
    if via_count != specification.expected_matrix_vias:
        raise ValueError(
            f"{specification.variant}: expected "
            f"{specification.expected_matrix_vias} matrix vias, "
            f"found {via_count}"
        )

    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError(f"{specification.variant}: L2 zone fill failed")
    if not zone.HasFilledPolysForLayer(pcbnew.In1_Cu):
        raise ValueError(f"{specification.variant}: L2 zone has no fill")

    filled_polygons = zone.GetFilledPolysList(pcbnew.In1_Cu)
    outline_count = filled_polygons.OutlineCount()
    if outline_count != 1:
        raise ValueError(
            f"{specification.variant}: expected one contiguous L2 fill outline, "
            f"found {outline_count}"
        )

    filled_area_mm2 = square_internal_units_to_square_millimeters(
        filled_polygons.Area()
    )
    zone_side_mm = (
        specification.board_size_mm - 2 * specification.edge_inset_mm
    )
    nominal_area_mm2 = zone_side_mm**2
    copper_coverage = filled_area_mm2 / nominal_area_mm2
    if copper_coverage < specification.minimum_copper_coverage:
        raise ValueError(
            f"{specification.variant}: L2 copper coverage "
            f"{copper_coverage:.1%} is below "
            f"{specification.minimum_copper_coverage:.1%}"
        )

    return filled_area_mm2, copper_coverage


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    source_board_path = (
        repository_root
        / "hardware"
        / SPECIFICATION.variant
        / f"{SPECIFICATION.variant}.kicad_pcb"
    )
    output_board_path = (
        repository_root
        / "hardware"
        / "analysis"
        / f"{SPECIFICATION.variant}_l2_ground_plane_probe.kicad_pcb"
    )
    board = pcbnew.LoadBoard(str(source_board_path))
    zone = add_rectangular_ground_zone(board, SPECIFICATION)
    filled_area_mm2, copper_coverage = verify_ground_plane(
        board,
        zone,
        SPECIFICATION,
    )
    pcbnew.SaveBoard(str(output_board_path), board)
    print(
        f"{SPECIFICATION.variant}: one contiguous L2 GND fill outline, "
        f"{filled_area_mm2:.1f} mm^2 copper, "
        f"{copper_coverage:.1%} zone coverage; saved probe to "
        f"{output_board_path}"
    )


if __name__ == "__main__":
    main()
