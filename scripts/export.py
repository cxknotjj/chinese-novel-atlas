#!/usr/bin/env python3
"""export.py — 把 data.json 导出成作者/读者能直接用的格式。

    fs      伏笔清单 CSV（作者改稿对照，最重要）
    md      Markdown 设定集
    csv     角色表 CSV
    single  单文件 HTML 设定集
    site    多页静态站（可挂 GitHub Pages）

用法：
    python scripts/export.py --dir output/青云签到三十年/ --format fs
    python scripts/export.py --dir output/青云签到三十年/ --format md
    python scripts/export.py --dir output/青云签到三十年/ --format csv
    python scripts/export.py --dir output/青云签到三十年/ --format single
    python scripts/export.py --dir output/青云签到三十年/ --format site
"""

import argparse
import csv
import html
import json
import math
import statistics
from collections import Counter
from pathlib import Path

TYPE_CN = {"character": "人物", "org": "势力", "item": "器物", "creature": "异兽"}
REL_CN = {"kinship": "血亲", "marriage": "婚姻", "romance": "情感", "service": "从属",
          "mentorship": "师承", "alliance": "同盟", "conflict": "敌对", "social": "交游"}
KIND_CN = {"worldview": "世界规则", "golden_finger": "金手指", "technique": "功法",
           "item_grade": "品阶", "organization_rule": "组织制度", "prophecy": "预言"}
STATUS_CN = {"paid": "已回收", "overdue": "已超期", "planted": "待回收", "dropped": "已放弃"}
STATUS_ORDER = {"overdue": 0, "planted": 1, "paid": 2, "dropped": 3}


def load(root):
    p = Path(root) / "data.json"
    if not p.exists():
        raise SystemExit(f"找不到 {p}")
    d = json.loads(p.read_text(encoding="utf-8"))
    meta = d.get("meta") or {}
    live = max((c.get("ch") or 0 for c in d.get("chapters") or []), default=0)
    span = live or meta.get("chapters") or 0
    d["_live"] = live
    d["_thr"] = max(50, int(span * 0.15))
    return d


def status_of(f, live, thr):
    if f.get("status") == "dropped":
        return "dropped"
    if f.get("payoff_ch"):
        return "paid"
    # 与 merge.py / validate.py / viewer.html 一致：看沉默时长而非埋设跨度
    last = f.get("last_mention_ch") or f.get("plant_ch") or 0
    return "overdue" if live - last > thr else "planted"


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


# ---------------------------------------------------------------- csv

def export_fs(d, out_dir):
    out = out_dir / "伏笔清单.csv"
    live = d["_live"]
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        # 「沉默」是判超期的依据，「跨度」只是埋了多久——两者差很远，都要给
        w.writerow(["id", "内容", "埋设章", "回收章", "最后提及", "沉默", "状态",
                    "跨度", "线索", "重要度", "备注"])
        for f, st, span in foresight_rows(d):
            last = f.get("last_mention_ch")
            silent = "" if f.get("payoff_ch") else (live - (last or f.get("plant_ch") or 0))
            w.writerow([f.get("id"), f.get("content"), f.get("plant_ch"),
                        f.get("payoff_ch") or "", last or "", silent, STATUS_CN[st], span,
                        f.get("thread") or "", f.get("importance"), f.get("note") or ""])
    return out


def export_csv(d, out_dir):
    out = out_dir / "角色表.csv"
    deg = degree_map(d)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "名称", "类型", "阵营", "别名", "首次登场", "最后登场",
                    "关系数", "简介"])
        for e in sorted(d.get("entities") or [], key=lambda x: -deg[x["id"]]):
            w.writerow([e.get("id"), e.get("name"), TYPE_CN.get(e.get("type"), e.get("type")),
                        e.get("group"), "、".join(e.get("aliases") or []),
                        e.get("first_ch"), e.get("last_ch") or "",
                        deg[e["id"]], (e.get("desc") or "").replace("\n", " ")])
    return out


