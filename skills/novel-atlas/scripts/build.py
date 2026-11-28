#!/usr/bin/env python3
"""build.py — 把 data.json 注入视图模板，产出可双击打开的 atlas.html。

模板源码放在 template/：viewer.html 是页面骨架，viewer.css 负责样式，
viewer.js 只是很薄的入口；实际交互按职责拆在 template/viewer/*.js，
build 时按文件名顺序拼进入口 IIFE，再内联回单文件。demo 和每本书的
atlas.html 都由同一份源码生成，不再手工复制，避免模板分叉。

默认产出**单文件** HTML（数据内嵌，发给别人只用传一个文件）；
加 --external 则把数据写成同目录 data.js，HTML 只引用它——适合数据大、
要反复重建视图的场景。

用法：
    python scripts/build.py --data output/青云签到三十年/data.json --out output/青云签到三十年/
    python scripts/build.py --data samples/fictional/data.json --out demo/ --name index.html
    python scripts/build.py --data output/凡人修仙传/data.json --out output/凡人修仙传/ --external
"""

import argparse
import base64
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_TAG = '<script src="./data.js"></script>'
CSS_TAG = "/*__ATLAS_CSS__*/"
JS_TAG = "/*__ATLAS_JS__*/"
VIEWER_MODULE_TAG = "// __VIEWER_MODULES__"

# 图片占位：模板里写 __ASSET__:map/web/base-clean.webp，构建时换成 data URI。
# 路径相对 template/assets/，这样单文件 HTML 里不带任何外部图片依赖。
ASSET_RE = re.compile(r"__ASSET__:([A-Za-z0-9_./-]+)")
MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".gif": "image/gif"}
_inline_stats = {"count": 0, "bytes": 0, "files": []}


def inline_images(text, tpl_path, mode="inline", out_dir=None):
    """把 __ASSET__:<相对 template/assets/ 的路径> 换成 base64 data URI。

    mode="link" 时改成相对路径 assets/<rel>，并把文件拷到 out_dir/assets/。
    单文件交付仍然默认 inline；站点 demo 用 link——1.2MB 素材不必跟着首屏一起下载。
    """
    def repl(m):
        rel = m.group(1)
        src = tpl_path.parent / "assets" / rel
        if not src.exists():
            raise SystemExit(f"找不到占位图片 {rel}（应在 {tpl_path.parent / 'assets'} 下）")
        if mode == "link":
            if out_dir is None:
                raise SystemExit("link 模式必须提供 out_dir")
            dst = out_dir / "assets" / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            return f"assets/{rel}"
        mime = MIME.get(src.suffix.lower())
        if not mime:
            raise SystemExit(f"不认识的图片格式 {src.suffix}（{src}）")
        raw = src.read_bytes()
        _inline_stats["count"] += 1
        _inline_stats["bytes"] += len(raw)
        _inline_stats["files"].append((rel, len(raw)))
        return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")

    return ASSET_RE.sub(repl, text)


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load_viewer_source(tpl_path):
    """读取薄入口 viewer.js；若入口含模块占位，则按文件名拼接 template/viewer/*.js。

    模块本身不带 IIFE，由入口统一包住，保证所有模块共享同一份闭包状态。
    这样源码可以按职责拆分，产物仍然是单文件、单 script。
    """
    js_path = tpl_path.parent / "viewer.js"
    if not js_path.exists():
        raise SystemExit(f"找不到交互源 {js_path}")
    js = js_path.read_text(encoding="utf-8")
    if VIEWER_MODULE_TAG not in js:
        return js
    module_dir = tpl_path.parent / "viewer"
    modules = sorted(module_dir.glob("*.js"))
    if not modules:
        raise SystemExit(f"入口含模块占位，但 {module_dir} 下没有 .js 模块")
    body = "\n\n".join(p.read_text(encoding="utf-8") for p in modules)
    return js.replace(VIEWER_MODULE_TAG, body, 1)


