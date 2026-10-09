"""Merge grid route JSON packages (e.g. PF + greedy supplements)."""

from __future__ import annotations


def merge_routes(primary: dict, supplement: dict, borrow_nets: set[str]) -> dict:
    if not borrow_nets:
        return primary
    segs = [segment for segment in primary.get("segs", []) if segment["net"] not in borrow_nets]
    segs.extend(segment for segment in supplement.get("segs", []) if segment["net"] in borrow_nets)
    vias = [via for via in primary.get("vias", []) if via["net"] not in borrow_nets]
    vias.extend(via for via in supplement.get("vias", []) if via["net"] in borrow_nets)
    p_complete = set(primary.get("complete_nets") or [])
    s_complete = set(supplement.get("complete_nets") or [])
    complete = sorted(p_complete | (s_complete & borrow_nets))
    incomplete = sorted(
        (set(primary.get("incomplete_nets") or []) | (s_complete - p_complete - borrow_nets))
        - set(borrow_nets)
    )
    merged = dict(primary)
    merged["segs"] = segs
    merged["vias"] = vias
    merged["complete_nets"] = complete
    merged["incomplete_nets"] = incomplete
    merged["route_engine"] = f"{primary.get('route_engine', 'primary')}+greedy({','.join(sorted(borrow_nets))})"
    return merged
