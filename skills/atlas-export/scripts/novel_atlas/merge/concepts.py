"""设定归并：按 (kind, name) 合并，并清理与设定重复的器物实体。"""

from collections import Counter

from ..names import norm


def merge_concepts(batches, taken_ids=None):
    """功法 / 金手指 / 品阶这类设定按 (kind, name) 归并。"""
    pool, order = {}, []
    for _, b in batches:
        for c in b.get("concepts") or []:
            key = (c.get("kind") or "technique", norm(c.get("name", "")))
            if not key[1]:
                continue
            if key in pool:
                cur = pool[key]
                if len(c.get("desc") or "") > len(cur.get("desc") or ""):
                    cur["desc"] = c["desc"]
                for field in ("rules", "limits"):
                    cur[field] = list(dict.fromkeys((cur.get(field) or []) + (c.get(field) or [])))
                fc = c.get("first_ch")
                if isinstance(fc, int) and (cur.get("first_ch") is None or fc < cur["first_ch"]):
                    cur["first_ch"] = fc
            else:
                pool[key] = dict(c)
                order.append(key)

    taken = set(taken_ids or ())
    out = []
    for i, key in enumerate(order, 1):
        c = pool[key]
        base = c.get("id") or f"c_{i:03d}"
        final, n = base, 2
        while final in taken:
            final = f"{base}_{n}"
            n += 1
        taken.add(final)
        c["id"] = final
        out.append(c)
    return out


def prune_concept_duplicates(ents, rels, concepts):
    """同一件东西既被抽成 item 又被抽成 concept 时，删掉没有关系的那个 item。

    典型：无名口诀、火弹术被模型当器物建了实体，同时又在 concepts 里出现。
    只在 item 没有任何关系边时删除——有关系的说明它参与了剧情，保留。
    """
    degree = Counter()
    for r in rels:
        degree[r["s"]] += 1
        degree[r["t"]] += 1
    names = {norm(c.get("name", "")) for c in concepts}
    drop = {e["id"] for e in ents
            if e.get("type") == "item" and degree[e["id"]] == 0
            and norm(e.get("name", "")) in names}
    if not drop:
        return ents, 0
    return [e for e in ents if e["id"] not in drop], len(drop)
