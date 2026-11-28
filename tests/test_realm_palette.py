"""境界配色回归护栏：多境界必须多色相，同境界内由浅到深，突破后换色。"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "template" / "viewer"


class RealmPaletteTest(unittest.TestCase):
    def test_realm_palette_has_distinct_hues_and_stage_gradient(self):
        foundation = (VIEWER / "00-foundation.js").read_text(encoding="utf-8")
        analysis = (VIEWER / "80-analysis.js").read_text(encoding="utf-8")

        block = foundation.split("const REALM_COLOR = [", 1)[1].split("];", 1)[0]
        colors = set(re.findall(r"#[0-9A-Fa-f]{6}", block))
        self.assertGreaterEqual(len(colors), 4, "境界至少要有 4 个不同色相")
        self.assertIn("function realmBaseColor", foundation)
        self.assertIn("function realmTone", foundation)
        self.assertIn("80 - f * 40", foundation)
        self.assertIn("if (!st.length) return 0;", foundation)

        self.assertIn("function realmSegFill", analysis)
        self.assertIn("linear-gradient(90deg", analysis)
        self.assertIn("border-left:3px solid", analysis)


if __name__ == "__main__":
    unittest.main()
