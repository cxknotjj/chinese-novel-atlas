"""build.py 图片内联机制回归测试：__ASSET__: 占位 → base64 data URI。

不依赖真实 1MB 资产：用 tempfile 造 mini 模板与假图片字节。
运行：
    python -m unittest discover -s tests -v
"""

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402

WEBP_BYTES = b"WEBP-FAKE-PAYLOAD-0001"
PNG_BYTES = b"\x89PNG\r\n\x1a\nFAKE-PNG"
JPG_BYTES = b"\xff\xd8\xffFAKE-JPEG"


class InlineAssetTest(unittest.TestCase):
    def _make_template(self, tmp, css_body="", js_body="", html_body=""):
        """造一个 mini 模板目录：viewer.html / viewer.css / viewer.js / assets。"""
        tpl_dir = Path(tmp) / "tpl"
        assets = tpl_dir / "assets" / "map" / "web"
        assets.mkdir(parents=True)
        html = (
            "<!DOCTYPE html>\n"
            "<style>/*__ATLAS_CSS__*/</style>\n"
            "<body>" + html_body + "</body>\n"
            '<script src="./data.js"></script>\n'
            "<script>/*__ATLAS_JS__*/</script>"
        )
        (tpl_dir / "viewer.html").write_text(html, encoding="utf-8")
        (tpl_dir / "viewer.css").write_text(css_body, encoding="utf-8")
        (tpl_dir / "viewer.js").write_text(js_body, encoding="utf-8")
        return tpl_dir / "viewer.html", assets

    def _write_asset(self, assets, name, data):
        (assets / name).write_bytes(data)

    # 1. 单张 webp：data URI 前缀正确、占位消失、base64 解回原字节。
    def test_webp_inline_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, assets = self._make_template(tmp)
            self._write_asset(assets, "foo.webp", WEBP_BYTES)
            out = build.inline_images('<img src="__ASSET__:map/web/foo.webp">', tpl)

            self.assertIn("data:image/webp;base64,", out)
            self.assertNotIn("__ASSET__:", out)
            payload = out.split("data:image/webp;base64,", 1)[1]
            payload = payload.split('"', 1)[0]
            self.assertEqual(base64.b64decode(payload), WEBP_BYTES)

    # 2. png / jpg 后缀映射到正确 mime。
    def test_mime_png_and_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, assets = self._make_template(tmp)
            self._write_asset(assets, "a.png", PNG_BYTES)
            self._write_asset(assets, "a.jpg", JPG_BYTES)
            text = ("__ASSET__:map/web/a.png __ASSET__:map/web/a.jpg")
            out = build.inline_images(text, tpl)

            self.assertIn("data:image/png;base64,", out)
            self.assertIn("data:image/jpeg;base64,", out)
            self.assertNotIn("__ASSET__:", out)

    # 3. 同一占位出现两次：sub 全替换，不是只换一次。
    def test_placeholder_replaced_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, assets = self._make_template(tmp)
            self._write_asset(assets, "foo.webp", WEBP_BYTES)
            text = "__ASSET__:map/web/foo.webp __ASSET__:map/web/foo.webp"
            out = build.inline_images(text, tpl)

            self.assertEqual(out.count("data:image/webp;base64,"), 2)
            self.assertNotIn("__ASSET__:", out)

    # 4. 缺图 → SystemExit，消息含「找不到占位图片」。
    def test_missing_image_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, _ = self._make_template(tmp)
            with self.assertRaisesRegex(SystemExit, "找不到占位图片"):
                build.inline_images("__ASSET__:map/web/nope.webp", tpl)

    # 5. 未知后缀（.bmp）→ SystemExit。
    def test_unknown_suffix_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, assets = self._make_template(tmp)
            self._write_asset(assets, "bad.bmp", b"BMFAKE")
            with self.assertRaisesRegex(SystemExit, "不认识的图片格式"):
                build.inline_images("__ASSET__:map/web/bad.bmp", tpl)

    # 6. CSS 里 url("__ASSET__:...") 引号内占位也能命中正则并替换。
    def test_css_url_placeholder_inlined(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = 'body { background: url("__ASSET__:map/web/paper-grain.webp"); }'
            tpl, assets = self._make_template(tmp, css_body=css)
            self._write_asset(assets, "paper-grain.webp", WEBP_BYTES)
            tpl_text = (tpl.parent / "viewer.html").read_text(encoding="utf-8")
            out = build.inline_assets(tpl_text, tpl)

            self.assertIn("data:image/webp;base64,", out)
            self.assertNotIn("__ASSET__:", out)

    # 7. 模块入口：按文件名顺序拼接 viewer/*.js，且保留单入口的 IIFE。
    def test_viewer_modules_joined_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, _ = self._make_template(
                tmp,
                js_body="(function () {\n  // __VIEWER_MODULES__\n})();",
            )
            module_dir = tpl.parent / "viewer"
            module_dir.mkdir()
            (module_dir / "00-foundation.js").write_text("const A = 'foundation';\n", encoding="utf-8")
            (module_dir / "10-map.js").write_text("const B = 'map';\n", encoding="utf-8")
            js = build.load_viewer_source(tpl)
            self.assertIn("const A = 'foundation';", js)
            self.assertIn("const B = 'map';", js)
            self.assertLess(js.index("const A"), js.index("const B"))
            self.assertNotIn("__VIEWER_MODULES__", js)
            self.assertTrue(js.startswith("(function () {"))

    # 8. 不含模块占位的老模板仍按单文件读取。
    def test_plain_viewer_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, _ = self._make_template(tmp, js_body="window.PLAIN = true;")
            self.assertEqual(build.load_viewer_source(tpl), "window.PLAIN = true;")

    # 9. 完整主流程冒烟：mini 模板 + mini data.json → 单文件 HTML，
    #    无残留占位、无 data.js 外链。
    def test_build_smoke_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = '<img src="__ASSET__:map/web/foo.webp">'
            css = 'body { background: url("__ASSET__:map/web/foo.webp"); }'
            tpl, assets = self._make_template(tmp, css_body=css, html_body=body)
            self._write_asset(assets, "foo.webp", WEBP_BYTES)

            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            data_json = data_dir / "data.json"
            data_json.write_text(json.dumps({
                "meta": {"title": "测试书"},
                "entities": [], "chapters": [], "foreshadows": [],
            }, ensure_ascii=False), encoding="utf-8")
            out_dir = Path(tmp) / "out"

            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build.py"),
                 "--data", str(data_json), "--out", str(out_dir),
                 "--template", str(tpl), "--skip-validate"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0,
                             f"构建失败：{proc.stderr or proc.stdout}")

            html = (out_dir / "atlas.html").read_text(encoding="utf-8")
            self.assertNotIn("__ASSET__:", html)
            self.assertNotIn('src="./data.js"', html)
            self.assertIn("data:image/webp;base64,", html)

    # 10. 反向保护：缺图占位 / 正则未命中的残留占位，构建都必须非零退出。
    def test_build_rejects_missing_or_leftover(self):
        cases = {
            # 路径不存在：替换阶段直接失败
            "missing": '__img src="__ASSET__:map/web/nope.webp">',
            # 冒号后是正则字符集外的字符，占位原样残留，走构建后守门
            "leftover": '__img src="__ASSET__:!nope.png">',
        }
        for name, body in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                tpl, assets = self._make_template(tmp, html_body=body)
                self._write_asset(assets, "foo.webp", WEBP_BYTES)
                data_dir = Path(tmp) / "data"
                data_dir.mkdir()
                data_json = data_dir / "data.json"
                data_json.write_text(json.dumps(
                    {"meta": {"title": "测试书"}}, ensure_ascii=False),
                    encoding="utf-8")
                out_dir = Path(tmp) / "out"

                proc = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "build.py"),
                     "--data", str(data_json), "--out", str(out_dir),
                     "--template", str(tpl), "--skip-validate"],
                    capture_output=True, text=True, encoding="utf-8")
                self.assertNotEqual(proc.returncode, 0,
                                    f"{name} 场景不应构建成功")
                combined = proc.stdout + proc.stderr
                self.assertTrue(
                    "找不到占位图片" in combined or "未替换" in combined,
                    f"{name} 场景缺少守门报错：{combined}")

    # 快速核验真实资产：base-clean.webp 内联后能解回原始字节（不写入仓库）。
    def test_real_asset_roundtrip(self):
        real = ROOT / "template" / "assets" / "map" / "web" / "base-clean.webp"
        if not real.exists():
            self.skipTest("真实资产尚未就位")
        tpl = ROOT / "template" / "viewer.html"
        raw = real.read_bytes()
        out = build.inline_images("__ASSET__:map/web/base-clean.webp", tpl)

        self.assertIn("data:image/webp;base64,", out)
        payload = out.split("data:image/webp;base64,", 1)[1]
        self.assertEqual(base64.b64decode(payload), raw)
        self.assertGreater(len(out), len(raw))


    # 11. link 模式：占位改成相对路径，并把素材拷到 <out>/assets/。
    def test_link_mode_copies_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, assets = self._make_template(tmp)
            self._write_asset(assets, "foo.webp", WEBP_BYTES)
            out_dir = Path(tmp) / "site"

            text = build.inline_images('src="__ASSET__:map/web/foo.webp"', tpl,
                                       "link", out_dir)
            self.assertIn('src="assets/map/web/foo.webp"', text)
            self.assertNotIn("data:image/webp;base64,", text)
            self.assertNotIn("__ASSET__:", text)
            copied = out_dir / "assets" / "map" / "web" / "foo.webp"
            self.assertTrue(copied.exists(), "素材应被拷到输出目录")
            self.assertEqual(copied.read_bytes(), WEBP_BYTES)

    # 12. link 模式的完整构建：首屏 HTML 里不应再有任何 base64 素材。
    def test_link_mode_build_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = '<img src="__ASSET__:map/web/foo.webp">'
            tpl, assets = self._make_template(tmp, html_body=body)
            self._write_asset(assets, "foo.webp", WEBP_BYTES)
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            data_json = data_dir / "data.json"
            data_json.write_text(json.dumps(
                {"meta": {"title": "测试书"}, "entities": [], "chapters": [],
                 "foreshadows": []}, ensure_ascii=False), encoding="utf-8")
            out_dir = Path(tmp) / "out"

            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build.py"),
                 "--data", str(data_json), "--out", str(out_dir),
                 "--template", str(tpl), "--skip-validate", "--assets", "link"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

            html = (out_dir / "atlas.html").read_text(encoding="utf-8")
            self.assertNotIn("data:image/webp;base64,", html)
            self.assertIn("assets/map/web/foo.webp", html)
            self.assertTrue((out_dir / "assets" / "map" / "web" / "foo.webp").exists())


if __name__ == "__main__":
    unittest.main()
