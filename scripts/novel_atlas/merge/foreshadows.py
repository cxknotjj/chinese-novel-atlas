"""伏笔：内容归并、mentions 轨迹并入、派生状态重算。"""

import json
from pathlib import Path

from ..names import norm, sim


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
        if payoff and payoff != f.get("plant_ch"):
            expect = "paid"
        else:
            last = f.get("last_mention_ch") or f.get("plant_ch") or 0
            expect = "overdue" if live - last > thr else "planted"
        if f.get("status") != expect:
            f["status"] = expect
            changed += 1
    return thr, changed
