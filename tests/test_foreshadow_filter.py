"""伏笔状态筛选回归护栏：点击统计卡只显示对应状态，且保留「全部」。"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "template" / "viewer"


class ForeshadowFilterTest(unittest.TestCase):
    def test_status_cards_filter_the_ledger(self):
        analysis = (VIEWER / "80-analysis.js").read_text(encoding="utf-8")
        css = (ROOT / "template" / "viewer.css").read_text(encoding="utf-8")

        for status in ("all", "overdue", "planted", "paid", "dropped"):
            self.assertIn(f'data-fs-filter="{status}"', analysis,
                          f"缺少 {status} 统计卡")
        self.assertIn("fsFilter === 'all'", analysis)
        self.assertIn("FORESHADOWS.filter(f => fsStatus(f) === fsFilter)", analysis)
        self.assertIn("fsFilter = next", analysis)
        self.assertIn("fsPage = 0", analysis)
        self.assertIn(".fs-stat.on", css, "筛选态需要可见的选中样式")


if __name__ == "__main__":
    unittest.main()
