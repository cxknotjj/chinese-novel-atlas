"""地图 M0–M4 成熟度分级。

等级不是视觉样式，而是证据能力：
M0 无坐标；M1 只有 parent/拓扑；M2 有 ≥3 条方向/距离证据；
M3 有多层（位面/父地图下钻）；M4 有时态切片。
"""

from __future__ import annotations

from collections import defaultdict


def _root(place_id: str, places: dict[str, dict]) -> str:
    cur = place_id
    seen = set()
    while cur in places:
        p = places[cur]
        # L1 是地理分支；map_layer 是显式地图层根。两者都终止上溯，
        # 否则「越国 → 天南」会把三层地图压成一个天南层。
        if p.get("level") == 1 or p.get("map_layer"):
            break
        if p.get("parent") not in places or cur in seen:
            break
        seen.add(cur)
        cur = p["parent"]
    return cur


def _directions(layout: dict | None) -> dict[str, int]:
    """按根层统计方向/距离约束数。"""
    return {k: v for k, v in (layout or {}).items()}


def compute_map_levels(data: dict) -> dict:
    places = {p.get("id"): p for p in data.get("places") or [] if p.get("id")}
    layout = data.get("map_layout") if isinstance(data.get("map_layout"), dict) else None
    spatial = data.get("spatial_relations") or []
    if not places:
        return {"global": "M0", "layers": [], "reason": "没有地点数据"}
    if not layout or not (layout.get("nodes") or layout.get("regions")):
        has_topology = any(p.get("parent") in places for p in places.values())
        if has_topology:
            return {"global": "M1", "layers": [], "reason": "没有示意布局，按 places.parent 做拓扑"}
        return {"global": "M0", "layers": [], "reason": "只有地点索引，没有坐标或层级"}

    # 层：根地点 + 有地图节点/区域的层
    layers = sorted({
        n.get("layer") or _root(n.get("place"), places)
        for n in (layout.get("nodes") or [])
        if n.get("place") in places
    } | {
        r.get("layer") for r in (layout.get("regions") or []) if r.get("layer") in places
    })
    by_layer = defaultdict(list)
    for r in spatial:
        if r.get("kind") not in ("direction", "distance"):
            continue
        if r.get("s") in places:
            by_layer[_root(r["s"], places)].append(r)
        if r.get("t") in places:
            by_layer[_root(r["t"], places)].append(r)

    out_layers = []
    for lid in layers:
        count = len({r.get("id") for r in by_layer.get(lid, [])})
        level = "M2" if count >= 3 else "M1"
        out_layers.append({
            "id": lid,
            "name": (places.get(lid) or {}).get("name") or lid,
            "level": level,
            "direction_constraints": count,
        })

    # 多层：至少两个根层都有地图节点，且节点/区域显式标了 layer
    explicit_layers = {
        n.get("layer") for n in (layout.get("nodes") or []) if n.get("layer")
    } | {
        r.get("layer") for r in (layout.get("regions") or []) if r.get("layer")
    }
    multi_layer = len({_root(x, places) for x in explicit_layers if x in places}) >= 2
    time_slices = layout.get("time_slices") if isinstance(layout.get("time_slices"), list) else []
    if time_slices:
        level = "M4"
        reason = f"存在 {len(time_slices)} 个时态切片"
    elif multi_layer:
        level = "M3"
        reason = f"存在 {len(explicit_layers)} 个显式层"
    elif any(x["level"] == "M2" for x in out_layers):
        level = "M2"
        reason = "至少一个层有 ≥3 条方向/距离约束"
    else:
        level = "M1"
        reason = "只有示意坐标，没有足够方向证据"
    return {"global": level, "layers": out_layers, "reason": reason, "time_slices": len(time_slices)}
