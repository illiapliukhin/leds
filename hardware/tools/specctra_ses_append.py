"""Append Freerouting SES routes to a KiCad board without removing existing copper."""

from __future__ import annotations

import re
from pathlib import Path

import pcbnew

from generate_mono_split_boards import add_through_via, route_net_polyline

SPECCTRA_UNITS_PER_MM = 10_000.0

LAYER_BY_NAME: dict[str, int] = {
    "F.Cu": pcbnew.F_Cu,
    "In1.Cu": pcbnew.In1_Cu,
    "In2.Cu": pcbnew.In2_Cu,
    "B.Cu": pcbnew.B_Cu,
}

VIA_DIAMETER_MM = 0.45
VIA_DRILL_MM = 0.20


def _specctra_mm(raw: int) -> float:
    return raw / SPECCTRA_UNITS_PER_MM


def _width_mm(raw: int) -> float:
    return raw / SPECCTRA_UNITS_PER_MM


def _network_out_blob(text: str) -> str:
    marker = "(network_out"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("SES missing network_out section")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise RuntimeError("Unbalanced network_out in SES")


def _split_net_blocks(network_blob: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r'\(net "([^"]+)"', network_blob))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        net_name = match.group(1)
        start = match.start()
        depth = 0
        end = start
        for pos in range(start, len(network_blob)):
            char = network_blob[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = pos + 1
                    break
        blocks.append((net_name, network_blob[start:end]))
    return blocks


def _parse_wire_paths(net_blob: str) -> list[tuple[str, float, list[tuple[float, float]]]]:
    paths: list[tuple[str, float, list[tuple[float, float]]]] = []
    for match in re.finditer(
        r"\(path ([^\s]+) (\d+)\s+((?:\s+-?\d+)+)\s*\)",
        net_blob,
        flags=re.MULTILINE,
    ):
        layer_name = match.group(1)
        width = _width_mm(int(match.group(2)))
        coords = [int(value) for value in match.group(3).split()]
        if len(coords) < 4 or len(coords) % 2 != 0:
            continue
        points = [
            (_specctra_mm(coords[i]), _specctra_mm(coords[i + 1]))
            for i in range(0, len(coords), 2)
        ]
        paths.append((layer_name, width, points))
    return paths


def _parse_vias(net_blob: str) -> list[tuple[float, float]]:
    vias: list[tuple[float, float]] = []
    for match in re.finditer(
        r'\(via "[^"]+"\s+(-?\d+)\s+(-?\d+)\s*\)',
        net_blob,
    ):
        vias.append((_specctra_mm(int(match.group(1))), _specctra_mm(int(match.group(2)))))
    return vias


def append_specctra_ses_routing(board: pcbnew.BOARD, ses_path: Path) -> tuple[int, int]:
    """Add wires/vias from SES; existing tracks are untouched."""
    text = ses_path.read_text(encoding="utf-8")
    network_blob = _network_out_blob(text)
    wire_count = 0
    via_count = 0
    for net_name, net_blob in _split_net_blocks(network_blob):
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Board missing net {net_name!r} referenced in SES")
        for layer_name, width_mm, points in _parse_wire_paths(net_blob):
            layer = LAYER_BY_NAME.get(layer_name)
            if layer is None:
                raise RuntimeError(f"Unsupported Specctra layer {layer_name!r}")
            route_net_polyline(board, net_name, layer, points, width_mm)
            wire_count += 1
        for x_mm, y_mm in _parse_vias(net_blob):
            add_through_via(
                board,
                net,
                x_mm,
                y_mm,
                diameter_mm=VIA_DIAMETER_MM,
            )
            via_count += 1
    return wire_count, via_count