# ---------------------------------------------------------------- markdown

def md_table(headers, rows):
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(cell(x) for x in r) + " |")
    return "\n".join(lines)


def build_markdown(d):
    m = d["meta"]
    deg = degree_map(d)
    out = [f"# {m.get('title', '?')} · 设定集", "",
           f"> {meta_line(d)}", "",
           f"> 由 Novel Atlas 生成 · schema {m.get('schema_version')} · {m.get('analyzed_at', '')}", ""]

    out += ["## 总览", "",
            f"- 实体 {len(d.get('entities') or [])}（人物 "
            f"{sum(1 for e in d.get('entities') or [] if e.get('type') == 'character')}）",
            f"- 关系 {len(d.get('relations') or [])} · 地点 {len(d.get('places') or [])}"
            f" · 设定 {len(d.get('concepts') or [])}",
            f"- 已分析 {len(d.get('chapters') or [])} 章 · 伏笔 {len(d.get('foreshadows') or [])} 条", ""]

    if d.get("realms"):
        out += ["## 境界体系", "",
                md_table(["序", "境界", "小阶段", "首现", "说明"],
                         [[r.get("order"), r.get("name"), "、".join(r.get("stages") or []) or "—",
                           r.get("first_ch") or "—", r.get("desc") or ""]
                          for r in d["realms"]]), ""]

    chars = [e for e in d.get("entities") or [] if e.get("type") == "character"]
    out += ["## 人物", ""]
    for e in sorted(chars, key=lambda x: (-deg[x["id"]], x.get("first_ch") or 0)):
        out += [f"### {e.get('name')}　<span style=\"color:#8A8578;font-size:12px\">"
                f"{e.get('group')} · 第 {e.get('first_ch', '?')} 章登场</span>", ""]
        if e.get("aliases"):
            out += [f"别名：{'、'.join(e['aliases'])}", ""]
        if e.get("desc"):
            out += [e["desc"], ""]
        rl = realm_line(e, d)
        if rl:
            out += [f"**境界**：{rl}", ""]
        rels = relations_of(d, e["id"])
        if rels:
            out += ["**关系**", ""]
            for r in rels:
                other = r["t"] if r["s"] == e["id"] else r["s"]
                out.append(f"- {name_of(d, other)} — {r.get('label') or REL_CN.get(r.get('type'), r.get('type'))}"
                           f"（{REL_CN.get(r.get('type'), r.get('type'))}）· 第 {r.get('first_ch', '?')} 章")
            out.append("")
        if e.get("attrs"):
            out += ["**档案**：" + " / ".join(f"{k} · {v}" for k, v in e["attrs"].items()), ""]

    orgs = [e for e in d.get("entities") or [] if e.get("type") == "org"]
    if orgs:
        out += ["## 势力", ""]
        for e in sorted(orgs, key=lambda x: -deg[x["id"]]):
            out += [f"### {e.get('name')}", "",
                    f"{e.get('desc') or ''}", "",
                    f"- 阵营：{e.get('group')} · 首次登场：第 {e.get('first_ch', '?')} 章"
                    f" · 关系数：{deg[e['id']]}", ""]

    if d.get("places"):
        out += ["## 地点", "",
                md_table(["地点", "上级", "首现", "说明"],
                         [[p.get("name"),
                           next((x.get("name") for x in d["places"] if x.get("id") == p.get("parent")), "—"),
                           p.get("first_ch") or "—", p.get("desc") or ""]
                          for p in d["places"]]), ""]

    if d.get("concepts"):
        out += ["## 设定", ""]
        for kind, items in sorted(((k, [c for c in d["concepts"] if c.get("kind") == k])
                                   for k in {c.get("kind") for c in d["concepts"]}),
                                  key=lambda kv: KIND_CN.get(kv[0], kv[0])):
            out += [f"### {KIND_CN.get(kind, kind)}", ""]
            for c in items:
                out.append(f"- **{c.get('name')}**（第 {c.get('first_ch', '?')} 章）：{c.get('desc') or ''}")
                if c.get("rules"):
                    out.append(f"  - 规则：{'；'.join(c['rules'])}")
                if c.get("limits"):
                    out.append(f"  - 限制：{'；'.join(c['limits'])}")
            out.append("")

    rows = foresight_rows(d)
    out += ["## 伏笔台账", "",
            f"> 超期阈值 {d['_thr']} 章（按已分析 {d['_live']} 章算）", "",
            md_table(["状态", "埋设", "回收", "跨度", "内容", "线索"],
                     [[STATUS_CN[st], f.get("plant_ch"), f.get("payoff_ch") or "—", span,
                       f.get("content"), f.get("thread") or ""] for f, st, span in rows]), ""]

    out += ["## 节奏", "",
            f"- 章末钩子率 {hook_rate(d):.0%}",
            f"- 爽点间隔 {thrill_gap(d) if thrill_gap(d) is not None else '—'} 章",
            f"- 平均章字数 {sum(c.get('words', 0) for c in d.get('chapters') or []) / max(len(d.get('chapters') or []), 1):.0f}", ""]
    return "\n".join(out)


