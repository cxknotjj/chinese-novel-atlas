#!/usr/bin/env python3
"""seek.py — 在已分章的原文里定位关键词，只返回命中位置和前后几段。

给 novel-atlas 的 ask 流程用的最后一步：结构化数据里查不到时，回原文找坐标，
但**不要把整章塞进上下文**。

坐标格式与 schema 一致：ch12:p8 = 第 12 章第 8 段（段 = 非空行）。

用法：
    python scripts/seek.py --dir output/凡人修仙传/ --keyword "小瓶" --context 2
    python scripts/seek.py --dir output/凡人修仙传/ --keyword "筑基" --chapter-range 50-100 --json
"""

import argparse
import json
import re
import sys
from pathlib import Path


def load_chapters(root):
    ch_dir = Path(root) / "chapters"
    if not ch_dir.exists():
        raise SystemExit(f"找不到 {ch_dir}，请先跑 scripts/chunk.py")
    out = []
    for f in ch_dir.glob("ch-*.txt"):
        m = re.search(r"ch-(\d+)", f.name)
        if m:
            out.append((int(m.group(1)), f))
    return sorted(out)


def paragraphs(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [(i + 1, ln.strip()) for i, ln in enumerate(lines) if ln.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--context", type=int, default=2, help="命中段前后各取几段")
    ap.add_argument("--limit", type=int, default=20, help="最多返回多少处命中")
    ap.add_argument("--chapter-range", default="", help="如 50-100")
    ap.add_argument("--ignore-case", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    lo, hi = 1, 10 ** 9
    if args.chapter_range:
        m = re.match(r"(\d+)\s*-\s*(\d+)", args.chapter_range)
        if not m:
            raise SystemExit("--chapter-range 格式应为 50-100")
        lo, hi = int(m.group(1)), int(m.group(2))

    needle = args.keyword.lower() if args.ignore_case else args.keyword
    hits = []
    for ch, path in load_chapters(args.dir):
        if not (lo <= ch <= hi):
            continue
        paras = paragraphs(path)
        for idx, (pno, text) in enumerate(paras):
            hay = text.lower() if args.ignore_case else text
            if needle not in hay:
                continue
            before = paras[max(0, idx - args.context):idx]
            after = paras[idx + 1:idx + 1 + args.context]
            hits.append({
                "coordinate": f"ch{ch}:p{pno}",
                "ch": ch, "p": pno,
                "text": text,
                "before": [t for _, t in before],
                "after": [t for _, t in after],
            })
            if len(hits) >= args.limit:
                break
        if len(hits) >= args.limit:
            break

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    else:
        print(f"「{args.keyword}」命中 {len(hits)} 处"
              + ("（已截断，用 --limit 调整）" if len(hits) >= args.limit else ""))
        for h in hits:
            print(f"\n— {h['coordinate']} —")
            for line in h["before"]:
                print(f"  … {line[:100]}")
            print(f"  ▸ {h['text']}")
            for line in h["after"]:
                print(f"  … {line[:100]}")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
