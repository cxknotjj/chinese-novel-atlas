#!/usr/bin/env python3
r"""atlas_map.py — Novel Atlas 地图渲染 skill 的统一入口。

只做四件事：审计 map_layout/atlas、输出 M0–M4 证据等级、准备网页底件、调用项目 build.py 出单文件页。
不生成像素地图，不猜坐标，不替代项目自带的 validate.py。

用法：
    python atlas_map.py info   --project-root D:\Desktop\project\chinese-novel-atlas
    python atlas_map.py audit  --project-root ... --data samples\fictional\data.json
    python atlas_map.py levels --project-root ... --data samples\fictional\data.json
    python atlas_map.py build  --project-root ... --data ... --out demo --name index.html
    python atlas_map.py prepare --project-root ...
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

MARKER_TYPES = {"city", "sect", "secret", "danger", "place", "none"}
ROUTE_KINDS = {"portal", "travel_path", "road", "river"}
REGION_SHAPES = {"land", "sea", "void"}


def find_project_root(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("NOVEL_ATLAS_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(Path.cwd())
    for cand in candidates:
        cand = cand.expanduser().resolve()
        for p in [cand, *cand.parents]:
            # atlas-kit/base 是关键区分：skill 里也带了 manifest.json 与 scripts/build.py，
            # 但没有 21 件手绘素材，渲染会失败，所以不能把 skill 目录当项目根。
            if ((p / "atlas-kit" / "manifest.json").is_file()
                    and (p / "atlas-kit" / "base").is_dir()
                    and (p / "scripts" / "build.py").is_file()):
                return p
    raise SystemExit(
        "找不到 Novel Atlas 项目根：需要同时包含 atlas-kit/manifest.json、"
        "atlas-kit/base/ 与 scripts/build.py。\n"
        "地图渲染依赖 20MB 手绘素材，无法随 skill 分发，请 clone 仓库后指定：\n"
        "  git clone https://github.com/cxknotjj/chinese-novel-atlas.git\n"
        "  或设置 NOVEL_ATLAS_ROOT=<仓库根>"
    )


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"找不到文件：{path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 解析失败：{path}: {exc}")


def atlas_asset_ids(root: Path) -> tuple[set[str], set[str]]:
    kit = load_json(root / "atlas-kit" / "manifest.json")
    png_ids = {
        a["id"] for a in kit.get("assets", []) if a.get("media") == "png"
    }
    support_ids = {a["id"] for a in kit.get("support_assets", [])}
    web_path = root / "template" / "assets" / "map" / "atlas" / "manifest.json"
    if web_path.is_file():
        web = load_json(web_path)
        png_ids |= {a["id"] for a in web.get("assets", [])}
        support_ids |= {a["id"] for a in web.get("support_assets", [])}
    return png_ids, support_ids


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def in_pct(v) -> bool:
    return is_num(v) and 0 <= v <= 100


def audit_data(data: dict, root: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {}

    ml = data.get("map_layout")
    if not isinstance(ml, dict):
        errors.append("缺少 map_layout（对象）")
        return {"errors": errors, "warnings": warnings, "stats": stats}

    if ml.get("mode") != "schematic":
        errors.append("map_layout.mode 必须是 schematic")
    if ml.get("canvas") != [100, 100]:
        errors.append("map_layout.canvas 必须是 [100,100]")
    note = ml.get("note") or ""
    if not isinstance(note, str) or len(note) > 120 or ("示意" not in note and "非经纬度" not in note):
        errors.append("map_layout.note 必须 ≤120 字并含「示意/非经纬度」")

    places = {p.get("id") for p in data.get("places", []) if p.get("id")}
    regions = ml.get("regions") if isinstance(ml.get("regions"), list) else []
    nodes = ml.get("nodes") if isinstance(ml.get("nodes"), list) else []
    routes = ml.get("routes") if isinstance(ml.get("routes"), list) else []
    atlas = ml.get("atlas") if isinstance(ml.get("atlas"), dict) else {}
    if ml.get("atlas") is not None and not isinstance(ml.get("atlas"), dict):
        errors.append("map_layout.atlas 必须是对象")

    region_ids: set[str] = set()
    region_layers: set[str] = set()
    for i, r in enumerate(regions):
        where = f"regions[{i}]"
        if not isinstance(r, dict):
            errors.append(f"{where} 不是对象")
            continue
        rid = r.get("id")
        if not isinstance(rid, str) or not rid.startswith("r_"):
            errors.append(f"{where}.id 必须以 r_ 开头")
        elif rid in region_ids:
            errors.append(f"{where}.id 重复：{rid}")
        else:
            region_ids.add(rid)
        if not r.get("name"):
            errors.append(f"{where}.name 不能为空")
        if r.get("shape") not in REGION_SHAPES:
            errors.append(f"{where}.shape 必须是 land/sea/void")
        poly = r.get("polygon")
        if not isinstance(poly, list) or len(poly) < 3 or not all(
            isinstance(p, list) and len(p) == 2 and in_pct(p[0]) and in_pct(p[1]) for p in poly
        ):
            errors.append(f"{where}.polygon 至少 3 个 0–100 的 [x,y] 点")
        la = r.get("label_at")
        if la is not None and not (isinstance(la, list) and len(la) == 2 and in_pct(la[0]) and in_pct(la[1])):
            errors.append(f"{where}.label_at 必须是 0–100 的 [x,y]")
        layer = r.get("layer")
        if layer:
            if layer not in places:
                errors.append(f"{where}.layer 指向不存在的 place：{layer}")
            else:
                region_layers.add(layer)

    node_places: set[str] = set()
    node_layers: set[str] = set()
    for i, n in enumerate(nodes):
        where = f"nodes[{i}]"
        if not isinstance(n, dict):
            errors.append(f"{where} 不是对象")
            continue
        place = n.get("place")
        if place not in places:
            errors.append(f"{where}.place 不存在：{place}")
        if place in node_places:
            errors.append(f"{where}.place 重复：{place}")
        node_places.add(place)
        if not in_pct(n.get("x")) or not in_pct(n.get("y")):
            errors.append(f"{where}.x / y 必须是 0–100")
        if n.get("rank", 2) not in (1, 2, 3):
            errors.append(f"{where}.rank 必须是 1/2/3")
        if "label" in n and not isinstance(n["label"], bool):
            errors.append(f"{where}.label 必须是布尔")
        if n.get("layer"):
            if n["layer"] not in places:
                errors.append(f"{where}.layer 指向不存在的 place：{n['layer']}")
            else:
                node_layers.add(n["layer"])

    terrain = ml.get("terrain")
    if terrain is not None and not isinstance(terrain, dict):
        errors.append("map_layout.terrain 必须是对象")
    if isinstance(terrain, dict):
        for i, islet in enumerate(terrain.get("islets", []) or []):
            if not isinstance(islet, dict) or not in_pct(islet.get("x")) or not in_pct(islet.get("y")):
                errors.append(f"terrain.islets[{i}] 必须是 {{x,y,r}} 对象且坐标 0–100")
            elif not is_num(islet.get("r")) or islet["r"] <= 0:
                errors.append(f"terrain.islets[{i}].r 必须是正数")

    for i, rt in enumerate(routes):
        where = f"routes[{i}]"
        if not isinstance(rt, dict):
            errors.append(f"{where} 不是对象")
            continue
        if rt.get("s") not in places or rt.get("t") not in places:
            errors.append(f"{where}.s/t 必须是已有 places id")
        if rt.get("kind") not in ROUTE_KINDS:
            errors.append(f"{where}.kind 必须是 portal/travel_path/road/river")

    if atlas:
        title = atlas.get("title")
        if title is not None:
            if not isinstance(title, dict):
                errors.append("atlas.title 必须是对象")
            else:
                if not title.get("text"):
                    errors.append("atlas.title.text 不能为空")
                if title.get("direction", "vertical") not in ("vertical", "horizontal"):
                    errors.append("atlas.title.direction 必须是 vertical/horizontal")
        seal = atlas.get("seal")
        if seal is not None:
            if not isinstance(seal, dict):
                errors.append("atlas.seal 必须是对象")
            else:
                ch = seal.get("ch")
                if not isinstance(ch, str) or len(ch) != 1 or ch.isspace():
                    errors.append("atlas.seal.ch 必须是单个非空白字符")
        compass = atlas.get("compass")
        if compass not in (None, False) and not isinstance(compass, dict):
            errors.append("atlas.compass 必须是对象或 false")
        if isinstance(compass, dict) and not (in_pct(compass.get("x")) and in_pct(compass.get("y"))):
            errors.append("atlas.compass.x/y 必须是 0–100")

        markers = atlas.get("markers", {})
        if markers is not None and not isinstance(markers, dict):
            errors.append("atlas.markers 必须是对象")
        elif isinstance(markers, dict):
            for place, kind in markers.items():
                if place not in places:
                    errors.append(f"atlas.markers 指向不存在的 place：{place}")
                if kind not in MARKER_TYPES:
                    errors.append(f"atlas.markers[{place}] 非法类型：{kind}")

        title_by_layer = atlas.get("titleByLayer", {})
        if title_by_layer is not None and not isinstance(title_by_layer, dict):
            errors.append("atlas.titleByLayer 必须是对象")
        elif isinstance(title_by_layer, dict):
            known_layers = region_layers | node_layers
            for layer, spec in title_by_layer.items():
                if layer not in known_layers:
                    warnings.append(f"atlas.titleByLayer 的层不在当前节点/区域里：{layer}")
                if not isinstance(spec, dict):
                    errors.append(f"atlas.titleByLayer[{layer}] 必须是对象")

        png_ids, support_ids = atlas_asset_ids(root)
        stamps = atlas.get("stamps", [])
        if stamps is not None and not isinstance(stamps, list):
            errors.append("atlas.stamps 必须是数组")
        elif isinstance(stamps, list):
            used_assets = set()
            for i, s in enumerate(stamps):
                where = f"atlas.stamps[{i}]"
                if not isinstance(s, dict):
                    errors.append(f"{where} 不是对象")
                    continue
                asset = s.get("asset")
                if asset not in png_ids:
                    errors.append(f"{where}.asset 不在 21 件网页资产：{asset}")
                else:
                    used_assets.add(asset)
                attach = s.get("attach")
                if attach:
                    if attach not in places:
                        errors.append(f"{where}.attach 指向不存在的 place：{attach}")
                    if attach not in node_places:
                        errors.append(f"{where}.attach 指向的 place 没有节点，无法定位：{attach}")
                else:
                    if not in_pct(s.get("x")) or not in_pct(s.get("y")):
                        errors.append(f"{where} 无 attach 时 x/y 必须是 0–100")
                if "w" in s and (not is_num(s["w"]) or s["w"] <= 0 or s["w"] > 100):
                    errors.append(f"{where}.w 必须是 (0,100] 的数字")
                if "opacity" in s and (not is_num(s["opacity"]) or not 0 <= s["opacity"] <= 1):
                    errors.append(f"{where}.opacity 必须在 0–1")
                layer = s.get("layer")
                if layer and layer not in (region_layers | node_layers):
                    warnings.append(f"{where}.layer 不在当前层集合：{layer}")
            stats["assets_used"] = len(used_assets)

        for key in ("seaTexture", "terrainStamps"):
            if key in atlas and not isinstance(atlas[key], bool):
                errors.append(f"atlas.{key} 必须是布尔")
        palette = atlas.get("palette")
        if palette is not None and not isinstance(palette, dict):
            errors.append("atlas.palette 必须是对象")

    stats.update({
        "regions": len(regions),
        "land": sum(1 for r in regions if isinstance(r, dict) and r.get("shape") == "land"),
        "sea": sum(1 for r in regions if isinstance(r, dict) and r.get("shape") == "sea"),
        "void": sum(1 for r in regions if isinstance(r, dict) and r.get("shape") == "void"),
        "nodes": len(nodes),
        "routes": len(routes),
        "stamps": len(atlas.get("stamps", []) or []),
        "has_atlas": bool(atlas),
    })
    return {"errors": errors, "warnings": warnings, "stats": stats}


def print_audit(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for key, value in report["stats"].items():
        print(f"  {key:<13} {value}")
    for msg in report["warnings"]:
        print(f"  ! {msg}")
    for msg in report["errors"]:
        print(f"  x {msg}")
    print(f"  {'结果':<13} {'通过' if not report['errors'] else '失败'} · 警告 {len(report['warnings'])} / 错误 {len(report['errors'])}")


def run_python(root: Path, script: str, extra: list[str]) -> None:
    path = root / script
    if not path.is_file():
        raise SystemExit(f"找不到项目脚本：{path}")
    cmd = [sys.executable, str(path), *extra]
    print("  $ " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(root))


def cmd_info(args) -> None:
    root = find_project_root(args.project_root)
    png_ids, support_ids = atlas_asset_ids(root)
    web_manifest = root / "template" / "assets" / "map" / "atlas" / "manifest.json"
    print(f"project      {root}")
    print(f"atlas-kit    {len(png_ids)} raster assets")
    print(f"support      {len(support_ids)} assets")
    print(f"viewer       {root / 'template' / 'viewer.js'}")
    print(f"web manifest {'ok' if web_manifest.is_file() else 'missing'}")
    print(f"build        {root / 'scripts' / 'build.py'}")


def cmd_audit(args) -> None:
    root = find_project_root(args.project_root)
    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = (root / data_path).resolve()
    report = audit_data(load_json(data_path), root)
    print_audit(report, args.json)
    if report["errors"]:
        raise SystemExit(1)


def cmd_levels(args) -> None:
    root = find_project_root(args.project_root)
    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = (root / data_path).resolve()
    data = load_json(data_path)
    sys.path.insert(0, str(root / "scripts"))
    from novel_atlas.reader.cutoff import filter_data
    from novel_atlas.reader.map_levels import compute_map_levels

    if args.cutoff:
        data = filter_data(data, args.cutoff)
    print(json.dumps(compute_map_levels(data), ensure_ascii=False, indent=2))


def cmd_prepare(args) -> None:
    root = find_project_root(args.project_root)
    run_python(root, "scripts/prepare_atlas_web.py", [])


def cmd_build(args) -> None:
    root = find_project_root(args.project_root)
    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = (root / data_path).resolve()
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = (root / out_dir).resolve()

    report = audit_data(load_json(data_path), root)
    print_audit(report, False)
    if report["errors"]:
        raise SystemExit("审计失败，未构建。")

    web_manifest = root / "template" / "assets" / "map" / "atlas" / "manifest.json"
    if args.refresh_assets or not web_manifest.is_file():
        run_python(root, "scripts/prepare_atlas_web.py", [])

    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.name
    extra = ["--data", str(data_path), "--out", str(out_dir), "--name", name]
    if args.external:
        extra.append("--external")
    run_python(root, "scripts/build.py", extra)
    output = out_dir / name
    if not output.is_file():
        raise SystemExit(f"构建结束但找不到产物：{output}")
    print(f"  output       {output}")
    print(f"  bytes        {output.stat().st_size:,}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Novel Atlas 地图渲染 skill")
    ap.add_argument("--project-root", default=None, help="Novel Atlas 项目根（含 atlas-kit / scripts）")
    sub = ap.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="检查项目根与底件状态")
    p_info.set_defaults(func=cmd_info)

    p_audit = sub.add_parser("audit", help="审计 map_layout / atlas")
    p_audit.add_argument("--data", required=True, help="data.json 路径")
    p_audit.add_argument("--json", action="store_true", help="输出 JSON")
    p_audit.set_defaults(func=cmd_audit)

    p_levels = sub.add_parser("levels", help="输出 M0–M4 地图证据等级")
    p_levels.add_argument("--data", required=True, help="data.json 路径")
    p_levels.add_argument("--cutoff", type=int, default=None, help="按第 N 章截断后再分级")
    p_levels.set_defaults(func=cmd_levels)

    p_prepare = sub.add_parser("prepare", help="把 atlas-kit PNG 转成网页 webp")
    p_prepare.set_defaults(func=cmd_prepare)

    p_build = sub.add_parser("build", help="审计 + 准备底件 + 构建单文件页面")
    p_build.add_argument("--data", required=True, help="data.json 路径")
    p_build.add_argument("--out", required=True, help="输出目录")
    p_build.add_argument("--name", default="atlas.html", help="输出文件名，默认 atlas.html")
    p_build.add_argument("--external", action="store_true", help="数据外置为 data.js，不内联")
    p_build.add_argument("--refresh-assets", action="store_true", help="强制重转 21 件 webp")
    p_build.set_defaults(func=cmd_build)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
