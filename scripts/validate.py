#!/usr/bin/env python3
"""validate.py — 按 references/schema.md 的规则校验 data.json。

schema 是契约，这个脚本是契约的执行者。校验不通过时**不要手改数据蒙混过去**，
先判断是抽取错了还是契约该改。

用法：
    python scripts/validate.py output/青云签到三十年/data.json
    python scripts/validate.py output/青云签到三十年/          # 自动找 data.json
    python scripts/validate.py data.json --strict             # 警告也算失败

退出码：0 通过（可能有警告） / 1 有错误
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from novel_atlas.foreshadow_rules import expected_status, threshold

RELATION_TYPES = {"kinship", "marriage", "romance", "service",
                  "mentorship", "alliance", "conflict", "social"}
ENTITY_TYPES = {"character", "org", "item", "creature"}
HOOK_TYPES = {"悬念", "反转", "冲突", "危机", "爽点", "无"}
EMOTIONS = {"爽", "压抑", "紧张", "温情", "悲", "平"}
FORESHADOW_STATUS = {"planted", "paid", "overdue", "dropped"}
CONCEPT_KINDS = {"worldview", "golden_finger", "technique",
                 "item_grade", "organization_rule", "prophecy"}

# 空间关系（spatial_relations，可选；契约见 output/<书名>/_contract/spatial-contract.md）
SPATIAL_KINDS = {"direction", "distance", "contain", "adjacent",
                 "portal", "travel_path", "road", "river",
                 "separated_by", "in_between"}
DIRECTION_VALUES = {"north_of", "south_of", "east_of", "west_of",
                    "northeast_of", "northwest_of", "southeast_of",
                    "southwest_of"}
SPATIAL_CONFIDENCE = {"high", "medium", "low"}

ID_PREFIX = {"entities": "e_", "places": "p_", "concepts": "c_",
             "realms": "r_", "foreshadows": "f_", "knowledge": "k_",
             "volumes": "v"}


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, rule, msg):
        self.errors.append((rule, msg))

    def warn(self, rule, msg):
        self.warnings.append((rule, msg))


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate(data, report):
    # ---------- 结构 ----------
    for key in ("meta", "volumes", "realms", "entities", "relations",
                "chapters", "foreshadows", "knowledge", "places", "concepts"):
        if key not in data:
            report.err("结构", f"缺少顶层字段 {key}")
    for key in ("meta", "volumes", "realms", "entities", "relations",
                "chapters", "foreshadows", "knowledge", "places", "concepts"):
        if key in data and not isinstance(data[key], (dict, list)):
            report.err("结构", f"{key} 类型错误")

    meta = data.get("meta") or {}
    for key in ("schema_version", "title", "author", "genre", "chars",
                "chapters", "analyzed_at", "model", "coverage"):
        if key not in meta:
            report.err("meta", f"缺少必填字段 meta.{key}")
    if meta.get("schema_version") != "2.0":
        report.err("meta", f"schema_version 应为 2.0，当前 {meta.get('schema_version')}")
    if not num(meta.get("chars")) or meta.get("chars", 0) <= 0:
        report.err("meta", f"chars 应为正数，当前 {meta.get('chars')}")
    if not isinstance(meta.get("chapters"), int) or meta.get("chapters", 0) <= 0:
        report.err("meta", f"chapters 应为正整数，当前 {meta.get('chapters')}")
    cov = meta.get("coverage")
    if not isinstance(cov, dict) or "chapters_done" not in cov or "chapters_skipped" not in cov:
        report.err("规则10", "coverage 必须包含 chapters_done / chapters_skipped")
    elif isinstance(meta.get("chapters"), int):
        if cov["chapters_done"] + cov["chapters_skipped"] != meta["chapters"]:
            report.err("规则10",
                       f"coverage 加和 {cov['chapters_done']}+{cov['chapters_skipped']}"
                       f" != chapters {meta['chapters']}")

    # ---------- id 全局唯一 ----------
    ids = {}
    for coll, prefix in ID_PREFIX.items():
        for item in data.get(coll) or []:
            i = item.get("id")
            if not i:
                report.err("规则2", f"{coll} 里有条目缺少 id：{str(item)[:60]}")
                continue
            if i in ids:
                report.err("规则2", f"id 重复：{i}（{ids[i]} 与 {coll}）")
            else:
                ids[i] = coll
            if not str(i).startswith(prefix):
                report.warn("命名", f"{coll} 的 id {i} 未使用 {prefix} 前缀")

    ent = {e.get("id"): e for e in data.get("entities") or []}
    place = {p.get("id"): p for p in data.get("places") or []}
    realm = {r.get("id"): r for r in data.get("realms") or []}
    fs = {f.get("id"): f for f in data.get("foreshadows") or []}

    # ---------- 规则1 引用 ----------
    for r in data.get("relations") or []:
        if r.get("s") not in ent:
            report.err("规则1", f"关系起点不存在：{r.get('s')}")
        if r.get("t") not in ent:
            report.err("规则1", f"关系终点不存在：{r.get('t')}")
        if r.get("s") in ent and r.get("t") in ent and r.get("s") == r.get("t"):
            report.err("规则1", f"自环关系：{r.get('s')}")
    for c in data.get("chapters") or []:
        for eid in c.get("new_entities") or []:
            if eid not in ent:
                report.err("规则1", f"ch{c.get('ch')} 的 new_entities 引用不存在：{eid}")
        for fid in c.get("new_foreshadows") or []:
            if fid not in fs:
                report.err("规则1", f"ch{c.get('ch')} 的 new_foreshadows 引用不存在：{fid}")
        for bi, b in enumerate(c.get("battles") or []):
            if not isinstance(b, dict):
                report.err("规则1", f"ch{c.get('ch')} battles[{bi}] 不是对象")
                continue
            # 旧批次写成了 s/t，契约要求 a/b；这里显式拒绝，避免静默漏掉
            if "s" in b or "t" in b:
                report.err("规则1", f"ch{c.get('ch')} battles[{bi}] 使用了旧字段 s/t，应为 a/b")
            for side in ("a", "b"):
                if b.get(side) not in ent:
                    report.err("规则1",
                               f"ch{c.get('ch')} battles[{bi}] 的 {side}={b.get(side)} 不是已有实体")
            if b.get("a") and b.get("a") == b.get("b"):
                report.err("规则1", f"ch{c.get('ch')} battles[{bi}] 双方相同：{b.get('a')}")
            if b.get("gap") is not None and not num(b.get("gap")):
                report.err("规则1", f"ch{c.get('ch')} battles[{bi}] gap 不是数字")
    for p in data.get("places") or []:
        if p.get("parent") and p["parent"] not in place:
            report.err("规则1", f"地点 {p.get('id')} 的 parent 不存在：{p['parent']}")
    for e in data.get("entities") or []:
        if e.get("parent") and e["parent"] not in ent:
            report.err("规则1", f"实体 {e.get('id')} 的 parent 不存在：{e['parent']}")

    # ---------- 规则3 关系枚举 ----------
    for r in data.get("relations") or []:
        if r.get("type") not in RELATION_TYPES:
            report.err("规则3", f"关系类型越界：{r.get('type')}（{r.get('s')}→{r.get('t')}）")

    # ---------- 规则4 0-1 区间 ----------
    for r in data.get("relations") or []:
        if not num(r.get("weight")) or not 0 <= r["weight"] <= 1:
            report.err("规则4", f"weight 应在 0-1：{r.get('weight')}（{r.get('s')}→{r.get('t')}）")
    for c in data.get("chapters") or []:
        if not num(c.get("tension")) or not 0 <= c["tension"] <= 1:
            report.err("规则4", f"ch{c.get('ch')} tension 应在 0-1：{c.get('tension')}")
    for f in data.get("foreshadows") or []:
        if not num(f.get("importance")) or not 0 <= f["importance"] <= 1:
            report.err("规则4", f"伏笔 {f.get('id')} importance 应在 0-1：{f.get('importance')}")

    # ---------- 规则5 境界序数 ----------
    orders = [r.get("order") for r in data.get("realms") or []]
    if orders:
        if orders != list(range(1, len(orders) + 1)):
            report.err("规则5", f"realms.order 应从 1 连续递增，当前 {orders}")
        if len(set(orders)) != len(orders):
            report.err("规则5", "realms.order 有重复")

    # ---------- 规则6 战力时间线 ----------
    stages = {rid: set(r.get("stages") or []) for rid, r in realm.items()}
    for e in data.get("entities") or []:
        ph = e.get("power_history") or []
        for i, p in enumerate(ph):
            if not isinstance(p.get("ch"), int):
                report.err("规则6", f"{e.get('name')} power_history 缺少章号：{p}")
                continue
            if p.get("realm") not in realm:
                report.err("规则6", f"{e.get('name')} 的境界 {p.get('realm')} 不在体系中")
            elif p.get("stage") and stages[p["realm"]] and p["stage"] not in stages[p["realm"]]:
                report.err("规则6",
                           f"{e.get('name')} 的小阶段 {p['stage']} 不属于 {p['realm']}")
            if i and isinstance(ph[i - 1].get("ch"), int) and p["ch"] <= ph[i - 1]["ch"]:
                report.err("规则6", f"{e.get('name')} power_history 章号未严格递增（ch{p['ch']}）")
            if i and p.get("realm") in realm and ph[i - 1].get("realm") in realm:
                if realm[p["realm"]]["order"] < realm[ph[i - 1]["realm"]]["order"]:
                    report.warn("跌境", f"{e.get('name')} 在 ch{p['ch']} 由 "
                                        f"{ph[i - 1]['realm']} 降到 {p['realm']}")

    # ---------- 规则7 parent 成环 ----------
    for coll, mapping in (("地点", place), ("实体", ent)):
        for i in mapping:
            seen = set()
            cur = i
            while cur and cur in mapping:
                if cur in seen:
                    report.err("规则7", f"{coll} parent 链成环：{i}")
                    break
                seen.add(cur)
                cur = mapping[cur].get("parent")

    # ---------- 规则8 / 10 章节覆盖 ----------
    chs = [c.get("ch") for c in data.get("chapters") or []]
    if len(set(chs)) != len(chs):
        dup = [k for k, v in Counter(chs).items() if v > 1]
        report.err("规则8", f"章节号重复：{dup[:10]}")
    done = (meta.get("coverage") or {}).get("chapters_done")
    if isinstance(done, int) and isinstance(meta.get("chapters"), int):
        if len(chs) > done:
            report.err("规则8", f"chapters 里有 {len(chs)} 条，但 chapters_done={done}")
        elif len(chs) < done:
            # 样例允许"只存关键章"，但节奏指标就不能当全量用
            report.warn("规则8", f"章节摘要非全量：{len(chs)}/{done}，"
                                 "节奏指标需标注「不完整」")
        if chs and max(chs) > meta["chapters"]:
            report.err("规则8", f"章号 {max(chs)} 超出总章数 {meta['chapters']}")
        if [c for c in chs if c < 1]:
            report.err("规则8", "存在小于 1 的章号")
        if len(chs) == done and chs:
            gaps = sorted(set(range(1, max(chs) + 1)) - set(chs))
            if gaps:
                report.warn("规则8", f"章节序列有 {len(gaps)} 处断档"
                                     f"（如 {gaps[:5]}）")

    # ---------- 规则9 伏笔回收章 ----------
    for f in data.get("foreshadows") or []:
        if f.get("payoff_ch") is not None and f.get("plant_ch") is not None:
            if f["payoff_ch"] < f["plant_ch"]:
                report.err("规则9", f"伏笔 {f.get('id')} 回收章 {f['payoff_ch']} "
                                    f"早于埋设章 {f['plant_ch']}")

    # ---------- status 派生一致性 ----------
    live = max(chs) if chs else 0
    total = meta.get("chapters") or live
    thr = threshold(live, total)
    for f in data.get("foreshadows") or []:
        if f.get("status") == "dropped":
            continue
        # 超期看「沉默时长」（距最后一次提及），没有提及数据时退回埋设章。
        # 阈值与派生规则统一来自 novel_atlas.foreshadow_rules，viewer.js 同步。
        expect = expected_status(f, live, thr)
        if f.get("status") != expect:
            report.err("status", f"伏笔 {f.get('id')} status={f.get('status')}，"
                                 f"按派生规则应为 {expect}（阈值 {thr} 章）")

    # ---------- 枚举 / 长度 / 字段形态 ----------
    for e in data.get("entities") or []:
        if e.get("type") not in ENTITY_TYPES:
            report.err("枚举", f"实体 {e.get('id')} type 越界：{e.get('type')}")
        if not e.get("group"):
            report.warn("字段", f"实体 {e.get('name')} 缺少 group")
        if len(e.get("desc") or "") > 100:
            report.warn("长度", f"实体 {e.get('name')} 简介超过 100 字")
    for c in data.get("chapters") or []:
        if c.get("hook_type") not in HOOK_TYPES:
            report.err("枚举", f"ch{c.get('ch')} hook_type 越界：{c.get('hook_type')}")
        if c.get("emotion") not in EMOTIONS:
            report.err("枚举", f"ch{c.get('ch')} emotion 越界：{c.get('emotion')}")
        if len(c.get("summary") or "") > 80:
            report.warn("长度", f"ch{c.get('ch')} 摘要超过 80 字")
        if len(c.get("hook") or "") > 30:
            report.warn("长度", f"ch{c.get('ch')} 章末钩子超过 30 字")
    for f in data.get("foreshadows") or []:
        if f.get("status") not in FORESHADOW_STATUS:
            report.err("枚举", f"伏笔 {f.get('id')} status 越界：{f.get('status')}")
        if len(f.get("content") or "") > 50:
            report.warn("长度", f"伏笔 {f.get('id')} content 超过 50 字")
    for c in data.get("concepts") or []:
        if c.get("kind") not in CONCEPT_KINDS:
            report.err("枚举", f"设定 {c.get('id')} kind 越界：{c.get('kind')}")

    # ---------- 空间关系（spatial_relations，可选） ----------
    # 缺失或空 list 不算错误：M2 回退 M1 是视图行为，不是数据问题。
    spatial = data.get("spatial_relations")
    if spatial is not None and not isinstance(spatial, list):
        report.err("空间", "spatial_relations 必须是 list")
        spatial = None
    if spatial:
        chapters_total = meta.get("chapters")

        def in_ch_range(x):
            return (isinstance(x, int) and not isinstance(x, bool)
                    and isinstance(chapters_total, int)
                    and 1 <= x <= chapters_total)

        def root_of(pid):
            # 沿 parent 上溯到根地点；parent 指向不存在地点时停在悬空处，不崩。
            seen = set()
            cur = pid
            while cur and cur in place:
                if cur in seen:
                    return cur
                seen.add(cur)
                cur = place[cur].get("parent")
            return cur

        sr_seen = set()
        layer_constraints = Counter()
        for i, rel in enumerate(spatial):
            tag = f"spatial_relations[{i}]"
            if not isinstance(rel, dict):
                report.err("空间", f"{tag} 条目必须是对象")
                continue
            rid = rel.get("id")
            if not rid:
                report.err("空间", f"{tag} 缺少 id")
            else:
                if not str(rid).startswith("sr_"):
                    report.err("空间", f"空间关系 id {rid} 未使用 sr_ 前缀")
                if rid in sr_seen:
                    report.err("空间", f"空间关系 id 重复：{rid}")
                elif rid in ids:
                    report.err("空间", f"空间关系 id {rid} 与既有条目 {ids[rid]} 重复")
                sr_seen.add(rid)

            s, t = rel.get("s"), rel.get("t")
            if s not in place:
                report.err("空间", f"空间关系 {rid or tag} 起点不存在：{s}")
            if t not in place:
                report.err("空间", f"空间关系 {rid or tag} 终点不存在：{t}")
            if s in place and t in place and s == t:
                report.err("空间", f"空间关系 {rid or tag} 自环：{s}")

            kind = rel.get("kind")
            if kind not in SPATIAL_KINDS:
                report.err("空间", f"空间关系 {rid or tag} kind 越界：{kind}")
            if kind == "direction" and rel.get("value") not in DIRECTION_VALUES:
                report.err("空间", f"空间关系 {rid or tag} direction value 越界：{rel.get('value')}")
            if rel.get("confidence") not in SPATIAL_CONFIDENCE:
                report.err("空间", f"空间关系 {rid or tag} confidence 越界：{rel.get('confidence')}")

            fc = rel.get("first_ch")
            if not in_ch_range(fc):
                report.err("空间", f"空间关系 {rid or tag} first_ch 越界：{fc}")

            ev = rel.get("evidence")
            if not isinstance(ev, dict):
                report.err("空间", f"空间关系 {rid or tag} evidence 必须是对象")
                ev = {}
            ech = ev.get("ch")
            if not in_ch_range(ech):
                report.err("空间", f"空间关系 {rid or tag} evidence.ch 越界：{ech}")
            quote = ev.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                report.err("空间", f"空间关系 {rid or tag} evidence.quote 为空")
            else:
                if len(quote) > 120:
                    report.err("空间", f"空间关系 {rid or tag} evidence.quote 超过 120 字")
                if "\n" in quote or "\r" in quote:
                    report.err("空间", f"空间关系 {rid or tag} evidence.quote 含换行")
            if in_ch_range(ech) and isinstance(fc, int) and ech != fc:
                report.warn("空间", f"证据章 {ech} 与 first_ch {fc} 不一致")

            value = rel.get("value")
            if not isinstance(value, str) or not value.strip():
                report.err("空间", f"空间关系 {rid or tag} value 为空")
            elif len(value) > 40:
                report.err("空间", f"空间关系 {rid or tag} value 超过 40 字")

            # 层统计只数 direction / distance 约束；两端都悬空时无法归层，跳过。
            if kind in ("direction", "distance"):
                anchor = s if s in place else (t if t in place else None)
                if anchor is not None:
                    layer_constraints[root_of(anchor)] += 1

        for layer, n in layer_constraints.items():
            if 1 <= n <= 2:
                report.warn("空间", f"该层仅 {n} 条方向/距离约束，M2 会回退")

    # ---------- 卷 ----------
    vols = data.get("volumes") or []
    for v in vols:
        a, b = v.get("ch_start"), v.get("ch_end")
        if isinstance(a, int) and isinstance(b, int) and b < a:
            report.err("卷", f"卷 {v.get('id')} 的 ch_end < ch_start")
    for i in range(len(vols) - 1):
        if isinstance(vols[i].get("ch_end"), int) and isinstance(vols[i + 1].get("ch_start"), int):
            if vols[i]["ch_end"] >= vols[i + 1]["ch_start"]:
                report.err("卷", f"卷 {vols[i].get('id')} 与下一卷章号重叠")
    for c in data.get("chapters") or []:
        if c.get("volume") and c["volume"] not in {v.get("id") for v in vols}:
            report.warn("卷", f"ch{c.get('ch')} 的 volume {c['volume']} 不在 volumes 中")
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="data.json 或书目录")
    ap.add_argument("--strict", action="store_true", help="警告也按失败处理")
    args = ap.parse_args()

    p = Path(args.path)
    if p.is_dir():
        p = p / "data.json"
    if not p.exists():
        raise SystemExit(f"找不到 {p}")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{p} 不是合法 JSON：{e}")

    rep = Report()
    validate(data, rep)

    e_cnt = Counter(r for r, _ in rep.errors)
    w_cnt = Counter(r for r, _ in rep.warnings)

    print(f"校验 {p}")
    print(f"  实体 {len(data.get('entities') or [])} · 关系 {len(data.get('relations') or [])}"
          f" · 章节 {len(data.get('chapters') or [])} · 伏笔 {len(data.get('foreshadows') or [])}"
          f" · 境界 {len(data.get('realms') or [])}")

    for rule, msg in rep.errors:
        print(f"  ✗ [{rule}] {msg}")
    if rep.warnings:
        shown = rep.warnings[:20]
        for rule, msg in shown:
            print(f"  ! [{rule}] {msg}")
        if len(rep.warnings) > len(shown):
            print(f"  ! …另有 {len(rep.warnings) - len(shown)} 条警告")

    print()
    if rep.errors:
        print(f"结果：不通过 · 错误 {len(rep.errors)}（{dict(e_cnt)}）"
              f" · 警告 {len(rep.warnings)}（{dict(w_cnt)}）")
        return 1
    if args.strict and rep.warnings:
        print(f"结果：严格模式不通过 · 警告 {len(rep.warnings)}（{dict(w_cnt)}）")
        return 1
    print(f"结果：通过 · 警告 {len(rep.warnings)}（{dict(w_cnt)}）" if rep.warnings else "结果：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
