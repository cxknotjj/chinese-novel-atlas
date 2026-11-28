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

# 2D 示意布局（map_layout，可选；契约见 output/<书名>/_contract/maplayout-contract.md）
MAP_MODE = "schematic"
MAP_SHAPES = {"land", "sea", "void"}
TERRAIN_KEYS = {"ridges", "rivers", "lakes", "islets"}
ROUTE_KINDS = {"portal", "travel_path", "road", "river"}
MARKER_TYPES = {"city", "sect", "secret", "danger", "place", "none"}

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

    # ---------- 2D 示意布局（map_layout，可选） ----------
    # 缺失时不报错：2D 视图回退拓扑是视图行为，不是数据问题。
    layout = data.get("map_layout")
    if layout is not None:
        if not isinstance(layout, dict):
            report.err("地图", "map_layout 必须是对象")
        else:
            def in_canvas(v):
                return num(v) and 0 <= v <= 100

            def check_point(pt, where):
                if (not isinstance(pt, list) or len(pt) != 2
                        or not in_canvas(pt[0]) or not in_canvas(pt[1])):
                    report.err("地图", f"{where} 坐标越界或格式错误：{pt}")
                    return False
                return True

            def check_points(pts, where, min_pts, max_pts=None):
                if not isinstance(pts, list):
                    report.err("地图", f"{where} 必须是坐标数组")
                    return False
                too_few = len(pts) < min_pts
                too_many = max_pts is not None and len(pts) > max_pts
                if too_few or too_many:
                    span = f"{min_pts}–{max_pts}" if max_pts else f"{min_pts} 以上"
                    report.err("地图", f"{where} 点数应为 {span}，当前 {len(pts)}")
                    return False
                ok = True
                for j, pt in enumerate(pts):
                    if not check_point(pt, f"{where}[{j}]"):
                        ok = False
                return ok

            if layout.get("mode") != MAP_MODE:
                report.err("地图",
                           f"map_layout.mode 必须为 schematic，当前 {layout.get('mode')}")

            note = layout.get("note")
            if not isinstance(note, str) or not note.strip():
                report.err("地图", "map_layout.note 为空")
            else:
                if len(note) > 120:
                    report.err("地图", "map_layout.note 超过 120 字")
                if "示意" not in note and "非经纬度" not in note:
                    report.warn("地图", "note 未含「示意」或「非经纬度」，"
                                       "可能把示意坐标说成精确坐标")

            canvas = layout.get("canvas")
            if (not isinstance(canvas, list) or len(canvas) != 2
                    or not num(canvas[0]) or canvas[0] != 100
                    or not num(canvas[1]) or canvas[1] != 100):
                report.err("地图", f"canvas 必须为 [100,100]，当前 {canvas}")

            regions = layout.get("regions")
            if regions is None:
                regions = []
            elif not isinstance(regions, list):
                report.err("地图", "regions 必须是 list")
                regions = []
            region_ids = set()
            for i, reg in enumerate(regions):
                where = f"regions[{i}]"
                if not isinstance(reg, dict):
                    report.err("地图", f"{where} 条目必须是对象")
                    continue
                rid = reg.get("id")
                if not rid:
                    report.err("地图", f"{where} 缺少 id")
                else:
                    if not str(rid).startswith("r_"):
                        report.err("地图", f"区域 id {rid} 未使用 r_ 前缀")
                    if rid in region_ids:
                        report.err("地图", f"区域 id 重复：{rid}")
                    region_ids.add(rid)
                if not (isinstance(reg.get("name"), str) and reg["name"].strip()):
                    report.err("地图", f"{where} name 为空")
                if reg.get("shape") not in MAP_SHAPES:
                    report.err("地图", f"{where} shape 越界：{reg.get('shape')}")
                if reg.get("layer") and reg["layer"] not in place:
                    report.err("地图", f"{where} layer 不存在：{reg['layer']}")
                label_at = reg.get("label_at")
                if label_at is not None:
                    check_point(label_at, f"区域 {rid or where} label_at")
                polygon = reg.get("polygon")
                if not isinstance(polygon, list) or len(polygon) < 3:
                    report.err("地图", f"{where} polygon 至少需要 3 个点")
                else:
                    for j, pt in enumerate(polygon):
                        check_point(pt, f"区域 {rid or where} polygon[{j}]")

            nodes = layout.get("nodes")
            if nodes is None:
                nodes = []
            elif not isinstance(nodes, list):
                report.err("地图", "nodes 必须是 list")
                nodes = []
            node_places = set()
            for i, node in enumerate(nodes):
                where = f"nodes[{i}]"
                if not isinstance(node, dict):
                    report.err("地图", f"{where} 条目必须是对象")
                    continue
                place_id = node.get("place")
                if place_id not in place:
                    report.err("地图", f"{where} place 不存在：{place_id}")
                elif place_id in node_places:
                    report.err("地图", f"节点 place 重复：{place_id}")
                node_places.add(place_id)
                if not in_canvas(node.get("x")):
                    report.err("地图", f"节点 {place_id or where} x 越界：{node.get('x')}")
                if not in_canvas(node.get("y")):
                    report.err("地图", f"节点 {place_id or where} y 越界：{node.get('y')}")
                if node.get("layer") and node["layer"] not in place:
                    report.err("地图", f"{where} layer 不存在：{node['layer']}")
                rank = node.get("rank")
                if rank is not None:
                    if not (isinstance(rank, int) and not isinstance(rank, bool)
                            and 1 <= rank <= 3):
                        report.err("地图", f"{where} rank 越界：{rank}")
                label = node.get("label")
                if label is not None and not isinstance(label, bool):
                    report.err("地图", f"{where} label 必须是布尔：{label}")

            if len(nodes) < 5:
                report.warn("地图", "示意地图过于稀疏")
            if not regions:
                report.warn("地图", "没有任何区域块，2D 视图只剩点")

            # ---------- terrain（装饰地形，可选；缺失只告警） ----------
            def check_ref_region(ref, where):
                if ref is not None and ref not in region_ids:
                    report.err("地图", f"{where} region 不存在：{ref}")

            def check_short_name(name, where):
                if name is not None and (not isinstance(name, str) or len(name) > 20):
                    report.err("地图", f"{where} name 超过 20 字或类型错误：{name}")

            terrain = layout.get("terrain")
            if terrain is None:
                report.warn("地图", "2D 地图没有地形骨架，只有色块")
            elif not isinstance(terrain, dict):
                report.err("地图", "terrain 必须是对象")
            else:
                unknown = set(terrain) - TERRAIN_KEYS
                if unknown:
                    report.err("地图", f"terrain 含未知子键：{sorted(unknown)}")

                for coll in ("ridges", "rivers"):
                    items = terrain.get(coll)
                    if items is None:
                        continue
                    if not isinstance(items, list):
                        report.err("地图", f"terrain.{coll} 必须是 list")
                        continue
                    for i, item in enumerate(items):
                        where = f"terrain.{coll}[{i}]"
                        if not isinstance(item, dict):
                            report.err("地图", f"{where} 条目必须是对象")
                            continue
                        check_points(item.get("points"), f"{where} points", 2)
                        w = item.get("width")
                        if w is not None and not (num(w) and 0 < w <= 6):
                            report.err("地图", f"{where} width 越界：{w}")
                        check_ref_region(item.get("region"), where)
                        check_short_name(item.get("name"), where)

                lakes = terrain.get("lakes")
                if lakes is not None:
                    if not isinstance(lakes, list):
                        report.err("地图", "terrain.lakes 必须是 list")
                    else:
                        for i, item in enumerate(lakes):
                            where = f"terrain.lakes[{i}]"
                            if not isinstance(item, dict):
                                report.err("地图", f"{where} 条目必须是对象")
                                continue
                            check_points(item.get("polygon"), f"{where} polygon", 3)
                            check_ref_region(item.get("region"), where)

                islets = terrain.get("islets")
                if islets is not None:
                    if not isinstance(islets, list):
                        report.err("地图", "terrain.islets 必须是 list")
                    else:
                        for i, item in enumerate(islets):
                            where = f"terrain.islets[{i}]"
                            if not isinstance(item, dict):
                                report.err("地图", f"{where} 条目必须是对象")
                                continue
                            if not in_canvas(item.get("x")):
                                report.err("地图", f"{where} x 越界：{item.get('x')}")
                            if not in_canvas(item.get("y")):
                                report.err("地图", f"{where} y 越界：{item.get('y')}")
                            r = item.get("r")
                            if not (num(r) and 0 < r <= 5):
                                report.err("地图", f"{where} r 越界：{r}")
                        if len(islets) < 4:
                            report.warn("地图", "岛链偏少，海面会显得空")

            # ---------- routes（弯曲航路，可选；缺失不告警） ----------
            routes = layout.get("routes")
            if routes is not None:
                if not isinstance(routes, list):
                    report.err("地图", "routes 必须是 list")
                elif not routes:
                    report.warn("地图", "跨区航路未配置")
                else:
                    for i, route in enumerate(routes):
                        where = f"routes[{i}]"
                        if not isinstance(route, dict):
                            report.err("地图", f"{where} 条目必须是对象")
                            continue
                        rs, rt = route.get("s"), route.get("t")
                        if rs not in place:
                            report.err("地图", f"{where} s 不存在：{rs}")
                        if rt not in place:
                            report.err("地图", f"{where} t 不存在：{rt}")
                        if rs in place and rt in place and rs == rt:
                            report.err("地图", f"{where} 自环：{rs}")
                        if route.get("kind") not in ROUTE_KINDS:
                            report.err("地图", f"{where} kind 越界：{route.get('kind')}")
                        curve = route.get("curve")
                        if curve is not None:
                            check_points(curve, f"{where} curve", 1, 6)
                        label = route.get("label")
                        if label is not None and (not isinstance(label, str) or len(label) > 20):
                            report.err("地图", f"{where} label 超过 20 字或类型错误：{label}")

            # ---------- atlas（网页版视觉层，可选；21 PNG + 9 代码/SVG） ----------
            atlas = layout.get("atlas")
            if atlas is not None:
                if not isinstance(atlas, dict):
                    report.err("地图", "atlas 必须是对象")
                else:
                    import json as _json
                    from pathlib import Path as _Path
                    kit_manifest = _Path(__file__).resolve().parent.parent / "atlas-kit" / "manifest.json"
                    known_assets = set()
                    if kit_manifest.exists():
                        _m = _json.loads(kit_manifest.read_text(encoding="utf-8"))
                        known_assets = {a["id"] for a in _m.get("assets", []) if a.get("media") == "png"}

                    title = atlas.get("title")
                    if title is not None:
                        if not isinstance(title, dict):
                            report.err("地图", "atlas.title 必须是对象")
                        else:
                            if not (isinstance(title.get("text"), str) and title["text"].strip()):
                                report.err("地图", "atlas.title.text 为空")
                            elif len(title["text"]) > 12:
                                report.err("地图", "atlas.title.text 超过 12 字")
                            if title.get("direction") not in (None, "vertical", "horizontal"):
                                report.err("地图", f"atlas.title.direction 越界：{title.get('direction')}")
                            for key in ("x", "y"):
                                if title.get(key) is not None and not in_canvas(title[key]):
                                    report.err("地图", f"atlas.title.{key} 越界：{title[key]}")
                            if title.get("size") is not None and not (num(title["size"]) and 1 <= title["size"] <= 8):
                                report.err("地图", f"atlas.title.size 越界：{title.get('size')}")

                    seal = atlas.get("seal")
                    if seal is not None:
                        if not isinstance(seal, dict):
                            report.err("地图", "atlas.seal 必须是对象")
                        else:
                            if not (isinstance(seal.get("ch"), str) and len(seal["ch"]) == 1):
                                report.err("地图", "atlas.seal.ch 必须是单字")
                            for key in ("x", "y"):
                                if seal.get(key) is not None and not in_canvas(seal[key]):
                                    report.err("地图", f"atlas.seal.{key} 越界：{seal[key]}")

                    compass = atlas.get("compass")
                    if compass is not None and compass is not False:
                        if not isinstance(compass, dict):
                            report.err("地图", "atlas.compass 必须是对象或 false")
                        else:
                            for key in ("x", "y", "size"):
                                if compass.get(key) is not None and not in_canvas(compass[key]):
                                    report.err("地图", f"atlas.compass.{key} 越界：{compass[key]}")
                            if compass.get("opacity") is not None and not (num(compass["opacity"]) and 0 <= compass["opacity"] <= 1):
                                report.err("地图", f"atlas.compass.opacity 越界：{compass.get('opacity')}")

                    marks = atlas.get("markers")
                    if marks is not None:
                        if not isinstance(marks, dict):
                            report.err("地图", "atlas.markers 必须是对象")
                        else:
                            for pid, kind in marks.items():
                                if pid not in node_places:
                                    report.err("地图", f"atlas.markers 引用了不存在的节点：{pid}")
                                if kind not in MARKER_TYPES:
                                    report.err("地图", f"atlas.markers[{pid}] 类型越界：{kind}")

                    stamps = atlas.get("stamps")
                    if stamps is not None:
                        if not isinstance(stamps, list):
                            report.err("地图", "atlas.stamps 必须是 list")
                        else:
                            for i, st in enumerate(stamps):
                                where = f"atlas.stamps[{i}]"
                                if not isinstance(st, dict):
                                    report.err("地图", f"{where} 条目必须是对象")
                                    continue
                                asset = st.get("asset")
                                if not isinstance(asset, str) or not asset:
                                    report.err("地图", f"{where} asset 为空")
                                elif known_assets and asset not in known_assets:
                                    report.err("地图", f"{where} asset 不在 atlas-kit：{asset}")
                                attach = st.get("attach")
                                if attach is not None:
                                    if attach not in node_places:
                                        report.err("地图", f"{where} attach 不存在：{attach}")
                                elif not (in_canvas(st.get("x")) and in_canvas(st.get("y"))):
                                    report.err("地图", f"{where} 缺少 attach 或合法 x/y")
                                if st.get("layer") and st["layer"] not in place:
                                    report.err("地图", f"{where} layer 不存在：{st['layer']}")
                                if st.get("w") is not None and not (num(st["w"]) and 1 <= st["w"] <= 40):
                                    report.err("地图", f"{where} w 越界：{st.get('w')}")
                                if st.get("opacity") is not None and not (num(st["opacity"]) and 0 <= st["opacity"] <= 1):
                                    report.err("地图", f"{where} opacity 越界：{st.get('opacity')}")
                                if st.get("rotation") is not None and not (num(st["rotation"]) and -180 <= st["rotation"] <= 180):
                                    report.err("地图", f"{where} rotation 越界：{st.get('rotation')}")
                                if st.get("markerOffset") is not None and not (num(st["markerOffset"]) and -10 <= st["markerOffset"] <= 10):
                                    report.err("地图", f"{where} markerOffset 越界：{st.get('markerOffset')}")

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
