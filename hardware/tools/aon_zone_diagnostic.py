#!/usr/bin/env python3
"""Print AON_3V3 In1 zone outline, filled areas (after refill), vias, and unconnected hints."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import pcbnew  # noqa: E402

from drc_summary import run_drc  # noqa: E402
from generate_mono_split_boards import footprint_by_reference, get_pad, millimeters  # noqa: E402


def kicad_cli() -> str:
    kicad10 = Path("/workspace/.kicad10/squashfs-root/usr/bin/kicad-cli")
    return str(kicad10) if kicad10.is_file() else "kicad-cli"


def refill_board(board_path: Path) -> None:
    subprocess.run(
        [kicad_cli(), "pcb", "drc", "--refill-zones", "--save-board", str(board_path)],
        check=True,
        capture_output=True,
    )


def zone_outline_mm(zone: pcbnew.ZONE) -> list[tuple[float, float]]:
    outline = zone.Outline()
    points: list[tuple[float, float]] = []
    if outline.OutlineCount() == 0:
        return points
    shape = outline.COutline(0)
    for index in range(shape.PointCount()):
        point = shape.CPoint(index)
        points.append((pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)))
    return points


def filled_polys_mm(board: pcbnew.BOARD, zone: pcbnew.ZONE, layer: int) -> list[list[tuple[float, float]]]:
    zones = [zone]
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(zones, True)
    polys = zone.GetFilledPolysList(board)
    result: list[list[tuple[float, float]]] = []
    if polys is None:
        return result
    for outline_index in range(polys.OutlineCount()):
        shape = polys.COutline(outline_index)
        ring: list[tuple[float, float]] = []
        for point_index in range(shape.PointCount()):
            point = shape.CPoint(point_index)
            ring.append((pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)))
        result.append(ring)
    return result


def aon_vias_mm(board: pcbnew.BOARD) -> list[tuple[float, float]]:
    positions: list[tuple[float, float]] = []
    for item in board.GetTracks():
        if item.GetClass() == "PCB_VIA" and item.GetNetname() == "AON_3V3":
            pos = item.GetPosition()
            positions.append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)))
    return sorted(positions)


def u1_aon_pads(board: pcbnew.BOARD) -> list[tuple[str, float, float]]:
    u1 = footprint_by_reference(board, "U1")
    pads: list[tuple[str, float, float]] = []
    for pad in u1.Pads():
        if pad.GetNetname() != "AON_3V3":
            continue
        x_mm, y_mm = millimeters(pad.GetPosition())
        pads.append((pad.GetNumber(), x_mm, y_mm))
    return sorted(pads, key=lambda row: row[0])


def main() -> None:
    board_path = Path(sys.argv[1]) if len(sys.argv) > 1 else TOOLS.parent / "mono_electronics/mono_electronics.kicad_pcb"
    refill_board(board_path)
    board = pcbnew.LoadBoard(str(board_path))

    print(f"board: {board_path.name}")
    print("U1 AON pads (pad, x, y mm):")
    for pad_num, x_mm, y_mm in u1_aon_pads(board):
        print(f"  {pad_num}: ({x_mm:.2f}, {y_mm:.2f})")

    print("AON_3V3 vias (x, y mm):")
    for x_mm, y_mm in aon_vias_mm(board):
        print(f"  ({x_mm:.2f}, {y_mm:.2f})")

    for zone in board.Zones():
        if zone.GetNetname() != "AON_3V3" or zone.GetLayer() != pcbnew.In1_Cu:
            continue
        print("In1 AON zone outline (mm):", zone_outline_mm(zone))
        fills = filled_polys_mm(board, zone, pcbnew.In1_Cu)
        print(f"In1 AON zone fill polygons: {len(fills)}")
        for index, ring in enumerate(fills[:4]):
            sample = ring[:8]
            print(f"  poly[{index}] vertices={len(ring)} sample={sample}")

    report = run_drc(board_path)
    by_net: dict[str, int] = {}
    for item in report.get("unconnected_items") or []:
        nets: set[str] = set()
        for sub in item.get("items") or []:
            match = re.search(r"\[([^\]]+)\]", sub.get("description") or "")
            if match:
                nets.add(match.group(1))
        if "AON_3V3" in nets:
            by_net["AON_3V3"] = by_net.get("AON_3V3", 0) + 1
            print("unconnected AON group:", item.get("description", "")[:60])
            for sub in (item.get("items") or [])[:2]:
                print(" ", sub.get("description", "")[:90], sub.get("pos"))

    print(f"AON unconnected groups: {by_net.get('AON_3V3', 0)}")


if __name__ == "__main__":
    main()
