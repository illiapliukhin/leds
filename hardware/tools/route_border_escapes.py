from collections import deque
from pathlib import Path
import os

import numpy
import pcbnew

from generate_board_skeletons import (
    deterministic_kiid,
    save_board_without_project_side_effects,
)
from generate_edge_routing_probe import TRACK_WIDTH_MM, add_through_via, add_track
from place_backside_components import build_placed_board


GRID_PITCH_MM = 0.1
TRACK_CLEARANCE_MM = 0.1
TRACK_KEEPOUT_MM = TRACK_WIDTH_MM / 2 + TRACK_CLEARANCE_MM
VIA_DIAMETER_MM = 0.45
VIA_RADIUS_MM = VIA_DIAMETER_MM / 2
VIA_KEEPOUT_MM = VIA_RADIUS_MM + TRACK_CLEARANCE_MM
BOARD_EDGE_MM = 0.6
FIELD_RING_MM = 1.4
BOARD_SIZE_MM = 69.0
COPPER_EDGE_CLEARANCE_MM = 0.3
TRACK_EDGE_MARGIN_MM = COPPER_EDGE_CLEARANCE_MM + TRACK_WIDTH_MM / 2
ESCAPE_PAST_COURTYARD_MM = 0.4
PAD_COPPER_INSET_MM = 0.2
ROUTING_LAYERS = (pcbnew.B_Cu, pcbnew.In2_Cu)


def cell_index(position_mm: float, cell_count: int) -> int:
    index = int(position_mm / GRID_PITCH_MM)
    return max(0, min(cell_count - 1, index))


def cell_center_mm(index: int) -> float:
    return (index + 0.5) * GRID_PITCH_MM


def stamp_disk(
    grid: numpy.ndarray,
    center_x_mm: float,
    center_y_mm: float,
    radius_mm: float,
) -> None:
    if radius_mm <= 0:
        return
    cell_count = grid.shape[0]
    center_x = cell_index(center_x_mm, cell_count)
    center_y = cell_index(center_y_mm, cell_count)
    radius_cells = int(radius_mm / GRID_PITCH_MM) + 2
    y0 = max(0, center_y - radius_cells)
    y1 = min(cell_count, center_y + radius_cells + 1)
    x0 = max(0, center_x - radius_cells)
    x1 = min(cell_count, center_x + radius_cells + 1)
    yy, xx = numpy.ogrid[y0:y1, x0:x1]
    center_columns = (xx + 0.5) * GRID_PITCH_MM
    center_rows = (yy + 0.5) * GRID_PITCH_MM
    mask = (center_columns - center_x_mm) ** 2 + (center_rows - center_y_mm) ** 2 <= (
        radius_mm ** 2
    )
    grid[y0:y1, x0:x1][mask] = 1


def stamp_segment(
    grid: numpy.ndarray,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    radius_mm: float,
) -> None:
    length_mm = ((end_x_mm - start_x_mm) ** 2 + (end_y_mm - start_y_mm) ** 2) ** 0.5
    steps = max(1, int(length_mm / (GRID_PITCH_MM / 2)) + 1)
    for step in range(steps + 1):
        blend = step / steps
        stamp_disk(
            grid,
            start_x_mm + (end_x_mm - start_x_mm) * blend,
            start_y_mm + (end_y_mm - start_y_mm) * blend,
            radius_mm,
        )