def export_md(d, out_dir):
    out = out_dir / "设定集.md"
    out.write_text(build_markdown(d), encoding="utf-8")
    return out


# ---------------------------------------------------------------- html

CSS = """
:root{--paper:#FAF9F5;--ink:#2B2A26;--ink2:#6B675E;--ink3:#9A9488;--line:#E3DFD5;--crimson:#A6314A;--indigo:#3D6B7D;--gold:#B8925A;--danger:#C0392B;--ok:#5A7A5E}
*{box-sizing:border-box}
body{margin:0;padding:0 0 60px;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.75;font-size:14px}
header{padding:42px 24px 28px;border-bottom:1px solid var(--line)}
h1{font-size:26px;font-weight:500;margin:0;letter-spacing:.02em}
.meta{color:var(--ink2);font-size:12.5px;margin-top:10px}
.wrap{max-width:880px;margin:0 auto;padding:0 24px}
h2{font-size:18px;font-weight:500;margin:38px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:15px;font-weight:500;margin:22px 0 6px}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:3px;background:#F2EFE7;color:var(--ink2);margin-left:6px;vertical-align:middle}
.desc{color:var(--ink2)}
.aliases{font-size:12px;color:var(--ink3)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:6px;padding:12px 14px;background:#fff}
.card b{font-weight:500}
.card .small{font-size:12px;color:var(--ink3)}
ul{margin:6px 0;padding-left:20px}
li{margin:3px 0}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--ink2);font-weight:400}
.st{font-size:11px;padding:1px 6px;border-radius:3px;white-space:nowrap}
.st.overdue{background:#FBEAE7;color:var(--danger)}
.st.paid{background:#EDF3EE;color:var(--ok)}
.st.planted{background:#F2EFE7;color:var(--ink2)}
.st.dropped{background:#EEE;color:var(--ink3)}
.stats{display:flex;gap:22px;flex-wrap:wrap;margin-top:16px}
.stat{font-size:12px;color:var(--ink2)}
.stat b{display:block;font-size:20px;font-weight:500;color:var(--ink)}
footer{max-width:880px;margin:48px auto 0;padding:16px 24px;border-top:1px solid var(--line);color:var(--ink3);font-size:11.5px}
a{color:var(--crimson);text-decoration:none}
a:hover{text-decoration:underline}
"""


def esc(x):
    return html.escape(str(x or ""))


def status_class(st):
    return st


