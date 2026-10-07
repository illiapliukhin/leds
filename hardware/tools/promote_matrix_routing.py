from dataclasses import dataclass
from pathlib import Path
import shutil

import pcbnew


@dataclass(frozen=True)
class BoardVariant:
    name: str
    expected_led_count: int
    expected_track_count: int


BOARD_VARIANTS = (
    BoardVariant("wearable_20x20", 400, 5_120),
    BoardVariant("wearable_28x28", 784, 10_064),
)


def count_leds(board: pcbnew.BOARD) -> int:
    return sum(
        1
        for footprint in board.GetFootprints()
        if footprint.GetValue() == "MHPA1010RGBDT"
    )


def validate_routed_matrix(board: pcbnew.BOARD, variant: BoardVariant) -> None:
    if count_leds(board) != variant.expected_led_count:
        raise ValueError(f"{variant.name}: unexpected LED count")

    tracks = list(board.GetTracks())
    if len(tracks) != variant.expected_track_count:
        raise ValueError(
            f"{variant.name}: expected {variant.expected_track_count} tracks and vias, "
            f"found {len(tracks)}"
        )

    l2_track_count = sum(
        1
        for track in tracks
        if not isinstance(track, pcbnew.PCB_VIA)
        and track.GetLayer() == pcbnew.In1_Cu
    )
    if l2_track_count:
        raise ValueError(f"{variant.name}: matrix routing occupies reserved L2")

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
