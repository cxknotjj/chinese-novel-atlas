#!/usr/bin/env python3
"""merge.py — 把分批抽取的结果合并成一份 data.json。

难点在**实体消解**：同一个角色在不同批次里可能被起成不同的 id
（"韩立" → e_hanli / e_han_li / e_hanli2）。这里做两级归并：

1. 正名归并：归一化后同名（且类型相同）的实体直接合并
2. 别名归并：A 的别名等于 B 的正名时，把 A 并进 B
   （"韩老魔" 是 "韩立" 的别名，两个批次各建了一条，合并后只留一条）

通用的尊称（"师兄""长老""老祖"）不参与别名归并，否则会把半个宗门并成一个人。

用法：
    python scripts/merge.py output/凡人修仙传/ --out output/凡人修仙传/data.json
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# 这些别名指向的是"身份"而不是"某个人"，参与归并会误伤
GENERIC_ALIASES = {
    "师兄", "师姐", "师弟", "师妹", "师父", "师傅", "师叔", "师伯",
    "长老", "前辈", "道友", "老祖", "大人", "公子", "姑娘", "小姐",
    "掌门", "宗主", "陛下", "殿下", "阁下", "兄台", "老大",
}
# 序数称谓（二夫人、三娘、五小姐……）指向位份而非具体人，不能拿来归并；
# 颜色+衣着（蓝衣人、白衣少女、青衫老者……）只是当场的视觉描述，跨批次极易撞车
GENERIC_ALIAS_RE = re.compile(
    r"^[一二三四五六七八九十]+(夫人|太太|奶奶|娘|姨|小姐|公子|少爷|爷)$"
    r"|^(蓝|白|青|灰|黑|黄|绿|红)衣(人|青年|老者|少女|女子|汉子)$"
)
# 姓氏+氏（李氏、王氏）重名极多，不能只凭名字跨阵营合并
GENERIC_NAME_RE = re.compile(r"^[\u4e00-\u9fa5]{1,2}氏$")


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
    files = sorted(Path(d).glob("batch-*.json"))
    if not files:
        raise SystemExit(f"{d} 下没有 batch-*.json")
    batches = []
    for f in files:
        if f.name.endswith(".failed.json"):
            continue
        try:
            batches.append((f.name, json.loads(f.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as e:
            print(f"  ⚠ 跳过 {f.name}：JSON 解析失败（{e}）")
    if not batches:
        raise SystemExit(f"{d} 下没有可用的 batch-*.json")
    return batches


def _new_record(e):
    rec = dict(e)
    rec.setdefault("parent", None)
    rec.setdefault("attrs", {})
    rec.setdefault("power_history", [])
    rec.setdefault("aliases", [])
    rec["_groups"] = Counter([e.get("group") or "其他"])
    rec["_ids"] = {e.get("id")} - {None}
    return rec


def _absorb(cur, e):
    """把 e 的信息补进 cur（保留更全的那份）。"""
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
        if isinstance(p.get("ch"), int) and p not in cur.setdefault("power_history", []):
            cur["power_history"].append(p)
    if e.get("parent") and not cur.get("parent"):
        cur["parent"] = e["parent"]
    cur.setdefault("_groups", Counter())[e.get("group") or "其他"] += 1
    cur.setdefault("_ids", set()).update({e.get("id")} - {None})


def merge_entities(batches):
    """按 (正名, 类型) 归并，再按别名做第二级归并。返回 (entities, id_map)。"""
    pool, index = [], {}
    for _, b in batches:
        for e in b.get("entities", []):
            name = norm(e.get("name", ""))
            if not name:
                continue
            key = (name, e.get("type") or "character")
            if key in index:
                cur = pool[index[key]]
                if GENERIC_NAME_RE.match(name) and (e.get("group") or "") != (cur.get("group") or ""):
                    pool.append(_new_record(e))       # 同名的“李氏”分属两府，各留各的
                    index[key] = len(pool) - 1
                    continue
                _absorb(pool[index[key]], e)
            else:
                index[key] = len(pool)
                pool.append(_new_record(e))

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
    for an, owners in alias_owner.items():
        target = name_to_idx.get(an)
        if target is None:
            continue          # 这个别名不是任何实体的正名，无从归并
        if len(owners) > 1:
            continue          # 同一个别名挂在多个人身上，说明是通用称号，跳过
        if owners == {target}:
            continue
        union(next(iter(owners)), target)
        merged_alias += 1

    # ---- 按簇合并 ----
    clusters = {}
    for i in range(len(pool)):
        clusters.setdefault(find(i), []).append(i)

    out, id_map = [], {}
    for root, members in sorted(clusters.items(), key=lambda kv: min(kv[1])):
        members = sorted(members)
        head = pool[members[0]]          # 最早出现的那条当主记录
        for i in members[1:]:
            _absorb(head, pool[i])
        head["group"] = head["_groups"].most_common(1)[0][0]
        head["aliases"] = [a for a in dict.fromkeys(head.get("aliases", []))
                           if norm(a) != norm(head["name"])]
        head["power_history"] = sorted(
            [p for p in head.get("power_history", []) if isinstance(p.get("ch"), int)],
            key=lambda x: x["ch"])
        ids = set(head.pop("_ids", set()))
        head.pop("_groups", None)
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
        out.append(head)

    if merged_alias:
        print(f"  别名归并 {merged_alias} 组（同一实体在不同批次用了不同名字）")
    return out, id_map


def normalize_groups(ents):
    """修正 group：分批抽取时模型容易把"所属人物"当成"阵营"填。

    规则：
    1. group 等于某个角色名 → 说明误填了人名，改为该角色自己的 group 或"其他"
    2. "无"/"不明"/空 → "其他"
    3. 阵营数超过 8 个时，只保留成员数最多的 8 个，其余并入"其他"
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
            w = r.get("weight")
            w = 0.5 if not isinstance(w, (int, float)) else max(0.0, min(1.0, float(w)))
            rec = dict(r)
            rec["s"], rec["t"], rec["weight"] = s, t, w
            if key not in best or w > best[key]["weight"]:
                best[key] = rec
    return list(best.values())


