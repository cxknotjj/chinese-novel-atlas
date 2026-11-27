"""导出的共享视图模型：加载数据、计算伏笔状态/统计/关系索引。"""

import json
import statistics
from collections import Counter
from pathlib import Path

from ..foreshadow_rules import expected_status, threshold

TYPE_CN = {"character": "人物", "org": "势力", "item": "器物", "creature": "异兽"}
REL_CN = {"kinship": "血亲", "marriage": "婚姻", "romance": "情感", "service": "从属",
          "mentorship": "师承", "alliance": "同盟", "conflict": "敌对", "social": "交游"}
KIND_CN = {"worldview": "世界规则", "golden_finger": "金手指", "technique": "功法",
           "item_grade": "品阶", "organization_rule": "组织制度", "prophecy": "预言"}
STATUS_CN = {"paid": "有回收章", "overdue": "已超期", "planted": "待回收", "dropped": "已放弃"}
STATUS_ORDER = {"overdue": 0, "planted": 1, "paid": 2, "dropped": 3}


def load(root):
    p = Path(root) / "data.json"
    if not p.exists():
        raise SystemExit(f"找不到 {p}")
    d = json.loads(p.read_text(encoding="utf-8"))
    meta = d.get("meta") or {}
    live = max((c.get("ch") or 0 for c in d.get("chapters") or []), default=0)
    d["_live"] = live
    d["_thr"] = threshold(live, meta.get("chapters") or 0)
    return d


def status_of(f, live, thr):
    return expected_status(f, live, thr)


def foresight_rows(d):
    rows = []
    for f in d.get("foreshadows") or []:
        st = status_of(f, d["_live"], d["_thr"])
        end = f.get("payoff_ch") or d["_live"]
        span = max(0, end - (f.get("plant_ch") or 0))
        rows.append((f, st, span))
    rows.sort(key=lambda x: (STATUS_ORDER[x[1]], -x[2], -x[0].get("importance", 0)))
    return rows


def degree_map(d):
    deg = Counter()
    for r in d.get("relations") or []:
        deg[r.get("s")] += 1
        deg[r.get("t")] += 1
    return deg


def relations_of(d, eid):
    out = []
    for r in d.get("relations") or []:
        if r.get("s") == eid or r.get("t") == eid:
            out.append(r)
    return out


def name_of(d, eid):
    for e in d.get("entities") or []:
        if e.get("id") == eid:
            return e.get("name")
    return eid


def realm_line(e, d=None):
    ph = e.get("power_history") or []
    if not ph:
        return ""
    names = {r.get("id"): r.get("name") for r in (d or {}).get("realms") or []}
    parts = []
    for p in ph:
        label = p.get("stage") or ""
        realm = names.get(p.get("realm"), p.get("realm") or "")
        parts.append(f"第 {p.get('ch')} 章 {realm}{label}".strip())
    return " → ".join(parts)


def hook_rate(d):
    chs = d.get("chapters") or []
    return sum(1 for c in chs if c.get("hook")) / len(chs) if chs else 0


def thrill_gap(d):
    chs = [c for c in d.get("chapters") or [] if c.get("emotion") == "爽"]
    gaps = [b["ch"] - a["ch"] for a, b in zip(chs, chs[1:])]
    return statistics.median(gaps) if gaps else None


def meta_line(d):
    m = d["meta"]
    done = len(d.get("chapters") or [])
    total = m.get("chapters", 0)
    chapter_bit = f"{total} 章" if not done or done >= total else f"已分析 {done} / {total} 章"
    bits = [m.get("author"), f"{m.get('chars', 0):,} 字", chapter_bit,
            m.get("genre"), m.get("platform")]
    return " · ".join(str(x) for x in bits if x)
