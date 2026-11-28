"""按读者阅读进度截断世界档案。

这是读者向产品的核心：同一份 data.json 可以投影成任意章节的“当时世界”。
规则刻意保守：没有 `first_ch` 的内容不进入读者档案；未来章节的 payoff /
power / knowledge / map 层全部裁掉，避免 UI 层漏剧透。
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any


def _int(v: Any, default: int | None = None) -> int | None:
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return default


def _first(obj: dict) -> int:
    return _int(obj.get("first_ch"), 0) or 0


def _visible_ch(obj: dict, cutoff: int) -> bool:
    ch = _first(obj)
    return ch <= cutoff and ch > 0


def _evidence_ch(ev: Any) -> int | None:
    if not isinstance(ev, dict):
        return None
    return _int(ev.get("ch"))


def _foreshadow_status(f: dict, live: int, threshold: int) -> str:
    if f.get("status") == "dropped":
        return "dropped"
    payoff = f.get("payoff_ch")
    if payoff and payoff != f.get("plant_ch"):
        return "paid"
    last = _int(f.get("last_mention_ch")) or _int(f.get("plant_ch")) or 0
    return "overdue" if live - last > threshold else "planted"


def reader_meta(data: dict, cutoff: int | None = None) -> dict:
    total = _int((data.get("meta") or {}).get("chapters"), 0) or 0
    analyzed = _int(((data.get("meta") or {}).get("coverage") or {}).get("chapters_done"), 0) or 0
    chapter_max = max([_int(c.get("ch"), 0) or 0 for c in data.get("chapters") or []] + [analyzed, 1])
    cutoff = max(1, min(cutoff or chapter_max, chapter_max))
    return {
        "cutoff_ch": cutoff,
        "analyzed_ch": analyzed or chapter_max,
        "chapter_max": chapter_max,
        "total_chapters": total,
        "analysis_complete": bool(total and analyzed >= total),
        "is_spoiler_safe": cutoff < chapter_max,
    }


def _cut_map_layout(layout: dict, visible_places: set[str], cutoff: int) -> dict:
    """只保留读者已经读到的地图节点、区域、路线和 stamp。"""
    out = copy.deepcopy(layout)
    raw_nodes = out.get("nodes") or []
    out["nodes"] = [n for n in raw_nodes if n.get("place") in visible_places]
    visible_region_ids = set()
    regions = []
    for r in out.get("regions") or []:
        layer = r.get("layer")
        if layer and layer not in visible_places:
            continue
        regions.append(r)
        if r.get("id"):
            visible_region_ids.add(r["id"])
    out["regions"] = regions

    out["routes"] = [
        r for r in (out.get("routes") or [])
        if r.get("s") in visible_places and r.get("t") in visible_places
    ]

    terrain = out.get("terrain")
    if isinstance(terrain, dict):
        def keeps_region(item):
            reg = item.get("region")
            return not reg or reg in visible_region_ids
        terrain = {
            "ridges": [x for x in (terrain.get("ridges") or []) if keeps_region(x)],
            "rivers": [x for x in (terrain.get("rivers") or []) if keeps_region(x)],
            "lakes": [x for x in (terrain.get("lakes") or []) if keeps_region(x)],
            "islets": terrain.get("islets") or [],
        }
        out["terrain"] = terrain

    atlas = out.get("atlas")
    if isinstance(atlas, dict):
        atlas = copy.deepcopy(atlas)
        stamps = []
        for s in atlas.get("stamps") or []:
            attach = s.get("attach")
            if attach and attach not in visible_places:
                continue
            layer = s.get("layer")
            if layer and layer not in visible_places:
                continue
            stamps.append(s)
        atlas["stamps"] = stamps
        markers = atlas.get("markers")
        if isinstance(markers, dict):
            atlas["markers"] = {k: v for k, v in markers.items() if k in visible_places}
        out["atlas"] = atlas

    if isinstance(out.get("time_slices"), list):
        def slice_ch(x):
            return (_int(x.get("ch")) or _int(x.get("first_ch")) or
                    _int(x.get("start_ch")) or 0)
        out["time_slices"] = [x for x in out["time_slices"] if 0 < slice_ch(x) <= cutoff]
    if isinstance(out.get("map_layout"), dict):
        ml = out["map_layout"]
        if isinstance(ml.get("time_slices"), list):
            def ml_slice_ch(x):
                return (_int(x.get("ch")) or _int(x.get("first_ch")) or
                        _int(x.get("start_ch")) or 0)
            ml["time_slices"] = [x for x in ml["time_slices"] if 0 < ml_slice_ch(x) <= cutoff]
    return out


def filter_data(data: dict, cutoff: int | None = None) -> dict:
    """返回只包含第 1..cutoff 章读者可知内容的数据副本。

    注意：这是 UI 投影，不替代服务端鉴权。静态单文件 HTML 仍携带完整
    data.json；若要真正不发布未来内容，应由发布端按 cutoff 生成对应副本。
    """
    meta = reader_meta(data, cutoff)
    c = meta["cutoff_ch"]
    out = copy.deepcopy(data)

    entities = []
    entity_ids = set()
    for e in out.get("entities") or []:
        if not _visible_ch(e, c):
            continue
        e = copy.deepcopy(e)
        e["power_history"] = [p for p in (e.get("power_history") or [])
                              if (_int(p.get("ch"), 0) or 0) <= c]
        last = _int(e.get("last_ch"))
        if last is not None and last > c:
            # 读者还没读到退场；不提前泄露“最后出现章”
            e["last_ch"] = None
        entities.append(e)
        entity_ids.add(e.get("id"))
    out["entities"] = entities

    out["relations"] = [
        r for r in out.get("relations") or []
        if (_int(r.get("first_ch"), 0) or 0) <= c
        and r.get("s") in entity_ids and r.get("t") in entity_ids
    ]

    out["chapters"] = [ch for ch in out.get("chapters") or []
                       if (_int(ch.get("ch"), 0) or 0) <= c]
    for ch in out["chapters"]:
        ch["battles"] = [b for b in (ch.get("battles") or [])
                         if b.get("a") in entity_ids and b.get("b") in entity_ids]

    foreshadows = []
    for f in out.get("foreshadows") or []:
        if (_int(f.get("plant_ch"), 0) or 0) > c:
            continue
        f = copy.deepcopy(f)
        payoff = _int(f.get("payoff_ch"))
        if payoff is not None and payoff > c:
            f["payoff_ch"] = None
            f["payoff_quote"] = None
        last = _int(f.get("last_mention_ch"))
        if last is not None and last > c:
            f["last_mention_ch"] = None
        # 状态按读者进度派生，不能用全书分析时的快照
        from ..foreshadow_rules import threshold
        thr = threshold(c, meta["total_chapters"])
        f["status"] = _foreshadow_status(f, c, thr)
        foreshadows.append(f)
    out["foreshadows"] = foreshadows

    knowledge = []
    for k in out.get("knowledge") or []:
        truth = _int(k.get("truth_ch"), 0) or 0
        known = _int(k.get("reader_known_ch"), truth) or truth
        if truth > c or known > c:
            continue
        k = copy.deepcopy(k)
        k["known_by"] = [x for x in (k.get("known_by") or [])
                         if (_int(x.get("ch"), 0) or 0) <= c and x.get("entity") in entity_ids]
        knowledge.append(k)
    out["knowledge"] = knowledge

    places = []
    place_ids = set()
    for p in out.get("places") or []:
        # 地理分支容器没有剧情首现章；它们必须留下，否则所有子树会掉回
        # 越国/乱星海这些旧根，L1 又空了。
        if not p.get("virtual") and not _visible_ch(p, c):
            continue
        places.append(p)
        place_ids.add(p.get("id"))
    out["places"] = places
    out["spatial_relations"] = [
        r for r in out.get("spatial_relations") or []
        if (_int(r.get("first_ch"), 0) or 0) <= c
        and r.get("s") in place_ids and r.get("t") in place_ids
        and (_evidence_ch(r.get("evidence")) or c) <= c
    ]

    out["concepts"] = [x for x in out.get("concepts") or [] if _visible_ch(x, c)]
    out["volumes"] = [v for v in out.get("volumes") or []
                      if (_int(v.get("first_ch"), 0) or 1) <= c]

    if isinstance(out.get("map_layout"), dict):
        out["map_layout"] = _cut_map_layout(out["map_layout"], place_ids, c)

    anomalies = []
    for a in out.get("anomalies") or []:
        rng = a.get("chapter_range") or []
        if rng:
            end = _int(rng[-1], 0) or 0
            if end and end > c:
                continue
        bad = False
        for ev in a.get("evidence") or []:
            if not isinstance(ev, dict):
                continue
            ch = _int(ev.get("ch"))
            if ch is None:
                m = re.match(r"ch(\d+)", str(ev.get("coordinate") or ""))
                ch = int(m.group(1)) if m else None
            if ch is not None and ch > c:
                bad = True
                break
        if bad:
            continue
        anomalies.append(a)
    if "anomalies" in out:
        out["anomalies"] = anomalies

    # 冻结副本的 coverage 就是 cutoff：读者站不应声称自己覆盖了更多章
    if isinstance(out.get("meta"), dict):
        source_chapter_max = meta["chapter_max"]
        cov = out["meta"].setdefault("coverage", {})
        total = meta["total_chapters"]
        cov["chapters_done"] = c
        if total:
            cov["chapters_skipped"] = max(0, total - c)
        meta["analyzed_ch"] = c
        meta["chapter_max"] = max(
            c,
            max([_int(ch.get("ch"), 0) or 0 for ch in out.get("chapters") or []] + [0]),
        )
        meta["analysis_complete"] = bool(total and c >= total)
        meta["is_spoiler_safe"] = c < source_chapter_max

    out["_reader"] = meta
    return out


def dump_filtered(data: dict, cutoff: int) -> str:
    return json.dumps(filter_data(data, cutoff), ensure_ascii=False, separators=(",", ":"))