def merge_chapters(batches, cm):
    """章节以 chunk-meta 为准补 words / volume；摘要等取模型结果。"""
    meta_ch = {}
    for r in cm.get("chapters", []):
        if isinstance(r.get("ch"), int):
            meta_ch[r["ch"]] = r

    by_ch = {}
    for _, b in batches:
        for c in b.get("chapters", []):
            ch = c.get("ch")
            if isinstance(ch, int) and ch not in by_ch:
                by_ch[ch] = c

    out = []
    for ch in sorted(by_ch):
        c = dict(by_ch[ch])
        m = meta_ch.get(ch)
        if m:
            c["words"] = m.get("words") or c.get("words", 0)
            if m.get("vol"):
                c["volume"] = f"v{m['vol']}"
        c.setdefault("words", 0)
        t = c.get("tension")
        c["tension"] = max(0.0, min(1.0, float(t))) if isinstance(t, (int, float)) else 0.0
        if c.get("hook_type") not in ("悬念", "反转", "冲突", "危机", "爽点", "无"):
            c["hook_type"] = "无"
        if c.get("emotion") not in ("爽", "压抑", "紧张", "温情", "悲", "平"):
            c["emotion"] = "平"
        c["summary"] = (c.get("summary") or "").strip()[:80]
        out.append(c)
    return out


def merge_foreshadows(batches, taken_ids=None):
    """按内容相似度归并同一条伏笔；id 保证全局唯一。"""
    pool = []
    for _, b in batches:
        for f in b.get("foreshadows", []):
            content = f.get("content", "")
            dup = None
            for ex in pool:
                score = sim(content, ex.get("content", ""))
                if score <= 0.62:
                    continue
                # 线索不同时先不合并，避免把两条并行的坑揉成一条；
                # 但文字几乎一模一样（>=0.92）时，线索标签不同也视为同一条
                if (score < 0.92 and f.get("thread") and ex.get("thread")
                        and norm(f["thread"]) != norm(ex["thread"])):
                    continue
                dup = ex
                break
            if dup:
                if len(f.get("note") or "") > len(dup.get("note") or ""):
                    dup["note"] = f["note"]
                if f.get("payoff_ch") and not dup.get("payoff_ch"):
                    dup["payoff_ch"] = f["payoff_ch"]
                    dup["payoff_quote"] = f.get("payoff_quote")
                dup["importance"] = max(dup.get("importance") or 0.5,
                                        f.get("importance") or 0.5)
            else:
                pool.append(dict(f))

    taken = set(taken_ids or ())
    out = []
    for i, f in enumerate(pool, 1):
        base = f.get("id") or f"f_{i:03d}"
        final, n = base, 2
        while final in taken:
            final = f"{base}_{n}"
            n += 1
        taken.add(final)
        f["id"] = final
        out.append(f)
    return out


