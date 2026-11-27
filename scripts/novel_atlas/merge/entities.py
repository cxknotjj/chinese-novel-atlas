"""实体归并：正名归并、别名 union-find、阵营修正与归并审计。"""

from collections import Counter
from datetime import datetime, timezone

from ..names import (
    GENERIC_ALIASES,
    GENERIC_ALIAS_RE,
    GENERIC_NAME_RE,
    norm,
)


def _new_record(e, source=""):
    rec = dict(e)
    rec.setdefault("parent", None)
    rec.setdefault("attrs", {})
    rec.setdefault("power_history", [])
    rec.setdefault("aliases", [])
    rec["_groups"] = Counter([e.get("group") or "其他"])
    rec["_ids"] = {e.get("id")} - {None}
    rec["_sources"] = {source} - {""}
    return rec


def _absorb(cur, e, source=""):
    """把 e 的信息补进 cur（保留更全的那份）。"""
    if len(e.get("desc") or "") > len(cur.get("desc") or ""):
        cur["desc"] = e["desc"]
    cur["aliases"] = list(dict.fromkeys(
        (cur.get("aliases") or []) + (e.get("aliases") or [])))
    fc = e.get("first_ch")
    if isinstance(fc, int) and (cur.get("first_ch") is None or fc < cur["first_ch"]):
        cur["first_ch"] = fc
    # last_ch：只要后续批次仍认为“未退场”（null），就清掉早批次的误判退场章
    if e.get("last_ch") is None:
        cur["last_ch"] = None
    elif cur.get("last_ch") is not None:
        cur["last_ch"] = max(cur["last_ch"], e["last_ch"])
    else:
        cur["last_ch"] = e["last_ch"]
    lc = e.get("last_ch")
    if isinstance(lc, int) and (cur.get("last_ch") is None or lc > cur["last_ch"]):
        cur["last_ch"] = lc
    if e.get("attrs"):
        cur.setdefault("attrs", {}).update(e["attrs"])
    for p in (e.get("power_history") or []):
        if isinstance(p.get("ch"), int) and p not in cur.setdefault("power_history", []):
            cur["power_history"].append(p)
    if e.get("parent") and not cur.get("parent"):
        cur["parent"] = e["parent"]
    cur.setdefault("_groups", Counter())[e.get("group") or "其他"] += 1
    cur.setdefault("_ids", set()).update({e.get("id")} - {None})
    cur.setdefault("_sources", set()).update(e.get("_sources") or set())
    cur.setdefault("_sources", set()).update({source} - {""})


