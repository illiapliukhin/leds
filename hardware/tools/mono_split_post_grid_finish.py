"""Post-grid MCU finish: GND stitch vias, AON ties, stub cleanup, signal joins (DRC-gated)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pcbnew

from generate_mono_split_boards import (
    FAN_IN_TRACK_WIDTH_MM,
    MINIMUM_VIA_DRILL_MM,
    STANDARD_VIA_DIAMETER_MM,
    add_through_via,
    footprint_by_reference,
    get_pad,
    millimeters,
    route_net_polyline,
)
from mcu_grid_drc import copper_gate_counts, refill_zones_save, run_drc_report, violation_type_counts
from mono_split_aon_in1_zone import apply_aon_in1_zone_plan
from mono_split_copper_utils import GND_STITCH_TARGETS, dogbone_via_candidates, remove_dangling_track_stubs

MM = 1e-6
VIA_D_MM = 0.45
STUB_W_MM = 0.25
GND_STUB_W_MM = 0.25


def _save_board(board: pcbnew.BOARD, path: Path) -> None:
    pcbnew.SaveBoard(str(path), board)


def _copper_gate(path: Path) -> tuple[int, int]:
    report = run_drc_report(path)
    return copper_gate_counts(report)


def _near_mm(ax: float, ay: float, bx: float, by: float, tol: float) -> bool:
    return abs(ax - bx) <= tol and abs(ay - by) <= tol


def _track_endpoints_mm(track: pcbnew.PCB_TRACK) -> tuple[tuple[float, float], tuple[float, float]]:
    start = track.GetStart()
    end = track.GetEnd()
    return millimeters(start), millimeters(end)


def _collect_copper_near(
    tracks: list,
    x_mm: float,
    y_mm: float,
    *,
    tol_mm: float = 0.12,
    net_name: str | None = None,
) -> list:
    hits: list = []
    for item in tracks:
        net = item.GetNetname()
        if net_name is not None and net != net_name:
            continue
        if item.GetClass() == "PCB_VIA":
            pos = item.GetPosition()
            vx, vy = millimeters(pos)
            if _near_mm(vx, vy, x_mm, y_mm, tol_mm):
                hits.append(item)
        elif item.GetClass() == "PCB_TRACK":
            start, end = _track_endpoints_mm(item)
            if any(_near_mm(px, py, x_mm, y_mm, tol_mm) for px, py in (start, end)):
                hits.append(item)
            else:
                mid_x = (start[0] + end[0]) / 2
                mid_y = (start[1] + end[1]) / 2
                if _near_mm(mid_x, mid_y, x_mm, y_mm, tol_mm * 2):
                    hits.append(item)
    return hits


def _move_net_anchor(
    board: pcbnew.BOARD,
    net_name: str,
    old_x: float,
    old_y: float,
    new_x: float,
    new_y: float,
    *,
    tol_mm: float = 0.08,
) -> None:
    for item in board.GetTracks():
        if item.GetNetname() != net_name:
            continue
        if item.GetClass() == "PCB_VIA":
            vx, vy = millimeters(item.GetPosition())
            if _near_mm(vx, vy, old_x, old_y, tol_mm):
                item.SetPosition(pcbnew.VECTOR2I_MM(new_x, new_y))
        elif item.GetClass() == "PCB_TRACK":
            start, end = _track_endpoints_mm(item)
            if _near_mm(start[0], start[1], old_x, old_y, tol_mm):
                item.SetStart(pcbnew.VECTOR2I_MM(new_x, new_y))
            if _near_mm(end[0], end[1], old_x, old_y, tol_mm):
                item.SetEnd(pcbnew.VECTOR2I_MM(new_x, new_y))


def move_row_xlat_oe_drop_via(board: pcbnew.BOARD, tracks: list | None = None) -> None:
    """Nudge grid ROW_XLAT_OE_N via above ROW_*_Y In1 at y≈18.075 (clearance)."""
    del tracks
    _move_net_anchor(board, "ROW_XLAT_OE_N", 46.65, 18.45, 46.65, 18.52)


def _add_gnd_stitch(board: pcbnew.BOARD, pad_x: float, pad_y: float, via_x: float, via_y: float) -> None:
    gnd = board.FindNet("GND")
    route_net_polyline(
        board,
        "GND",
        pcbnew.F_Cu,
        [(pad_x, pad_y), (via_x, via_y)],
        GND_STUB_W_MM,
    )
    add_through_via(board, gnd, via_x, via_y, diameter_mm=VIA_D_MM)


def stitch_gnd_pads_with_drc_gate(board_path: Path) -> int:
    """Add one GND via per F-only pad; keep only if copper gate stays 0/0 after refill."""
    accepted = 0
    baseline_clearance = violation_type_counts(run_drc_report(board_path)).get("clearance", 0)
    board = pcbnew.LoadBoard(str(board_path))
    gnd = board.FindNet("GND")
    if gnd is None or gnd.GetNetCode() == 0:
        return 0

    for ref, pad_num in GND_STITCH_TARGETS:
        footprint = footprint_by_reference(board, ref)
        pad = get_pad(footprint, pad_num)
        if pad.GetNetname() != "GND":
            continue
        pad_x, pad_y = millimeters(pad.GetPosition())
        placed = False
        for via_x, via_y, from_x, from_y in dogbone_via_candidates(pad_x, pad_y):
            with tempfile.TemporaryDirectory() as temporary_directory:
                trial_path = Path(temporary_directory) / board_path.name
                shutil.copy2(board_path, trial_path)
                trial = pcbnew.LoadBoard(str(trial_path))
                _add_gnd_stitch(trial, from_x, from_y, via_x, via_y)
                _save_board(trial, trial_path)
                try:
                    refill_zones_save(trial_path)
                except Exception:
                    continue
                report = run_drc_report(trial_path)
                shorts, crossings = copper_gate_counts(report)
                clearance = violation_type_counts(report).get("clearance", 0)
                if shorts == 0 and crossings == 0 and clearance <= baseline_clearance:
                    baseline_clearance = clearance
                    _add_gnd_stitch(board, from_x, from_y, via_x, via_y)
                    _save_board(board, board_path)
                    try:
                        refill_zones_save(board_path)
                    except Exception:
                        pass
                    accepted += 1
                    placed = True
                    break
        if not placed:
            print(f"gnd stitch: no legal via for {ref}:{pad_num} @ ({pad_x:.2f},{pad_y:.2f})", flush=True)
    return accepted


def _aon_north_face(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    north_bus_y = 6.55
    pad2_x, pad2_y = millimeters(get_pad(u1, "2").GetPosition())
    pad3_x, pad3_y = millimeters(get_pad(u1, "3").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad2_x, pad2_y), (pad2_x, north_bus_y), (pad3_x, north_bus_y), (pad3_x, pad3_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def _aon_east_face(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    east_col_x = 50.55
    pad55_x, pad55_y = millimeters(get_pad(u1, "55").GetPosition())
    pad56_x, pad56_y = millimeters(get_pad(u1, "56").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad55_x, pad55_y), (east_col_x, pad55_y), (east_col_x, pad56_y), (pad56_x, pad56_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    pad29_x, pad29_y = millimeters(get_pad(u1, "29").GetPosition())
    drop_y = 10.15
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad29_x, pad29_y), (east_col_x, pad29_y), (east_col_x, drop_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def _aon_in2_spine(board: pcbnew.BOARD) -> None:
    aon = board.FindNet("AON_3V3")
    east_col_x = 50.55
    drop_y = 10.15
    spine_x, spine_y = 50.80, 9.20
    add_through_via(board, aon, east_col_x, drop_y, diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In2_Cu,
        [(east_col_x, drop_y), (spine_x, drop_y), (spine_x, spine_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def _aon_pad20_pulls(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    pad20_x, pad20_y = millimeters(get_pad(u1, "20").GetPosition())
    r_chip = footprint_by_reference(board, "R_CHIP_PU")
    pull_x, pull_y = millimeters(get_pad(r_chip, "1").GetPosition())
    cap_aon_x, cap_aon_y = millimeters(
        get_pad(footprint_by_reference(board, "C_MCU1"), "1").GetPosition()
    )
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad20_x, pad20_y), (pull_x, pad20_y), (pull_x, pull_y), (cap_aon_x, cap_aon_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def _aon_pad46_in1(board: pcbnew.BOARD) -> None:
    u1 = footprint_by_reference(board, "U1")
    aon = board.FindNet("AON_3V3")
    in1_bus_x, in1_bus_y = 64.20, 10.15
    pad46_x, pad46_y = millimeters(get_pad(u1, "46").GetPosition())
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.F_Cu,
        [(pad46_x, pad46_y), (pad46_x, in1_bus_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )
    add_through_via(board, aon, pad46_x, in1_bus_y, diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "AON_3V3",
        pcbnew.In1_Cu,
        [(pad46_x, in1_bus_y), (in1_bus_x, in1_bus_y)],
        FAN_IN_TRACK_WIDTH_MM,
    )


def route_aon_u1_ties(board: pcbnew.BOARD) -> None:
    _aon_north_face(board)
    _aon_east_face(board)
    _aon_in2_spine(board)
    _aon_pad20_pulls(board)
    _aon_pad46_in1(board)


def apply_aon_steps_gated(board_path: Path) -> None:
    steps = (
        ("aon_north", _aon_north_face),
        ("aon_east", _aon_east_face),
        ("aon_in2", _aon_in2_spine),
        ("aon_pad20", _aon_pad20_pulls),
        ("aon_pad46", _aon_pad46_in1),
    )
    for label, step in steps:
        if _try_signal_step(board_path, step):
            print(f"aon step {label}: ok", flush=True)
        else:
            print(f"aon step {label}: skipped (DRC gate)", flush=True)


def join_dec_a_en_to_stubs(board: pcbnew.BOARD) -> None:
    """Join U1 pad 47 to existing DEC_A_EN_N fan-in stubs."""
    u1 = footprint_by_reference(board, "U1")
    pad_x, pad_y = millimeters(get_pad(u1, "47").GetPosition())
    stub_f = (68.75, 16.44)
    stub_in1 = (61.40, 20.80)
    route_net_polyline(
        board,
        "DEC_A_EN_N",
        pcbnew.F_Cu,
        [(pad_x, pad_y), (stub_f[0], pad_y), stub_f],
        FAN_IN_TRACK_WIDTH_MM,
    )
    net = board.FindNet("DEC_A_EN_N")
    add_through_via(board, net, stub_f[0], stub_f[1], diameter_mm=VIA_D_MM)
    route_net_polyline(
        board,
        "DEC_A_EN_N",
        pcbnew.In1_Cu,
        [stub_f, stub_in1],
        FAN_IN_TRACK_WIDTH_MM,
    )


def _try_signal_step(
    board_path: Path,
    apply_fn,
    *,
    max_clearance: int | None = None,
) -> bool:
    if max_clearance is None:
        max_clearance = violation_type_counts(run_drc_report(board_path)).get("clearance", 999)
    with tempfile.TemporaryDirectory() as temporary_directory:
        trial_path = Path(temporary_directory) / board_path.name
        shutil.copy2(board_path, trial_path)
        board = pcbnew.LoadBoard(str(trial_path))
        apply_fn(board)
        _save_board(board, trial_path)
        try:
            refill_zones_save(trial_path)
        except Exception:
            return False
        report = run_drc_report(trial_path)
        shorts, crossings = copper_gate_counts(report)
        clearance = violation_type_counts(report).get("clearance", 0)
        if shorts or crossings or clearance > max_clearance:
            return False
        board = pcbnew.LoadBoard(str(board_path))
        apply_fn(board)
        _save_board(board, board_path)
        try:
            refill_zones_save(board_path)
        except Exception:
            return False
        return True


def _try_apply_grid_routes(board_path: Path, routes: dict, *, max_clearance: int) -> bool:
    from mcu_grid_route import apply_grid_routes

    if not routes.get("complete_nets"):
        return False
    with tempfile.TemporaryDirectory() as temporary_directory:
        trial_path = Path(temporary_directory) / board_path.name
        shutil.copy2(board_path, trial_path)
        board = pcbnew.LoadBoard(str(trial_path))
        apply_grid_routes(board, routes.get("segs", []), routes.get("vias", []))
        _save_board(board, trial_path)
        try:
            refill_zones_save(trial_path)
        except Exception:
            return False
        report = run_drc_report(trial_path)
        shorts, crossings = copper_gate_counts(report)
        clearance = violation_type_counts(report).get("clearance", 0)
        if shorts or crossings or clearance > max_clearance:
            return False
        board = pcbnew.LoadBoard(str(board_path))
        apply_grid_routes(board, routes.get("segs", []), routes.get("vias", []))
        _save_board(board, board_path)
        try:
            refill_zones_save(board_path)
        except Exception:
            return False
        return True


def apply_aon_in1_zone_gated(board_path: Path) -> bool:
    baseline = violation_type_counts(run_drc_report(board_path)).get("clearance", 999)
    return _try_signal_step(
        board_path,
        apply_aon_in1_zone_plan,
        max_clearance=baseline,
    )


def route_grid_one_net(board_path: Path, net_name: str, *, max_clearance: int) -> bool:
    import json
    import subprocess

    tools_dir = Path(__file__).resolve().parent
    kpy = Path("/workspace/.kicad10/squashfs-root/usr/bin/python3.11")
    compute = Path("/usr/bin/python3")
    geometry_path = board_path.with_suffix(".mcu_geom.json")
    subprocess.run([str(kpy), str(tools_dir / "dump_mcu_geom.py"), str(board_path), str(geometry_path)], check=True)
    result = subprocess.run(
        [str(compute), str(tools_dir / "mcu_grid_route_one_net.py"), str(geometry_path), net_name],
        check=True,
        capture_output=True,
        text=True,
    )
    routes = json.loads(result.stdout)
    if not routes.get("complete_nets"):
        print(f"grid_one {net_name}: no path", flush=True)
        return False
    ok = _try_apply_grid_routes(board_path, routes, max_clearance=max_clearance)
    print(f"grid_one {net_name}: {'ok' if ok else 'skipped (gate)'}", flush=True)
    return ok


def route_grid_open_nets(board_path: Path) -> None:
    import os

    raw = os.environ.get(
        "MONO_GRID_ONE_NETS",
        "LED_CLK,DEC_A_EN_N,USB_D_N_MCU,IMU_SDA,IMU_SCL,IMU_INT1,ROW_A3,GND",
    )
    nets = [part.strip() for part in raw.split(",") if part.strip()]
    max_clearance = violation_type_counts(run_drc_report(board_path)).get("clearance", 999)
    for net_name in nets:
        if _try_apply_grid_routes is None:
            break
        route_grid_one_net(board_path, net_name, max_clearance=max_clearance)
        max_clearance = violation_type_counts(run_drc_report(board_path)).get("clearance", max_clearance)


def route_open_mcu_signals(board_path: Path) -> None:
    from mono_split_esp32 import (
        route_mcu_boot_switch,
        route_mcu_imu_links,
        route_mcu_strap_passives,
        route_mcu_usb,
    )

    steps = (
        ("strap+boot", lambda b: (route_mcu_strap_passives(b), route_mcu_boot_switch(b))),
        ("usb_d_n", lambda b: route_mcu_usb(b, only_mcu_nets={"USB_D_N_MCU"})),
        ("imu", lambda b: route_mcu_imu_links(b)),
    )
    for label, apply_fn in steps:
        if _try_signal_step(board_path, apply_fn):
            print(f"signal step {label}: ok", flush=True)
        else:
            print(f"signal step {label}: skipped (DRC gate)", flush=True)


def cleanup_danglers_and_move_oe(board: pcbnew.BOARD) -> None:
    """Nudge ROW_XLAT clearance via; delete only tracks with a floating endpoint."""
    move_row_xlat_oe_drop_via(board, None)
    removed = remove_dangling_track_stubs(board)
    if removed:
        print(f"cleanup: removed {removed} dangling track stub(s)", flush=True)


def _trial_copper_gate(board_path: Path, apply_fn) -> tuple[int, int]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        trial_path = Path(temporary_directory) / board_path.name
        shutil.copy2(board_path, trial_path)
        board = pcbnew.LoadBoard(str(trial_path))
        apply_fn(board)
        _save_board(board, trial_path)
        try:
            refill_zones_save(trial_path)
        except Exception:
            return 999, 999
        return _copper_gate(trial_path)


def run_phase(board_path: Path, phase: str) -> dict[str, int]:
    """Run one post-grid phase in a single pcbnew session (KiCad SWIG safe)."""
    stats: dict[str, int] = {"gnd_stitches": 0, "shorts": 0, "crossings": 0}
    if phase == "cleanup":
        board = pcbnew.LoadBoard(str(board_path))
        cleanup_danglers_and_move_oe(board)
        _save_board(board, board_path)
        refill_zones_save(board_path)
        return stats
    if phase == "gnd":
        stats["gnd_stitches"] = stitch_gnd_pads_with_drc_gate(board_path)
        return stats
    if phase == "aon_zone":
        if apply_aon_in1_zone_gated(board_path):
            print("aon_zone: ok", flush=True)
        else:
            print("aon_zone: skipped (DRC gate)", flush=True)
        stats["shorts"], stats["crossings"] = _copper_gate(board_path)
        return stats
    if phase == "aon":
        apply_aon_steps_gated(board_path)
        if _try_signal_step(board_path, join_dec_a_en_to_stubs):
            print("dec_a join: ok", flush=True)
        else:
            print("dec_a join: skipped (DRC gate)", flush=True)
        stats["shorts"], stats["crossings"] = _copper_gate(board_path)
        return stats
    if phase == "grid_one":
        route_grid_open_nets(board_path)
        stats["shorts"], stats["crossings"] = _copper_gate(board_path)
        return stats
    if phase == "signals":
        route_open_mcu_signals(board_path)
        shorts, crossings = _copper_gate(board_path)
        stats["shorts"], stats["crossings"] = shorts, crossings
        return stats
    if phase == "all":
        merged: dict[str, int] = {"gnd_stitches": 0, "shorts": 0, "crossings": 0}
        for step in ("cleanup", "gnd", "aon", "signals"):
            part = run_phase(board_path, step)
            for key, value in part.items():
                merged[key] = merged.get(key, 0) + (value if key == "gnd_stitches" else value)
            if step == "aon" and (part.get("shorts") or part.get("crossings")):
                print(f"post-grid stopping early after {step} (copper gate)", flush=True)
                break
        print(f"post-grid finish stats: {merged}", flush=True)
        return merged
    raise ValueError(f"unknown post-grid phase {phase!r}")


def run_post_grid_finish(board_path: Path) -> dict[str, int]:
    """Run all phases (each phase should run in its own OS process — see main())."""
    return run_phase(board_path, "all")


def _default_phases() -> tuple[str, ...]:
    import os

    raw = os.environ.get("MONO_POST_GRID_PHASES", "cleanup,gnd,aon,signals")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def main() -> None:
    import subprocess
    import sys

    board_path = Path(sys.argv[1])
    phase = sys.argv[2] if len(sys.argv) > 2 else "all"
    if phase == "all":
        kpy = Path("/workspace/.kicad10/squashfs-root/usr/bin/python3.11")
        if not kpy.is_file():
            kpy = Path(sys.executable)
        for step in _default_phases():
            result = subprocess.run(
                [str(kpy), str(Path(__file__).resolve()), str(board_path), step],
                check=False,
            )
            if result.returncode != 0:
                raise SystemExit(result.returncode)
        shorts, crossings = _copper_gate(board_path)
        print(
            f"post-grid finish: shorts={shorts}, crossings={crossings}",
            flush=True,
        )
        return
    stats = run_phase(board_path, phase)
    if stats:
        print(f"post-grid phase {phase}: {stats}", flush=True)


if __name__ == "__main__":
    main()
