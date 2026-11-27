"""合并后的引用清理：断链关系、章节引用、势力树断链与成环。"""


def drop_dangling_relations(rels, alive):
    """丢掉指向不存在实体的关系。"""
    before = len(rels)
    kept = [r for r in rels if r["s"] in alive and r["t"] in alive]
    if before != len(kept):
        print(f"  清理断链关系 {before - len(kept)} 条")
    return kept


def drop_unknown_chapter_refs(chaps, entity_ids, foreshadow_ids):
    """引用不到实体的 id 从章节里剔除，否则校验器直接报错。"""
    for c in chaps:
        c["new_entities"] = [x for x in (c.get("new_entities") or []) if x in entity_ids]
        c["new_foreshadows"] = [x for x in (c.get("new_foreshadows") or []) if x in foreshadow_ids]


def repair_entity_parents(ents, alive):
    """势力树断链：parent 指向不存在实体时清空；parent 链成环时断开。"""
    for e in ents:
        if e.get("parent") and e["parent"] not in alive:
            e["parent"] = None

    parent_of = {e["id"]: e.get("parent") for e in ents}
    for e in ents:
        seen, cur = set(), e["id"]
        while cur and cur in parent_of and cur not in seen:
            seen.add(cur)
            cur = parent_of[cur]
            if cur == e["id"]:
                e["parent"] = None
                print(f"  ⚠ {e['name']} 的 parent 链成环，已断开")
                break
