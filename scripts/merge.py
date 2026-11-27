#!/usr/bin/env python3
"""merge.py — 把分批抽取的结果合并成一份 data.json。

难点在**实体消解**：同一个角色在不同批次里可能被起成不同的 id
（"韩立" → e_hanli / e_han_li / e_hanli2）。这里按 name 归并，
关系边跟着重映射，避免出现孤立节点。

用法：
    python scripts/merge.py output/凡人修仙传/ --out output/凡人修仙传/data.json
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def norm(s):
    """归一化名字用于匹配：去空格、去标点、全角转半角。"""
    s = (s or "").strip()
    s = s.replace("　", "").replace(" ", "")
    s = re.sub(r"[·・．.、，,（）()\[\]【】]", "", s)
    return s


def sim(a, b):
    """粗粒度相似度：完全包含或 2-gram Jaccard。"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
        return 0.75
    ga = {a[i:i + 2] for i in range(len(a) - 1)}
    gb = {b[i:i + 2] for i in range(len(b) - 1)}
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def load_batches(d):
    files = sorted(Path(d).glob("out/batch-*.json"))
    if not files:
        raise SystemExit(f"{d}/out/ 下没有 batch-*.json")
    batches = []
    for f in files:
        try:
            batches.append((f.name, json.loads(f.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as e:
            print(f"  ⚠ 跳过 {f.name}：JSON 解析失败（{e}）")
    return batches


def merge_entities(batches):
    """按 name 归并实体，返回 (entities, id_map)。"""
    pool = []          # [{id, name, ...}]
    by_name = {}       # 归一化名字 → pool 下标

    for _, b in batches:
        for e in b.get("entities", []):
            name = norm(e.get("name", ""))
            if not name:
                continue
            if name in by_name:
                i = by_name[name]
                cur = pool[i]
                # 补全信息：desc 取更长的，别名取并集，first_ch 取更小
                if len(e.get("desc") or "") > len(cur.get("desc") or ""):
                    cur["desc"] = e["desc"]
                cur["aliases"] = list(dict.fromkeys(
                    (cur.get("aliases") or []) + (e.get("aliases") or [])))
                fc = e.get("first_ch")
                if isinstance(fc, int) and (cur.get("first_ch") is None or fc < cur["first_ch"]):
                    cur["first_ch"] = fc
                lc = e.get("last_ch")
                if isinstance(lc, int) and (cur.get("last_ch") is None or lc > cur["last_ch"]):
                    cur["last_ch"] = lc
                if e.get("attrs"):
                    cur.setdefault("attrs", {}).update(e["attrs"])
                for p in (e.get("power_history") or []):
                    if p not in cur.setdefault("power_history", []):
                        cur["power_history"].append(p)
                cur.setdefault("_groups", Counter())[e.get("group") or "其他"] += 1
                cur.setdefault("_ids", set()).add(e.get("id"))
            else:
                rec = dict(e)
                rec.setdefault("parent", None)
                rec.setdefault("attrs", {})
                rec.setdefault("power_history", [])
                rec["_groups"] = Counter([e.get("group") or "其他"])
                rec["_ids"] = {e.get("id")}
                by_name[name] = len(pool)
                pool.append(rec)

    # 第二遍：别名也能对上（"韩老魔" 归到 "韩立"）
    alias_map = {}
    for i, e in enumerate(pool):
        for a in e.get("aliases") or []:
            an = norm(a)
            if an and an not in by_name:
                alias_map.setdefault(an, i)

    id_map = {}
    for e in pool:
        primary = e["id"]
        for old in e["_ids"]:
            if old:
                id_map[old] = primary
        for a in e.get("aliases") or []:
            if norm(a) in alias_map and alias_map[norm(a)] != pool.index(e):
                continue

    out = []
    for e in pool:
        e["group"] = e["_groups"].most_common(1)[0][0]
        e["aliases"] = [a for a in e.get("aliases", []) if norm(a) != norm(e["name"])]
        e["power_history"] = sorted(e.get("power_history", []), key=lambda x: x.get("ch", 0))
        for k in ("_groups", "_ids"):
            e.pop(k, None)
        out.append(e)
    return out, id_map


def normalize_groups(ents, rels):
    """修正 group：分批抽取时模型容易把"所属人物"当成"阵营"填。

    规则：
    1. group 等于某个实体的 name → 说明误填了人名，改为该实体自己的 group 或"其他"
    2. "无"/"不明"/空 → "其他"
    3. 阵营数超过 8 个时，把只含 1 个成员的并入"其他"
    """
    names = {norm(e["name"]) for e in ents}
    by_name = {norm(e["name"]): e for e in ents}
    # 只有"人物名"被当成 group 才算误填；组织名自成阵营是合法的
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
    mains = [g for g, n in counts.items() if n >= 3]
    if len(mains) > 8:
        mains = [g for g, _ in counts.most_common(8)]
    for e in ents:
        if e["group"] not in mains:
            e["group"] = "其他"
    return ents


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
            w = r.get("weight") or 0.5
            if key not in best or w > (best[key].get("weight") or 0):
                rec = dict(r)
                rec["s"], rec["t"] = s, t
                best[key] = rec
    return list(best.values())


def merge_chapters(batches):
    by_ch = {}
    for _, b in batches:
        for c in b.get("chapters", []):
            ch = c.get("ch")
            if isinstance(ch, int) and ch not in by_ch:
                by_ch[ch] = c
    return [by_ch[k] for k in sorted(by_ch)]


def merge_foreshadows(batches, id_map):
    """按内容相似度归并同一条伏笔。"""
    pool = []
    for _, b in batches:
        for f in b.get("foreshadows", []):
            content = f.get("content", "")
            dup = None
            for ex in pool:
                if sim(content, ex.get("content", "")) > 0.62:
                    dup = ex
                    break
            if dup:
                if len(f.get("note") or "") > len(dup.get("note") or ""):
                    dup["note"] = f["note"]
                if f.get("payoff_ch") and not dup.get("payoff_ch"):
                    dup["payoff_ch"] = f["payoff_ch"]
                    dup["payoff_quote"] = f.get("payoff_quote")
                dup["importance"] = max(dup.get("importance", 0.5), f.get("importance", 0.5))
            else:
                pool.append(dict(f))
    for i, f in enumerate(pool, 1):
        f["id"] = f.get("id") or f"f_{i:03d}"
    return pool


def load_realm_spec(root):
    """读取全局境界体系定义 realms.json（若有）。

    境界是全局概念，不能由逐批抽取各自建立——批次只看 10 章，
    各批 order 独立编号，合并后必然错乱（曾出现「筑基」被排成 order=1）。
    因此体系由 realms.json 权威定义，批次内联的 realms 仅作补充。
    """
    p = Path(root) / "realms.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  realms.json 解析失败：{e}")
        return None


def merge_realms(batches, spec=None):
    out, seen = [], set()

    # 1) 权威定义优先
    if spec and spec.get("realms"):
        for r in spec["realms"]:
            key = norm(r.get("name", ""))
            if key and key not in seen:
                seen.add(key)
                out.append(dict(r))

    # 2) 批次补充 spec 里没有的境界（保持声明顺序，排在最后）
    extra = []
    for _, b in batches:
        for r in b.get("realms", []):
            key = norm(r.get("name", ""))
            if key and key not in seen:
                seen.add(key)
                extra.append(dict(r))

    if extra:
        print(f"  批次补充境界 {len(extra)} 个：{', '.join(r['name'] for r in extra)}")
        # 补充项按批次的 order 排序后接在权威序列之后
        extra.sort(key=lambda x: x.get("order", 99))
        out.extend(extra)

    # 3) order 重新编号为连续序列
    for i, r in enumerate(out, 1):
        r["order"] = i
    return out


def apply_power_history(ents, spec):
    """把 realms.json 里按原文核实的修为时间线注入实体。

    抽取产物的 attrs 里常有「修为: 长春功第八层」这类自由文本，
    但结构化时间线（第几章到第几层）跨批次不可靠，故由人工核实后覆盖。
    """
    if not spec or not spec.get("power_history"):
        return 0
    by_id = {e["id"]: e for e in ents}
    n = 0
    for eid, hist in spec["power_history"].items():
        e = by_id.get(eid)
        if not e:
            print(f"  警告：realms.json 指向不存在的实体 {eid}")
            continue
        e["power_history"] = sorted(hist, key=lambda x: x.get("ch", 0))
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.dir)
    batches = load_batches(root)
    print(f"读入 {len(batches)} 个批次")

    ents, id_map = merge_entities(batches)
    ents = normalize_groups(ents, [])
    rels = merge_relations(batches, id_map)
    chaps = merge_chapters(batches)
    fores = merge_foreshadows(batches, id_map)
    spec = load_realm_spec(root)
    realms = merge_realms(batches, spec)
    if spec:
        k = apply_power_history(ents, spec)
        print(f"  修为时间线注入 {k} 个实体（来自 realms.json）")

    # 丢掉指向不存在实体的关系
    alive = {e["id"] for e in ents}
    before = len(rels)
    rels = [r for r in rels if r["s"] in alive and r["t"] in alive]
    if before != len(rels):
        print(f"  清理断链关系 {before - len(rels)} 条")

    # 补 group：出现在关系里但没抽到的实体
    # meta 从 chunk-meta.json 取章节信息
    cm_path = root / "chunk-meta.json"
    cm = json.loads(cm_path.read_text(encoding="utf-8")) if cm_path.exists() else {}
    title = "未知书名"
    if cm.get("source"):
        title = re.sub(r"【[^】]*】", "", cm["source"]).split(".")[0].strip()

    total_chars = cm.get("total_chars") or sum(c.get("words", 0) for c in chaps)
    vols, seen_v = [], set()
    for r in cm.get("chapters", []):
        v = r.get("vol")
        if v and v not in seen_v:
            seen_v.add(v)
            vols.append({"id": f"v{v}", "name": r.get("vol_name") or f"第{v}卷",
                         "ch_start": r["ch"], "ch_end": None, "summary": ""})
    for i in range(len(vols) - 1):
        vols[i]["ch_end"] = vols[i + 1]["ch_start"] - 1
    if vols:
        vols[-1]["ch_end"] = max(c.get("ch", 0) for c in chaps) if chaps else None

    data = {
        "meta": {
            "schema_version": "2.0",
            "title": title,
            "author": "忘语" if "忘语" in (cm.get("source") or "") else "未知",
            "genre": "仙侠",
            "platform": "起点",
            "status": "完结",
            "source_file": cm.get("source", ""),
            "chars": total_chars,
            "chapters": cm.get("chapters_found") or len(chaps),
            "analyzed_at": "2026-11-27T05:30:00Z",
            "model": "manual-agent",
            "cost_cny": 0,
            "elapsed_sec": 0,
            "coverage": {"chapters_done": len(chaps),
                         "chapters_skipped": max((cm.get("chapters_found") or len(chaps)) - len(chaps), 0)},
            "note": f"分批抽取后合并；{len(ents)} 个实体经名称归并",
        },
        "volumes": vols,
        "realms": realms,
        "entities": ents,
        "relations": rels,
        "chapters": chaps,
        "foreshadows": fores,
        "knowledge": [],
        "places": [],
        "concepts": [],
    }

    out = Path(args.out) if args.out else root / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n实体    {sum(len(b.get('entities', [])) for _, b in batches)} → {len(ents)}（去重）")
    print(f"关系    {sum(len(b.get('relations', [])) for _, b in batches)} → {len(rels)}（去重）")
    print(f"章节    {len(chaps)}")
    print(f"伏笔    {sum(len(b.get('foreshadows', [])) for _, b in batches)} → {len(fores)}（去重）")
    print(f"境界    {len(realms)}")
    print(f"输出    {out}")


if __name__ == "__main__":
    main()
