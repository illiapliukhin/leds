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


def _track_width_mm(net_name: str) -> float:
    if net_name == "GND":
        return 0.25
    if net_name == "AON_3V3":
        return 0.20
    return FAN_IN_TRACK_WIDTH_MM


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
        track.SetWidth(pcbnew.FromMM(_track_width_mm(segment["net"])))
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


def link_test_point_footprints(board: pcbnew.BOARD) -> None:
    """Join both pads of 0402 test-point footprints (same net, DRC otherwise flags open)."""
    from generate_mono_split_boards import (
        FAN_IN_TRACK_WIDTH_MM,
        footprint_by_reference,
        get_pad,
        millimeters,
        route_net_polyline,
    )

    for reference in ("TP1", "TP2"):
        footprint = footprint_by_reference(board, reference)
        pad_one = get_pad(footprint, "1")
        pad_two = get_pad(footprint, "2")
        net_name = pad_one.GetNetname()
        if not net_name or net_name != pad_two.GetNetname():
            continue
        start = millimeters(pad_one.GetPosition())
        end = millimeters(pad_two.GetPosition())
        route_net_polyline(
            board,
            net_name,
            pcbnew.F_Cu,
            [start, end],
            FAN_IN_TRACK_WIDTH_MM,
        )


def post_grid_hand_finish(board: pcbnew.BOARD, incomplete_nets: set[str]) -> None:
    """Legacy hook — use mono_split_post_grid_finish.run_post_grid_finish on board path."""
    del board, incomplete_nets


def _existing_via_near(board: pcbnew.BOARD, x_mm: float, y_mm: float, *, tol_mm: float = 0.12) -> bool:
    for item in board.GetTracks():
        if item.GetClass() != "PCB_VIA":
            continue
        pos = item.GetPosition()
        via_x = pcbnew.ToMM(pos.x)
        via_y = pcbnew.ToMM(pos.y)
        if abs(via_x - x_mm) <= tol_mm and abs(via_y - y_mm) <= tol_mm:
            return True
    return False


def add_gnd_stitch_vias(board: pcbnew.BOARD) -> None:
    """Sparse GND stitching vias (MCU west keep-in) — ties B/F to existing spines."""
    gnd = board.FindNet("GND")
    if gnd is None or gnd.GetNetCode() == 0:
        return
    stitch_points_mm = [
        (13.20, 22.35),
        (13.20, 81.30),
        (73.40, 22.35),
        (109.20, 22.35),
        (50.80, 9.20),
    ]
    for x_mm, y_mm in stitch_points_mm:
        if _existing_via_near(board, x_mm, y_mm):
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetNet(gnd)
        via.SetPosition(pcbnew.VECTOR2I_MM(x_mm, y_mm))
        via.SetWidth(pcbnew.FromMM(STANDARD_VIA_DIAMETER_MM))
        via.SetDrill(pcbnew.FromMM(MINIMUM_VIA_DRILL_MM))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(via)


def ensure_gnd_copper_zones(board: pcbnew.BOARD) -> int:
    """Add solid GND pours on In2 + B if missing (filled via kicad-cli --refill-zones)."""
    gnd = board.FindNet("GND")
    if gnd is None or gnd.GetNetCode() == 0:
        return 0
    existing = [
        zone
        for zone in board.Zones()
        if zone.GetNetname() == "GND" and zone.GetLayer() in (pcbnew.In2_Cu, pcbnew.B_Cu)
    ]
    if existing:
        return 0
    added = 0
    margin_mm = 1.0
    width_mm = 152.0
    height_mm = 138.0
    corners_mm = [
        (margin_mm, margin_mm),
        (width_mm - margin_mm, margin_mm),
        (width_mm - margin_mm, height_mm - margin_mm),
        (margin_mm, height_mm - margin_mm),
    ]
    for layer_id in (pcbnew.In2_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer_id)
        zone.SetNet(gnd)
        zone.SetIsRuleArea(False)
        outline = zone.Outline()
        outline.NewOutline()
        for x_mm, y_mm in corners_mm:
            outline.Append(pcbnew.VECTOR2I_MM(x_mm, y_mm))
        zone.SetMinThickness(pcbnew.FromMM(0.25))
        board.Add(zone)
        added += 1
    return added


