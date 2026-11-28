"""GitHub Star 入口回归测试。

所有 atlas / reader 页面都由 template/viewer.html 生成；这里同时检查
模板源码、vendored skill 副本，以及仓库内已生成的 demo 页面。
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAR_URL = "https://github.com/cxknotjj/chinese-novel-atlas"
STAR_TEXT = "觉得好用的话，就给个 <b>Star</b> 吧"
STAR_LABEL = "觉得好用的话，就给个 Star 吧"


class GitHubStarTest(unittest.TestCase):
    def assert_star_entry(self, path: Path, label: str) -> None:
        self.assertTrue(path.exists(), f"缺少页面：{path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn(f'href="{STAR_URL}"', text, f"{label} 缺少仓库外链")
        self.assertIn('target="_blank"', text, f"{label} 外链应在新窗口打开")
        self.assertIn(STAR_TEXT, text, f"{label} 缺少 Star 引导文案")
        self.assertIn(STAR_LABEL, text, f"{label} 缺少无障碍标签")
        self.assertIn('class="gh-star-icon"', text, f"{label} 缺少 GitHub 图标")
        self.assertIn("M6.766 11.328", text, f"{label} 的 GitHub 图标路径不完整")
        self.assertIn("gh-star-strip", text, f"{label} 缺少 Star 入口样式")

    def test_shared_template_and_vendored_skill(self):
        for rel in (
            "template/viewer.html",
            "skills/novel-atlas/template/viewer.html",
        ):
            with self.subTest(path=rel):
                self.assert_star_entry(ROOT / rel, rel)

    def test_generated_demo_pages(self):
        for rel in (
            "demo/index.html",
            "demo/reader/index.html",
        ):
            path = ROOT / rel
            if path.exists():
                with self.subTest(path=rel):
                    self.assert_star_entry(path, rel)


if __name__ == "__main__":
    unittest.main()
