#!/usr/bin/env python3
"""snapshot.py — 世界模型版本快照 / 重跑对比。

    python scripts/snapshot.py --data output/凡人修仙传/data.json --label 500章
    python scripts/snapshot.py --diff output/凡人修仙传/versions/v1.json output/凡人修仙传/versions/v2.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_atlas.reader.versions import create_snapshot, diff_snapshots  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="data.json 路径")
    ap.add_argument("--out", default="", help="版本目录；默认 data 所在目录")
    ap.add_argument("--label", default="")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"))
    args = ap.parse_args()

    if args.diff:
        d = diff_snapshots(*args.diff)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    if not args.data:
        ap.error("需要 --data 或 --diff")
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else Path(args.data).parent
    snap = create_snapshot(data, out, label=args.label)
    print(f"快照 v{snap['version']} → {snap['path']}")
    print(f"指纹 {snap['fingerprint'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
