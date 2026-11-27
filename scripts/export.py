#!/usr/bin/env python3
"""把 data.json 导出成作者/读者能直接用的格式。

    fs      伏笔清单 CSV（作者改稿对照，最重要）
    md      Markdown 设定集
    csv     角色表 CSV
    single  单文件 HTML 设定集
    site    多页静态站（可挂 GitHub Pages）

用法：
    python scripts/export.py --dir output/青云签到三十年/ --format fs
    python scripts/export.py --dir output/青云签到三十年/ --format md
    python scripts/export.py --dir output/青云签到三十年/ --format csv
    python scripts/export.py --dir output/青云签到三十年/ --format single
    python scripts/export.py --dir output/青云签到三十年/ --format site

实现已拆到 `novel_atlas.export` 包；本文件只保留命令行入口。
"""

import argparse
from pathlib import Path

from novel_atlas.export.common import load
from novel_atlas.export.csv import export_csv, export_fs
from novel_atlas.export.html import export_single
from novel_atlas.export.markdown import export_md
from novel_atlas.export.site import export_site


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--format", required=True,
                    choices=["fs", "md", "csv", "single", "site", "all"])
    ap.add_argument("--out", default="", help="默认 <dir>/export/")
    args = ap.parse_args()

    d = load(args.dir)
    out_dir = Path(args.out) if args.out else Path(args.dir) / "export"
    out_dir.mkdir(parents=True, exist_ok=True)

    exporters = {
        "fs": export_fs,
        "md": export_md,
        "csv": export_csv,
        "single": export_single,
        "site": export_site,
    }
    formats = list(exporters) if args.format == "all" else [args.format]
    made = [exporters[f](d, out_dir) for f in formats]

    for p in made:
        if p.is_dir():
            n = sum(1 for _ in p.rglob("*.html"))
            print(f"{p}/（{n} 个页面）")
        else:
            print(f"{p}（{p.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
