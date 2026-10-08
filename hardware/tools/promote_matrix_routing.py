from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import shutil

import pcbnew


@dataclass(frozen=True)
class BoardVariant:
    name: str
    expected_led_count: int
    expected_track_count: int
    expected_via_count: int
    expected_row_via_count: int
    expected_row_net_count: int
    expected_orientation_counts: tuple[tuple[int, int], ...]


BOARD_VARIANTS = (
    BoardVariant(
        "wearable_20x20",
        400,
        5_120,
        1_564,
        400,
        20,
        ((0, 180), (90, 20), (180, 180), (270, 20)),
    ),
    BoardVariant(
        "wearable_28x28",
        784,
        10_064,
        3_084,
        784,
        28,
        ((0, 364), (90, 28), (180, 364), (270, 28)),
    ),
)


def count_leds(board: pcbnew.BOARD) -> int:
    return sum(
        1
        for footprint in board.GetFootprints()
        if footprint.GetValue() == "MHPA1010RGBDT"
    )


def validate_routed_matrix(board: pcbnew.BOARD, variant: BoardVariant) -> None:
    led_count = count_leds(board)
    if led_count != variant.expected_led_count:
        raise ValueError(f"{variant.name}: unexpected LED count")

    footprint_count = len(list(board.GetFootprints()))
    if footprint_count != led_count:
        raise ValueError(
            f"{variant.name}: analysis matrix must contain only LEDs, "
            f"found {footprint_count - led_count} non-LED footprints"
        )

    orientation_counts = Counter(
        int(round(footprint.GetOrientationDegrees())) % 360
        for footprint in board.GetFootprints()
    )
    expected_orientation_counts = dict(variant.expected_orientation_counts)
    if dict(orientation_counts) != expected_orientation_counts:
        raise ValueError(
            f"{variant.name}: expected orientations "
            f"{expected_orientation_counts}, found {dict(orientation_counts)}"
        )

    tracks = list(board.GetTracks())
    if len(tracks) != variant.expected_track_count:
        raise ValueError(
            f"{variant.name}: expected {variant.expected_track_count} tracks and vias, "
            f"found {len(tracks)}"
        )

    vias = [
        track
        for track in tracks
        if isinstance(track, pcbnew.PCB_VIA)
    ]
    if len(vias) != variant.expected_via_count:
        raise ValueError(
            f"{variant.name}: expected {variant.expected_via_count} vias, "
            f"found {len(vias)}"
        )

    via_width_counts = Counter(
        round(pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu)), 3)
        for via in vias
    )
    expected_rgb_via_count = (
        variant.expected_via_count - variant.expected_row_via_count
    )
    expected_via_width_counts = {
        0.4: expected_rgb_via_count,
        0.45: variant.expected_row_via_count,
    }
    if dict(via_width_counts) != expected_via_width_counts:
        raise ValueError(
            f"{variant.name}: expected via widths "
            f"{expected_via_width_counts}, found {dict(via_width_counts)}"
        )

    via_drill_counts = Counter(
        round(pcbnew.ToMM(via.GetDrillValue()), 3)
        for via in vias
    )
    if dict(via_drill_counts) != {0.2: variant.expected_via_count}:
        raise ValueError(
            f"{variant.name}: expected all via drills at 0.2 mm, "
            f"found {dict(via_drill_counts)}"
        )

    l2_track_count = sum(
        1
        for track in tracks
        if not isinstance(track, pcbnew.PCB_VIA)
        and track.GetLayer() == pcbnew.In1_Cu
    )
    if l2_track_count:
        raise ValueError(f"{variant.name}: matrix routing occupies reserved L2")

    row_nets_on_l3 = {
        track.GetNetname()
        for track in tracks
        if not isinstance(track, pcbnew.PCB_VIA)
        and track.GetLayer() == pcbnew.In2_Cu
        and track.GetNetname().startswith("ROW_")
    }
    if len(row_nets_on_l3) != variant.expected_row_net_count:
        raise ValueError(
            f"{variant.name}: expected every row net on L3, found "
            f"{len(row_nets_on_l3)}"
        )

    unconnected_items = board.GetConnectivity().GetUnconnectedCount(False)
    if unconnected_items:
        raise ValueError(
            f"{variant.name}: routed matrix has {unconnected_items} unconnected items"
        )


def promote_variant(repository_root: Path, variant: BoardVariant) -> None:
    source_path = (
        repository_root
        / "hardware"
        / "analysis"
        / f"{variant.name}_full_matrix_routing.kicad_pcb"
    )
    destination_path = (
        repository_root
        / "hardware"
        / variant.name
        / f"{variant.name}.kicad_pcb"
    )

    board = pcbnew.LoadBoard(str(source_path))
    validate_routed_matrix(board, variant)
    shutil.copyfile(source_path, destination_path)

    promoted_board = pcbnew.LoadBoard(str(destination_path))
    validate_routed_matrix(promoted_board, variant)
    print(f"Promoted matrix routing to {destination_path}")


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    for variant in BOARD_VARIANTS:
        promote_variant(repository_root, variant)


if __name__ == "__main__":
    main()