def merge_entities(batches):
    """按 (正名, 类型) 归并，再按别名做第二级归并。返回 (entities, id_map, merge_log)。"""
    pool, index = [], {}
    name_merges = []
    for source, b in batches:
        for e in b.get("entities", []):
            name = norm(e.get("name", ""))
            if not name:
                continue
            key = (name, e.get("type") or "character")
            if key in index:
                cur = pool[index[key]]
                if GENERIC_NAME_RE.match(name) and (e.get("group") or "") != (cur.get("group") or ""):
                    pool.append(_new_record(e, source))       # 同名的“李氏”分属两府，各留各的
                    index[key] = len(pool) - 1
                    continue
                name_merges.append({
                    "name": e.get("name"), "type": e.get("type"),
                    "kept_id": cur.get("id"), "merged_id": e.get("id"),
                    "source": source
                })
                _absorb(cur, e, source)
            else:
                index[key] = len(pool)
                pool.append(_new_record(e, source))

    # ---- 第二级：别名归并（union-find）----
    parent = list(range(len(pool)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    name_to_idx = {}
    for i, e in enumerate(pool):
        name_to_idx.setdefault(norm(e.get("name", "")), i)

    alias_owner = {}   # 别名 → {可能指向的实体下标}
    for i, e in enumerate(pool):
        for a in e.get("aliases") or []:
            an = norm(a)
            if not an or len(an) < 2 or an in GENERIC_ALIASES or GENERIC_ALIAS_RE.match(an) or GENERIC_NAME_RE.match(an):
                continue
            alias_owner.setdefault(an, set()).add(i)

    merged_alias = 0
    alias_merges = []
    for an, owners in alias_owner.items():
        target = name_to_idx.get(an)
        if target is None:
            continue          # 这个别名不是任何实体的正名，无从归并
        if len(owners) > 1:
            continue          # 同一个别名挂在多个人身上，说明是通用称号，跳过
        if owners == {target}:
            continue
        owner = next(iter(owners))
        union(owner, target)
        alias_merges.append({
            "alias": an,
            "merged_name": pool[owner].get("name"),
            "merged_id": pool[owner].get("id"),
            "target_name": pool[target].get("name"),
            "target_id": pool[target].get("id"),
        })
        merged_alias += 1

    # ---- 按簇合并 ----
    clusters = {}
    for i in range(len(pool)):
        clusters.setdefault(find(i), []).append(i)

    out, id_map, clusters_log = [], {}, []
    for root, members in sorted(clusters.items(), key=lambda kv: min(kv[1])):
        members = sorted(members)
        head = pool[members[0]]          # 最早出现的那条当主记录
        for i in members[1:]:
            _absorb(head, pool[i], "")
        head["group"] = head["_groups"].most_common(1)[0][0]
        head["aliases"] = [a for a in dict.fromkeys(head.get("aliases", []))
                           if norm(a) != norm(head["name"])]
        head["power_history"] = sorted(
            [p for p in head.get("power_history", []) if isinstance(p.get("ch"), int)],
            key=lambda x: x["ch"])
        ids = set(head.pop("_ids", set()))
        head.pop("_groups", None)
        sources = sorted(head.pop("_sources", set()))
        # 全局 id 唯一：主记录沿用最早那批的 id，冲突时加后缀
        base = head.get("id") or f"e_{len(out) + 1:03d}"
        final, n = base, 2
        while any(x["id"] == final for x in out):
            final = f"{base}_{n}"
            n += 1
        head["id"] = final
        for old in ids:
            id_map[old] = final
        id_map.setdefault(base, final)
        if len(members) > 1:
            clusters_log.append({
                "final_id": final,
                "name": head.get("name"),
                "type": head.get("type"),
                "group": head.get("group"),
                "merged_ids": sorted(ids),
                "sources": sources,
                "members": [
                    {
                        "id": pool[m].get("id"),
                        "name": pool[m].get("name"),
                        "aliases": pool[m].get("aliases") or [],
                    } for m in members
                ],
            })
        out.append(head)

    if merged_alias:
        print(f"  别名归并 {merged_alias} 组（同一实体在不同批次用了不同名字）")
    merge_log = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "batch_count": len(batches),
        "summary": {
            "input_entities": sum(len(b.get("entities", [])) for _, b in batches),
            "output_entities": len(out),
            "merged_clusters": len(clusters_log),
            "name_merges": len(name_merges),
            "alias_merges": len(alias_merges),
        },
        "clusters": clusters_log,
        "name_merges": name_merges,
        "alias_merges": alias_merges,
    }
    return out, id_map, merge_log


def normalize_groups(ents):
    """修正 group：分批抽取时模型容易把"所属人物"当成"阵营"填。

    规则：
    1. group 等于某个角色名 → 说明误填了人名，改为该角色自己的 group 或"其他"
    2. "无"/"不明"/空 → "其他"
    3. 阵营数超过 8 个时，只保留成员数最多的 8 个，其余并入"其他"；
       但本身有 org 实体（门派/家族/帮会）的阵营一律保留——长篇里 40+ 门派
       若被这条上限吞成"其他"，势力视图会失效
    """
    by_name = {norm(e["name"]): e for e in ents}
    person_names = {norm(e["name"]) for e in ents if e.get("type") == "character"}

    for e in ents:
        g = (e.get("group") or "").strip()
        if not g or g in ("无", "不明", "未知", "—", "-"):
            e["group"] = "其他"
            continue
        if norm(g) in person_names and norm(g) != norm(e["name"]):
            owner = by_name.get(norm(g))
            og = (owner.get("group") or "").strip() if owner else ""
            e["group"] = og if og and norm(og) not in person_names and og not in ("无", "不明") else "其他"

    counts = Counter(e["group"] for e in ents)
    org_names = {norm(e["name"]) for e in ents if e.get("type") == "org"}
    mains = {g for g, _ in counts.most_common(8)}
    mains |= {g for g in counts if norm(g) in org_names}
    for e in ents:
        if e["group"] not in mains:
            e["group"] = "其他"
    return ents