def build_html(d):
    m = d["meta"]
    deg = degree_map(d)
    chars = [e for e in d.get("entities") or [] if e.get("type") == "character"]
    stats = f"""<div class="stats">
      <div class="stat"><b>{len(chars)}</b>人物</div>
      <div class="stat"><b>{len(d.get('relations') or [])}</b>关系</div>
      <div class="stat"><b>{len(d.get('places') or [])}</b>地点</div>
      <div class="stat"><b>{len(d.get('concepts') or [])}</b>设定</div>
      <div class="stat"><b>{len(d.get('foreshadows') or [])}</b>伏笔</div>
      <div class="stat"><b>{len(d.get('chapters') or [])}</b>已分析章</div>
    </div>"""

    sections = []

    if d.get("realms"):
        rows = "".join(
            f"<tr><td>{r.get('order')}</td><td><b>{esc(r.get('name'))}</b></td>"
            f"<td>{esc('、'.join(r.get('stages') or []) or '—')}</td>"
            f"<td>{esc(r.get('first_ch') or '—')}</td><td class='desc'>{esc(r.get('desc'))}</td></tr>"
            for r in d["realms"])
        sections.append(f"<h2>境界体系</h2><table><tr><th>序</th><th>境界</th><th>小阶段</th>"
                        f"<th>首现</th><th>说明</th></tr>{rows}</table>")

    cards = []
    for e in sorted(chars, key=lambda x: (-deg[x["id"]], x.get("first_ch") or 0)):
        rels = relations_of(d, e["id"])
        rel_html = ""
        if rels:
            items = []
            for r in rels:
                other = r["t"] if r["s"] == e["id"] else r["s"]
                items.append(f"<li>{esc(name_of(d, other))} — "
                             f"{esc(r.get('label') or REL_CN.get(r.get('type'), r.get('type')))}"
                             f"<span class='aliases'> · ch{r.get('first_ch', '?')}</span></li>")
            rel_html = f"<div class='aliases' style='margin-top:8px'>关系 {len(rels)}</div><ul>{''.join(items)}</ul>"
        realm = realm_line(e, d)
        realm_html = f"<div class='small' style='margin-top:6px'>境界：{esc(realm)}</div>" if realm else ""
        aliases = f"<div class='aliases'>{esc('、'.join(e.get('aliases') or []))}</div>" if e.get("aliases") else ""
        cards.append(f"""<div class="card"><b>{esc(e.get('name'))}</b>
          <span class="tag">{esc(e.get('group'))}</span>
          {aliases}<div class="small" style="margin-top:6px">{esc(e.get('desc'))}</div>
          {realm_html}{rel_html}</div>""")
    sections.append(f"<h2>人物</h2><div class='grid'>{''.join(cards)}</div>")

    orgs = [e for e in d.get("entities") or [] if e.get("type") == "org"]
    if orgs:
        cards = "".join(
            f"<div class='card'><b>{esc(e.get('name'))}</b><span class='tag'>{esc(e.get('group'))}</span>"
            f"<div class='small' style='margin-top:6px'>{esc(e.get('desc'))}</div>"
            f"<div class='aliases'>首次登场 ch{e.get('first_ch', '?')} · 关系 {deg[e['id']]}</div></div>"
            for e in sorted(orgs, key=lambda x: -deg[x["id"]]))
        sections.append(f"<h2>势力</h2><div class='grid'>{cards}</div>")

    if d.get("places"):
        rows = "".join(
            f"<tr><td><b>{esc(p.get('name'))}</b></td>"
            f"<td>{esc(next((x.get('name') for x in d['places'] if x.get('id') == p.get('parent')), '—'))}</td>"
            f"<td>{esc(p.get('first_ch') or '—')}</td><td class='desc'>{esc(p.get('desc'))}</td></tr>"
            for p in d["places"])
        sections.append(f"<h2>地点</h2><table><tr><th>地点</th><th>上级</th><th>首现</th>"
                        f"<th>说明</th></tr>{rows}</table>")

    if d.get("concepts"):
        rows = "".join(
            f"<tr><td><b>{esc(c.get('name'))}</b></td><td>{esc(KIND_CN.get(c.get('kind'), c.get('kind')))}</td>"
            f"<td>{esc(c.get('first_ch') or '—')}</td><td class='desc'>{esc(c.get('desc'))}"
            + (f"<div class='aliases'>规则：{esc('；'.join(c['rules']))}</div>" if c.get("rules") else "")
            + (f"<div class='aliases'>限制：{esc('；'.join(c['limits']))}</div>" if c.get("limits") else "")
            + "</td></tr>"
            for c in d["concepts"])
        sections.append(f"<h2>设定</h2><table><tr><th>名称</th><th>类别</th><th>首现</th>"
                        f"<th>说明</th></tr>{rows}</table>")

    rows = []
    for f, st, span in foresight_rows(d):
        rows.append(f"<tr><td><span class='st {st}'>{STATUS_CN[st]}</span></td>"
                    f"<td>ch{f.get('plant_ch')}</td><td>{('ch' + str(f['payoff_ch'])) if f.get('payoff_ch') else '—'}</td>"
                    f"<td>{span}</td><td>{esc(f.get('content'))}</td><td class='aliases'>{esc(f.get('thread'))}</td></tr>")
    sections.append(f"<h2>伏笔台账</h2><div class='aliases'>超期阈值 {d['_thr']} 章"
                    f"（按已分析 {d['_live']} 章算）</div>"
                    f"<table><tr><th>状态</th><th>埋设</th><th>回收</th><th>跨度</th>"
                    f"<th>内容</th><th>线索</th></tr>{''.join(rows)}</table>")

    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(m.get('title'))} · 设定集</title>
