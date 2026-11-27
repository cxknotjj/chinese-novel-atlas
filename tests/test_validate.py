#!/usr/bin/env python3
"""契约回归测试：不依赖网络，也不需要真实书稿。

运行：
    python -m unittest discover -s tests -v
"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate import Report, validate  # noqa: E402


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_path = ROOT / "samples" / "fictional" / "data.json"
        cls.sample = json.loads(cls.sample_path.read_text(encoding="utf-8"))

    def check(self, data):
        report = Report()
        validate(data, report)
        return report

    def test_sample_passes(self):
        report = self.check(self.sample)
        self.assertEqual(report.errors, [], f"样例数据校验失败：{report.errors[:3]}")

    def test_battle_legacy_s_t_rejected(self):
        data = copy.deepcopy(self.sample)
        chapter = data["chapters"][0]
        chapter.setdefault("battles", []).append({
            "s": data["entities"][0]["id"],
            "t": data["entities"][1]["id"],
            "gap": 0,
            "note": "legacy fields",
        })
        report = self.check(data)
        self.assertTrue(any("旧字段 s/t" in msg for _, msg in report.errors),
                        f"没有拒绝旧战斗字段：{report.errors[:5]}")

    def test_battle_dangling_id_rejected(self):
        data = copy.deepcopy(self.sample)
        chapter = data["chapters"][0]
        chapter.setdefault("battles", []).append({
            "a": "e_does_not_exist",
            "b": data["entities"][0]["id"],
            "gap": 0,
            "note": "dangling",
        })
        report = self.check(data)
        self.assertTrue(any("不是已有实体" in msg for _, msg in report.errors),
                        f"没有拒绝悬空战斗引用：{report.errors[:5]}")

    def test_coverage_sum_must_match(self):
        data = copy.deepcopy(self.sample)
        data["meta"]["coverage"]["chapters_skipped"] += 1
        report = self.check(data)
        self.assertTrue(any("coverage 加和" in msg for _, msg in report.errors),
                        f"没有拒绝 coverage 加和不一致：{report.errors[:5]}")


if __name__ == "__main__":
    unittest.main()
