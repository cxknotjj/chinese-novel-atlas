#!/usr/bin/env python3
"""compare.py — 把两本已拆解的书放在一起比节奏、伏笔和设定规模。

产出：
    metrics.md    指标对照表 + 结论
    diff.json     机器可读的指标与差值
    compare.html  并排条形图，双击可看

用法：
    python scripts/compare.py --a output/青云签到三十年/data.json \
                              --b output/万古剑尊/data.json --out output/_compare/
"""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def foreshadow_status(f, live, thr):
    if f.get("status") == "dropped":
        return "dropped"
    if f.get("payoff_ch"):
        return "paid"
    return "overdue" if live - (f.get("plant_ch") or 0) > thr else "planted"


def metrics(d):
    meta = d.get("meta") or {}
    chs = d.get("chapters") or []
    live = max((c.get("ch") or 0 for c in chs), default=0)
    span = live or (meta.get("chapters") or 0)
    thr = max(50, int(span * 0.15))

    hook = sum(1 for c in chs if c.get("hook"))
    words = [c.get("words") or 0 for c in chs if c.get("words")]
    tension = [c.get("tension") for c in chs if isinstance(c.get("tension"), (int, float))]
    thrill = sorted(c["ch"] for c in chs if c.get("emotion") == "爽")
    gaps = [b - a for a, b in zip(thrill, thrill[1:])]

    ent = d.get("entities") or []
    chars = [e for e in ent if e.get("type") == "character"]
    rels = d.get("relations") or []
    degree = Counter()
    for r in rels:
        degree[r.get("s")] += 1
        degree[r.get("t")] += 1

    fores = d.get("foreshadows") or []
    states = Counter(foreshadow_status(f, live, thr) for f in fores)

    # 主角 = 关系最多的角色；用他的战力时间线估算升级速度
    proto = max(chars, key=lambda e: degree[e["id"]], default=None)
    ph = (proto or {}).get("power_history") or []
    level_gap = (statistics.mean([b["ch"] - a["ch"] for a, b in zip(ph, ph[1:])])
                 if len(ph) >= 2 else None)

    return {
        "title": meta.get("title") or "?",
        "schema": meta.get("schema_version"),
        "chapters": len(chs),
        "chapters_total": meta.get("chapters") or 0,
        "complete": len(chs) >= (meta.get("coverage") or {}).get("chapters_done", 0),
        "chars": meta.get("chars") or sum(words),
        "hook_rate": hook / len(chs) if chs else None,
        "thrill_gap": statistics.median(gaps) if gaps else None,
        "avg_words": sum(words) / len(words) if words else None,
        "avg_tension": sum(tension) / len(tension) if tension else None,
        "realms": len(d.get("realms") or []),
        "characters": len(chars),
        "relations": len(rels),
        "density": len(rels) / len(chars) if chars else None,
        "groups": len({e.get("group") for e in ent if e.get("group")}),
        "setting_density": ((len(d.get("places") or []) + len(d.get("concepts") or []))
                            / ((meta.get("chars") or 1) / 10000)),
        "foreshadows": len(fores),
        "paid_rate": states["paid"] / len(fores) if fores else None,
        "overdue_rate": states["overdue"] / len(fores) if fores else None,
        "level_gap": level_gap,
    }


def fmt(key, v):
    if v is None:
        return "—"
    if key in ("hook_rate", "paid_rate", "overdue_rate"):
        return f"{v:.0%}"
    if key in ("density", "setting_density", "avg_tension", "thrill_gap", "level_gap", "avg_words"):
        return f"{v:.1f}" if key != "density" else f"{v:.2f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def delta(key, a, b):
    if a is None or b is None:
        return "—"
    d = b - a
    unit = "pp" if key in ("hook_rate", "paid_rate", "overdue_rate") else ""
    if key in ("hook_rate", "paid_rate", "overdue_rate"):
        d *= 100
    return f"{d:+.1f}{unit}" if unit else f"{d:+.2f}"


ROWS = [
    ("章末钩子率", "hook_rate"),
    ("爽点间隔（章）", "thrill_gap"),
    ("平均章字数", "avg_words"),
    ("平均章节张力", "avg_tension"),
    ("伏笔回收率", "paid_rate"),
    ("伏笔超期率", "overdue_rate"),
    ("境界层数", "realms"),
    ("主要角色数", "characters"),
    ("关系数", "relations"),
    ("关系密度", "density"),
    ("势力数", "groups"),
    ("设定密度（/万字）", "setting_density"),
    ("主角升级间隔（章）", "level_gap"),
]


