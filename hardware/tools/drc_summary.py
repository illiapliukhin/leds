#!/usr/bin/env python3
"""Print mono_electronics copper DRC counts (shorts, crossings, unconnected)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
BOARD = REPO_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pcb"

COPPER_TYPES = frozenset({"shorting_items", "tracks_crossing"})


def kicad_cli() -> str:
    kicad10 = Path("/workspace/.kicad10/squashfs-root/usr/bin/kicad-cli")
    if kicad10.is_file():
        return str(kicad10)
    return "kicad-cli"


def run_drc(board_path: Path) -> dict:
    output_json = board_path.with_name("drc-cli.json")
    command = [
        kicad_cli(),
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-error",
        "--severity-warning",
        "--output",
        str(output_json),
        str(board_path),
    ]
    subprocess.run(command, check=False, capture_output=True, text=True)
    if not output_json.exists():
        raise RuntimeError("DRC did not produce JSON")
    return json.loads(output_json.read_text())


def main() -> None:
    board_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BOARD
    report = run_drc(board_path)
    violations = report.get("violations", [])
    copper = [v for v in violations if v.get("type") in COPPER_TYPES]
    by_type: dict[str, int] = {}
    for violation in violations:
        kind = violation.get("type", "unknown")
        by_type[kind] = by_type.get(kind, 0) + 1
    unconnected = report.get("unconnected_items", [])
    print(f"board: {board_path.name}")
    print(f"shorts: {by_type.get('shorting_items', 0)}")
    print(f"crossings: {by_type.get('tracks_crossing', 0)}")
    print(f"unconnected: {len(unconnected)}")
    if copper:
        print("first copper issue:", copper[0].get("description"))


if __name__ == "__main__":
    main()
