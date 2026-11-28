"""关系归并：重映射实体 id，按 (s, t, type) 去重。"""


def merge_relations(batches, id_map):
    """重映射 id，按 (s,t,type) 去重，weight 取最大。"""
    best = {}
    for _, b in batches:
        for r in b.get("relations", []):
            s = id_map.get(r.get("s"), r.get("s"))
            t = id_map.get(r.get("t"), r.get("t"))
            if not s or not t or s == t:
                continue
            key = (s, t, r.get("type"))
            w = r.get("weight")
            w = 0.5 if not isinstance(w, (int, float)) else max(0.0, min(1.0, float(w)))
            rec = dict(r)
            rec["s"], rec["t"], rec["weight"] = s, t, w
            if key not in best or w > best[key]["weight"]:
                best[key] = rec
    return list(best.values())
