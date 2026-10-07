import hashlib
from pathlib import Path
import subprocess
import sys

import pcbnew

from promote_matrix_routing import BOARD_VARIANTS, validate_routed_matrix


def calculate_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_matrix_artifacts(tools_directory: Path) -> None:
    for script_name in (
        "generate_board_skeletons.py",
        "generate_full_matrix_routing.py",
    ):
        subprocess.run(
            (sys.executable, str(tools_directory / script_name)),
            check=True,
            cwd=tools_directory.parents[1],
        )


def collect_artifact_digests(
    analysis_directory: Path,
) -> dict[str, str]:
    artifact_paths = []
    for variant in BOARD_VARIANTS:
        artifact_paths.extend(
            (
                analysis_directory
                / f"{variant.name}_matrix_skeleton.kicad_pcb",
                analysis_directory
                / f"{variant.name}_full_matrix_routing.kicad_pcb",
            )
        )
    return {
        path.name: calculate_digest(path)
        for path in artifact_paths
    }


def main() -> None:
    tools_directory = Path(__file__).resolve().parent
    hardware_directory = tools_directory.parent
    analysis_directory = hardware_directory / "analysis"

    generate_matrix_artifacts(tools_directory)
    first_digests = collect_artifact_digests(analysis_directory)
    generate_matrix_artifacts(tools_directory)
    second_digests = collect_artifact_digests(analysis_directory)

    if first_digests != second_digests:
        changed_artifacts = sorted(
            artifact_name
            for artifact_name, first_digest in first_digests.items()
            if second_digests.get(artifact_name) != first_digest
        )
        raise ValueError(
            "Matrix generation is not deterministic: "
            + ", ".join(changed_artifacts)
        )

    for variant in BOARD_VARIANTS:
        matrix_path = (
            analysis_directory
            / f"{variant.name}_full_matrix_routing.kicad_pcb"
        )
        board = pcbnew.LoadBoard(str(matrix_path))
        validate_routed_matrix(board, variant)

    print(
        "Matrix generation is deterministic and all promoted topology "
        "checks pass."
    )


if __name__ == "__main__":
    main()