def add_mcu_gnd_pour_b_cu(board: pcbnew.BOARD) -> None:
    """B.Cu GND bus mesh (zone fill is unstable in headless pcbnew — use 0.30 mm tracks)."""
    gnd = board.FindNet("GND")
    if gnd is None or gnd.GetNetCode() == 0:
        return
    width = pcbnew.FromMM(0.30)
    for y_mm in (12.0, 24.0, 36.0, 48.0, 60.0, 72.0, 84.0, 96.0, 108.0, 120.0, 132.0):
        track = pcbnew.PCB_TRACK(board)
        track.SetNet(gnd)
        track.SetLayer(pcbnew.B_Cu)
        track.SetStart(pcbnew.VECTOR2I_MM(1.0, y_mm))
        track.SetEnd(pcbnew.VECTOR2I_MM(71.0, y_mm))
        track.SetWidth(width)
        board.Add(track)
    for x_mm in (8.0, 20.0, 32.0, 44.0, 56.0, 68.0):
        track = pcbnew.PCB_TRACK(board)
        track.SetNet(gnd)
        track.SetLayer(pcbnew.B_Cu)
        track.SetStart(pcbnew.VECTOR2I_MM(x_mm, 4.0))
        track.SetEnd(pcbnew.VECTOR2I_MM(x_mm, 140.0))
        track.SetWidth(width)
        board.Add(track)


def _prefer_u1_pad(net_name: str) -> tuple[str, str] | None:
    if net_name == "GND":
        return ("U1", "57")
    if net_name == "AON_3V3":
        return ("U1", "46")
    return None


