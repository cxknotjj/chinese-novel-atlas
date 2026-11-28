#!/usr/bin/env python3
"""atlas-audit.py — 疑点索引的查看、复核与误报标记。

不重新分析小说；只读 anomalies.json，复核结果写到 anomalies-verdicts.json。

用法：
    python <SKILL_DIR>/scripts/audit.py stats --data output/凡人修仙传/data.json
    python <SKILL_DIR>/scripts/audit.py list --data output/凡人修仙传/data.json --severity warning
    python <SKILL_DIR>/scripts/audit.py show --data output/凡人修仙传/data.json --id an_fs_xxx
    python <SKILL_DIR>/scripts/audit.py mark --data output/凡人修仙传/data.json --id an_fs_xxx --status verified --note "第73章已回收"

疑点文件默认取 data.json 同目录的 anomalies.json，由 <SKILL_DIR>/scripts/anomalies.py 生成。
"""

from __future__ import annotations

import argparse
import json
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
    ap.add_argument("command", choices=["stats", "list", "show", "mark"])
    ap.add_argument("--data", required=True, help="data.json 路径")
    ap.add_argument("--anomalies", default="", help="默认 data 同目录 anomalies.json")
    ap.add_argument("--project-root", default="")
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
