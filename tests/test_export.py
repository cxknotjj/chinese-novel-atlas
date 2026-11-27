"""导出层单元测试：共享状态计算与 Markdown/HTML 产物。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from novel_atlas.export.common import load, status_of  # noqa: E402
from novel_atlas.export.html import build_html  # noqa: E402
from novel_atlas.export.markdown import build_markdown  # noqa: E402


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load(ROOT / "samples" / "fictional")

    def test_status_semantics_are_shared(self):
        self.assertEqual(status_of({"status": "dropped"}, 200, 50), "dropped")
        self.assertEqual(status_of({"plant_ch": 1, "payoff_ch": 9}, 200, 50), "paid")
        self.assertEqual(status_of({"plant_ch": 1, "last_mention_ch": 190}, 200, 50), "planted")
        self.assertEqual(status_of({"plant_ch": 1}, 200, 50), "overdue")

    def test_markdown_contains_all_major_sections(self):
        md = build_markdown(self.data)
        self.assertIn("# 青云签到三十年 · 设定集", md)
        self.assertIn("## 伏笔台账", md)
        self.assertIn("## 地点", md)

    def test_html_is_self_contained(self):
        html = build_html(self.data)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("青云签到三十年", html)
        self.assertNotIn("<link rel=\"stylesheet\"", html)


if __name__ == "__main__":
    unittest.main()
