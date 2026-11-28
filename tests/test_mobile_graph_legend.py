"""手机端图谱图例回归测试。

图例在手机上默认收起，只留一个「图例」按钮；展开后盖在画布上方，
且必须可滚动，避免 20 多个势力色块把整个图谱压没。
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MobileGraphLegendTest(unittest.TestCase):
    def assert_mobile_legend(self, base: Path, label: str) -> None:
        html = (base / "viewer.html").read_text(encoding="utf-8")
        css = (base / "viewer.css").read_text(encoding="utf-8")
        js = (base / "viewer" / "90-search-boot.js").read_text(encoding="utf-8")

        self.assertIn('id="legendToggle"', html, f"{label} 缺少手机端图例按钮")
        self.assertIn('aria-controls="legend"', html, f"{label} 图例按钮缺少 aria-controls")
        self.assertIn("classList.toggle('mobile-open')", js, f"{label} 图例按钮没有绑定展开状态")
        self.assertIn("#legend.mobile-open", css, f"{label} 缺少展开态样式")
        self.assertIn("max-height: 42vh", css, f"{label} 展开态没有限高/滚动")
        self.assertIn("overflow-y: auto", css, f"{label} 展开态不可滚动")

    def test_shared_template_and_vendored_skill(self):
        for rel in ("template", "skills/novel-atlas/template"):
            with self.subTest(path=rel):
                self.assert_mobile_legend(ROOT / rel, rel)

    def test_built_demo_pages(self):
        for rel in ("demo/index.html", "demo/reader/index.html"):
            path = ROOT / rel
            if not path.exists():
                continue
            with self.subTest(path=rel):
                text = path.read_text(encoding="utf-8")
                self.assertIn('id="legendToggle"', text, f"{rel} 未包含手机端图例按钮")
                self.assertIn("#legend.mobile-open", text, f"{rel} 未包含手机端图例样式")


if __name__ == "__main__":
    unittest.main()
