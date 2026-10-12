#!/usr/bin/env python3
"""AON_3V3 In1 zone: fill islands, pad/via membership, foreign In1 slicers."""

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
from generate_mono_split_boards import footprint_by_reference, millimeters  # noqa: E402
from mono_split_aon_in1_zone import MAIN_ZONE_OUTLINE_MM  # noqa: E402

NET_IN_DESC = re.compile(r"\[([^\]]+)\]")
PAD_DESC = re.compile(r"of\s+(\S+)\s+pad\s+(\S+)", re.I)
FP_PAD_DESC = re.compile(r"(\w+)\s+pad\s+(\d+)", re.I)
VIA_DESC = re.compile(r"via", re.I)


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


def filled_polys_mm(zone: pcbnew.ZONE, layer: int) -> list[list[tuple[float, float]]]:
    polys = zone.GetFilledPolysList(layer)
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


def point_in_polygon(x_mm: float, y_mm: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    count = len(ring)
    if count < 3:
        return False
    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        if ((current_y > y_mm) != (previous_y > y_mm)) and (
            x_mm
            < (previous_x - current_x) * (y_mm - current_y) / (previous_y - current_y + 1e-12)
            + current_x
        ):
            inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def fill_poly_index(x_mm: float, y_mm: float, polys: list[list[tuple[float, float]]]) -> int | None:
    for index, ring in enumerate(polys):
        if len(ring) >= 3 and point_in_polygon(x_mm, y_mm, ring):
            return index
    return None


def point_in_any_poly(x_mm: float, y_mm: float, polys: list[list[tuple[float, float]]]) -> bool:
    return fill_poly_index(x_mm, y_mm, polys) is not None


def aon_zone_in1(board: pcbnew.BOARD) -> pcbnew.ZONE | None:
    for zone in board.Zones():
        if zone.GetNetname() == "AON_3V3" and zone.GetLayer() == pcbnew.In1_Cu:
            return zone
    return None


def collect_aon_pads(board: pcbnew.BOARD) -> list[dict]:
    rows: list[dict] = []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            if pad.GetNetname() != "AON_3V3":
                continue
            x_mm, y_mm = millimeters(pad.GetPosition())
            rows.append({"ref": ref, "num": pad.GetNumber(), "x": x_mm, "y": y_mm})
    return sorted(rows, key=lambda row: (row["ref"], row["num"]))


def collect_aon_vias(board: pcbnew.BOARD) -> list[dict]:
    rows: list[dict] = []
    for item in board.GetTracks():
        if item.GetClass() != "PCB_VIA" or item.GetNetname() != "AON_3V3":
            continue
        x_mm, y_mm = millimeters(item.GetPosition())
        rows.append({"x": x_mm, "y": y_mm})
    return sorted(rows, key=lambda row: (row["x"], row["y"]))


def foreign_in1_in_aon_pocket(board: pcbnew.BOARD) -> list[dict]:
    pocket = MAIN_ZONE_OUTLINE_MM
    tracks: list[dict] = []
    for item in board.GetTracks():
        if item.GetClass() != "PCB_TRACK" or item.GetLayer() != pcbnew.In1_Cu:
            continue
        net = item.GetNetname()
        if net == "AON_3V3":
            continue
        x1, y1 = millimeters(item.GetStart())
        x2, y2 = millimeters(item.GetEnd())
        mid = ((x1 + x2) / 2, (y1 + y2) / 2)
        if point_in_polygon(mid[0], mid[1], pocket):
            tracks.append(
                {
                    "net": net,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "w": item.GetWidth() * 1e-6,
                }
            )
    return sorted(tracks, key=lambda row: (row["net"], row["y1"], row["x1"]))


def parse_unconnected_aon_groups(report: dict) -> list[dict]:
    groups: list[dict] = []
    for item in report.get("unconnected_items") or []:
        nets: set[str] = set()
        subs: list[dict] = []
        for sub in item.get("items") or []:
            desc = sub.get("description") or ""
            match = NET_IN_DESC.search(desc)
            if match:
                nets.add(match.group(1))
            pad_match = PAD_DESC.search(desc) or FP_PAD_DESC.search(desc)
            pos = sub.get("pos") or {}
            subs.append(
                {
                    "description": desc,
                    "net": match.group(1) if match else "",
                    "ref": pad_match.group(1) if pad_match else "",
                    "pad": pad_match.group(2) if pad_match else "",
                    "is_via": bool(VIA_DESC.search(desc)),
                    "x": pos.get("x"),
                    "y": pos.get("y"),
                }
            )
        if "AON_3V3" not in nets:
            continue
        groups.append({"items": subs, "description": item.get("description", "")})
    return groups


def cluster_endpoints(groups: list[dict]) -> list[dict]:
    """One row per DRC unconnected AON endpoint cluster (approximate island anchor)."""
    islands: list[dict] = []
    seen: set[tuple] = set()
    for group in groups:
        for sub in group["items"]:
            if sub.get("net") != "AON_3V3":
                continue
            key = (
                sub.get("ref"),
                sub.get("pad"),
                sub.get("x"),
                sub.get("y"),
                sub.get("is_via"),
            )
            if key in seen:
                continue
            seen.add(key)
            islands.append(sub)
    islands.sort(key=lambda row: (row.get("y") or 0, row.get("x") or 0))
    return islands


def diagnose_island(
    anchor: dict,
    *,
    fills: list[list[tuple[float, float]]],
    all_vias: list[dict],
    u1_pads: list[dict],
) -> dict:
    x = anchor.get("x")
    y = anchor.get("y")
    if x is None or y is None:
        in_fill = False
    else:
        in_fill = point_in_any_poly(float(x), float(y), fills)

    pad_label = ""
    if anchor.get("ref") and anchor.get("pad"):
        pad_label = f"{anchor['ref']}.{anchor['pad']}"
    elif anchor.get("ref"):
        pad_label = str(anchor["ref"])

    nearest_via: dict | None = None
    best_dist_sq = 1e9
    if x is not None and y is not None:
        for via in all_vias:
            dist_sq = (via["x"] - float(x)) ** 2 + (via["y"] - float(y)) ** 2
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                nearest_via = via
    via_in_fill = False
    if nearest_via:
        via_in_fill = point_in_any_poly(nearest_via["x"], nearest_via["y"], fills)

    u1_pad = ""
    for pad in u1_pads:
        if pad_label == f"U1.{pad['num']}":
            u1_pad = pad["num"]
            break

    fill_idx = fill_poly_index(float(x), float(y), fills) if x is not None and y is not None else None

    return {
        "anchor": pad_label or ("via" if anchor.get("is_via") else "?"),
        "x": x,
        "y": y,
        "fill_poly": fill_idx,
        "in_in1_fill": in_fill,
        "has_nearby_aon_via": nearest_via is not None and best_dist_sq < 4.0,
        "nearest_via": nearest_via,
        "nearest_via_in_fill": via_in_fill,
        "u1_pad": u1_pad,
    }


def main() -> None:
    board_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else TOOLS.parent / "mono_electronics/mono_electronics.kicad_pcb"
    )
    refill_board(board_path)
    board = pcbnew.LoadBoard(str(board_path))
    board.BuildConnectivity()

    zone = aon_zone_in1(board)
    fills: list[list[tuple[float, float]]] = []
    if zone is not None:
        filler = pcbnew.ZONE_FILLER(board)
        filler.Fill([zone], True)
        fills = filled_polys_mm(zone, pcbnew.In1_Cu)

    u1_pads = [p for p in collect_aon_pads(board) if p["ref"] == "U1"]
    all_vias = collect_aon_vias(board)
    slicers = foreign_in1_in_aon_pocket(board)
    report = run_drc(board_path)
    aon_groups = parse_unconnected_aon_groups(report)
    anchors = cluster_endpoints(aon_groups)

    print(f"board: {board_path.name}")
    print("U1 AON pads (num, x, y mm):")
    for pad in u1_pads:
        in_fill = point_in_any_poly(pad["x"], pad["y"], fills)
        print(f"  {pad['num']}: ({pad['x']:.2f}, {pad['y']:.2f}) in_fill={in_fill}")

    print(f"In1 AON zone outline (mm): {zone_outline_mm(zone) if zone else []}")
    print(f"In1 AON filled polygons: {len(fills)}")
    print(f"AON vias total: {len(all_vias)}")
    print(f"Foreign In1 tracks inside AON pocket (net≠AON): {len(slicers)}")
    for track in slicers[:20]:
        print(
            f"  [{track['net']}] ({track['x1']:.2f},{track['y1']:.2f})-"
            f"({track['x2']:.2f},{track['y2']:.2f}) w={track['w']:.2f}"
        )
    if len(slicers) > 20:
        print(f"  ... +{len(slicers) - 20} more")

    print(f"DRC AON_3V3 unconnected groups: {len(aon_groups)}")
    print(f"Unique AON endpoint anchors: {len(anchors)}")
    print("--- per-island ---")
    for index, anchor in enumerate(anchors, start=1):
        row = diagnose_island(anchor, fills=fills, all_vias=all_vias, u1_pads=u1_pads)
        via_str = "none"
        if row["nearest_via"]:
            via = row["nearest_via"]
            via_str = f"({via['x']:.2f},{via['y']:.2f}) in_fill={row['nearest_via_in_fill']}"
        print(
            f"island {index:2d}: pad={row['anchor']!s:12s} pos=({row['x']},{row['y']}) "
            f"fill_poly={row['fill_poly']} via_near={row['has_nearby_aon_via']} via={via_str}"
        )

    if len(sys.argv) > 2 and sys.argv[2] == "--json":
        payload = {
            "fills": len(fills),
            "slicers": slicers,
            "aon_unconnected_groups": len(aon_groups),
            "anchors": [
                diagnose_island(a, fills=fills, all_vias=all_vias, u1_pads=u1_pads) for a in anchors
            ],
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