def inset_box(
    bounds: tuple[float, float, float, float],
    inset_mm: float,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bounds
    if x1 - x0 <= 2 * inset_mm or y1 - y0 <= 2 * inset_mm:
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        return (center_x - 0.05, center_y - 0.05, center_x + 0.05, center_y + 0.05)
    return (x0 + inset_mm, y0 + inset_mm, x1 - inset_mm, y1 - inset_mm)


def copper_box(item: pcbnew.BOARD_ITEM) -> tuple[float, float, float, float]:
    bounds = item.GetBoundingBox()
    left = pcbnew.ToMM(bounds.GetLeft())
    right = pcbnew.ToMM(bounds.GetRight())
    top = pcbnew.ToMM(bounds.GetTop())
    bottom = pcbnew.ToMM(bounds.GetBottom())
    return min(left, right), min(top, bottom), max(left, right), max(top, bottom)


def dilate(grid: numpy.ndarray, radius_cells: int) -> numpy.ndarray:
    dilated = grid.copy()
    height, width = grid.shape[-2], grid.shape[-1]
    for offset_y in range(-radius_cells, radius_cells + 1):
        for offset_x in range(-radius_cells, radius_cells + 1):
            if offset_x * offset_x + offset_y * offset_y > radius_cells * radius_cells:
                continue
            source_y = slice(max(0, -offset_y), height - max(0, offset_y))
            source_x = slice(max(0, -offset_x), width - max(0, offset_x))
            dest_y = slice(max(0, offset_y), height - max(0, -offset_y))
            dest_x = slice(max(0, offset_x), width - max(0, -offset_x))
            dilated[..., dest_y, dest_x] = numpy.maximum(
                dilated[..., dest_y, dest_x],
                grid[..., source_y, source_x],
            )
    return dilated


def stamp_box(
    grid: numpy.ndarray,
    bounds: tuple[float, float, float, float],
    expansion_mm: float,
) -> None:
    x0, y0, x1, y1 = bounds
    x0 -= expansion_mm
    y0 -= expansion_mm
    x1 += expansion_mm
    y1 += expansion_mm
    cell_count = grid.shape[-1]
    column0 = max(0, int(x0 / GRID_PITCH_MM))
    row0 = max(0, int(y0 / GRID_PITCH_MM))
    column1 = min(cell_count, int(numpy.ceil(x1 / GRID_PITCH_MM)))
    row1 = min(grid.shape[-2], int(numpy.ceil(y1 / GRID_PITCH_MM)))
    if column0 < column1 and row0 < row1:
        grid[row0:row1, column0:column1] = 1


class BorderRouter:
    def __init__(self, board: pcbnew.BOARD) -> None:
        self.board = board
        self.cell_count = cell_index(69.0, 10_000) + 1
        self.layer_count = len(ROUTING_LAYERS)
        self.blocked = numpy.zeros(
            (self.layer_count, self.cell_count, self.cell_count),
            dtype=numpy.uint8,
        )
        self.via_blocked = numpy.zeros(
            (self.cell_count, self.cell_count),
            dtype=numpy.uint8,
        )
        self.back_courtyard = numpy.zeros(
            (self.cell_count, self.cell_count),
            dtype=numpy.uint8,
        )
        self._mark_via_field_interior()
        self._mark_existing_copper()
        self._mark_board_edge()
        self._mark_via_obstacles()

    def _mark_via_field_interior(self) -> None:
        xs: list[float] = []
        ys: list[float] = []
        for item in self.board.GetTracks():
            if isinstance(item, pcbnew.PCB_VIA):
                xs.append(pcbnew.ToMM(item.GetPosition().x))
                ys.append(pcbnew.ToMM(item.GetPosition().y))
        minimum_x = min(xs) + FIELD_RING_MM
        maximum_x = max(xs) - FIELD_RING_MM
        minimum_y = min(ys) + FIELD_RING_MM
        maximum_y = max(ys) - FIELD_RING_MM
        for index_y in range(self.cell_count):
            y_mm = cell_center_mm(index_y)
            if not minimum_y < y_mm < maximum_y:
                continue
            for index_x in range(self.cell_count):
                x_mm = cell_center_mm(index_x)
                if minimum_x < x_mm < maximum_x:
                    self.blocked[:, index_y, index_x] = 1
                    self.via_blocked[index_y, index_x] = 1

    def _mark_board_edge(self) -> None:
        for index in range(self.cell_count):
            center_mm = cell_center_mm(index)
            outside_track_margin = (
                center_mm < TRACK_EDGE_MARGIN_MM
                or center_mm > BOARD_SIZE_MM - TRACK_EDGE_MARGIN_MM
            )
            if outside_track_margin:
                self.blocked[:, index, :] = 1
                self.blocked[:, :, index] = 1

    def _mark_via_obstacles(self) -> None:
        for item in self.board.GetTracks():
            if isinstance(item, pcbnew.PCB_VIA):
                continue
            if self._layer_index(item.GetLayer()) is not None:
                continue
            half_width_mm = pcbnew.ToMM(item.GetWidth()) / 2
            stamp_segment(
                self.via_blocked,
                pcbnew.ToMM(item.GetStart().x),
                pcbnew.ToMM(item.GetStart().y),
                pcbnew.ToMM(item.GetEnd().x),
                pcbnew.ToMM(item.GetEnd().y),
                half_width_mm + VIA_KEEPOUT_MM,
            )
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                if pad.IsOnLayer(pcbnew.B_Cu):
                    continue
                stamp_box(self.via_blocked, copper_box(pad), VIA_KEEPOUT_MM)
            self._mark_courtyard(footprint)

    def _mark_courtyard(self, footprint: pcbnew.FOOTPRINT) -> None:
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            courtyard = footprint.GetCourtyard(layer)
            if courtyard.OutlineCount() == 0:
                continue
            bounds = courtyard.BBox()
            left = pcbnew.ToMM(bounds.GetLeft())
            right = pcbnew.ToMM(bounds.GetRight())
            top = pcbnew.ToMM(bounds.GetTop())
            bottom = pcbnew.ToMM(bounds.GetBottom())
            bounds = (min(left, right), min(top, bottom), max(left, right), max(top, bottom))
            stamp_box(self.via_blocked, bounds, 0.0)
            if layer == pcbnew.B_CrtYd:
                stamp_box(self.back_courtyard, bounds, 0.0)

    def _mark_existing_copper(self) -> None:
        for item in self.board.GetTracks():
            self._mark_item(item, foreign=True)
        for footprint in self.board.GetFootprints():
            if footprint.GetValue() == "MHPA1010RGBDT":
                continue
            for pad in footprint.Pads():
                self._mark_pad(pad, foreign=True)

    def _layer_index(self, layer: int) -> int | None:
        try:
            return ROUTING_LAYERS.index(layer)
        except ValueError:
            return None

    def _mark_item(self, item: pcbnew.BOARD_CONNECTED_ITEM, foreign: bool) -> None:
        expansion = TRACK_KEEPOUT_MM if foreign else 0.0
        via_expansion = VIA_KEEPOUT_MM if foreign else 0.0
        if isinstance(item, pcbnew.PCB_VIA):
            x_mm = pcbnew.ToMM(item.GetPosition().x)
            y_mm = pcbnew.ToMM(item.GetPosition().y)
            radius = pcbnew.ToMM(item.GetWidth(pcbnew.B_Cu)) / 2
            for layer_index in range(self.layer_count):
                stamp_disk(self.blocked[layer_index], x_mm, y_mm, radius + expansion)
            stamp_disk(
                self.via_blocked,
                x_mm,
                y_mm,
                radius + via_expansion + GRID_PITCH_MM / 2,
            )
            return
        layer_index = self._layer_index(item.GetLayer())
        if layer_index is None:
            return
        start_x = pcbnew.ToMM(item.GetStart().x)
        start_y = pcbnew.ToMM(item.GetStart().y)
        end_x = pcbnew.ToMM(item.GetEnd().x)
        end_y = pcbnew.ToMM(item.GetEnd().y)
        half_width = pcbnew.ToMM(item.GetWidth()) / 2
        stamp_segment(
            self.blocked[layer_index],
            start_x,
            start_y,
            end_x,
            end_y,
            half_width + expansion,
        )
        stamp_segment(
            self.via_blocked,
            start_x,
            start_y,
            end_x,
            end_y,
            half_width + via_expansion,
        )

    def _mark_pad(self, pad: pcbnew.PAD, foreign: bool) -> None:
        if not pad.IsOnLayer(pcbnew.B_Cu):
            return
        expansion = TRACK_KEEPOUT_MM if foreign else 0.0
        bounds = copper_box(pad)
        stamp_box(self.blocked[0], bounds, expansion)
        stamp_box(
            self.via_blocked,
            bounds,
            VIA_KEEPOUT_MM if foreign else 0.0,
        )

    def _via_allowed(self, index_y: int, index_x: int) -> bool:
        if self.via_blocked[index_y, index_x]:
            return False
        x_mm = cell_center_mm(index_x)
        y_mm = cell_center_mm(index_y)
        if (
            x_mm < BOARD_EDGE_MM
            or y_mm < BOARD_EDGE_MM
            or x_mm > 69.0 - BOARD_EDGE_MM
            or y_mm > 69.0 - BOARD_EDGE_MM
        ):
            return False
        return True

    def _search(
        self,
        blocked: numpy.ndarray,
        starts: list[tuple[int, int]],
        targets: numpy.ndarray,
    ) -> list[tuple[int, int, int]] | None:
        stride = self.cell_count * self.cell_count
        parent = numpy.full(self.layer_count * stride, -1, dtype=numpy.int32)
        queue: deque[int] = deque()
        for index_y, index_x in starts:
            state = index_y * self.cell_count + index_x
            if targets[0, index_y, index_x]:
                return [(0, index_y, index_x)]
            parent[state] = state
            queue.append(state)
        offsets = ((1, 0), (-1, 0), (0, 1), (0, -1))
        while queue:
            state = queue.popleft()
            layer = state // stride
            remainder = state % stride
            index_y = remainder // self.cell_count
            index_x = remainder % self.cell_count
            for offset_y, offset_x in offsets:
                next_y = index_y + offset_y
                next_x = index_x + offset_x
                if (
                    next_y < 0
                    or next_x < 0
                    or next_y >= self.cell_count
                    or next_x >= self.cell_count
                ):
                    continue
                if blocked[layer, next_y, next_x] and not targets[layer, next_y, next_x]:
                    continue
                next_state = layer * stride + next_y * self.cell_count + next_x
                if parent[next_state] != -1:
                    continue
                parent[next_state] = state
                if targets[layer, next_y, next_x]:
                    return self._reconstruct(parent, next_state, stride)
                queue.append(next_state)
            if self._via_allowed(index_y, index_x):
                for other_layer in range(self.layer_count):
                    if other_layer == layer:
                        continue
                    if (
                        blocked[other_layer, index_y, index_x]
                        and not targets[other_layer, index_y, index_x]
                    ):
                        continue
                    next_state = (
                        other_layer * stride + index_y * self.cell_count + index_x
                    )
                    if parent[next_state] != -1:
                        continue
                    parent[next_state] = state
                    if targets[other_layer, index_y, index_x]:
                        return self._reconstruct(parent, next_state, stride)
                    queue.append(next_state)
        return None

    def _reconstruct(
        self,
        parent: numpy.ndarray,
        state: int,
        stride: int,
    ) -> list[tuple[int, int, int]]:
        path: list[tuple[int, int, int]] = []
        seen = 0
        while True:
            layer = state // stride
            remainder = state % stride
            index_y = remainder // self.cell_count
            index_x = remainder % self.cell_count
            path.append((layer, index_y, index_x))
            previous = int(parent[state])
            if previous == state or previous < 0:
                break
            state = previous
            seen += 1
            if seen > parent.size:
                break
        path.reverse()
        return path

    def _commit_path(self, net: pcbnew.NETINFO_ITEM, path: list[tuple[int, int, int]]) -> None:
        serial = 0
        index = 0
        while index < len(path) - 1:
            layer, index_y, index_x = path[index]
            next_layer, next_y, next_x = path[index + 1]
            if layer != next_layer:
                x_mm = cell_center_mm(index_x)
                y_mm = cell_center_mm(index_y)
                add_through_via(self.board, net, x_mm, y_mm, VIA_DIAMETER_MM)
                stamp_disk(
                    self.via_blocked,
                    x_mm,
                    y_mm,
                    VIA_DIAMETER_MM + TRACK_CLEARANCE_MM + GRID_PITCH_MM / 2,
                )
                for layer_index in range(self.layer_count):
                    stamp_disk(
                        self.blocked[layer_index],
                        x_mm,
                        y_mm,
                        VIA_RADIUS_MM + TRACK_KEEPOUT_MM + GRID_PITCH_MM / 2,
                    )
                index += 1
                continue
            step_y = next_y - index_y
            step_x = next_x - index_x
            end_index = index + 1
            while end_index + 1 < len(path):
                current = path[end_index]
                following = path[end_index + 1]
                if following[0] != layer:
                    break
                if (
                    following[1] - current[1] != step_y
                    or following[2] - current[2] != step_x
                ):
                    break
                end_index += 1
            self._add_segment(net, path[index], path[end_index], serial)
            serial += 1
            index = end_index

    def _add_segment(
        self,
        net: pcbnew.NETINFO_ITEM,
        start: tuple[int, int, int],
        end: tuple[int, int, int],
        serial: int,
    ) -> None:
        if start[0] != end[0] or (start[1] == end[1] and start[2] == end[2]):
            return
        if start[1] != end[1] and start[2] != end[2]:
            return
        start_x = cell_center_mm(start[2])
        start_y = cell_center_mm(start[1])
        end_x = cell_center_mm(end[2])
        end_y = cell_center_mm(end[1])
        add_track(
            self.board,
            net,
            ROUTING_LAYERS[start[0]],
            start_x,
            start_y,
            end_x,
            end_y,
            TRACK_WIDTH_MM,
        )
        track = list(self.board.GetTracks())[-1]
        track.SetUuid(
            deterministic_kiid(f"border-route:{net.GetNetname()}:{serial}:{start}:{end}")
        )
        stamp_segment(
            self.blocked[start[0]],
            start_x,
            start_y,
            end_x,
            end_y,
            TRACK_WIDTH_MM / 2 + TRACK_KEEPOUT_MM,
        )
        stamp_segment(
            self.via_blocked,
            start_x,
            start_y,
            end_x,
            end_y,
            TRACK_WIDTH_MM / 2 + VIA_KEEPOUT_MM,
        )

    def _target_grid(self, net_name: str, excluded_pad: pcbnew.PAD) -> numpy.ndarray:
        targets = numpy.zeros_like(self.blocked)
        for item in self.board.GetTracks():
            if item.GetNetname() != net_name:
                continue
            if isinstance(item, pcbnew.PCB_VIA):
                x_mm = pcbnew.ToMM(item.GetPosition().x)
                y_mm = pcbnew.ToMM(item.GetPosition().y)
                radius = pcbnew.ToMM(item.GetWidth(pcbnew.B_Cu)) / 2
                for layer_index in range(self.layer_count):
                    stamp_disk(targets[layer_index], x_mm, y_mm, radius)
                continue
            layer_index = self._layer_index(item.GetLayer())
            if layer_index is None:
                continue
            stamp_segment(
                targets[layer_index],
                pcbnew.ToMM(item.GetStart().x),
                pcbnew.ToMM(item.GetStart().y),
                pcbnew.ToMM(item.GetEnd().x),
                pcbnew.ToMM(item.GetEnd().y),
                pcbnew.ToMM(item.GetWidth()) / 2,
            )
        excluded_reference = excluded_pad.GetParentFootprint().GetReference()
        excluded_number = excluded_pad.GetNumber()
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                same_pad = (
                    footprint.GetReference() == excluded_reference
                    and pad.GetNumber() == excluded_number
                )
                if same_pad or pad.GetNetname() != net_name:
                    continue
                if pad.IsOnLayer(pcbnew.B_Cu):
                    stamp_box(targets[0], inset_box(copper_box(pad), PAD_COPPER_INSET_MM), 0.0)
        return targets

    def _start_cells(self, pad: pcbnew.PAD) -> list[tuple[int, int]]:
        x0, y0, x1, y1 = inset_box(copper_box(pad), PAD_COPPER_INSET_MM)
        cells: list[tuple[int, int]] = []
        index_y = cell_index(y0, self.cell_count)
        last_y = cell_index(y1, self.cell_count)
        index_x = cell_index(x0, self.cell_count)
        last_x = cell_index(x1, self.cell_count)
        for cell_y in range(index_y, last_y + 1):
            for cell_x in range(index_x, last_x + 1):
                cells.append((cell_y, cell_x))
        return cells

    def connect_pad(self, pad: pcbnew.PAD) -> bool:
        net_name = pad.GetNetname()
        net = self.board.FindNet(net_name)
        if net is None or not net_name:
            return False
        targets = self._target_grid(net_name, pad)
        if not targets.any():
            return False
        blocked = self.blocked.copy()
        keepout_cells = int(TRACK_KEEPOUT_MM / GRID_PITCH_MM) + 1
        blocked[0][self.back_courtyard == 1] = 1
        blocked[dilate(targets, keepout_cells) == 1] = 0
        blocked[0][self.back_courtyard == 1] = 1
        self._open_escape(blocked, pad)
        self._clear_net_pads(blocked, net_name)
        starts = [
            (index_y, index_x)
            for index_y, index_x in self._start_cells(pad)
            if not blocked[0, index_y, index_x]
        ]
        if not starts:
            return False
        path = self._search(blocked, starts, targets)
        if path is None:
            return False
        path = self._smooth_path(path, blocked, targets)
        path = self._extend_to_pad_center(path, net_name)
        self._commit_path(net, path)
        return True

    def _clear_net_pads(self, blocked: numpy.ndarray, net_name: str) -> None:
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                if pad.GetNetname() != net_name or not pad.IsOnLayer(pcbnew.B_Cu):
                    continue
                pad_cells = numpy.zeros((self.cell_count, self.cell_count), dtype=numpy.uint8)
                stamp_box(pad_cells, copper_box(pad), 0.0)
                blocked[0][pad_cells == 1] = 0

    def _extend_to_pad_center(
        self,
        path: list[tuple[int, int, int]],
        net_name: str,
    ) -> list[tuple[int, int, int]]:
        if not path or path[-1][0] != 0:
            return path
        _, index_y, index_x = path[-1]
        x_mm = cell_center_mm(index_x)
        y_mm = cell_center_mm(index_y)
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                if pad.GetNetname() != net_name or not pad.IsOnLayer(pcbnew.B_Cu):
                    continue
                pad_x0, pad_y0, pad_x1, pad_y1 = copper_box(pad)
                tolerance_mm = GRID_PITCH_MM / 2
                inside_pad = (
                    pad_x0 - tolerance_mm <= x_mm <= pad_x1 + tolerance_mm
                    and pad_y0 - tolerance_mm <= y_mm <= pad_y1 + tolerance_mm
                )
                if not inside_pad:
                    continue
                center = pad.GetPosition()
                target_x = cell_index(pcbnew.ToMM(center.x), self.cell_count)
                target_y = cell_index(pcbnew.ToMM(center.y), self.cell_count)
                extended = list(path)
                cursor_y = index_y
                cursor_x = index_x
                for _ in range(40):
                    if cursor_y == target_y and cursor_x == target_x:
                        break
                    if abs(target_y - cursor_y) >= abs(target_x - cursor_x) and cursor_y != target_y:
                        cursor_y += 1 if target_y > cursor_y else -1
                    else:
                        cursor_x += 1 if target_x > cursor_x else -1
                    extended.append((0, cursor_y, cursor_x))
                return extended
        return path

    def _open_escape(self, blocked: numpy.ndarray, pad: pcbnew.PAD) -> None:
        corridor = numpy.zeros((self.cell_count, self.cell_count), dtype=numpy.uint8)
        stamp_box(corridor, copper_box(pad), 0.0)
        stamp_box(corridor, self._escape_bounds(pad), 0.0)
        foreign = self.blocked[0].copy()
        own_pad = numpy.zeros_like(foreign)
        stamp_box(own_pad, copper_box(pad), TRACK_KEEPOUT_MM)
        foreign[own_pad == 1] = 0
        blocked[0][(corridor == 1) & (foreign == 0)] = 0

    def _escape_bounds(self, pad: pcbnew.PAD) -> tuple[float, float, float, float]:
        pad_bounds = copper_box(pad)
        footprint = pad.GetParentFootprint()
        courtyard = footprint.GetCourtyard(pcbnew.B_CrtYd)
        if courtyard.OutlineCount() == 0:
            return pad_bounds
        bounds = courtyard.BBox()
        court_x0 = min(pcbnew.ToMM(bounds.GetLeft()), pcbnew.ToMM(bounds.GetRight()))
        court_x1 = max(pcbnew.ToMM(bounds.GetLeft()), pcbnew.ToMM(bounds.GetRight()))
        court_y0 = min(pcbnew.ToMM(bounds.GetTop()), pcbnew.ToMM(bounds.GetBottom()))
        court_y1 = max(pcbnew.ToMM(bounds.GetTop()), pcbnew.ToMM(bounds.GetBottom()))
        pad_x0, pad_y0, pad_x1, pad_y1 = pad_bounds
        pad_center_x = (pad_x0 + pad_x1) / 2
        pad_center_y = (pad_y0 + pad_y1) / 2
        edge_distance = {
            "left": pad_center_x - court_x0,
            "right": court_x1 - pad_center_x,
            "top": pad_center_y - court_y0,
            "bottom": court_y1 - pad_center_y,
        }
        nearest_edge = min(edge_distance, key=edge_distance.get)
        if nearest_edge == "left":
            return (court_x0 - ESCAPE_PAST_COURTYARD_MM, pad_y0, pad_x1, pad_y1)
        if nearest_edge == "right":
            return (pad_x0, pad_y0, court_x1 + ESCAPE_PAST_COURTYARD_MM, pad_y1)
        if nearest_edge == "bottom":
            return (pad_x0, pad_y0, pad_x1, court_y1 + ESCAPE_PAST_COURTYARD_MM)
        return (pad_x0, court_y0 - ESCAPE_PAST_COURTYARD_MM, pad_x1, pad_y1)

    def _smooth_path(
        self,
        path: list[tuple[int, int, int]],
        blocked: numpy.ndarray,
        targets: numpy.ndarray,
    ) -> list[tuple[int, int, int]]:
        if len(path) < 3:
            return path
        kept = [0]
        index = 0
        while index < len(path) - 1:
            farthest = index + 1
            for candidate in range(len(path) - 1, index, -1):
                if self._orthogonal_span_clear(path[index], path[candidate], blocked, targets):
                    farthest = candidate
                    break
            kept.append(farthest)
            index = farthest
        return [path[point] for point in kept]

    def _orthogonal_span_clear(
        self,
        start: tuple[int, int, int],
        end: tuple[int, int, int],
        blocked: numpy.ndarray,
        targets: numpy.ndarray,
    ) -> bool:
        if start[0] != end[0] or (start[1] != end[1] and start[2] != end[2]):
            return False
        layer = start[0]
        for index_y in range(min(start[1], end[1]), max(start[1], end[1]) + 1):
            for index_x in range(min(start[2], end[2]), max(start[2], end[2]) + 1):
                if blocked[layer, index_y, index_x] and not targets[layer, index_y, index_x]:
                    return False
        return True


def pads_to_route(board: pcbnew.BOARD) -> list[pcbnew.PAD]:
    pads: list[pcbnew.PAD] = []
    for footprint in board.GetFootprints():
        if footprint.GetValue() == "MHPA1010RGBDT":
            continue
        for pad in footprint.Pads():
            if pad.GetNetname():
                pads.append(pad)
    return pads


def route_distance_key(pad: pcbnew.PAD) -> tuple[int, float, float, str, str]:
    net_name = pad.GetNetname()
    phase = 1
    if net_name.startswith("COL_") or net_name.endswith("_ANODE"):
        phase = 0
    if net_name in {"GND", "AON_3V3", "LED_4V1", "SYS", "BAT_RAW", "VBUS_USB"}:
        phase = 2
    return (
        phase,
        round(pcbnew.ToMM(pad.GetPosition().x), 3),
        round(pcbnew.ToMM(pad.GetPosition().y), 3),
        net_name,
        pad.GetNumber(),
    )


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    board_path = (
        repository_root / "hardware" / "wearable_20x20" / "wearable_20x20.kicad_pcb"
    )
    limit = int(os.environ.get("BORDER_ROUTE_LIMIT", "0"))
    phase_text = os.environ.get("BORDER_ROUTE_PHASE")
    selected_phase = int(phase_text) if phase_text is not None else None
    board = build_placed_board(repository_root)
    router = BorderRouter(board)
    connected = 0
    attempted = 0
    for pad in sorted(pads_to_route(board), key=route_distance_key):
        if selected_phase is not None and route_distance_key(pad)[0] != selected_phase:
            continue
        if limit and attempted >= limit:
            break
        attempted += 1
        if router.connect_pad(pad):
            connected += 1
        else:
            footprint = pad.GetParentFootprint()
            print(
                f"unrouted {footprint.GetReference()} pad {pad.GetNumber()} {pad.GetNetname()}"
            )
        if attempted % 25 == 0:
            print(f"routed {connected}/{attempted}")
    save_board_without_project_side_effects(board_path, board)
    print(f"Border router connected {connected} of {attempted} pads.")


if __name__ == "__main__":
    main()
