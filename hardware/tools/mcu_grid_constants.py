"""Shared MCU grid routing constants (no pcbnew dependency)."""

from __future__ import annotations

MCU_ROUTE_ORDER: tuple[str, ...] = (
    "XTAL_P",
    "XTAL_N",
    "USB_D_P_MCU",
    "USB_D_N_MCU",
    "USB_D_P",
    "USB_D_N",
    "ROW_A0",
    "ROW_A1",
    "ROW_A2",
    "ROW_A3",
    "DEC_A_EN_N",
    "DEC_B_EN_N",
    "ROW_XLAT_OE_N",
    "LED_CLK",
    "LED_SDI",
    "LED_LE",
    "LED_OE_N",
    "LED_EN",
    "LED_LOGIC_EN",
    "AUDIO_EN",
    "CHIP_PU",
    "GPIO0_BOOT",
    "AON_3V3",
    "GND",
)


def paths_to_segments(all_paths: dict[str, list]) -> tuple[list[dict], list[dict]]:
    resolution_mm = 0.1
    layer_names = ["F", "In1", "In2", "B"]
    segments: list[dict] = []
    vias: list[dict] = []

    for net_name, path_list in all_paths.items():
        for layer_indices, row_indices, column_indices in path_list:
            points = [
                (
                    int(layer_indices[point_index]),
                    (column_indices[point_index] + 0.5) * resolution_mm,
                    (row_indices[point_index] + 0.5) * resolution_mm,
                )
                for point_index in range(len(layer_indices))
            ]
            run = [points[0]]
            for point in points[1:]:
                if point[0] != run[-1][0]:
                    if len(run) >= 2:
                        _flush_segment_run(net_name, layer_names, run, segments)
                    vias.append({"net": net_name, "x": point[1], "y": point[2]})
                    run = [point]
                else:
                    run.append(point)
            if len(run) >= 2:
                _flush_segment_run(net_name, layer_names, run, segments)
    return segments, vias


def _flush_segment_run(
    net_name: str,
    layer_names: list[str],
    run: list[tuple[int, float, float]],
    segments: list[dict],
) -> None:
    merged = [run[0]]
    for point_index in range(1, len(run) - 1):
        previous = merged[-1]
        current = run[point_index]
        next_point = run[point_index + 1]
        direction_a = (
            round((current[1] - previous[1]) / 0.1),
            round((current[2] - previous[2]) / 0.1),
        )
        direction_b = (
            round((next_point[1] - current[1]) / 0.1),
            round((next_point[2] - current[2]) / 0.1),
        )
        cross = direction_a[0] * direction_b[1] - direction_a[1] * direction_b[0]
        dot = direction_a[0] * direction_b[0] + direction_a[1] * direction_b[1]
        if cross != 0 or dot < 0:
            merged.append(current)
    merged.append(run[-1])
    for start_point, end_point in zip(merged, merged[1:]):
        segments.append(
            {
                "net": net_name,
                "layer": layer_names[start_point[0]],
                "x1": start_point[1],
                "y1": start_point[2],
                "x2": end_point[1],
                "y2": end_point[2],
            }
        )
