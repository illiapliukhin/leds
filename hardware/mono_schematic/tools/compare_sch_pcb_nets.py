#!/usr/bin/env python3
"""Compare PCB pad nets with schematic net manifest generated from the same PCB source."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMATIC_ROOT = REPOSITORY_ROOT / "hardware/mono_schematic"
TOOLS_DIR = SCHEMATIC_ROOT / "tools"

sys.path.insert(0, str(TOOLS_DIR))
from extract_pcb_components import extract_board  # noqa: E402


def load_manifest(manifest_path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {entry["reference"]: entry["pad_nets"] for entry in payload}


def pcb_netlist(board_path: Path) -> dict[str, dict[str, str]]:
    return {
        footprint.reference: footprint.pad_nets
        for footprint in extract_board(board_path)
    }


def compare(
    schematic_nets: dict[str, dict[str, str]],
    board_nets: dict[str, dict[str, str]],
) -> tuple[list[str], list[str]]:
    missing_refs = sorted(set(board_nets) - set(schematic_nets))
    extra_refs = sorted(set(schematic_nets) - set(board_nets))
    mismatches: list[str] = []
    for reference in sorted(set(schematic_nets) & set(board_nets)):
        board_pads = board_nets[reference]
        schematic_pads = schematic_nets[reference]
        if board_pads != schematic_pads:
            mismatches.append(
                f"{reference}: pcb={board_pads} sch={schematic_pads}"
            )
    return missing_refs + extra_refs, mismatches


def main() -> int:
    manifest_path = SCHEMATIC_ROOT / "mono_electronics_net_manifest.json"
    board_path = REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pcb"
    if not manifest_path.is_file():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 2
    schematic_nets = load_manifest(manifest_path)
    board_nets = pcb_netlist(board_path)
    reference_issues, pad_mismatches = compare(schematic_nets, board_nets)
    report = {
        "board": str(board_path),
        "manifest": str(manifest_path),
        "reference_issues": reference_issues,
        "pad_mismatches": pad_mismatches,
        "matched_references": len(set(schematic_nets) & set(board_nets)),
        "pcb_references": len(board_nets),
        "schematic_references": len(schematic_nets),
    }
    output_path = SCHEMATIC_ROOT / "reports" / "sch_pcb_net_compare.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if reference_issues or pad_mismatches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
