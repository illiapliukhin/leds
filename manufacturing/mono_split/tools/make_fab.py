#!/usr/bin/env python3
"""Generate JLCPCB-style fab outputs for mono split boards via kicad-cli."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
KICAD10_ROOT = Path(os.environ.get("KICAD10_ROOT", "/workspace/.kicad10/squashfs-root"))
KICAD_CLI = KICAD10_ROOT / "usr/bin/kicad-cli"
LCSC_MAP_PATH = Path(__file__).resolve().parent / "lcsc_bom_map.json"


@dataclass(frozen=True)
class BoardJob:
    name: str
    pcb_path: Path
    project_path: Path
    commit_outputs: bool
    status_label: str


BOARD_JOBS: tuple[BoardJob, ...] = (
    BoardJob(
        name="mono_panel_20x20",
        pcb_path=REPOSITORY_ROOT / "hardware/mono_panel_20x20/mono_panel_20x20.kicad_pcb",
        project_path=REPOSITORY_ROOT / "hardware/mono_panel_20x20/mono_panel_20x20.kicad_pro",
        commit_outputs=True,
        status_label="READY",
    ),
    BoardJob(
        name="mono_panel_32x32",
        pcb_path=REPOSITORY_ROOT / "hardware/mono_panel_32x32/mono_panel_32x32.kicad_pcb",
        project_path=REPOSITORY_ROOT / "hardware/mono_panel_32x32/mono_panel_32x32.kicad_pro",
        commit_outputs=True,
        status_label="READY",
    ),
    BoardJob(
        name="mono_electronics",
        pcb_path=REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pcb",
        project_path=REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pro",
        commit_outputs=False,
        status_label="NOT_READY",
    ),
)


def run_kicad_cli(arguments: list[str]) -> None:
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = ":".join(
        [
            str(KICAD10_ROOT / "usr/lib/x86_64-linux-gnu"),
            str(KICAD10_ROOT / "usr/lib"),
            environment.get("LD_LIBRARY_PATH", ""),
        ]
    )
    command = [str(KICAD_CLI), *arguments]
    subprocess.run(command, check=True, env=environment)


def export_gerbers(pcb_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_kicad_cli(
        [
            "pcb",
            "export",
            "gerbers",
            "--board-plot-params",
            "-o",
            str(output_dir),
            str(pcb_path),
        ]
    )


def export_drill(pcb_path: Path, output_dir: Path) -> None:
    run_kicad_cli(
        [
            "pcb",
            "export",
            "drill",
            "-o",
            str(output_dir),
            str(pcb_path),
        ]
    )


def export_pos(pcb_path: Path, output_dir: Path) -> None:
    run_kicad_cli(
        [
            "pcb",
            "export",
            "pos",
            "--format",
            "csv",
            "--units",
            "mm",
            "-o",
            str(output_dir / "positions.csv"),
            str(pcb_path),
        ]
    )


def export_renders(pcb_path: Path, output_dir: Path) -> None:
    layer_list = "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run_kicad_cli(
        [
            "pcb",
            "export",
            "pdf",
            "--layers",
            layer_list,
            "--mode-single",
            "-o",
            str(output_dir / "board.pdf"),
            str(pcb_path),
        ]
    )
    run_kicad_cli(
        [
            "pcb",
            "export",
            "svg",
            "--layers",
            layer_list,
            "-o",
            str(output_dir / "layers.svg"),
            str(pcb_path),
        ]
    )


def export_bom_csv(pcb_path: Path, output_dir: Path) -> None:
    lcsc_map = json.loads(LCSC_MAP_PATH.read_text(encoding="utf-8"))
    sys.path.insert(0, str(REPOSITORY_ROOT / "hardware/mono_schematic/tools"))
    from extract_pcb_components import extract_board  # noqa: E402

    footprints = extract_board(pcb_path)
    rows: dict[tuple[str, str, str], int] = {}
    for footprint in footprints:
        key = (footprint.value, footprint.footprint, footprint.reference[0])
        rows[key] = rows.get(key, 0) + 1
    bom_path = output_dir / "bom.csv"
    with bom_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            ["Comment", "Designator", "Footprint", "Qty", "LCSC Part #", "Notes"]
        )
        for (value, footprint_name, _), quantity in sorted(rows.items()):
            writer.writerow(
                [
                    value,
                    "",
                    footprint_name,
                    quantity,
                    lcsc_map.get(value, ""),
                    "EVT" if not lcsc_map.get(value) else "",
                ]
            )


def write_status(output_dir: Path, job: BoardJob) -> None:
    status_path = output_dir / "FAB_PACKAGE_STATUS.txt"
    status_path.write_text(
        "\n".join(
            [
                f"board: {job.name}",
                f"status: {job.status_label}",
                f"commit_outputs: {job.commit_outputs}",
                f"pcb: {job.pcb_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def process_job(job: BoardJob, output_root: Path) -> None:
    if not job.pcb_path.is_file():
        raise FileNotFoundError(job.pcb_path)
    output_dir = output_root / job.name
    if job.status_label == "NOT_READY":
        output_dir = output_root / f"{job.name}_NOT_READY"
    output_dir.mkdir(parents=True, exist_ok=True)
    export_gerbers(job.pcb_path, output_dir / "gerbers")
    export_drill(job.pcb_path, output_dir / "drill")
    export_pos(job.pcb_path, output_dir)
    export_bom_csv(job.pcb_path, output_dir)
    export_renders(job.pcb_path, output_dir)
    write_status(output_dir, job)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPOSITORY_ROOT / "manufacturing/mono_split/output",
    )
    parser.add_argument(
        "--boards",
        nargs="*",
        default=[job.name for job in BOARD_JOBS],
        help="Board names to export (default: all)",
    )
    arguments = parser.parse_args()
    selected = {name for name in arguments.boards}
    for job in BOARD_JOBS:
        if job.name not in selected:
            continue
        print(f"Exporting {job.name} ({job.status_label})...")
        process_job(job, arguments.output_root)
    print(f"Done. Outputs under {arguments.output_root}")


if __name__ == "__main__":
    main()