<style>{CSS}</style></head><body>
<header><div class="wrap"><h1>{esc(m.get('title'))}</h1>
<div class="meta">{esc(meta_line(d))}</div>{stats}</div></header>
<div class="wrap">{body}</div>
<footer>由 Novel Atlas 生成 · schema {esc(m.get('schema_version'))} · {esc(m.get('analyzed_at'))}<br>
原文不在导出物中，引用只保留章号坐标。</footer>
</body></html>"""


def export_single(d, out_dir):
    out = out_dir / "设定集.html"
    out.write_text(build_html(d), encoding="utf-8")
    return out


# ---------------------------------------------------------------- site

def page(title, body, up="."):
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>
<link rel="stylesheet" href="{up}/style.css"></head><body>
<header><div class="wrap"><h1>{esc(title)}</h1></div></header>
<div class="wrap">{body}</div>
<footer>由 Novel Atlas 生成 · <a href="{up}/index.html">返回总览</a></footer></body></html>"""


def export_site(d, out_dir):
    site = out_dir / "site"
    (site / "character").mkdir(parents=True, exist_ok=True)
    (site / "place").mkdir(parents=True, exist_ok=True)
    (site / "concept").mkdir(parents=True, exist_ok=True)
    (site / "style.css").write_text(CSS, encoding="utf-8")

    m = d["meta"]
    deg = degree_map(d)
    chars = [e for e in d.get("entities") or [] if e.get("type") == "character"]
    groups = {}
    for e in chars:
        groups.setdefault(e.get("group") or "其他", []).append(e)

    cards = []
    for g, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        inner = "".join(
            f"<a class='card' href='character/{esc(e['id'])}.html'><b>{esc(e.get('name'))}</b>"
            f"<div class='small'>{esc(e.get('desc'))[:40]}</div></a>"
            for e in sorted(items, key=lambda x: -deg[x["id"]]))
        cards.append(f"<h2>{esc(g)}（{len(items)}）</h2><div class='grid'>{inner}</div>")
    fores_rows = "".join(
        f"<tr><td><span class='st {st}'>{STATUS_CN[st]}</span></td><td>ch{f.get('plant_ch')}</td>"
        f"<td>{('ch' + str(f['payoff_ch'])) if f.get('payoff_ch') else '—'}</td>"
        f"<td>{esc(f.get('content'))}</td></tr>" for f, st, span in foresight_rows(d))
    body = (f"<div class='meta'>{esc(meta_line(d))}</div>"
            f"<h2>伏笔台账</h2><table><tr><th>状态</th><th>埋设</th><th>回收</th><th>内容</th></tr>"
            f"{fores_rows}</table>" + "".join(cards))
    (site / "index.html").write_text(page(m.get("title"), body, up="."), encoding="utf-8")

    for e in d.get("entities") or []:
        if e.get("type") not in ("character", "org"):
            continue
        rels = relations_of(d, e["id"])
        rel_html = ""
        if rels:
            items = "".join(
                f"<li><a href='../character/{esc(r['t'] if r['s'] == e['id'] else r['s'])}.html'>"
                f"{esc(name_of(d, r['t'] if r['s'] == e['id'] else r['s']))}</a> — "
                f"{esc(r.get('label') or REL_CN.get(r.get('type'), r.get('type')))} · ch{r.get('first_ch', '?')}</li>"
                for r in rels)
            rel_html = f"<h2>关系</h2><ul>{items}</ul>"
        realm = realm_line(e, d)
        realm_html = f"<h2>境界</h2><p>{esc(realm)}</p>" if realm else ""
        attrs = ""
        if e.get("attrs"):
            attrs = "<h2>档案</h2><ul>" + "".join(
                f"<li>{esc(k)} · {esc(v)}</li>" for k, v in e["attrs"].items()) + "</ul>"
        body = (f"<p class='meta'>{esc(e.get('group'))} · 第 {e.get('first_ch', '?')} 章登场"
                f"{' · 别名：' + esc('、'.join(e['aliases'])) if e.get('aliases') else ''}</p>"
                f"<p class='desc'>{esc(e.get('desc'))}</p>{realm_html}{attrs}{rel_html}")
        (site / "character" / f"{e['id']}.html").write_text(
            page(e.get("name"), body, up=".."), encoding="utf-8")

    for p in d.get("places") or []:
        parent = next((x.get("name") for x in d["places"] if x.get("id") == p.get("parent")), None)
        body = (f"<p class='meta'>{esc('上级：' + parent) if parent else ''} · 第 {p.get('first_ch', '?')} 章</p>"
                f"<p class='desc'>{esc(p.get('desc'))}</p>")
        (site / "place" / f"{p['id']}.html").write_text(page(p.get("name"), body, up=".."), encoding="utf-8")

    for c in d.get("concepts") or []:
        rules = f"<h2>规则</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in c.get('rules') or [])}</ul>" if c.get("rules") else ""
        limits = f"<h2>限制</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in c.get('limits') or [])}</ul>" if c.get("limits") else ""
        body = (f"<p class='meta'>{esc(KIND_CN.get(c.get('kind'), c.get('kind')))} · 第 {c.get('first_ch', '?')} 章</p>"
                f"<p class='desc'>{esc(c.get('desc'))}</p>{rules}{limits}")
        (site / "concept" / f"{c['id']}.html").write_text(page(c.get("name"), body, up=".."), encoding="utf-8")

    return site


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--format", required=True,
                    choices=["fs", "md", "csv", "single", "site", "all"])
    ap.add_argument("--out", default="", help="默认 <dir>/export/")
    args = ap.parse_args()

    d = load(args.dir)
    out_dir = Path(args.out) if args.out else Path(args.dir) / "export"
    out_dir.mkdir(parents=True, exist_ok=True)

    formats = ["fs", "md", "csv", "single", "site"] if args.format == "all" else [args.format]
    made = []
    for f in formats:
        if f == "fs":
            made.append(export_fs(d, out_dir))
        elif f == "md":
            made.append(export_md(d, out_dir))
        elif f == "csv":
            made.append(export_csv(d, out_dir))
        elif f == "single":
            made.append(export_single(d, out_dir))
        elif f == "site":
            made.append(export_site(d, out_dir))

    for p in made:
        if p.is_dir():
            n = sum(1 for _ in p.rglob("*.html"))
            print(f"{p}/（{n} 个页面）")
        else:
            print(f"{p}（{p.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
