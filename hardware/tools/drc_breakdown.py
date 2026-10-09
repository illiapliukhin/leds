#!/usr/bin/env python3
"""Summarize KiCad DRC JSON for mono_electronics (unconnected by net + violations by type)."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from drc_summary import run_drc

NET_IN_DESC = re.compile(r"\[([^\]]+)\]")


def net_names_from_unconnected_item(item: dict) -> set[str]:
    names: set[str] = set()
    for sub in item.get("items") or []:
        match = NET_IN_DESC.search(sub.get("description") or "")
        if match:
            names.add(match.group(1))
    return names


def main() -> None:
    board_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / "mono_electronics/mono_electronics.kicad_pcb"
    )
    report = run_drc(board_path)
    by_net: Counter[str] = Counter()
    for item in report.get("unconnected_items") or []:
        names = net_names_from_unconnected_item(item)
        if len(names) == 1:
            by_net[next(iter(names))] += 1
        elif names:
            by_net["+".join(sorted(names))] += 1
        else:
            by_net["?"] += 1
    by_type: Counter[str] = Counter()
    for violation in report.get("violations") or []:
        by_type[violation.get("type") or "unknown"] += 1
    shorts, crossings = by_type.get("shorting_items", 0), by_type.get("tracks_crossing", 0)
    print(f"board: {board_path.name}")
    print(f"unconnected_groups: {sum(by_net.values())}")
    for net, count in sorted(by_net.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  {net}: {count}")
    print(f"shorts: {shorts}  crossings: {crossings}")
    print("violations_by_type:")
    for kind, count in sorted(by_type.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  {kind}: {count}")


if __name__ == "__main__":
    main()
