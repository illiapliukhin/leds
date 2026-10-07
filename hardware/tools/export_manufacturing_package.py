import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

from check_release_readiness import collect_checks, print_report


VARIANTS = ("wearable_20x20", "wearable_28x28")
GERBER_LAYERS = (
    "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,"
    "F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
)


def run_command(command: tuple[str, ...], working_directory: Path) -> None:
    subprocess.run(command, check=True, cwd=working_directory)


def export_variant(
    repository_root: Path,
    release_directory: Path,
    variant: str,
) -> None:
    source_directory = repository_root / "hardware" / variant
    board_path = source_directory / f"{variant}.kicad_pcb"
    schematic_path = source_directory / f"{variant}.kicad_sch"
    output_directory = release_directory / variant
    gerber_directory = output_directory / "gerber"
    drill_directory = output_directory / "drill"
    output_directory.mkdir(parents=True)
    gerber_directory.mkdir()
    drill_directory.mkdir()

    run_command(
        (
            "kicad-cli",
            "sch",
            "erc",
            "--format",
            "report",
            "--severity-all",
            "--exit-code-violations",
            "-o",
            str(output_directory / "erc.rpt"),
            str(schematic_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--exit-code-violations",
            "-o",
            str(output_directory / "drc.rpt"),
            str(board_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "sch",
            "export",
            "pdf",
            "-o",
            str(output_directory / f"{variant}_schematic.pdf"),
            str(schematic_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "sch",
            "export",
            "bom",
            "--exclude-dnp",
            "--fields",
            "Reference,Value,Footprint,Datasheet,Function,FootprintStatus,"
            "QUANTITY,DNP",
            "--group-by",
            "Value,Footprint",
            "-o",
            str(output_directory / f"{variant}_bom.csv"),
            str(schematic_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "export",
            "gerbers",
            "--layers",
            GERBER_LAYERS,
            "--subtract-soldermask",
            "--check-zones",
            "-o",
            str(gerber_directory),
            str(board_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "export",
            "drill",
            "--format",
            "excellon",
            "--excellon-units",
            "mm",
            "--excellon-separate-th",
            "--generate-map",
            "--map-format",
            "pdf",
            "--generate-report",
            "--report-path",
            str(output_directory / "drill_report.rpt"),
            "-o",
            str(drill_directory),
            str(board_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "export",
            "pos",
            "--side",
            "both",
            "--format",
            "csv",
            "--units",
            "mm",
            "--exclude-dnp",
            "-o",
            str(output_directory / f"{variant}_positions.csv"),
            str(board_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "export",
            "ipcd356",
            "-o",
            str(output_directory / f"{variant}.d356"),
            str(board_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "export",
            "ipc2581",
            "-o",
            str(output_directory / f"{variant}.xml"),
            str(board_path),
        ),
        source_directory,
    )
    run_command(
        (
            "kicad-cli",
            "pcb",
            "export",
            "step",
            "--force",
            "--no-dnp",
            "--subst-models",
            "-o",
            str(output_directory / f"{variant}.step"),
            str(board_path),
        ),
        source_directory,
    )
    shutil.copy2(board_path, output_directory / board_path.name)
    shutil.copy2(schematic_path, output_directory / schematic_path.name)


def write_manifest(repository_root: Path, release_directory: Path) -> None:
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        check=True,
        cwd=repository_root,
        capture_output=True,
        text=True,
    ).stdout.strip()
    files = sorted(
        path
        for path in release_directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(
            f"{digest}  {path.relative_to(release_directory).as_posix()}"
        )
    (release_directory / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )
    (release_directory / "RELEASE_MANIFEST.txt").write_text(
        f"git_commit={commit}\n",
        encoding="utf-8",
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release-name",
        required=True,
        help="Immutable output directory name, for example evt-a1",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    repository_root = Path(__file__).resolve().parents[2]
    checks = collect_checks(repository_root)
    if not all(check.passed for check in checks):
        print_report(checks)
        print(
            "\nRelease export refused: all readiness gates must pass.",
            file=sys.stderr,
        )
        sys.exit(1)

    release_directory = (
        repository_root
        / "manufacturing"
        / "releases"
        / arguments.release_name
    )
    if release_directory.exists():
        raise FileExistsError(
            f"Refusing to overwrite immutable release: {release_directory}"
        )
    release_directory.mkdir(parents=True)

    for variant in VARIANTS:
        export_variant(repository_root, release_directory, variant)
    write_manifest(repository_root, release_directory)
    print(f"Exported manufacturing release to {release_directory}")


if __name__ == "__main__":
    main()
