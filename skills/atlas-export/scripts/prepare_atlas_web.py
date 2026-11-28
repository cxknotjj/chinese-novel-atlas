#!/usr/bin/env python3
"""prepare_atlas_web.py — 把 atlas-kit 的 21 件手绘 PNG 压成网页可内联的 webp。

源：atlas-kit/manifest.json + base/**
输出：template/assets/map/atlas/
     <asset_id>.webp        21 件地形 / 水 / 建筑 / 植被
     paper_ornate.webp     全幅纸底
     water_sea_01.webp     可选海面纹理
     ornament_*.webp       角饰 / 分隔
     manifest.json         网页侧资产索引（id / type / pivot / size / file）

网页只认 id，不认目录；这样 atlas-kit 内部结构怎么调整，viewer.js 都不用改。
转换保持 640×640 画布和 pivot，避免裁切后定位漂移。
"""

import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "atlas-kit"
OUT = ROOT / "template" / "assets" / "map" / "atlas"
QUALITY = 86


def to_webp(src: Path, dst: Path, quality=QUALITY):
    im = Image.open(src).convert("RGBA")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "WEBP", quality=quality, method=6)
    return dst.stat().st_size


def main():
    manifest = json.loads((KIT / "manifest.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    total_in = total_out = 0

    # 21 件基础 PNG：manifest 前 21 条即 raster 资产
    for asset in manifest.get("assets", []):
        if asset.get("media") != "png":
            continue
        src = KIT / asset["file"]
        dst = OUT / f"{asset['id']}.webp"
        total_in += src.stat().st_size
        size = to_webp(src, dst)
        total_out += size
        rows.append({
            "id": asset["id"],
            "name": asset.get("name", asset["id"]),
            "type": asset.get("type", "terrain"),
            "pivot": asset.get("pivot", [0.5, 0.875]),
            "size": asset.get("size", [640, 640]),
            "file": f"map/atlas/{dst.name}",
            "source": asset["file"],
            "bytes": size,
        })
        print(f"  {asset['id']:<22} {size / 1024:>6.1f} KB")

    # 可选支持资产：纸底、海纹、角饰、分隔
    support = []
    for item in manifest.get("support_assets", []):
        src = KIT / item["file"]
        if not src.exists():
            continue
        dst = OUT / f"{item['id']}.webp"
        total_in += src.stat().st_size
        size = to_webp(src, dst)
        total_out += size
        support.append({
            "id": item["id"],
            "name": item.get("name", item["id"]),
            "type": "support",
            "pivot": [0.5, 0.5],
            "size": item.get("size"),
            "file": f"map/atlas/{dst.name}",
            "source": item["file"],
            "bytes": size,
        })
        print(f"  {item['id']:<22} {size / 1024:>6.1f} KB")

    web_manifest = {
        "name": "atlas-kit web layer",
        "version": "0.2.0",
        "style": manifest.get("style"),
        "note": "21 件手绘 PNG 转 webp；路线 / 标记 / 罗盘 / 题签 / 印章由 viewer.js 代码绘制，不在此清单。",
        "quality": QUALITY,
        "asset_count": len(rows),
        "supported_count": len(support),
        "assets": rows,
        "support_assets": support,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(web_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n输出 {OUT}")
    print(f"原始 {total_in / 1024:.1f} KB → webp {total_out / 1024:.1f} KB "
          f"（{total_out / total_in * 100:.0f}%）")


if __name__ == "__main__":
    main()
