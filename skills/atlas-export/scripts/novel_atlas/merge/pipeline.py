"""合并管线：把批次组装成 schema v2.0 的 data.json。

这里只负责编排；实体、关系、章节、伏笔、地点、设定、境界各自的规则
放在同目录下的独立模块，CLI 由 `scripts/merge.py` 负责。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from ..batches import load_batches
from ..sources import count_chars, find_source_file, parse_source_name
from .chapters import build_volumes, merge_chapters
from .cleanup import drop_dangling_relations, drop_unknown_chapter_refs, repair_entity_parents
from .concepts import merge_concepts, prune_concept_duplicates
from .entities import merge_entities, normalize_groups
from .foreshadows import apply_status, attach_mentions, merge_foreshadows
from .places import merge_places
from .realms import apply_power_history, load_realms
from .relations import merge_relations
from .spatial import load_spatial


def merge_book(root, *, out="", batches="", title="", author="", genre="未标注",
               platform="", status="完结", elapsed=0):
    """读取批次并写出 data.json / merge-log.json，返回 (data, log, out, stats)。"""
    root = Path(root)
    if batches:
        bd = Path(batches)
        batch_dir = bd if bd.is_absolute() else root / bd
    else:
        batch_dir = root / "out"
    batches = load_batches(batch_dir)
    print(f"读入 {len(batches)} 个批次（{batch_dir}）")

    cm_path = root / "chunk-meta.json"
    cm = json.loads(cm_path.read_text(encoding="utf-8")) if cm_path.exists() else {}

    ents, id_map, merge_log = merge_entities(batches)
    ents = normalize_groups(ents)
    rels = merge_relations(batches, id_map)
    chaps = merge_chapters(batches, cm, id_map)
    fores = merge_foreshadows(batches, taken_ids={e["id"] for e in ents})
    places = merge_places(
        batches,
        taken_ids={e["id"] for e in ents} | {f["id"] for f in fores},
        entity_names={e["id"]: e["name"] for e in ents},
    )

    # 人工证据化空间数据：补充地点（id 已存在则跳过，不覆盖批次抽取结果），
    # 空间关系原样挂到顶层；无 spatial.json 时关系为空 list，字段保持存在。
    extra_places, spatial_relations, map_layout = load_spatial(root)
    place_ids = {p["id"] for p in places}
    spatial_places_added = 0
    for p in extra_places:
        pid = p.get("id")
        if not pid:
            print(f"  空间地点缺少 id，已跳过：{str(p)[:60]}")
            continue
        if pid in place_ids:
            print(f"  空间地点冲突跳过：{pid} 已存在，不覆盖已有地点")
            continue
        places.append(dict(p))
        place_ids.add(pid)
        spatial_places_added += 1

    concepts = merge_concepts(
        batches,
        taken_ids={e["id"] for e in ents} | {f["id"] for f in fores}
        | {p["id"] for p in places},
    )
    ents, pruned = prune_concept_duplicates(ents, rels, concepts)
    if pruned:
        print(f"  清理与设定重复的器物 {pruned} 个")
    merge_log["summary"]["entity_merge_output"] = merge_log["summary"]["output_entities"]
    merge_log["summary"]["pruned_item_concepts"] = pruned
    merge_log["summary"]["output_entities"] = len(ents)
    realms, realm_ph = load_realms(root, batches)
    apply_power_history(ents, id_map, realms, realm_ph)

    alive = {e["id"] for e in ents}
    rels = drop_dangling_relations(rels, alive)
    drop_unknown_chapter_refs(chaps, alive, {f["id"] for f in fores})
    repair_entity_parents(ents, alive)

    source_title, source_author = parse_source_name(cm.get("source", ""))
    title = title or source_title
    author = author or source_author or "未知"
    source_file = cm.get("source", "")
    src_path = find_source_file(root, source_file)
    book_chars = count_chars(src_path) if src_path else None

    total_chapters = cm.get("chapters_found") or len(chaps)
    data = {
        "meta": {
            "schema_version": "2.0",
            "title": title,
            "author": author,
            "genre": genre,
            "platform": platform,
            "status": status,
            "source_file": source_file,
            "chars": book_chars if book_chars else cm.get("total_chars", 0),
            "chapters": total_chapters,
            "analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": "manual",
            "cost_cny": 0,
            "elapsed_sec": elapsed,
            "coverage": {"chapters_done": len(chaps),
                         "chapters_skipped": max(total_chapters - len(chaps), 0)},
            "note": (f"分批抽取后合并；{len(ents)} 个实体经名称/别名归并"
                     + "；原生抽取，未调用外部 API"
                     + ("" if book_chars else "；chars 仅为已切分章节字数")),
        },
        "volumes": build_volumes(cm, chaps),
        "realms": realms,
        "entities": ents,
        "relations": rels,
        "chapters": chaps,
        "foreshadows": fores,
        "knowledge": [],
        "places": places,
        "concepts": concepts,
        "spatial_relations": spatial_relations,
    }
    # map_layout 缺省时不写该键，视图回退拓扑；提供时原样挂到顶层。
    if map_layout is not None:
        data["map_layout"] = map_layout

    n_m = attach_mentions(root, fores)
    if n_m:
        print(f"  提及轨迹 {n_m} 条（来自 mentions.json）")

    thr, changed = apply_status(data)

    out_path = Path(out) if out else root / "data.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    merge_log["summary"]["chapters_done"] = len(chaps)
    merge_log["summary"]["relations_out"] = len(rels)
    merge_log["summary"]["foreshadows_out"] = len(fores)
    (out_path.parent / "merge-log.json").write_text(
        json.dumps(merge_log, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = {
        "entities_in": sum(len(b.get("entities", [])) for _, b in batches),
        "relations_in": sum(len(b.get("relations", [])) for _, b in batches),
        "foreshadows_in": sum(len(b.get("foreshadows", [])) for _, b in batches),
        "entities_out": len(ents),
        "relations_out": len(rels),
        "chapters_out": len(chaps),
        "chapters_total": total_chapters,
        "foreshadows_out": len(fores),
        "threshold": thr,
        "realms": len(realms),
        "places": len(places),
        "concepts": len(concepts),
        "spatial": len(spatial_relations),
        "spatial_places": spatial_places_added,
        "spatial_nodes": len(map_layout.get("nodes", [])) if map_layout else 0,
        "spatial_regions": len(map_layout.get("regions", [])) if map_layout else 0,
        "chars": data["meta"]["chars"],
        "status_changed": changed,
    }
    return data, merge_log, out_path, stats
