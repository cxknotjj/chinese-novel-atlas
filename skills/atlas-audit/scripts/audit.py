#!/usr/bin/env python3
"""atlas-audit.py — 疑点索引的查看、复核、误报标记与联网线索核对。

不重新分析小说；只读 anomalies.json，复核结果写到 anomalies-verdicts.json。

用法：
    python <SKILL_DIR>/scripts/audit.py stats --data output/凡人修仙传/data.json
    python <SKILL_DIR>/scripts/audit.py list --data output/凡人修仙传/data.json --severity warning
    python <SKILL_DIR>/scripts/audit.py show --data output/凡人修仙传/data.json --id an_fs_xxx
    python <SKILL_DIR>/scripts/audit.py mark --data output/凡人修仙传/data.json --id an_fs_xxx --status verified --note "第73章已回收"

联网核对模式（可选，默认关闭）：
    python <SKILL_DIR>/scripts/audit.py --web --data output/凡人修仙传/data.json
        没有 review/web-leads.json 时：生成 review/web-questions.json/.md
        已有 review/web-leads.json 时：校验并汇总成 review/web-leads.md
    python <SKILL_DIR>/scripts/audit.py --web --data ... --leads review/web-leads.json

外部线索只是参考，不是原文证据，脚本绝不修改 data.json。

疑点文件默认取 data.json 同目录的 anomalies.json，由 <SKILL_DIR>/scripts/anomalies.py 生成。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERDICT_FILE = "anomalies-verdicts.json"


def find_project_root(start: Path | None = None) -> Path | None:
    """定位仓库根，仅用于解析相对路径。

    这个 skill 是独立安装的：用户手上可能只有 data.json，没有完整仓库。
    所以找不到时返回 None，由调用方退回「相对当前目录」解析，而不是直接失败。
    """
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "scripts" / "novel_atlas" / "reader" / "anomalies.py").exists():
            return p
        if (p / "scripts" / "novel_atlas" / "reader").is_dir():
            return p
    return None


def resolve(path_str: str, base: Path) -> Path:
    """相对路径先按项目根解析；项目根不存在就按当前目录解析。"""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def load_report(data_path: Path, anomalies_path: Path | None) -> tuple[dict, Path]:
    ap = anomalies_path or (data_path.parent / "anomalies.json")
    if not ap.exists():
        raise SystemExit(f"找不到疑点文件：{ap}\n先运行 scripts/anomalies.py --data {data_path}\n"
                         f"（anomalies.py 与本脚本同目录）")
    return json.loads(ap.read_text(encoding="utf-8")), ap


def load_verdicts(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"version": "1.0", "updated_at": None, "verdicts": {}}


def save_verdicts(path: Path, state: dict) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def evidence_text(a: dict) -> str:
    ev = a.get("evidence") or []
    return "；".join(f"{e.get('coordinate', '?')} {e.get('quote', '')[:50]}" for e in ev) or "无证据"


# ================= 联网核对（可选） =================
# 只允许核验「非剧情」字段：别名、类型、上级、术语、写法。
# 死亡/退场/结局/伏笔回收/战力终值一律不看，避免把外部资料的剧透带进档案。
WEB_ALLOWED_FIELDS = {"aliases", "type", "parent", "terminology", "spelling"}
WEB_RISK_LEVELS = {"none", "low", "medium", "high"}
WEB_POLICY = {
    "allowed_fields": sorted(WEB_ALLOWED_FIELDS),
    "blocked": "死亡、退场、结局、伏笔回收、战力终值等剧情字段",
    "evidence_rule": "外部线索不是原文证据，禁止自动写入 data.json",
    "source_rule": "每条线索至少 1 个 http(s) 来源，并带 retrieved_at",
    "spoiler_rule": "spoiler_risk=high 的线索会被隔离，不进入可参考区",
}

WEB_LEADS_SCHEMA = {
    "version": "1.0",
    "title": "书名",
    "searched_at": "2026-11-28T00:00:00+00:00",
    "leads": [{
        "id": "wl_001",
        "field": "aliases",
        "target_id": "e_xxx",
        "claim": "外部资料怎么说（只写非剧情信息）",
        "sources": [{"url": "https://example.com/wiki", "title": "站点名", "retrieved_at": "2026-11-28"}],
        "confidence": "low",
        "spoiler_risk": "none",
        "suggestion": "建议人工核对第 N 章的写法，再决定是否补 alias",
    }],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _index_records(data: dict) -> dict:
    idx = {}
    for key in ("entities", "places", "concepts", "foreshadows"):
        for item in data.get(key) or []:
            rid = item.get("id")
            if rid:
                idx[rid] = (key, item)
    return idx


def _rel_degree(data: dict) -> Counter:
    deg = Counter()
    for r in data.get("relations") or []:
        if r.get("s"):
            deg[r["s"]] += 1
        if r.get("t"):
            deg[r["t"]] += 1
    return deg


def build_web_questions(data: dict, anomalies: list[dict] | None = None, limit: int = 24) -> list[dict]:
    """从数据缺口生成「值得联网核对」的问题。只碰非剧情字段。"""
    title = (data.get("meta") or {}).get("title") or "这本书"
    idx = _index_records(data)
    deg = _rel_degree(data)
    out: list[dict] = []
    seen: set[str] = set()

    def add(field: str, target_id: str, question: str, query: str, why: str,
            risk: str = "none", related: list[str] | None = None):
        if target_id in seen or len(out) >= limit:
            return
        rec = idx.get(target_id)
        if not rec:
            return
        seen.add(target_id)
        out.append({
            "id": f"wq_{len(out) + 1:03d}",
            "field": field,
            "target": {"kind": rec[0], "id": target_id, "name": rec[1].get("name") or rec[1].get("content") or target_id},
            "related": related or [],
            "question": question,
            "search_query": query,
            "why": why,
            "spoiler_risk": risk,
        })

    # 1) 高连接、但没有别名的角色/势力：别名缺失会直接影响搜索与合并
    chars = [e for e in data.get("entities") or []
             if e.get("type") in ("character", "org") and not (e.get("aliases") or [])]
    # 人物优先：势力别名对搜索的帮助通常小于人物称号
    chars.sort(key=lambda e: (0 if e.get("type") == "character" else 1,
                              -deg.get(e["id"], 0), e.get("first_ch") or 99999, e.get("name") or ""))
    for e in chars[:8]:
        add("aliases", e["id"],
            f"《{title}》里的「{e['name']}」在通行资料中还有哪些别名/称号？档案目前没有记录。",
            f"{title} {e['name']} 别名 称号",
            "关系多但别名缺失，会漏搜、漏合并",
            "none")

    # 2) 已有的低置信别名候选：让外部资料帮忙确认是不是同一个人
    for a in anomalies or []:
        if a.get("kind") != "alias_candidate" or len(out) >= limit:
            continue
        ids = [i for i in (a.get("entities") or []) if i in idx]
        if len(ids) < 2:
            continue
        names = [idx[i][1].get("name") for i in ids]
        add("aliases", ids[0],
            f"《{title}》里 {' / '.join(names)} 是不是同一角色或势力？规则引擎只是候选，需要外部资料旁证。",
            f"{title} {' '.join(names)} 是同一人吗",
            "低置信别名候选，误合并会污染关系网",
            "low", related=names[1:])

    # 3) 无归属的根地点：只问早期出现的，避免外部资料带出后期版图变化
    roots = [p for p in data.get("places") or []
             if not p.get("parent") and not any(k in (p.get("attrs") or {})
                                               for k in ("所属", "门派", "势力", "所属势力"))]
    roots.sort(key=lambda p: (p.get("first_ch") or 99999, p.get("name") or ""))
    for p in roots[:6]:
        if (p.get("first_ch") or 99999) > 120:
            continue
        add("parent", p["id"],
            f"《{title}》第 {p.get('first_ch')} 章出现的「{p['name']}」属于哪个势力或上级地区？档案里没有归属。",
            f"{title} {p['name']} 属于 势力",
            "根地点没有归属，版图会留缺口",
            "low")

    # 4) 术语归类：只挑「功法/品阶」两类，确认不是把法宝写成功法
    concepts = [c for c in data.get("concepts") or [] if c.get("kind") in ("technique", "item_grade")]
    concepts.sort(key=lambda c: (c.get("first_ch") or 99999, c.get("name") or ""))
    for c in concepts[:6]:
        add("terminology", c["id"],
            f"《{title}》里的「{c['name']}」在通行资料里算{('功法' if c.get('kind') == 'technique' else '法宝/丹药/材料')}吗？档案当前归类是 {c.get('kind')}。",
            f"{title} {c['name']} 功法 法宝",
            "术语归类错了会影响百科与战力体系",
            "low")

    return out


def cmd_web_plan(data: dict, anomalies: list[dict], review_dir: Path, limit: int) -> int:
    title = (data.get("meta") or {}).get("title") or "这本书"
    questions = build_web_questions(data, anomalies, limit)
    review_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "version": "1.0",
        "title": title,
        "generated_at": _now(),
        "policy": WEB_POLICY,
        "leads_schema": WEB_LEADS_SCHEMA,
        "questions": questions,
    }
    jpath = review_dir / "web-questions.json"
    jpath.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = "\n".join(
        f"| {q['id']} | {q['target']['name']} | {q['field']} | {q['question']} | `{q['search_query']}` | {q['spoiler_risk']} |"
        for q in questions) or "| — | — | — | 没有需要外部核对的字段 | — | — |"
    md = f"""# 《{title}》联网核对清单

