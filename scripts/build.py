#!/usr/bin/env python3
"""build.py — 把 data.json 注入视图模板，产出可双击打开的 atlas.html。

模板只有一份：template/viewer.html。demo 和每本书的 atlas.html 都由它生成，
不再手工复制，避免模板分叉。

默认产出**单文件** HTML（数据内嵌，发给别人只用传一个文件）；
加 --external 则把数据写成同目录 data.js，HTML 只引用它——适合数据大、
要反复重建视图的场景。

用法：
    python scripts/build.py --data output/青云签到三十年/data.json --out output/青云签到三十年/
    python scripts/build.py --data samples/fictional/data.json --out demo/ --name index.html
    python scripts/build.py --data output/凡人修仙传/data.json --out output/凡人修仙传/ --external
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_TAG = '<script src="./data.js"></script>'


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="data.json 路径")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--name", default="atlas.html", help="输出文件名")
    ap.add_argument("--template", default=str(ROOT / "template" / "viewer.html"))
    ap.add_argument("--external", action="store_true",
                    help="数据写成 data.js 外链，而不是内嵌")
    args = ap.parse_args()

    data = load_json(args.data)
    tpl_path = Path(args.template)
    if not tpl_path.exists():
        raise SystemExit(f"找不到模板 {tpl_path}")
    tpl = tpl_path.read_text(encoding="utf-8")

    if DATA_TAG not in tpl:
        raise SystemExit(f"模板里找不到数据占位 {DATA_TAG}，请检查 {tpl_path}")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")      # 防止正文里的 </script> 截断

    # --out 既接受目录也接受完整文件路径：以 .html 结尾就当文件名。
    # 之前只认目录，传 path/to/atlas.html 会试图把它建成目录并崩掉。
    out_arg = Path(args.out)
    if out_arg.suffix.lower() in (".html", ".htm"):
        out_dir, out_name = out_arg.parent, out_arg.name
    else:
        out_dir, out_name = out_arg, args.name

    out_dir.mkdir(parents=True, exist_ok=True)
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

    out_file.write_text(html, encoding="utf-8")

    # 汇报关键指标，方便一眼判断这份视图值不值得发
    print(f"模板    {tpl_path}")
    print(f"数据    {args.data}")
    print(f"输出    {out_file}（{out_file.stat().st_size / 1024:.1f} KB，"
          f"{'外链 data.js' if args.external else '单文件内嵌'}）")
    print(f"内容    {data['meta']['title']} · {len(data.get('entities') or [])} 实体 · "
          f"{len(data.get('chapters') or [])} 章 · {len(data.get('foreshadows') or [])} 伏笔")
    expired = sum(1 for f in data.get("foreshadows") or [] if f.get("status") == "overdue")
    if expired:
        print(f"        其中 {expired} 条伏笔已超期")


if __name__ == "__main__":
    main()
