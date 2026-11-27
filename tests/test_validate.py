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

    # ---------- spatial_relations（空间关系，可选字段） ----------

    def _spatial(self, **overrides):
        rel = {
            "id": "sr_demo",
            "s": "p_dongyu",
            "t": "p_qingyunshan",
            "kind": "direction",
            "value": "north_of",
            "confidence": "high",
            "first_ch": 1,
            "evidence": {"ch": 1, "quote": "青云山位于东岳以北"},
        }
        rel.update(overrides)
        return rel

    def _load_spatial(self, rels):
        data = copy.deepcopy(self.sample)
        data["spatial_relations"] = rels
        return data

    def test_spatial_missing_or_empty_passes(self):
        missing = copy.deepcopy(self.sample)
        self.assertEqual(self.check(missing).errors, [],
                         "缺失 spatial_relations 不应报错")
        empty = self._load_spatial([])
        self.assertEqual(self.check(empty).errors, [],
                         "空 spatial_relations 不应报错")

    def test_spatial_not_a_list_rejected(self):
        data = self._load_spatial({"id": "sr_x"})
        report = self.check(data)
        self.assertTrue(any("必须是 list" in msg for _, msg in report.errors),
                        f"没有拒绝非 list 的 spatial_relations：{report.errors[:5]}")

    def test_spatial_dangling_endpoint_rejected(self):
        data = self._load_spatial([self._spatial(s="p_no_such_place")])
        report = self.check(data)
        self.assertTrue(any("起点不存在" in msg for _, msg in report.errors),
                        f"没有拒绝悬空起点：{report.errors[:5]}")
        data = self._load_spatial([self._spatial(t="p_no_such_place")])
        report = self.check(data)
        self.assertTrue(any("终点不存在" in msg for _, msg in report.errors),
                        f"没有拒绝悬空终点：{report.errors[:5]}")

    def test_spatial_self_loop_rejected(self):
        data = self._load_spatial([self._spatial(t="p_dongyu")])
        report = self.check(data)
        self.assertTrue(any("自环" in msg for _, msg in report.errors),
                        f"没有拒绝 s == t：{report.errors[:5]}")

    def test_spatial_kind_invalid_rejected(self):
        data = self._load_spatial([self._spatial(kind="teleport")])
        report = self.check(data)
        self.assertTrue(any("kind 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 kind：{report.errors[:5]}")

    def test_spatial_direction_value_invalid_rejected(self):
        data = self._load_spatial([self._spatial(value="above")])
        report = self.check(data)
        self.assertTrue(any("direction value 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界方向值：{report.errors[:5]}")

    def test_spatial_confidence_invalid_rejected(self):
        data = self._load_spatial([self._spatial(confidence="sure")])
        report = self.check(data)
        self.assertTrue(any("confidence 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 confidence：{report.errors[:5]}")

    def test_spatial_quote_empty_or_too_long_rejected(self):
        data = self._load_spatial([self._spatial(evidence={"ch": 1, "quote": ""})])
        report = self.check(data)
        self.assertTrue(any("quote 为空" in msg for _, msg in report.errors),
                        f"没有拒绝空 quote：{report.errors[:5]}")
        data = self._load_spatial([self._spatial(evidence={"ch": 1, "quote": "长" * 121})])
        report = self.check(data)
        self.assertTrue(any("超过 120 字" in msg for _, msg in report.errors),
                        f"没有拒绝超长 quote：{report.errors[:5]}")

    def test_spatial_chapter_out_of_range_rejected(self):
        data = self._load_spatial([self._spatial(first_ch=9999)])
        report = self.check(data)
        self.assertTrue(any("first_ch 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 first_ch：{report.errors[:5]}")
        data = self._load_spatial([self._spatial(evidence={"ch": 9999, "quote": "原文"})])
        report = self.check(data)
        self.assertTrue(any("evidence.ch 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 evidence.ch：{report.errors[:5]}")

    def test_spatial_id_duplicate_or_bad_prefix_rejected(self):
        dup = [self._spatial(), self._spatial(t="p_jishiji")]
        report = self.check(self._load_spatial(dup))
        self.assertTrue(any("id 重复" in msg for _, msg in report.errors),
                        f"没有拒绝重复 id：{report.errors[:5]}")
        bad = self._load_spatial([self._spatial(id="x_demo")])
        report = self.check(bad)
        self.assertTrue(any("sr_ 前缀" in msg for _, msg in report.errors),
                        f"没有拒绝错误前缀 id：{report.errors[:5]}")

    def test_spatial_value_empty_or_too_long_rejected(self):
        data = self._load_spatial([self._spatial(value="")])
        report = self.check(data)
        self.assertTrue(any("value 为空" in msg for _, msg in report.errors),
                        f"没有拒绝空 value：{report.errors[:5]}")
        data = self._load_spatial([self._spatial(value="长" * 41)])
        report = self.check(data)
        self.assertTrue(any("value 超过 40 字" in msg for _, msg in report.errors),
                        f"没有拒绝超长 value：{report.errors[:5]}")

    def test_spatial_evidence_not_object_rejected(self):
        data = self._load_spatial([self._spatial(evidence="ch1 原文")])
        report = self.check(data)
        self.assertTrue(any("evidence 必须是对象" in msg for _, msg in report.errors),
                        f"没有拒绝非对象 evidence：{report.errors[:5]}")

    def test_spatial_evidence_ch_mismatch_warn(self):
        data = self._load_spatial([self._spatial(
            first_ch=1, evidence={"ch": 5, "quote": "第五章才点明方位"})])
        report = self.check(data)
        self.assertFalse(report.errors, f"不一致只应告警：{report.errors[:5]}")
        self.assertTrue(any("不一致" in msg for _, msg in report.warnings),
                        f"没有提示证据章与 first_ch 不一致：{report.warnings[:5]}")

    def test_spatial_layer_fallback_warn(self):
        rels = [
            self._spatial(id="sr_one", s="p_qingyunshan", t="p_zayiyuan"),
            self._spatial(id="sr_two", s="p_houshan", t="p_yanwuchang"),
        ]
        report = self.check(self._load_spatial(rels))
        self.assertFalse(report.errors, f"层统计 fixture 不应报错：{report.errors[:5]}")
        self.assertTrue(any("M2 会回退" in msg for _, msg in report.warnings),
                        f"没有提示层内约束不足回退 M2：{report.warnings[:5]}")


if __name__ == "__main__":
    unittest.main()