def attach_mentions(root, fores):
    """把 mentions.json 的提及轨迹并入伏笔（若已跑过 mentions.py）。

    有它之后，超期判定从「埋了多少章」升级为「多久没被提及」：
    第 7 章埋、第 196 章还在提的主线伏笔不会被误报，而埋下就再没管的才会。
    """
    p = Path(root) / "mentions.json"
    if not p.exists():
        return 0
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ mentions.json 解析失败：{e}")
        return 0
    n = 0
    for f in fores:
        rec = m.get(f.get("id"))
        if not rec:
            continue
        f["last_mention_ch"] = rec.get("last_mention_ch")
        f["keywords"] = rec.get("keywords") or []
        n += 1
    return n


def apply_status(data):
    """按 schema 的派生规则重算 foreshadow.status（存储值不可信）。

    阈值按**已分析到的章数**算，而不是全书总章数：只拆了前 200 章时，
    用 2443 章的 15%（366 章）做阈值会让所有坑永远不超期。

    判定优先看 silent（距最后一次提及过了多久），没有提及数据时退回 span：
    「埋了很久但一直在提」的伏笔不算超期，那是有意经营的长线。
    """
    meta = data["meta"]
    live = max((c["ch"] for c in data["chapters"]), default=0)
    total = meta.get("chapters") or live
    span = live if live else total
    thr = max(50, int(span * 0.15))
    changed = 0
    for f in data["foreshadows"]:
        if f.get("status") == "dropped":
            continue                      # 唯一允许人工标注的状态
        payoff = f.get("payoff_ch")
        if payoff is not None and payoff < (f.get("plant_ch") or 0):
            f["payoff_ch"] = None         # 回收早于埋设，按未回收处理
            payoff = None
        if payoff:
            expect = "paid"
        else:
            last = f.get("last_mention_ch") or f.get("plant_ch") or 0
            expect = "overdue" if live - last > thr else "planted"
        if f.get("status") != expect:
            f["status"] = expect
            changed += 1
    return thr, changed


def load_realms(root, batches):
    """境界体系以全文扫描出的 realms.json 为权威；没有就退回批次并集。"""
    spec = root / "realms.json"
    if spec.exists():
        raw = json.loads(spec.read_text(encoding="utf-8"))
        realms = raw["realms"] if isinstance(raw, dict) else raw
        orders = [r.get("order") for r in realms]
        if orders != list(range(1, len(realms) + 1)):
            raise SystemExit(f"{spec} 的 order 必须从 1 连续递增，当前 {orders}")
        # 用批次里的信息补 first_ch / desc
        seen = {norm(r.get("name", "")): r for r in realms}
        for _, b in batches:
            for r in b.get("realms", []):
                t = seen.get(norm(r.get("name", "")))
                if t is None:
                    continue
                if not t.get("first_ch") and r.get("first_ch"):
                    t["first_ch"] = r["first_ch"]
                if not t.get("desc") and r.get("desc"):
                    t["desc"] = r["desc"]
        print(f"  境界体系 {len(realms)} 级（来自 realms.json）")
        ph = raw.get("power_history") if isinstance(raw, dict) else {}
        return realms, (ph or {})

    # 没有权威文件：批次各自编号，冲突必然发生
    seen, collected = set(), []
    for _, b in batches:
        for r in b.get("realms", []):
            key = norm(r.get("name", ""))
            if key and key not in seen:
                seen.add(key)
                collected.append(dict(r))
    if len(collected) < 2:
        if collected:
            print("  ⚠ 只抽到 1 个境界，无法构成有序体系，realms 留空。"
                  "请先跑 scripts/realms.py 生成 realms.json")
        return [], {}
    orders = sorted({r.get("order") for r in collected})
    if len(orders) != len(collected):
        print("  ⚠ 批次间 order 冲突，realms 留空。请先跑 scripts/realms.py 确认体系")
        return [], {}
    collected.sort(key=lambda x: x.get("order", 99))
    return collected, {}


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


