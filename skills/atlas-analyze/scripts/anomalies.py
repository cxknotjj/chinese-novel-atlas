#!/usr/bin/env python3
"""anomalies.py — 生成读者向疑点索引。

用法：
    python scripts/anomalies.py --data output/凡人修仙传/data.json
    python scripts/anomalies.py --data samples/fictional/data.json --out samples/fictional/anomalies.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_atlas.reader.anomalies import build_anomalies  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--live", type=int, default=None)
    ap.add_argument("--cutoff", type=int, default=None,
                    help="只保留证据不晚于第 N 章的疑点，并按 N 作为 live 章")
    ap.add_argument("--list", action="store_true", help="打印疑点清单")
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    live = args.cutoff or args.live
    report = build_anomalies(data, live=live)
    if args.cutoff:
        from collections import Counter

        from novel_atlas.reader.publish import _anomaly_known
        report["anomalies"] = [a for a in report["anomalies"] if _anomaly_known(a, args.cutoff)]
        report["total"] = len(report["anomalies"])
        report["counts"] = dict(Counter(a.get("kind") for a in report["anomalies"]))
        report["cutoff_ch"] = args.cutoff
    out = Path(args.out) if args.out else Path(args.data).parent / "anomalies.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"疑点 {report['total']} 条 → {out}")
    for kind, n in sorted(report["counts"].items(), key=lambda x: -x[1]):
        print(f"  {kind:24s} {n}")
    if args.list:
        for a in report["anomalies"][:80]:
            print(f"- [{a['severity']}/{a['confidence']}] {a['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
