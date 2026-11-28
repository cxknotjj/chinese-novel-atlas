"""单文件 HTML 设定集导出（独立样式、无外部依赖）。"""

import html

from .common import (
    KIND_CN,
    REL_CN,
    STATUS_CN,
    degree_map,
    foresight_rows,
    meta_line,
    name_of,
    relations_of,
    realm_line,
)

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
