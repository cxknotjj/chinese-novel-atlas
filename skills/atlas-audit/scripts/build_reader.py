#!/usr/bin/env python3
"""build_reader.py — 生成读者向世界档案页面 / 静态站。

用法：
    python scripts/build_reader.py --data samples/fictional/data.json --out demo/reader/
    python scripts/build_reader.py --data output/凡人修仙传/data.json --out output/凡人修仙传/reader/ --external
    python scripts/build_reader.py --data ... --out ... --cutoff 120 --single
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_atlas.reader.publish import build_reader  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="index.html")
    ap.add_argument("--cutoff", type=int, default=None,
                    help="冻结到第 N 章；默认输出已分析到的最大章节")
    ap.add_argument("--single", action="store_true", help="单文件 HTML（不外链 data.js）")
    ap.add_argument("--snapshot", action="store_true", help="同时写 versions/vN.json")
    ap.add_argument("--label", default="")
    ap.add_argument("--allow-partial", action="store_true",
                    help="允许未 100% 覆盖的档案（样书/试读）；默认发布要求全书覆盖")
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    result = build_reader(data, args.out, name=args.name, cutoff=args.cutoff,
                          external=not args.single, snapshot=args.snapshot, label=args.label,
                          require_complete=not args.allow_partial)
    m = result["manifest"]
    print(f"输出    {result['entry']}")
    print(f"读者进度 第 {m['reader']['cutoff_ch']} / {m['reader']['chapter_max']} 章"
          f"（全书 {m['reader']['total_chapters']} 章）")
    print(f"疑点    {m['anomalies']['visible']} / {m['anomalies']['total']} 条可见；地图 {m['map_levels']['global']}")
    print(f"规模    {m['counts']}")
    if result["stdout"]:
        print(result["stdout"].rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
