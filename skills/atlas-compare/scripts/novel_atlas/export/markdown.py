"""Markdown 设定集导出。"""

from .common import (
    KIND_CN,
    REL_CN,
    STATUS_CN,
    degree_map,
    foresight_rows,
    hook_rate,
    meta_line,
    relations_of,
    realm_line,
    thrill_gap,
    name_of,
)


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
