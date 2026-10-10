"""Shared copper helpers (dogbone vias, dangling detection)."""

from __future__ import annotations

import math

import pcbnew  # noqa: E402

from generate_mono_split_boards import millimeters

ENDPOINT_TOL_MM = 0.06
PAD_HIT_TOL_MM = 0.08

# F-only GND pads that need a stitch into In2/B pours (ref, pad number).
# Validated on baseline mono_electronics (run #7); used when dogbone search finds no candidate.
GND_STITCH_FIXED_FALLBACK: dict[tuple[str, str], tuple[float, float]] = {
    ("C_USB1", "2"): (16.48, 24.45),
    ("U_ESD", "5"): (17.14, 12.45),
    ("C_MCU1", "2"): (40.95, 14.55),
    ("U_IMU", "6"): (62.66, 5.20),
    ("U_IMU", "7"): (62.85, 5.96),
}

GND_STITCH_TARGETS: tuple[tuple[str, str], ...] = (
    ("SW1", "2"),
    ("U_ESD", "2"),
    ("U_ESD", "4"),
    ("U_ESD", "5"),
    ("C_USB1", "2"),
    ("C_CHIP_PU", "2"),
    ("C_MCU1", "2"),
    ("C_XTAL1", "2"),
    ("C_XTAL2", "2"),
    ("Y1", "2"),
    ("Y1", "4"),
    ("U_IMU", "6"),
    ("U_IMU", "7"),
)


def pad_hit_mm(pad: pcbnew.PAD, x_mm: float, y_mm: float) -> bool:
    box = pad.GetBoundingBox()
    x0 = pcbnew.ToMM(box.GetX()) - PAD_HIT_TOL_MM
    x1 = pcbnew.ToMM(box.GetRight()) + PAD_HIT_TOL_MM
    y0 = pcbnew.ToMM(box.GetY()) - PAD_HIT_TOL_MM
    y1 = pcbnew.ToMM(box.GetBottom()) + PAD_HIT_TOL_MM
    return x0 <= x_mm <= x1 and y0 <= y_mm <= y1


def endpoint_attachment_count(
    board: pcbnew.BOARD,
    x_mm: float,
    y_mm: float,
    net_name: str,
    *,
    skip_item: pcbnew.BOARD_ITEM | None = None,
    tol_mm: float = ENDPOINT_TOL_MM,
    tracks: list | None = None,
) -> int:
    """How many distinct copper items (other than skip_item) touch this point."""
    hits = 0
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() != net_name:
                continue
            if pad_hit_mm(pad, x_mm, y_mm):
                hits += 1
    track_items = tracks if tracks is not None else list(board.GetTracks())
    for item in track_items:
        if skip_item is not None and item.m_Uuid == skip_item.m_Uuid:
            continue
        if item.GetNetname() != net_name:
            continue
        if item.GetClass() == "PCB_VIA":
            vx, vy = millimeters(item.GetPosition())
            if abs(vx - x_mm) <= tol_mm and abs(vy - y_mm) <= tol_mm:
                hits += 1
        elif item.GetClass() == "PCB_TRACK":
            start = millimeters(item.GetStart())
            end = millimeters(item.GetEnd())
            if abs(start[0] - x_mm) <= tol_mm and abs(start[1] - y_mm) <= tol_mm:
                hits += 1
            if abs(end[0] - x_mm) <= tol_mm and abs(end[1] - y_mm) <= tol_mm:
                hits += 1
    return hits


def track_is_dangling_stub(
    board: pcbnew.BOARD,
    track: pcbnew.PCB_TRACK,
    *,
    tracks: list,
) -> bool:
    """True if at least one track endpoint touches nothing else on the same net."""
    if track.GetClass() != "PCB_TRACK":
        return False
    net_name = track.GetNetname()
    start = millimeters(track.GetStart())
    end = millimeters(track.GetEnd())
    start_n = endpoint_attachment_count(
        board, start[0], start[1], net_name, skip_item=track, tracks=tracks
    )
    end_n = endpoint_attachment_count(
        board, end[0], end[1], net_name, skip_item=track, tracks=tracks
    )
    return start_n == 0 or end_n == 0


def remove_dangling_track_stubs(board: pcbnew.BOARD) -> int:
    """Delete short F.Cu stubs with a floating endpoint (avoid matrix In1/In2 tails)."""
    tracks = list(board.GetTracks())
    batch: list[pcbnew.BOARD_ITEM] = []
    max_stub_mm = 0.90
    for item in tracks:
        if item.GetClass() != "PCB_TRACK":
            continue
        if item.GetLayer() != pcbnew.F_Cu:
            continue
        start = millimeters(item.GetStart())
        end = millimeters(item.GetEnd())
        if math.hypot(end[0] - start[0], end[1] - start[1]) > max_stub_mm:
            continue
        if track_is_dangling_stub(board, item, tracks=tracks):
            batch.append(item)
    for item in batch:
        board.Remove(item)
    return len(batch)


def dogbone_via_candidates(
    pad_x: float,
    pad_y: float,
    *,
    stub_mm: float = 0.45,
) -> list[tuple[float, float, float, float]]:
    """Return (via_x, via_y, stub_from_x, stub_from_y) — never via at pad center."""
    directions = (
        (0.0, stub_mm),
        (0.0, -stub_mm),
        (stub_mm, 0.0),
        (-stub_mm, 0.0),
        (stub_mm * 0.7, stub_mm * 0.7),
        (-stub_mm * 0.7, stub_mm * 0.7),
        (stub_mm * 0.7, -stub_mm * 0.7),
        (-stub_mm * 0.7, -stub_mm * 0.7),
    )
    out: list[tuple[float, float, float, float]] = []
    seen: set[tuple[float, float]] = set()
    for dx, dy in directions:
        via_x = round(pad_x + dx, 2)
        via_y = round(pad_y + dy, 2)
        key = (via_x, via_y)
        if key in seen:
            continue
        seen.add(key)
        if math.hypot(via_x - pad_x, via_y - pad_y) < 0.12:
            continue
        out.append((via_x, via_y, pad_x, pad_y))
    return out