> 这是**外部线索**清单，不是原文证据，也不会自动写入 `data.json`。
> 只核验非剧情字段：{', '.join(WEB_POLICY['allowed_fields'])}；禁止核验：{WEB_POLICY['blocked']}。
> 网页资料容易剧透，搜索时只看词条首段，不要把结局、死亡、伏笔回收写进线索。

- 生成时间：{plan['generated_at']}
- 问题数：{len(questions)}（上限 {limit}）
- 下一步：逐条搜索后写入 `{review_dir.as_posix()}/web-leads.json`（schema 见 `web-questions.json` 的 `leads_schema`），
  再运行 `audit.py --web --data ... --leads ...` 汇总。

| # | 目标 | 字段 | 问题 | 建议检索词 | 剧透风险 |
|---|---|---|---|---|---|
{rows}
"""
    mpath = review_dir / "web-questions.md"
    mpath.write_text(md, encoding="utf-8")

    print(f"标题      {title}")
    print(f"问题      {len(questions)} 条（上限 {limit}）")
    print(f"清单      {jpath}")
    print(f"说明      {mpath}")
    print("下一步    由 agent 联网搜索，写 review/web-leads.json，再跑 --web 汇总")
    return 0


def _valid_time(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate_web_leads(data: dict, payload: dict) -> tuple[list[dict], list[dict]]:
    """校验外部线索：来源、目标、字段、剧透风险。返回 (可参考, 已隔离)。"""
    idx = _index_records(data)
    accepted, rejected = [], []
    for i, lead in enumerate(payload.get("leads") or [], 1):
        lid = lead.get("id") or f"wl_{i:03d}"
        errors: list[str] = []
        field = str(lead.get("field") or "")
        if field not in WEB_ALLOWED_FIELDS:
            errors.append(f"字段 {field or '（空）'} 不在允许列表 {sorted(WEB_ALLOWED_FIELDS)}")
        target_id = str(lead.get("target_id") or "")
        if target_id not in idx:
            errors.append(f"目标 {target_id or '（空）'} 不在 data.json 里")
        claim = str(lead.get("claim") or "").strip()
        if not claim:
            errors.append("缺少 claim（外部资料的说法）")
        elif len(claim) > 600:
            errors.append("claim 超过 600 字，像是整段复制，请压缩")
        sources = lead.get("sources") or []
        if not isinstance(sources, list) or not sources:
            errors.append("至少需要 1 个来源")
            sources = []
        for s in sources:
            if not isinstance(s, dict):
                errors.append("来源必须是对象")
                continue
            url = str(s.get("url") or "")
            if not re.match(r"^https?://", url):
                errors.append(f"来源 URL 不合法：{url or '（空）'}")
            if not _valid_time(s.get("retrieved_at")):
                errors.append("来源缺少合法的 retrieved_at（ISO 日期）")
        risk = str(lead.get("spoiler_risk") or "none").lower()
        if risk not in WEB_RISK_LEVELS:
            errors.append(f"spoiler_risk 不合法：{risk}")
        elif risk == "high":
            errors.append("剧透风险 high，按规则隔离")
        if errors:
            rejected.append({"id": lid, "target_id": target_id, "errors": errors})
        else:
            accepted.append(lead)
    return accepted, rejected


def cmd_web_report(data: dict, leads_path: Path, review_dir: Path) -> int:
    if not leads_path.exists():
        raise SystemExit(f"找不到外部线索文件：{leads_path}\n先跑 --web 生成问题清单，再由 agent 联网补全。")
    try:
        payload = json.loads(leads_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{leads_path} 不是合法 JSON：{e}")
    accepted, rejected = validate_web_leads(data, payload)
    title = (data.get("meta") or {}).get("title") or payload.get("title") or "这本书"
    idx = _index_records(data)

    def fmt(lead: dict) -> str:
        target = lead.get("target_id")
        rec = idx.get(target)
        tname = (rec[1].get("name") if rec else "") or str(target)
        sources = "\n".join(
            f"    - [{s.get('title') or s.get('url')}]({s.get('url')}) · {s.get('retrieved_at')}"
            for s in lead.get("sources") or [])
        lines = [f"- **[{lead.get('field')}] {tname}**（`{target}` · {lead.get('confidence') or 'low'} · 剧透 {lead.get('spoiler_risk') or 'none'}）",
                 f"  - 外部说法：{lead.get('claim')}"]
        if lead.get("suggestion"):
            lines.append(f"  - 建议：{lead.get('suggestion')}")
        lines.append("  - 来源：\n" + sources)
        return "\n".join(lines)

    body = "\n\n".join(fmt(x) for x in accepted) or "（没有可参考的线索）"
    blocked = "\n".join(
        f"- {r['id']} → {r['target_id'] or '?'}：{'；'.join(r['errors'])}"
        for r in rejected) or "（无）"
    md = f"""# 《{title}》外部线索（联网核对）

