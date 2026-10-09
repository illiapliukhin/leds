"""KiCad CLI DRC helpers for MCU grid route selection (no pcbnew)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

COPPER_GATE_TYPES = frozenset({"shorting_items", "tracks_crossing"})


def kicad_cli() -> str:
    kicad10 = Path("/workspace/.kicad10/squashfs-root/usr/bin/kicad-cli")
    if kicad10.is_file():
        return str(kicad10)
    return "kicad-cli"


def run_drc_report(board_path: Path, *, refill_zones: bool = False, save_board: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as temporary_directory:
        output_path = Path(temporary_directory) / "drc.json"
        command = [
            kicad_cli(),
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-error",
            "--severity-warning",
            "--output",
            str(output_path),
        ]
        if refill_zones:
            command.append("--refill-zones")
            if save_board:
                command.append("--save-board")
        command.append(str(board_path))
        subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(output_path.read_text())


def violation_type_counts(report: dict) -> Counter:
    counts: Counter = Counter()
    for violation in report.get("violations", []):
        counts[violation.get("type", "unknown")] += 1
    return counts


def copper_gate_counts(report: dict) -> tuple[int, int]:
    shorts = 0
    crossings = 0
    for violation in report.get("violations", []):
        violation_type = violation.get("type")
        if violation_type == "shorting_items":
            shorts += 1
        elif violation_type == "tracks_crossing":
            crossings += 1
    return shorts, crossings


def refill_zones_save(board_path: Path) -> None:
    run_drc_report(board_path, refill_zones=True, save_board=True)


def drc_gate_routes(
    board_path: Path,
    routes: dict,
    *,
    kicad_python: Path,
    apply_script: Path,
) -> tuple[bool, int, int]:
    """Apply routes to a temp copy and return (passes_gate, shorts, crossings)."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_board = Path(temporary_directory) / board_path.name
        shutil.copy2(board_path, temporary_board)
        subprocess.run(
            [str(kicad_python), str(apply_script), str(temporary_board), "-"],
            input=json.dumps(routes),
            check=True,
            capture_output=True,
            text=True,
        )
        report = run_drc_report(temporary_board)
        shorts, crossings = copper_gate_counts(report)
        return shorts == 0 and crossings == 0, shorts, crossings
