"""地点归并：同名合并，父节点支持名称/id/势力名解析。"""

from ..names import norm


def merge_places(batches, taken_ids=None, entity_names=None):
    """地点按名字归并，parent 允许写名字或 id，统一解析成 id。

    模型常把"宗门"写成 entity（e_qixuanmen）再拿它当地点父节点。
    这种情况不硬造一个同名地点，而是把势力名记进 attrs.所属势力，parent 置空。
    """
    pool, order = {}, []
    for _, b in batches:
        for p in b.get("places") or []:
            key = norm(p.get("name", ""))
            if not key:
                continue
            if key in pool:
                cur = pool[key]
                if len(p.get("desc") or "") > len(cur.get("desc") or ""):
                    cur["desc"] = p["desc"]
                fc = p.get("first_ch")
                if isinstance(fc, int) and (cur.get("first_ch") is None or fc < cur["first_ch"]):
                    cur["first_ch"] = fc
                if p.get("parent") and not cur.get("parent"):
                    cur["parent"] = p["parent"]
                if p.get("attrs"):
                    cur.setdefault("attrs", {}).update(p["attrs"])
            else:
                pool[key] = dict(p)
                order.append(key)

    taken = set(taken_ids or ())
    ids, name_to_id = {}, {}
    for i, key in enumerate(order, 1):
        p = pool[key]
        base = p.get("id") or f"p_{i:03d}"
        final, n = base, 2
        while final in taken:
            final = f"{base}_{n}"
            n += 1
        taken.add(final)
        p["id"] = final
        ids[key] = final
        name_to_id[key] = final

    place_ids = set(ids.values())
    for key in order:
        p = pool[key]
        parent = p.get("parent")
        if parent and parent not in place_ids:
            resolved = name_to_id.get(norm(parent))
            if resolved:
                p["parent"] = resolved
            elif entity_names and parent in entity_names:
                p.setdefault("attrs", {}).setdefault("所属势力", entity_names[parent])
                p["parent"] = None
            else:
                p["parent"] = None
    return [pool[k] for k in order]
