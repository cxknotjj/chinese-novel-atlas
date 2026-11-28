"""多页静态站导出（可挂 GitHub Pages）。"""

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
from .html import CSS, esc


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
