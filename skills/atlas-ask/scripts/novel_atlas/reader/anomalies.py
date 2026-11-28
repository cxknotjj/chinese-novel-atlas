"""读者向疑点索引：把“作品内部可能矛盾/值得考据”的地方做成可复核对象。

原则：
- 只标注，不给改稿建议；
- 每条必须有原文/章节证据；
- 不确定的用 confidence + reader_note 表达，不假装是定论。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..foreshadow_rules import threshold

KIND_CN = {
    "foreshadow_unresolved": "伏笔未回收",
    "power_regression": "战力倒退",
    "battle_gap": "越级战斗",
    "knowledge_leak": "认知提前",
    "entity_after_last": "档案退场章疑点",
    "death_reappearance": "死亡后再出现",
    "timeline_conflict": "时间线疑点",
    "item_disconnect": "器物断线",
    "place_conflict": "地点方位冲突",
    "relation_reversal": "关系反转",
    "alias_candidate": "别名候选",
}

SEVERITY_ORDER = {"high": 0, "warning": 1, "info": 2}


def _ch(v: Any, default: int | None = None) -> int | None:
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return default


def _coord(ch: int | None, quote: str | None = None) -> str:
    if quote:
        m = re.match(r"^ch(\d+):p(\d+)", quote.strip())
        if m:
            return f"ch{int(m.group(1))}:p{int(m.group(2))}"
    return f"ch{ch}" if ch else "ch?"


def _evidence(ch: int | None, quote: str | None, note: str = "") -> dict:
    """证据对象：coordinate 可取 chN:pM；quote 必须是可读文本，不能只重复坐标。"""
    coordinate = _coord(ch, quote)
    text = (note or "").strip()
    if not text and quote and not re.match(r"^ch\d+(?::p\d+)?$", quote.strip()):
        text = quote.strip()
    return {
        "coordinate": coordinate,
        "quote": (text or "章节记录")[:240],
    }


def _id(kind: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return "an_" + kind[:10] + "_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _add(out: list[dict], *, kind: str, title: str, detail: str,
         chapter_range: list[int], entities: list[str], evidence: list[dict],
         confidence: str = "medium", reader_note: str = "",
         severity: str = "info", extra: dict | None = None) -> None:
    if not evidence:
        return
    item = {
        "id": _id(kind, title, chapter_range, evidence[0].get("coordinate")),
        "kind": kind,
        "kind_cn": KIND_CN.get(kind, kind),
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "detail": detail,
        "chapter_range": [int(x) for x in chapter_range if isinstance(x, int)],
        "entities": [x for x in entities if x],
        "evidence": evidence,
        "reader_note": reader_note or "这是基于结构化数据的候选疑点，读者可回到原文自行判断。",
        "verified": False,
    }
    if extra:
        item.update(extra)
    out.append(item)


def _chapter_text(ch: dict) -> str:
    return " ".join(str(ch.get(k) or "") for k in ("title", "summary", "hook"))


def _realm_order(data: dict) -> dict[str, int]:
    out = {}
    for i, r in enumerate(data.get("realms") or []):
        if r.get("id"):
            out[r["id"]] = _ch(r.get("order"), i) or i
    return out


def _find_chapters_mentioning(data: dict, names: list[str], after: int) -> list[dict]:
    names = [n for n in names if n and (len(n) >= 2 or re.fullmatch(r"[\u4e00-\u9fff]", n))]
    if not names:
        return []
    hits = []
    for ch in data.get("chapters") or []:
        n = _ch(ch.get("ch"), 0) or 0
        if n <= after:
            continue
        text = _chapter_text(ch)
        if any(name in text for name in names):
            hits.append(ch)
    return hits


def rule_foreshadow(data: dict, live: int, thr: int) -> list[dict]:
    out = []
    for f in data.get("foreshadows") or []:
        if f.get("status") == "dropped" or f.get("payoff_ch"):
            continue
        plant = _ch(f.get("plant_ch"), 0) or 0
        last = _ch(f.get("last_mention_ch")) or plant
        silent = live - last
        if silent <= thr:
            continue
        evidence = [_evidence(plant, f.get("plant_quote") or f.get("content"), f.get("content") or "")]
        if f.get("last_mention_ch"):
            evidence.append(_evidence(last, f.get("last_mention_quote"),
                                      f"第 {last} 章后未再出现；沉默 {silent} 章"))
        _add(out, kind="foreshadow_unresolved",
             title=f"{f.get('content', '未命名伏笔')[:28]}：第 {plant} 章埋下，{last} 章后未再提",
             detail=f"沉默 {silent} 章，超过当前阈值 {thr} 章。",
             chapter_range=[plant, last],
             entities=[f.get("id")],
             evidence=evidence,
             confidence="high" if silent > thr * 2 else "medium",
             severity="warning" if f.get("importance", 0) >= 0.7 else "info",
             reader_note="可能是作者有意留白或续作钩子；是否算“坑”由读者判断。",
             extra={"importance": f.get("importance"), "silent_chapters": silent})
    return out


def rule_power_regression(data: dict) -> list[dict]:
    out = []
    order = _realm_order(data)
    for e in data.get("entities") or []:
        hist = [p for p in (e.get("power_history") or []) if _ch(p.get("ch")) is not None]
        hist.sort(key=lambda p: _ch(p.get("ch"), 0) or 0)
        prev = None
        for p in hist:
            o = order.get(p.get("realm"))
            if o is None:
                continue
            if prev is not None and o < prev[0]:
                ch = _ch(p.get("ch"), 0) or 0
                evidence = [
                    _evidence(prev[1], None, f"{prev[2]} · {prev[3]}"),
                    _evidence(ch, None, f"{p.get('stage') or ''} · {p.get('note') or ''}"),
                ]
                _add(out, kind="power_regression",
                     title=f"{e.get('name')}：第 {ch} 章境界低于前一次记录",
                     detail=f"从 {prev[2]} 降到 {p.get('realm')}；数据记录的境界 order 出现下降。",
                     chapter_range=[prev[1], ch], entities=[e.get("id"), p.get("realm")],
                     evidence=evidence, confidence="high", severity="warning",
                     reader_note="可能是跌境/重修/伪装，也可能是数据抽取错位；需回原文核对。")
            prev = (o, _ch(p.get("ch"), 0) or 0, p.get("realm"), p.get("note") or p.get("stage") or "")
    return out


def rule_battle_gap(data: dict) -> list[dict]:
    out = []
    names = {e.get("id"): e.get("name") or e.get("id") for e in data.get("entities") or []}
    for c in data.get("chapters") or []:
        for b in c.get("battles") or []:
            gap = _ch(b.get("gap"), 0) or 0
            if abs(gap) < 2:
                continue
            a, t = b.get("a") or b.get("s"), b.get("b") or b.get("t")
            if not a or not t or a == t:
                continue
            ch = _ch(c.get("ch"), 0) or 0
            _add(out, kind="battle_gap",
                 title=f"第 {ch} 章：{names.get(a, a)} vs {names.get(t, t)}，境界差 {gap:+d}",
                 detail=f"战斗记录显示境界差 {gap:+d}；绝对值 ≥2，属于越级战斗候选。",
                 chapter_range=[ch, ch], entities=[a, t],
                 evidence=[_evidence(ch, None, b.get("note") or c.get("summary") or "战斗记录")],
                 confidence="high", severity="info",
                 reader_note="越级本身是爽点结构，不等于错误；列为疑点是因为缺少前置铺垫时容易崩。",
                 extra={"battle": b})
    return out


def rule_knowledge(data: dict) -> list[dict]:
    out = []
    for k in data.get("knowledge") or []:
        truth = _ch(k.get("truth_ch"), 0) or 0
        reader_known = _ch(k.get("reader_known_ch"), truth) or truth
        for x in k.get("known_by") or []:
            ch = _ch(x.get("ch"), 0) or 0
            if truth and ch and ch < truth:
                _add(out, kind="knowledge_leak",
                     title=f"{x.get('entity')} 在第 {ch} 章知道「{k.get('fact', '')[:24]}」",
                     detail=f"真相章为第 {truth} 章，角色知道章为第 {ch} 章；角色比真相揭示更早知情。",
                     chapter_range=[ch, truth], entities=[x.get("entity")],
                     evidence=[_evidence(ch, None, k.get("fact") or "认知记录"),
                               _evidence(truth, None, "真相揭示章")],
                     confidence="medium", severity="info",
                     reader_note="可能是秘密知情者/幕后布局，不必然是穿帮；需结合上下文判断。")
    return out


def rule_entity_after_last(data: dict) -> list[dict]:
    """data 里的 last_ch 表示最后出场；若后续章节摘要仍点名，标为档案疑点。

    注意：`last_ch` 不等于死亡。只有 attrs 明确写“死亡/陨落/被杀”时，
    才升级为 death_reappearance。
    """
    out = []
    for e in data.get("entities") or []:
        if e.get("type") not in ("character", "creature"):
            continue
        last = _ch(e.get("last_ch"))
        if last is None:
            continue
        hits = _find_chapters_mentioning(data, [e.get("name")] + list(e.get("aliases") or []), last)
        if not hits:
            continue
        ch = hits[0]
        attrs = e.get("attrs") or {}
        status = " ".join(str(attrs.get(k) or "") for k in ("状态", "结局", "生死"))
        dead = any(w in status for w in ("死", "亡", "陨落", "被杀", "身亡"))
        kind = "death_reappearance" if dead else "entity_after_last"
        _add(out, kind=kind,
             title=(f"{e.get('name')}：记录已死亡，第 {_ch(ch.get('ch'))} 章仍被点名"
                    if dead else f"{e.get('name')}：记录最后出场第 {last} 章，后续仍被点名"),
             detail=(f"attrs 标记死亡/退场，但第 {_ch(ch.get('ch'))} 章摘要仍出现该角色名/别名。"
                     if dead else f"第 {_ch(ch.get('ch'))} 章摘要仍出现该角色名/别名；last_ch 可能偏早。"),
             chapter_range=[last, _ch(ch.get("ch"), last) or last],
             entities=[e.get("id")],
             evidence=[_evidence(last, None, "entities.last_ch"),
                       _evidence(_ch(ch.get("ch")), None, _chapter_text(ch)[:180])],
             confidence="medium" if dead else "low",
             severity="warning" if dead else "info",
             reader_note=("可能是回忆/残魂/同名，也可能是死亡记录错误；需回原文确认。"
                          if dead else "这是档案退场章与章节摘要不一致，属于数据疑点，不一定是剧情矛盾。"))
    return out


def rule_place_conflict(data: dict) -> list[dict]:
    out = []
    by_pair = defaultdict(list)
    for r in data.get("spatial_relations") or []:
        if r.get("kind") in ("direction", "distance"):
            by_pair[(r.get("s"), r.get("t"))].append(r)
    opposites = {
        "north_of": "south_of", "south_of": "north_of",
        "east_of": "west_of", "west_of": "east_of",
        "northeast_of": "southwest_of", "southwest_of": "northeast_of",
        "northwest_of": "southeast_of", "southeast_of": "northwest_of",
    }
    for (s, t), rows in by_pair.items():
        dirs = [r for r in rows if r.get("kind") == "direction"]
        values = [r.get("value") for r in dirs]
        for a in dirs:
            for b in dirs:
                if a is b:
                    continue
                if opposites.get(a.get("value")) == b.get("value"):
                    _add(out, kind="place_conflict",
                         title=f"地点方位冲突：{s} ↔ {t}",
                         detail=f"同时记录 {a.get('value')} 与 {b.get('value')}；同一对地点出现相反方位。",
                         chapter_range=[_ch(a.get("first_ch"), 0) or 0,
                                        _ch(b.get("first_ch"), 0) or 0],
                         entities=[s, t],
                         evidence=[_evidence(_ch(a.get("first_ch")), (a.get("evidence") or {}).get("quote"), "方向 A"),
                                   _evidence(_ch(b.get("first_ch")), (b.get("evidence") or {}).get("quote"), "方向 B")],
                         confidence="high", severity="warning",
                         reader_note="可能来自不同角色/不同时期的说法，先对照两条原文证据。")
    return out


def rule_relation_reversal(data: dict) -> list[dict]:
    out = []
    names = {e.get("id"): e.get("name") or e.get("id") for e in data.get("entities") or []}
    pairs = defaultdict(list)
    for r in data.get("relations") or []:
        if r.get("type") in ("alliance", "conflict"):
            key = tuple(sorted([r.get("s"), r.get("t")]))
            pairs[key].append(r)
    for (s, t), rows in pairs.items():
        types = {r.get("type") for r in rows}
        if "alliance" in types and "conflict" in types:
            a = next(r for r in rows if r.get("type") == "alliance")
            b = next(r for r in rows if r.get("type") == "conflict")
            cha = _ch(a.get("first_ch"), 0) or 0
            chb = _ch(b.get("first_ch"), 0) or 0
            lo, hi = sorted([cha, chb])
            _add(out, kind="relation_reversal",
                 title=f"关系反转候选：{names.get(s, s)} ↔ {names.get(t, t)} 同时有同盟/敌对",
                 detail="relations 同时记录 alliance 与 conflict；若发生在同一时间段，需检查是否有事件支撑。",
                 chapter_range=[lo, hi],
                 entities=[s, t],
                 evidence=[_evidence(cha, (a.get("evidence") or [""])[0], "同盟记录"),
                           _evidence(chb, (b.get("evidence") or [""])[0], "敌对记录")],
                 confidence="medium", severity="info",
                 reader_note="反目/结盟本身是正常剧情；标出来是提醒核对时间顺序。")
    return out


def rule_alias_candidate(data: dict) -> list[dict]:
    """别名写成了另一个实体名，但没有被 merge 归并。"""
    out = []
    names = {}
    for e in data.get("entities") or []:
        names[e.get("name")] = e
    for e in data.get("entities") or []:
        for a in e.get("aliases") or []:
            if a in names and names[a].get("id") != e.get("id"):
                other = names[a]
                cha = _ch(e.get("first_ch"), 0) or 0
                chb = _ch(other.get("first_ch"), 0) or 0
                lo, hi = sorted([cha, chb])
                _add(out, kind="alias_candidate",
                     title=f"别名指向另一个实体：{e.get('name')} 的别名「{a}」",
                     detail=f"{a} 同时是实体 {other.get('id')} 的正名；当前未被 merge 合并。",
                     chapter_range=[lo, hi],
                     entities=[e.get("id"), other.get("id")],
                     evidence=[_evidence(cha, None, f"{e.get('name')} aliases={a}")],
                     confidence="low", severity="info",
                     reader_note="可能是同名不同人，也可能是漏归并；不要直接当成同一人。")
    return out


def rule_item_disconnect(data: dict) -> list[dict]:
    """器物首现章不在任何章节 new_entities 里，标数据断线候选。"""
    out = []
    new_by_ch = Counter()
    for ch in data.get("chapters") or []:
        for eid in ch.get("new_entities") or []:
            new_by_ch[eid] += 1
    for e in data.get("entities") or []:
        if e.get("type") != "item":
            continue
        if new_by_ch.get(e.get("id")):
            continue
        first = _ch(e.get("first_ch"), 0) or 0
        if first <= 1:
            continue
        _add(out, kind="item_disconnect",
             title=f"器物 {e.get('name')} 未登记首现章节",
             detail=f"first_ch={first}，但 chapters.new_entities 中没有该器物。",
             chapter_range=[first, first], entities=[e.get("id")],
             evidence=[_evidence(first, None, e.get("desc") or "器物记录")],
             confidence="low", severity="info",
             reader_note="可能是抽取遗漏，不代表作品矛盾。")
    return out


def rule_timeline(data: dict) -> list[dict]:
    """只做可验证的章节顺序冲突：summary 明说“之前/之后”且指向未来章。"""
    out = []
    for ch in data.get("chapters") or []:
        n = _ch(ch.get("ch"), 0) or 0
        text = _chapter_text(ch)
        for m in re.finditer(r"(?:第\s*(\d+)\s*章|(\d+)\s*章)(?:之后|以后|后)", text):
            target = _ch(m.group(1) or m.group(2))
            if target and target > n:
                _add(out, kind="timeline_conflict",
                     title=f"第 {n} 章摘要提前引用第 {target} 章之后的事",
                     detail="当前章摘要出现“第 N 章之后”的表述，可能造成时间线前置泄露。",
                     chapter_range=[n, target], entities=[],
                     evidence=[_evidence(n, None, text[:180])],
                     confidence="low", severity="info",
                     reader_note="可能只是叙述者预叙，不必然是错误。")
                break
    return out


def build_anomalies(data: dict, *, live: int | None = None, generated_at: str = "") -> dict:
    """构建疑点报告。

    generated_at 默认取 data.meta.analyzed_at，而不是 time.now()：
    报告描述的是「分析产物」，同一份 data.json 必须得到逐字节相同的结果，
    否则每次重建都会在 data.js 里写进一个新的时间戳，产生几百 KB 的假 diff。
    需要「本次生成时间」的调用方（例如导出独立报告）可以显式传入。
    """
    meta = data.get("meta") or {}
    analyzed = _ch((meta.get("coverage") or {}).get("chapters_done"), 0) or 0
    total = _ch(meta.get("chapters"), 0) or 0
    live = live or analyzed or max([_ch(c.get("ch"), 0) or 0 for c in data.get("chapters") or []] + [1])
    thr = threshold(live, total)
    rules = [
        ("foreshadow_unresolved", lambda: rule_foreshadow(data, live, thr)),
        ("power_regression", lambda: rule_power_regression(data)),
        ("battle_gap", lambda: rule_battle_gap(data)),
        ("knowledge_leak", lambda: rule_knowledge(data)),
        ("entity_after_last", lambda: rule_entity_after_last(data)),
        ("place_conflict", lambda: rule_place_conflict(data)),
        ("relation_reversal", lambda: rule_relation_reversal(data)),
        ("alias_candidate", lambda: rule_alias_candidate(data)),
        ("item_disconnect", lambda: rule_item_disconnect(data)),
        ("timeline_conflict", lambda: rule_timeline(data)),
    ]
    found = []
    for name, fn in rules:
        try:
            found.extend(fn())
        except Exception as exc:  # 单条规则失败不能拖垮整份档案
            found.append({
                "id": _id("rule_error", name, str(exc)),
                "kind": "rule_error", "kind_cn": "规则执行失败",
                "severity": "warning", "confidence": "low",
                "title": f"{name} 规则执行失败", "detail": str(exc),
                "chapter_range": [], "entities": [], "evidence": [],
                "reader_note": "规则错误，不影响其他疑点。", "verified": False,
                "rule": name,
            })
    # 去重：同 kind + 同标题 + 同首条证据
    seen = set()
    unique = []
    for a in found:
        key = (a.get("kind"), a.get("title"), (a.get("evidence") or [{}])[0].get("coordinate"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(a)
    unique.sort(key=lambda a: (SEVERITY_ORDER.get(a.get("severity"), 3),
                               a.get("chapter_range") or [999999],
                               a.get("title") or ""))
    counts = Counter(a.get("kind") for a in unique)
    return {
        "version": "1.0",
        "generated_at": generated_at or meta.get("analyzed_at") or "",
        "source_title": meta.get("title"),
        "source_file": meta.get("source_file"),
        "coverage": meta.get("coverage"),
        "threshold": thr,
        "live_ch": live,
        "counts": dict(counts),
        "total": len(unique),
        "anomalies": unique,
    }


def write_anomalies(data: dict, out_path: str | Path, *, live: int | None = None) -> dict:
    report = build_anomalies(data, live=live)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
