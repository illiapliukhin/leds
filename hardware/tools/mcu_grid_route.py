"""A* grid router for mono_electronics U1 nets (F/In1/In2/B, via-legal pockets)."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pcbnew

TOOLS_DIR = Path(__file__).resolve().parent

from generate_mono_split_boards import (  # noqa: E402
    FAN_IN_TRACK_WIDTH_MM,
    MINIMUM_VIA_DRILL_MM,
    STANDARD_VIA_DIAMETER_MM,
)

LAYER_NAME = {
    pcbnew.F_Cu: "F",
    pcbnew.In1_Cu: "In1",
    pcbnew.In2_Cu: "In2",
    pcbnew.B_Cu: "B",
}
LAYER_ID = {name: layer for layer, name in LAYER_NAME.items()}
MM = 1e-6

from mcu_grid_constants import MCU_ROUTE_ORDER, paths_to_segments  # noqa: E402


def _pad_polygons(pad: pcbnew.PAD, layer: int) -> list[list[tuple[float, float]]]:
    polygon_set = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(polygon_set, layer, 0, 5000, pcbnew.ERROR_INSIDE)
    polygons: list[list[tuple[float, float]]] = []
    for outline_index in range(polygon_set.OutlineCount()):
        outline = polygon_set.Outline(outline_index)
        polygons.append(
            [
                (outline.CPoint(point_index).x * MM, outline.CPoint(point_index).y * MM)
                for point_index in range(outline.PointCount())
            ]
        )
    return polygons


def dump_board_geometry(board: pcbnew.BOARD) -> dict:
    geometry: dict = {
        "tracks": [],
        "vias": [],
        "pads": [],
        "zones": [],
        "fps": [],
        "edge": [],
    }
    for track_item in board.GetTracks():
        if track_item.GetClass() == "PCB_VIA":
            geometry["vias"].append(
                {
                    "x": track_item.GetPosition().x * MM,
                    "y": track_item.GetPosition().y * MM,
                    "d": track_item.GetWidth(pcbnew.F_Cu) * MM,
                    "drill": track_item.GetDrillValue() * MM,
                    "net": track_item.GetNetname(),
                    "locked": track_item.IsLocked(),
                }
            )
        elif track_item.GetClass() == "PCB_TRACK":
            layer_name = LAYER_NAME.get(track_item.GetLayer())
            if layer_name is None:
                continue
            geometry["tracks"].append(
                {
                    "x1": track_item.GetStart().x * MM,
                    "y1": track_item.GetStart().y * MM,
                    "x2": track_item.GetEnd().x * MM,
                    "y2": track_item.GetEnd().y * MM,
                    "w": track_item.GetWidth() * MM,
                    "layer": layer_name,
                    "net": track_item.GetNetname(),
                    "locked": track_item.IsLocked(),
                }
            )
    for footprint in board.GetFootprints():
        courtyard = footprint.GetCourtyard(
            pcbnew.B_CrtYd if footprint.IsFlipped() else pcbnew.F_CrtYd
        )
        court_polys: list[list[tuple[float, float]]] = []
        for outline_index in range(courtyard.OutlineCount()):
            outline = courtyard.Outline(outline_index)
            court_polys.append(
                [
                    (outline.CPoint(point_index).x * MM, outline.CPoint(point_index).y * MM)
                    for point_index in range(outline.PointCount())
                ]
            )
        geometry["fps"].append(
            {
                "ref": footprint.GetReference(),
                "x": footprint.GetPosition().x * MM,
                "y": footprint.GetPosition().y * MM,
                "rot": footprint.GetOrientationDegrees(),
                "side": "B" if footprint.IsFlipped() else "F",
                "court": court_polys,
                "locked": footprint.IsLocked(),
                "value": footprint.GetValue(),
            }
        )
        for pad in footprint.Pads():
            for layer_id, layer_name in LAYER_NAME.items():
                if pad.IsOnLayer(layer_id) and pad.FlashLayer(layer_id):
                    geometry["pads"].append(
                        {
                            "ref": footprint.GetReference(),
                            "num": pad.GetNumber(),
                            "net": pad.GetNetname(),
                            "layer": layer_name,
                            "poly": _pad_polygons(pad, layer_id),
                            "x": pad.GetPosition().x * MM,
                            "y": pad.GetPosition().y * MM,
                        }
                    )
    return geometry


def apply_grid_routes(
    board: pcbnew.BOARD,
    segments: list[dict],
    vias: list[dict],
) -> None:
    for segment in segments:
        net = board.FindNet(segment["net"])
        if net is None or net.GetNetCode() == 0:
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetNet(net)
        track.SetLayer(LAYER_ID[segment["layer"]])
        track.SetStart(pcbnew.VECTOR2I_MM(segment["x1"], segment["y1"]))
        track.SetEnd(pcbnew.VECTOR2I_MM(segment["x2"], segment["y2"]))
        track.SetWidth(pcbnew.FromMM(FAN_IN_TRACK_WIDTH_MM))
        board.Add(track)
    for via_spec in vias:
        net = board.FindNet(via_spec["net"])
        if net is None or net.GetNetCode() == 0:
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetNet(net)
        via.SetPosition(pcbnew.VECTOR2I_MM(via_spec["x"], via_spec["y"]))
        via.SetWidth(pcbnew.FromMM(STANDARD_VIA_DIAMETER_MM))
        via.SetDrill(pcbnew.FromMM(MINIMUM_VIA_DRILL_MM))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(via)


def _prefer_u1_pad(net_name: str) -> tuple[str, str] | None:
    if net_name == "GND":
        return ("U1", "57")
    if net_name == "AON_3V3":
        return ("U1", "46")
    return None


def run_mcu_grid_pipeline(board_path: Path) -> None:
    """Dump geometry → grid route (system Python) → apply routes (KiCad Python)."""
    import subprocess

    tools_dir = Path(__file__).resolve().parent
    kicad_root = Path("/workspace/.kicad10/squashfs-root/usr/bin")
    kicad_python = kicad_root / "python3.11"
    if not kicad_python.is_file():
        kicad_python = Path("python3.11")
    geometry_path = board_path.with_suffix(".mcu_geom.json")
    routes_path = board_path.with_suffix(".mcu_routes.json")
    subprocess.run(
        [str(kicad_python), str(tools_dir / "dump_mcu_geom.py"), str(board_path), str(geometry_path)],
        check=True,
    )
    compute_python = Path("/usr/bin/python3")
    if not compute_python.is_file():
        compute_python = Path(sys.executable)
    compute_env = {
        key: value
        for key, value in __import__("os").environ.items()
        if key not in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH")
    }
    subprocess.run(
        [str(compute_python), str(tools_dir / "mcu_grid_compute.py"), str(geometry_path), str(routes_path)],
        check=True,
        env=compute_env,
    )
    apply_result = subprocess.run(
        [str(kicad_python), str(tools_dir / "apply_mcu_grid_routes.py"), str(board_path), str(routes_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    if apply_result.stdout:
        print(apply_result.stdout.strip())


def route_mcu_with_grid(
    board: pcbnew.BOARD,
    *,
    via_cost: float = 15.0,
    layer_cost: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.85),
    max_passes: int = 4,
) -> dict[str, tuple[int, int]]:
    sys.path.insert(0, str(TOOLS_DIR / "mcu_grid"))
    from grid import Board  # noqa: WPS433

    geometry = dump_board_geometry(board)
    grid_board = Board(geometry)
    grid_board.newvias = {}
    all_paths: dict[str, list] = {}
    summary: dict[str, tuple[int, int]] = {}
    order = list(MCU_ROUTE_ORDER)

    for _pass_index in range(max_passes):
        failed_nets: list[str] = []
        for net_name in order:
            if board.FindNet(net_name) is None:
                continue
            prefer = _prefer_u1_pad(net_name)
            prefer_source = prefer if prefer and prefer in grid_board.padcells else None
            joins_ok, joins_fail, paths = grid_board.route_net(
                net_name,
                viacost=via_cost,
                layercost=layer_cost,
                commit=True,
                prefer_comp_of=prefer_source,
            )
            if paths:
                all_paths.setdefault(net_name, []).extend(paths)
            summary[net_name] = (joins_ok, joins_fail)
            if joins_fail > 0:
                failed_nets.append(net_name)
        if not failed_nets:
            break
        order = failed_nets + [net for net in order if net not in failed_nets]

    segments, vias = paths_to_segments(all_paths)
    apply_grid_routes(board, segments, vias)
    return summary