> **这些是外部资料的说法，不是原文证据；不会自动写入 `data.json`。**
> 确认后请手工改 `data.json`（别名/归属/术语），再跑 `merge.py` 与 `validate.py`。
> 本报告只覆盖非剧情字段：{', '.join(WEB_POLICY['allowed_fields'])}。

- 生成时间：{_now()}
- 线索：{len(accepted)} 条可参考 · {len(rejected)} 条已隔离
- 原始文件：`{leads_path.name}`

## 可参考（仍需人工核对）

{body}

## 已隔离（剧透风险 / 字段违规 / 来源不全）

{blocked}
"""
    review_dir.mkdir(parents=True, exist_ok=True)
    out = review_dir / "web-leads.md"
    out.write_text(md, encoding="utf-8")

    print(f"标题      {title}")
    print(f"线索      {len(accepted)} 条可参考 · {len(rejected)} 条已隔离")
    print(f"报告      {out}")
    print("提醒      外部线索不是原文证据；确认后手工改 data.json，再跑 validate")
    return 0


def cmd_stats(report: dict, verdicts: dict) -> int:
    items = report.get("anomalies") or []
    sev = Counter(a.get("severity") for a in items)
    conf = Counter(a.get("confidence") for a in items)
    verdict_counts = Counter(v.get("status") for v in verdicts.get("verdicts", {}).values())
    print(f"标题      {report.get('source_title')}")
    print(f"覆盖      {report.get('coverage')}")
    print(f"当前章    {report.get('live_ch')}  阈值 {report.get('threshold')}")
    print(f"疑点      {len(items)} 条")
    print(f"严重度    high={sev.get('high', 0)} warning={sev.get('warning', 0)} info={sev.get('info', 0)}")
    print(f"置信度    high={conf.get('high', 0)} medium={conf.get('medium', 0)} low={conf.get('low', 0)}")
    print(f"复核      verified={verdict_counts.get('verified', 0)} rejected={verdict_counts.get('rejected', 0)}")
    print("规则")
    for kind, n in sorted((report.get("counts") or {}).items(), key=lambda x: (-x[1], x[0])):
        print(f"  {kind:24s} {n}")
    return 0


def cmd_list(report: dict, verdicts: dict, args) -> int:
    items = report.get("anomalies") or []
    if args.kind:
        items = [a for a in items if a.get("kind") == args.kind]
    if args.severity:
        items = [a for a in items if a.get("severity") == args.severity]
    if args.confidence:
        items = [a for a in items if a.get("confidence") == args.confidence]
    if args.limit:
        items = items[: args.limit]
    for a in items:
        verdict = (verdicts.get("verdicts") or {}).get(a.get("id"), {})
        state = verdict.get("status") or "-"
        print(f"[{a.get('severity'):7s}/{a.get('confidence'):6s}/{state:9s}] {a.get('kind'):24s} {a.get('title')}")
        print(f"  id={a.get('id')} range={a.get('chapter_range')} {evidence_text(a)}")
    print(f"\n{len(items)} 条")
    return 0


def cmd_show(report: dict, verdicts: dict, args) -> int:
    for a in report.get("anomalies") or []:
        if a.get("id") == args.id:
            print(json.dumps(a, ensure_ascii=False, indent=2))
            v = (verdicts.get("verdicts") or {}).get(args.id)
            if v:
                print("\n人工复核：")
                print(json.dumps(v, ensure_ascii=False, indent=2))
            return 0
    raise SystemExit(f"找不到疑点：{args.id}")


def cmd_mark(report: dict, verdicts: dict, args, verdict_path: Path) -> int:
    if not any(a.get("id") == args.id for a in report.get("anomalies") or []):
        raise SystemExit(f"找不到疑点：{args.id}")
    verdicts.setdefault("verdicts", {})[args.id] = {
        "status": args.status,
        "note": args.note or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_verdicts(verdict_path, verdicts)
    print(f"已标记 {args.id} → {args.status}（{verdict_path}）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?",
                    choices=["stats", "list", "show", "mark", "web-plan", "web-report"],
                    default=None)
    ap.add_argument("--data", required=True, help="data.json 路径")
    ap.add_argument("--anomalies", default="", help="默认 data 同目录 anomalies.json")
    ap.add_argument("--project-root", default="")
    ap.add_argument("--web", action="store_true",
                    help="联网核对模式：没有 review/web-leads.json 时生成问题清单，有则汇总")
    ap.add_argument("--leads", default="", help="外部线索 JSON（默认 review/web-leads.json）")
    ap.add_argument("--id", default="")
    ap.add_argument("--status", choices=["verified", "rejected", "pending"], default="verified")
    ap.add_argument("--note", default="")
    ap.add_argument("--kind", default="")
    ap.add_argument("--severity", choices=["high", "warning", "info"], default="")
    ap.add_argument("--confidence", choices=["high", "medium", "low"], default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    root = find_project_root(Path(args.project_root) if args.project_root else None)
    base = root or Path.cwd()
    if root is None and args.project_root:
        raise SystemExit(f"找不到项目根：{args.project_root} 下没有 scripts/novel_atlas/reader/")

    data_path = resolve(args.data, base)
    anomalies_path = resolve(args.anomalies, base) if args.anomalies else data_path.parent / "anomalies.json"

    # ---- 联网核对模式：只读写 review/，不碰 data.json ----
    if args.web or args.command in ("web-plan", "web-report"):
        data = json.loads(data_path.read_text(encoding="utf-8"))
        anomalies = []
        if anomalies_path.exists():
            anomalies = json.loads(anomalies_path.read_text(encoding="utf-8")).get("anomalies") or []
        review_dir = anomalies_path.parent / "review"
        leads_path = resolve(args.leads, base) if args.leads else review_dir / "web-leads.json"
        if args.command == "web-report":
            return cmd_web_report(data, leads_path, review_dir)
        if args.command == "web-plan":
            return cmd_web_plan(data, anomalies, review_dir, args.limit or 24)
        # --web：先看有没有线索文件，没有就出问题清单
        if leads_path.exists():
            return cmd_web_report(data, leads_path, review_dir)
        return cmd_web_plan(data, anomalies, review_dir, args.limit or 24)

    if not args.command:
        ap.error("需要 command（stats/list/show/mark）或 --web")

    report, apath = load_report(data_path, anomalies_path)
    verdict_path = apath.parent / VERDICT_FILE
    verdicts = load_verdicts(verdict_path)

    if args.command == "stats":
        return cmd_stats(report, verdicts)
    if args.command == "list":
        return cmd_list(report, verdicts, args)
    if args.command == "show":
        if not args.id:
            raise SystemExit("show 需要 --id")
        return cmd_show(report, verdicts, args)
    if args.command == "mark":
        if not args.id:
            raise SystemExit("mark 需要 --id")
        return cmd_mark(report, verdicts, args, verdict_path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