def inline_assets(tpl, tpl_path, mode="inline", out_dir=None):
    """把模板目录里的 viewer.css / viewer.js 组装并内联回 HTML 骨架。"""
    if CSS_TAG in tpl:
        css_path = tpl_path.parent / "viewer.css"
        if not css_path.exists():
            raise SystemExit(f"找不到样式源 {css_path}")
        css = css_path.read_text(encoding="utf-8")
        tpl = tpl.replace(CSS_TAG, inline_images(css, tpl_path, mode, out_dir), 1)
    if JS_TAG in tpl:
        js = load_viewer_source(tpl_path)
        tpl = tpl.replace(JS_TAG, inline_images(js, tpl_path, mode, out_dir), 1)
    return inline_images(tpl, tpl_path, mode, out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="data.json 路径")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--name", default="atlas.html", help="输出文件名")
    ap.add_argument("--template", default=str(ROOT / "template" / "viewer.html"))
    ap.add_argument("--external", action="store_true",
                    help="数据写成 data.js 外链，而不是内嵌")
    ap.add_argument("--assets", choices=["inline", "link"], default="inline",
                    help="素材处理：inline 内嵌 base64（单文件，默认）；"
                         "link 写相对路径并拷到 <out>/assets/（站点 demo 用，首屏小 1.5MB）")
    ap.add_argument("--strict", action="store_true",
                    help="把校验警告也视为失败")
    ap.add_argument("--skip-validate", action="store_true",
                    help="跳过构建前的 data.json 契约校验（仅用于临时预览）")
    args = ap.parse_args()

    data = load_json(args.data)
    if not args.skip_validate:
        # 构建前先过契约校验，避免把引用错误的数据直接发给读者
        sys.path.insert(0, str(ROOT / "scripts"))
        from validate import Report, validate as validate_data
        rep = Report()
        validate_data(data, rep)
        if rep.errors:
            for rule, msg in rep.errors[:12]:
                print(f"  ✗ [{rule}] {msg}", file=sys.stderr)
            if len(rep.errors) > 12:
                print(f"  ✗ …另有 {len(rep.errors) - 12} 条错误", file=sys.stderr)
            raise SystemExit(f"data.json 校验失败（{len(rep.errors)} 个错误），"
                             "修好数据或加 --skip-validate 后再构建")
        if args.strict and rep.warnings:
            for rule, msg in rep.warnings[:8]:
                print(f"  ! [{rule}] {msg}", file=sys.stderr)
            raise SystemExit(f"严格模式：data.json 有 {len(rep.warnings)} 条警告")
    tpl_path = Path(args.template)
    if not tpl_path.exists():
        raise SystemExit(f"找不到模板 {tpl_path}")

    # --out 既接受目录也接受完整文件路径：以 .html 结尾就当文件名。
    # 之前只认目录，传 path/to/atlas.html 会试图把它建成目录并崩掉。
    out_arg = Path(args.out)
    if out_arg.suffix.lower() in (".html", ".htm"):
        out_dir, out_name = out_arg.parent, out_arg.name
    else:
        out_dir, out_name = out_arg, args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    tpl = tpl_path.read_text(encoding="utf-8")
    tpl = inline_assets(tpl, tpl_path, args.assets, out_dir)

    if DATA_TAG not in tpl:
        raise SystemExit(f"模板里找不到数据占位 {DATA_TAG}，请检查 {tpl_path}")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")      # 防止正文里的 </script> 截断

    out_file = out_dir / out_name

    if args.external:
        (out_dir / "data.js").write_text(
            "/* 由 scripts/build.py 生成，勿手改 */\n"
            f"window.ATLAS_DATA = {payload};\n", encoding="utf-8")
        html = tpl
    else:
        inline = ("<script>\n/* 由 scripts/build.py 内嵌生成，勿手改 */\n"
                  f"window.ATLAS_DATA = {payload};\n</script>")
        html = tpl.replace(DATA_TAG, inline)
        # 顺手清掉旧外链数据，避免"到底读的是哪份"的歧义
        stale = out_dir / "data.js"
        if stale.exists():
            stale.unlink()

    html = re.sub(r"<title>.*?</title>",
                  f"<title>{data['meta']['title']} · Novel Atlas</title>",
                  html, count=1)

    # 占位没被替换干净就直接失败，免得发出去的单文件缺图
    if "__ASSET__:" in html:
        raise SystemExit("构建后有未替换的 __ASSET__: 占位，请检查模板里的图片路径")

    out_file.write_text(html, encoding="utf-8")

    # 汇报关键指标，方便一眼判断这份视图值不值得发
    print(f"模板    {tpl_path}")
    print(f"数据    {args.data}")
    print(f"输出    {out_file}（{out_file.stat().st_size / 1024:.1f} KB，"
          f"{'外链 data.js' if args.external else '单文件内嵌'}）")
    if _inline_stats["count"]:
        files = "、".join(f"{n}({b / 1024:.0f}KB)" for n, b in _inline_stats["files"])
        print(f"图片    内联 {_inline_stats['count']} 张 / 原始 {_inline_stats['bytes'] / 1024:.1f} KB"
              f"（base64 后约 {_inline_stats['bytes'] * 1.34 / 1024:.0f} KB）：{files}")
    print(f"内容    {data['meta']['title']} · {len(data.get('entities') or [])} 实体 · "
          f"{len(data.get('chapters') or [])} 章 · {len(data.get('foreshadows') or [])} 伏笔")
    expired = sum(1 for f in data.get("foreshadows") or [] if f.get("status") == "overdue")
    if expired:
        print(f"        其中 {expired} 条伏笔已超期")


if __name__ == "__main__":
    main()
