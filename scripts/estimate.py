#!/usr/bin/env python3
"""estimate.py — 开跑前估算章数、token、花费和耗时。

用法：
    python scripts/estimate.py "novals/某书.txt"
    python scripts/estimate.py output/青云签到三十年/ --limit 200
    python scripts/estimate.py "某书.txt" --price-in 1 --price-out 2 --concurrency 8

估算是为了做预算决策，不是精确账单；真实花费以接口返回的 usage 为准。
"""

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chunk as chunkmod  # noqa: E402


def from_dir(root, limit):
    meta_p = root / "chunk-meta.json"
    if not meta_p.exists():
        raise SystemExit(f"{root} 下没有 chunk-meta.json，先跑 chunk.py")
    import json
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    found = meta.get("chapters_found") or 0
    records = meta.get("chapters") or []
    total = len(records) if (limit or not found) else found
    if limit:
        records = records[:limit]
    if records:
        avg = sum(r.get("words") or 0 for r in records) / len(records)
        if limit or len(records) >= found:
            chars = sum(r.get("words") or 0 for r in records)
        else:                     # 只切了一部分，按已切章均值外推全书
            chars = int(avg * total)
    else:
        chars = meta.get("total_chars") or 0
    return total, chars, "chunk-meta"


def from_file(path, limit):
    text, enc = chunkmod.read_text(path)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    best, _ = chunkmod.detect(lines)
    if best:
        _, name, desc, hits, _ = best
        total = len(hits)
    else:
        total = max(1, len(text) // 3000)
        name, desc = "fallback", "按字数兜底"
    chars = len(re.sub(r"\s", "", text))
    if limit and total > limit:
        total = limit
    return total, chars, f"{name}（{desc}）/ {enc}"


def money(tokens, price):
    return tokens / 1e6 * price


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="txt 文件或已分章的书目录")
    ap.add_argument("--limit", type=int, default=0, help="只分析前 N 章")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--price-in", type=float, default=1.0, help="元 / 百万输入 token")
    ap.add_argument("--price-out", type=float, default=2.0, help="元 / 百万输出 token")
    ap.add_argument("--max-budget", type=float, default=5.0, help="超过这个数要显式确认")
    ap.add_argument("--sec-per-batch", type=float, default=45.0)
    args = ap.parse_args()

    p = Path(args.path)
    if p.is_dir():
        total, chars, src = from_dir(p, args.limit)
    elif p.is_file():
        total, chars, src = from_file(p, args.limit)
    else:
        raise SystemExit(f"找不到 {p}")

    batches = math.ceil(total / args.batch_size) if total else 0
    input_tokens = int(chars / 1.5) + batches * 2500
    output_tokens = batches * (1200 + args.batch_size * 60)
    cost = money(input_tokens, args.price_in) + money(output_tokens, args.price_out)
    minutes = batches / max(args.concurrency, 1) * args.sec_per_batch / 60

    print(f"识别方式    {src}")
    print(f"章节        {total:,} 章" + (f"（限前 {args.limit} 章）" if args.limit else ""))
    print(f"字数        {chars:,}")
    print(f"批次        {batches} 批（每批 ≤{args.batch_size} 章，{args.concurrency} 并发）")
    print(f"输入 token  ≈ {input_tokens / 1e4:.1f} 万")
    print(f"输出 token  ≈ {output_tokens / 1e3:.1f} k")
    print(f"预计花费    ≈ {cost:.2f} 元")
    print(f"预计耗时    ≈ {minutes:.0f} 分钟")
    if cost > args.max_budget:
        print(f"⚠ 超过预算线 {args.max_budget} 元，开跑前必须让用户确认")
    return 0


if __name__ == "__main__":
    sys.exit(main())
