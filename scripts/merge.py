#!/usr/bin/env python3
"""把抽取批次合并为 schema v2.0 的 data.json。

实现已拆到 `novel_atlas.merge` 包；本文件只保留命令行入口。
"""

import argparse

from novel_atlas.merge.foreshadows import apply_status  # noqa: F401  (mentions.py 兼容)
from novel_atlas.merge.pipeline import merge_book


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", default="")
    ap.add_argument("--batches", default="", help="批次目录，默认 <dir>/out")
    ap.add_argument("--title", default="", help="覆盖书名（默认从源文件名解析）")
    ap.add_argument("--author", default="", help="覆盖作者")
    ap.add_argument("--genre", default="未标注")
    ap.add_argument("--platform", default="")
    ap.add_argument("--status", default="完结")
    ap.add_argument("--elapsed", type=int, default=0, help="处理耗时（秒），写入 meta.elapsed_sec")
    args = ap.parse_args()

    data, merge_log, out, stats = merge_book(
        args.dir,
        out=args.out,
        batches=args.batches,
        title=args.title,
        author=args.author,
        genre=args.genre,
        platform=args.platform,
        status=args.status,
        elapsed=args.elapsed,
    )

    print(f"\n实体    {stats['entities_in']} → {stats['entities_out']}（去重）")
    print(f"关系    {stats['relations_in']} → {stats['relations_out']}（去重）")
    print(f"章节    {stats['chapters_out']} / {stats['chapters_total']}"
          f"（覆盖 {stats['chapters_out'] / max(stats['chapters_total'], 1):.1%}）")
    print(f"伏笔    {stats['foreshadows_in']} → {stats['foreshadows_out']}（去重），"
          f"超期阈值 {stats['threshold']} 章")
    print(f"境界    {stats['realms']}")
    print(f"地点    {stats['places']}　设定 {stats['concepts']}")
    print(f"空间关系 {stats['spatial']} 条（新增地点 {stats['spatial_places']} 个）")
    if stats.get("spatial_nodes"):
        print(f"示意坐标 {stats['spatial_nodes']} 个节点 / {stats['spatial_regions']} 个区域")
    print(f"字数    {stats['chars']:,}")
    print(f"输出    {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
