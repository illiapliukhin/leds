#!/usr/bin/env python3
"""Extract reference → pad net map from mono_electronics.kicad_pcb via pcbnew."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
KICAD10_ROOT = Path(os.environ.get("KICAD10_ROOT", "/workspace/.kicad10/squashfs-root"))
sys.path.insert(0, str(KICAD10_ROOT / "usr/lib/python3/dist-packages"))

import pcbnew  # noqa: E402


@dataclass
class FootprintNets:
    reference: str
    value: str
    footprint: str
    pad_nets: dict[str, str] = field(default_factory=dict)


def extract_board(board_path: Path) -> list[FootprintNets]:
    board = pcbnew.LoadBoard(str(board_path))
    results: list[FootprintNets] = []
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if reference.startswith("REF**"):
            continue
        pad_nets: dict[str, str] = {}
        for pad in footprint.Pads():
            pad_number = pad.GetNumber()
            net_name = pad.GetNetname()
            if net_name:
                pad_nets[str(pad_number)] = net_name
        results.append(
            FootprintNets(
                reference=reference,
                value=footprint.GetValue(),
                footprint=str(footprint.GetFPID().GetLibItemName()),
                pad_nets=pad_nets,
            )
        )
    results.sort(key=lambda item: item.reference)
    return results


def main() -> None:
    board_path = REPOSITORY_ROOT / "hardware/mono_electronics/mono_electronics.kicad_pcb"
    footprints = extract_board(board_path)
    payload = [
        {
            "reference": fp.reference,
            "value": fp.value,
            "footprint": fp.footprint,
            "pad_nets": fp.pad_nets,
        }
        for fp in footprints
    ]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