def build_volumes(cm, chapters):
    """只从**已分析章节**归卷，避免只拆前 100 章时把第 3 卷写成 101..100。"""
    names = {}
    for r in cm.get("chapters", []):
        v = r.get("vol")
        if v:
            names.setdefault(v, r.get("vol_name") or f"第{v}卷")

    groups = {}
    for c in chapters:
        v = c.get("volume")
        if not v:
            continue
        num = v[1:] if str(v).startswith("v") else str(v)
        groups.setdefault(num, []).append(c["ch"])

    vols = []
    for num in sorted(groups, key=lambda x: int(x) if str(x).isdigit() else 999):
        chs = groups[num]
        label = names.get(int(num)) if str(num).isdigit() else None
        label = label or names.get(num) or f"第{num}卷"
        vols.append({"id": f"v{num}", "name": label,
                     "ch_start": min(chs), "ch_end": max(chs), "summary": ""})

    if not vols:                      # 章节没标卷时退回 chunk-meta，但仍以已分析章号为界
        live = max((c["ch"] for c in chapters), default=0)
        for r in cm.get("chapters", []):
            v = r.get("vol")
            if not v or r["ch"] > live:
                continue
            if vols and vols[-1]["id"] == f"v{v}":
                vols[-1]["ch_end"] = max(vols[-1]["ch_end"], r["ch"])
            elif not vols or vols[-1]["id"] != f"v{v}":
                if all(x["id"] != f"v{v}" for x in vols):
                    vols.append({"id": f"v{v}", "name": r.get("vol_name") or f"第{v}卷",
                                 "ch_start": r["ch"], "ch_end": r["ch"], "summary": ""})
    return vols


def parse_source_name(source):
    """《凡人修仙传》【精校全本】作者：忘语.txt → (书名, 作者)"""
    stem = Path(source).stem
    stem = re.sub(r"【[^】]*】", "", stem).strip()
    author = ""
    m = re.search(r"作者[：:]\s*(.*)$", stem)
    if m:
        author = m.group(1).strip()
        stem = stem[:m.start()].strip()
    title = stem.strip("《》 ").strip()
    return title or "未知书名", author


def find_source_file(root, name):
    """在 book 目录的上级 / novals/ 里找原始 txt，用于统计全书字数。"""
    if not name:
        return None
    cands = [
        root.parent / name,
        root.parent / "novals" / name,
        root.parent.parent / "novals" / name,
        Path.cwd() / "novals" / name,
        Path.cwd() / name,
    ]
    for p in cands:
        if p.is_file():
            return p
    return None