def run_mcu_grid_pipeline(board_path: Path) -> None:
    """Pre-grid power fanout → dump geometry → greedy + PathFinder → DRC-gated apply."""
    import json
    import os
    import subprocess

    from mcu_grid_drc import copper_gate_counts, drc_gate_routes, refill_zones_save, run_drc_report

    tools_dir = Path(__file__).resolve().parent
    if os.environ.get("MONO_PRE_GRID_FANOUT", "0") == "1":
        from mono_split_pre_grid_fanout import apply_pre_grid_power_fanout

        board = pcbnew.LoadBoard(str(board_path))
        apply_pre_grid_power_fanout(board)
        pcbnew.SaveBoard(str(board_path), board)
        print("pre-grid power fanout applied (locked stubs)", flush=True)
    kicad_root = Path("/workspace/.kicad10/squashfs-root/usr/bin")
    kicad_python = kicad_root / "python3.11"
    if not kicad_python.is_file():
        kicad_python = Path("python3.11")
    geometry_path = board_path.with_suffix(".mcu_geom.json")
    routes_path = board_path.with_suffix(".mcu_routes.json")
    greedy_path = board_path.with_suffix(".mcu_routes.greedy.json")
    pathfinder_path = board_path.with_suffix(".mcu_routes.pf.json")
    subprocess.run(
        [str(kicad_python), str(tools_dir / "dump_mcu_geom.py"), str(board_path), str(geometry_path)],
        check=True,
    )
    compute_python = Path("/usr/bin/python3")
    if not compute_python.is_file():
        compute_python = Path(sys.executable)
    compute_env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH")
    }
    compute_script = str(tools_dir / "mcu_grid_compute.py")
    greedy_env = {**compute_env, "MONO_PATHFINDER": "0"}
    subprocess.run(
        [str(compute_python), compute_script, str(geometry_path), str(greedy_path), "15", "8"],
        check=True,
        env=greedy_env,
    )
    pf_env = {**compute_env, "MONO_PATHFINDER": "1"}
    pf_rounds = os.environ.get("MONO_PF_ROUNDS", "12")
    subprocess.run(
        [str(compute_python), compute_script, str(geometry_path), str(pathfinder_path), "15", pf_rounds],
        check=True,
        env=pf_env,
    )
    greedy_routes = json.loads(greedy_path.read_text())
    pf_routes = json.loads(pathfinder_path.read_text())
    apply_script = tools_dir / "apply_mcu_grid_routes.py"
    pf_ok, pf_shorts, pf_cross = drc_gate_routes(
        board_path, pf_routes, kicad_python=kicad_python, apply_script=apply_script
    )
    greedy_ok, greedy_shorts, greedy_cross = drc_gate_routes(
        board_path, greedy_routes, kicad_python=kicad_python, apply_script=apply_script
    )
    from mcu_grid_merge import merge_routes

    pf_complete = len(pf_routes.get("complete_nets") or [])
    greedy_complete = len(greedy_routes.get("complete_nets") or [])
    pf_nets = set(pf_routes.get("complete_nets") or [])
    greedy_nets = set(greedy_routes.get("complete_nets") or [])
    borrow_nets = greedy_nets - pf_nets
    pf_candidate = pf_routes
    if pf_ok and borrow_nets and greedy_ok:
        merged = merge_routes(pf_routes, greedy_routes, borrow_nets)
        merge_ok, merge_shorts, merge_cross = drc_gate_routes(
            board_path, merged, kicad_python=kicad_python, apply_script=apply_script
        )
        if merge_ok:
            pf_candidate = merged
            pf_complete = len(merged.get("complete_nets") or [])
            print(
                f"grid merge pf+greedy nets {sorted(borrow_nets)} "
                f"DRC {merge_shorts}/{merge_cross}",
                flush=True,
            )
    merge_led = greedy_ok and "LED_CLK" in greedy_nets and "LED_CLK" not in pf_nets
    if merge_led and pf_ok:
        merged_led = merge_routes(pf_routes, greedy_routes, {"LED_CLK"})
        led_ok, _, _ = drc_gate_routes(
            board_path, merged_led, kicad_python=kicad_python, apply_script=apply_script
        )
        if led_ok:
            pf_candidate = merged_led
            pf_complete = len(merged_led.get("complete_nets") or [])
    if pf_ok and pf_complete >= greedy_complete:
        chosen = pf_candidate
        chosen_label = pf_candidate.get("route_engine", "pathfinder")
    elif greedy_ok and greedy_complete >= pf_complete:
        chosen = greedy_routes
        chosen_label = "greedy"
    elif pf_ok:
        chosen = pf_candidate
        chosen_label = pf_candidate.get("route_engine", "pathfinder")
    elif greedy_ok:
        chosen = greedy_routes
        chosen_label = "greedy"
    else:
        raise RuntimeError(
            "MCU grid DRC gate failed: "
            f"pathfinder shorts={pf_shorts} crossings={pf_cross} "
            f"({pf_complete} nets), greedy shorts={greedy_shorts} "
            f"crossings={greedy_cross} ({greedy_complete} nets). "
            "Fix geometry or routing order; refusing to apply copper."
        )
    chosen["route_engine"] = chosen_label
    routes_path.write_text(json.dumps(chosen, indent=2))
    print(
        f"grid select {chosen_label}: pf {len(pf_routes.get('complete_nets', []))} nets "
        f"DRC {pf_shorts}/{pf_cross}, greedy {len(greedy_routes.get('complete_nets', []))} "
        f"DRC {greedy_shorts}/{greedy_cross}",
        flush=True,
    )
    apply_result = subprocess.run(
        [str(kicad_python), str(apply_script), str(board_path), str(routes_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    if apply_result.stdout:
        print(apply_result.stdout.strip())
    board = pcbnew.LoadBoard(str(board_path))
    if ensure_gnd_copper_zones(board):
        pcbnew.SaveBoard(str(board_path), board)
        print("added GND zones on In2/B for CLI refill", flush=True)
    try:
        refill_zones_save(board_path)
        print("refilled copper zones via kicad-cli", flush=True)
    except subprocess.CalledProcessError as error:
        print(f"zone refill skipped: {error.stderr}", flush=True)

    board = pcbnew.LoadBoard(str(board_path))
    incomplete = set(chosen.get("incomplete_nets") or [])
    if os.environ.get("MONO_GND_STITCH", "0") == "1":
        add_gnd_stitch_vias(board)
    if os.environ.get("MONO_LINK_TP", "1") == "1":
        link_test_point_footprints(board)
    pcbnew.SaveBoard(str(board_path), board)
    post_grid_backup: Path | None = None
    if os.environ.get("MONO_POST_GRID", "1") == "1":
        import shutil
        import tempfile

        post_grid_backup = Path(tempfile.mkdtemp()) / board_path.name
        shutil.copy2(board_path, post_grid_backup)
        post_script = tools_dir / "mono_split_post_grid_finish.py"
        post_env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH")
        }
        post_env.setdefault("MONO_POST_GRID_PHASES", "cleanup,aon_zone,gnd,grid_one")
        # grid_one runs last; post-grid backup reverts all phases if copper gate fails.
        post_env.setdefault("MONO_GRID_ONE_NETS", "DEC_A_EN_N,USB_D_N_MCU,IMU_SDA,IMU_SCL,IMU_INT1,ROW_A3,GND")
        subprocess.run(
            [str(kicad_python), str(post_script), str(board_path)],
            check=True,
            env=post_env,
        )
    else:
        print(
            f"post-grid skipped ({len(incomplete)} incomplete nets); MONO_POST_GRID=0",
            flush=True,
        )
        try:
            refill_zones_save(board_path)
        except subprocess.CalledProcessError as error:
            print(f"post-finish zone refill skipped: {error.stderr}", flush=True)

    report = run_drc_report(board_path)
    shorts, crossings = copper_gate_counts(report)
    print(f"post-finish DRC gate: shorts={shorts} crossings={crossings}", flush=True)
    if (shorts > 0 or crossings > 0) and post_grid_backup is not None:
        import shutil

        shutil.copy2(post_grid_backup, board_path)
        print(
            "post-grid reverted: copper gate failed after finish (backup restored)",
            flush=True,
        )
        report = run_drc_report(board_path)
        shorts, crossings = copper_gate_counts(report)
        print(f"post-finish DRC gate (restored): shorts={shorts} crossings={crossings}", flush=True)


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