def conclusion(a, b):
    lines = []
    if a["hook_rate"] is not None and b["hook_rate"] is not None:
        if abs(a["hook_rate"] - b["hook_rate"]) > 0.03:
            better = a if a["hook_rate"] > b["hook_rate"] else b
            lines.append(f"钩子率：**{better['title']}** 高 {abs(a['hook_rate'] - b['hook_rate']):.0%}，"
                         f"章末留人的能力强一些。")
    if a["paid_rate"] is not None and b["paid_rate"] is not None:
        if abs(a["paid_rate"] - b["paid_rate"]) > 0.05:
            better = a if a["paid_rate"] > b["paid_rate"] else b
            lines.append(f"伏笔：**{better['title']}** 回收率高 "
                         f"{abs(a['paid_rate'] - b['paid_rate']):.0%}；"
                         f"{'另一本' if better is a else a['title']} 的坑更可能烂尾。")
    if a["density"] and b["density"]:
        looser = a if a["density"] < b["density"] else b
        lines.append(f"关系密度：**{looser['title']}** 更松（{fmt('density', looser['density'])}），"
                     f"人物之间还没织起来。")
    if not a["complete"] or not b["complete"]:
        lines.append("**注意**：至少一本是部分章节的抽样，节奏指标只能看趋势，不能当全书结论。")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", default="output/_compare/")
    args = ap.parse_args()

    da, db = load(args.a), load(args.b)
    if (da.get("meta") or {}).get("schema_version") != (db.get("meta") or {}).get("schema_version"):
        raise SystemExit("schema 版本不一致，先转换再比")
    if (da.get("meta") or {}).get("schema_version") != "2.0":
        raise SystemExit("只支持 schema 2.0")

    ma, mb = metrics(da), metrics(db)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, table = [], ["| 指标 | %s | %s | 差异 |" % (ma["title"], mb["title"]),
                       "|---|---:|---:|---:|"]
    for label, key in ROWS:
        va, vb = ma[key], mb[key]
        rows.append((label, key))
        table.append(f"| {label} | {fmt(key, va)} | {fmt(key, vb)} | {delta(key, va, vb)} |")

    md = [f"## {ma['title']} vs {mb['title']}", "",
          f"> {ma['chapters']} 章（全书 {ma['chapters_total']}） · "
          f"{mb['chapters']} 章（全书 {mb['chapters_total']}） · schema 2.0", ""]
    md += table + [""]
    con = conclusion(ma, mb)
    if con:
        md += ["**结论**", ""] + con + [""]
    (out / "metrics.md").write_text("\n".join(md), encoding="utf-8")

    diff = {"a": ma, "b": mb,
            "rows": [{"label": l, "key": k,
                      "a": ma[k], "b": mb[k], "delta": delta(k, ma[k], mb[k])}
                     for l, k in ROWS]}
    (out / "diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")

    body_rows = []
    for label, key in ROWS:
        va, vb = ma[key], mb[key]
        mx = max([x for x in (va, vb) if isinstance(x, (int, float)) and x is not None] or [1])
        def bar(v, txt):
            w = 0 if v is None or not mx else min(100, v / mx * 100)
            return f'<div class="bar"><i style="width:{w:.1f}%"></i><span>{txt}</span></div>'
        body_rows.append(f"<tr><th>{label}</th><td>{bar(va, fmt(key, va))}</td>"
                         f"<td>{bar(vb, fmt(key, vb))}</td></tr>")
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ma['title']} vs {mb['title']}</title>
<style>
body{{margin:0;padding:40px 24px;background:#FAF9F5;color:#2B2A26;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
h1{{font-size:22px;font-weight:500;text-align:center}}
p.sub{{text-align:center;color:#8A8578;font-size:12px;margin-top:8px}}
table{{width:min(880px,100%);margin:28px auto;border-collapse:collapse;font-size:13px}}
th,td{{padding:10px 8px;border-bottom:1px solid #E3DFD5;vertical-align:middle}}
th{{width:150px;text-align:left;font-weight:400;color:#6B675E}}
.bar{{position:relative;background:#F2EFE7;height:20px;border-radius:3px;overflow:hidden}}
th + td .bar i{{background:#A6314A}}
td + td .bar i{{background:#3D6B7D}}
.bar i{{position:absolute;inset:0 auto 0 0;opacity:.25}}
.bar span{{position:relative;padding-left:7px;line-height:20px;font-size:12px}}
.foot{{text-align:center;color:#9A9488;font-size:11px;margin-top:24px}}
</style></head><body>
<h1>{ma['title']} <span style="color:#A6314A">vs</span> {mb['title']}</h1>
<p class="sub">{ma['chapters']} 章 / {mb['chapters']} 章 · schema {ma['schema']} / {mb['schema']}</p>
<table>{"".join(body_rows)}</table>
<p class="foot">由 Novel Atlas compare.py 生成 · 指标口径见 references/schema.md</p>
</body></html>"""
    (out / "compare.html").write_text(doc, encoding="utf-8")

    print(f"A {ma['title']}：{ma['chapters']} 章 / {ma['characters']} 角色 / 钩子率 {fmt('hook_rate', ma['hook_rate'])}")
    print(f"B {mb['title']}：{mb['chapters']} 章 / {mb['characters']} 角色 / 钩子率 {fmt('hook_rate', mb['hook_rate'])}")
    print(f"输出 {out}/ metrics.md · diff.json · compare.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