def count_chars(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "utf-16"):
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        sample = text[:8000]
        if sample and sum(1 for c in sample if "\u4e00" <= c <= "\u9fff") / len(sample) > 0.15:
            return len(re.sub(r"\s", "", text))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", default="")
    ap.add_argument("--batches", default="", help="批次目录，默认 <dir>/out")
    ap.add_argument("--title", default="", help="覆盖书名（默认从源文件名解析）")
    ap.add_argument("--author", default="", help="覆盖作者")
    ap.add_argument("--genre", default="未标注")
    ap.add_argument("--platform", default="")
    ap.add_argument("--status", default="完结")
    ap.add_argument("--model", default="manual-agent")
    ap.add_argument("--cost", type=float, default=0.0, help="抽取花费（元），写入 meta.cost_cny")
    ap.add_argument("--elapsed", type=int, default=0, help="抽取耗时（秒），写入 meta.elapsed_sec")
    args = ap.parse_args()

    root = Path(args.dir)
    if args.batches:
        bd = Path(args.batches)
        batch_dir = bd if bd.is_absolute() else root / bd
    else:
        batch_dir = root / "out"
    batches = load_batches(batch_dir)
    print(f"读入 {len(batches)} 个批次（{batch_dir}）")

    cm_path = root / "chunk-meta.json"
    cm = json.loads(cm_path.read_text(encoding="utf-8")) if cm_path.exists() else {}

    ents, id_map = merge_entities(batches)
    ents = normalize_groups(ents)
    rels = merge_relations(batches, id_map)
    chaps = merge_chapters(batches, cm)
    fores = merge_foreshadows(batches, taken_ids={e["id"] for e in ents})
    places = merge_places(batches, taken_ids={e["id"] for e in ents} | {f["id"] for f in fores},
                          entity_names={e["id"]: e["name"] for e in ents})
    concepts = merge_concepts(
        batches,
        taken_ids={e["id"] for e in ents} | {f["id"] for f in fores} | {p["id"] for p in places})
    ents, pruned = prune_concept_duplicates(ents, rels, concepts)
    if pruned:
        print(f"  清理与设定重复的器物 {pruned} 个")
    realms, realm_ph = load_realms(root, batches)

    # realms.json 里的战力时间线是人工核过原文的，优先于批次模型结果
    if realm_ph:
        by_id = {e["id"]: e for e in ents}
        applied = 0
        for old_id, timeline in realm_ph.items():
            target = by_id.get(id_map.get(old_id, old_id)) or by_id.get(old_id)
            if not target:
                print(f"  ⚠ realms.json 里的 {old_id} 在实体表中不存在，跳过")
                continue
            order = {r["id"]: r.get("order", 99) for r in realms}
            stages = {r["id"]: set(r.get("stages") or []) for r in realms}
            clean = []
            for p in timeline:
                if p.get("realm") not in order:
                    print(f"  ⚠ {target['name']}: 境界 {p.get('realm')} 不在体系中，跳过")
                    continue
                if p.get("stage") and stages[p["realm"]] and p["stage"] not in stages[p["realm"]]:
                    print(f"  ⚠ {target['name']}: 小阶段 {p['stage']} 不属于 {p['realm']}，跳过")
                    continue
                clean.append({k: v for k, v in p.items() if k in ("ch", "realm", "stage", "note")})
            target["power_history"] = sorted(clean, key=lambda x: x["ch"])
            applied += 1
        print(f"  战力时间线 {applied} 人（来自 realms.json）")

    # 丢掉指向不存在实体的关系
    alive = {e["id"] for e in ents}
    before = len(rels)
    rels = [r for r in rels if r["s"] in alive and r["t"] in alive]
    if before != len(rels):
        print(f"  清理断链关系 {before - len(rels)} 条")

    # 引用不到实体的 id 从章节里剔除，否则校验器直接报错
    fs_ids = {f["id"] for f in fores}
    for c in chaps:
        c["new_entities"] = [x for x in (c.get("new_entities") or []) if x in alive]
        c["new_foreshadows"] = [x for x in (c.get("new_foreshadows") or []) if x in fs_ids]

    # 势力树断链：parent 指向不存在实体时清空
    for e in ents:
        if e.get("parent") and e["parent"] not in alive:
            e["parent"] = None

    # parent 成环检测：成环的直接断开
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

    title, author = parse_source_name(cm.get("source", ""))
    title = args.title or title
    author = args.author or author or "未知"
    source_file = cm.get("source", "")
    src_path = find_source_file(root, source_file)
    book_chars = count_chars(src_path) if src_path else None

    total_chapters = cm.get("chapters_found") or len(chaps)
    data = {
        "meta": {
            "schema_version": "2.0",
            "title": title,
            "author": author,
            "genre": args.genre,
            "platform": args.platform,
            "status": args.status,
            "source_file": source_file,
            "chars": book_chars if book_chars else cm.get("total_chars", 0),
            "chapters": total_chapters,
            "analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": args.model,
            "cost_cny": args.cost,
            "elapsed_sec": args.elapsed,
            "coverage": {"chapters_done": len(chaps),
                         "chapters_skipped": max(total_chapters - len(chaps), 0)},
            "note": (f"分批抽取后合并；{len(ents)} 个实体经名称/别名归并"
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
    }

    n_m = attach_mentions(root, fores)
    if n_m:
        print(f"  提及轨迹 {n_m} 条（来自 mentions.json）")

    thr, changed = apply_status(data)

    out = Path(args.out) if args.out else root / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n实体    {sum(len(b.get('entities', [])) for _, b in batches)} → {len(ents)}（去重）")
    print(f"关系    {sum(len(b.get('relations', [])) for _, b in batches)} → {len(rels)}（去重）")
    print(f"章节    {len(chaps)} / {total_chapters}（覆盖 {len(chaps) / max(total_chapters, 1):.1%}）")
    print(f"伏笔    {sum(len(b.get('foreshadows', [])) for _, b in batches)} → {len(fores)}（去重），"
          f"超期阈值 {thr} 章")
    print(f"境界    {len(realms)}")
    print(f"地点    {len(places)}　设定 {len(concepts)}")
    print(f"字数    {data['meta']['chars']:,}")
    print(f"输出    {out}")


if __name__ == "__main__":
    main()
