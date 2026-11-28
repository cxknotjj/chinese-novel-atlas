"""novel-atlas 审计流程的联网核对模式：问题生成、线索校验、报告落盘。"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "skills" / "novel-atlas" / "scripts" / "audit.py"


def load_audit():
    spec = importlib.util.spec_from_file_location("atlas_audit_web", AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DATA = {
    "meta": {"title": "测试书", "chapters": 10},
    "entities": [
        {"id": "e_a", "name": "甲", "type": "character", "aliases": [], "first_ch": 1},
        {"id": "e_b", "name": "乙", "type": "character", "aliases": ["小乙"], "first_ch": 2},
        {"id": "e_c", "name": "丙", "type": "org", "aliases": [], "first_ch": 3},
    ],
    "relations": [
        {"s": "e_a", "t": "e_b", "type": "kinship", "first_ch": 1, "evidence": ["ch01:p2"]},
        {"s": "e_a", "t": "e_c", "type": "service", "first_ch": 3, "evidence": ["ch03:p1"]},
    ],
    "places": [{"id": "p_x", "name": "某地", "parent": None, "attrs": {}, "first_ch": 3}],
    "concepts": [{"id": "c_x", "name": "某功", "kind": "technique", "first_ch": 4}],
}

GOOD_LEAD = {
    "id": "wl_001", "field": "aliases", "target_id": "e_a",
    "claim": "资料称甲另有称号。",
    "sources": [{"url": "https://example.com/a", "title": "示例", "retrieved_at": "2026-11-28"}],
    "confidence": "low", "spoiler_risk": "none",
}


class WebQuestionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_audit()

    def test_alias_question_prefers_character_without_alias(self):
        qs = self.mod.build_web_questions(DATA)
        targets = {q["target"]["id"] for q in qs}
        self.assertIn("e_a", targets)
        self.assertNotIn("e_b", targets)  # 已有别名，不再问
        q = next(x for x in qs if x["target"]["id"] == "e_a")
        self.assertEqual(q["field"], "aliases")
        self.assertIn("甲", q["search_query"])
        self.assertEqual(q["spoiler_risk"], "none")

    def test_place_and_terminology_questions(self):
        qs = self.mod.build_web_questions(DATA)
        fields = {q["field"] for q in qs}
        self.assertIn("parent", fields)
        self.assertIn("terminology", fields)

    def test_limit_and_dedup(self):
        qs = self.mod.build_web_questions(DATA, limit=2)
        self.assertEqual(len(qs), 2)
        self.assertEqual(len({q["target"]["id"] for q in qs}), 2)

    def test_web_plan_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.mod.cmd_web_plan(DATA, [], out, 10)
            self.assertEqual(rc, 0)
            plan = json.loads((out / "web-questions.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["title"], "测试书")
            self.assertTrue(plan["questions"])
            self.assertIn("leads_schema", plan)
            md = (out / "web-questions.md").read_text(encoding="utf-8")
            self.assertIn("外部线索", md)
            self.assertIn("不会自动写入", md)


class WebLeadsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_audit()

    def test_accepts_well_formed_lead(self):
        accepted, rejected = self.mod.validate_web_leads(DATA, {"leads": [GOOD_LEAD]})
        self.assertEqual(len(accepted), 1)
        self.assertEqual(rejected, [])

    def test_rejects_unknown_target_and_bad_field(self):
        bad = dict(GOOD_LEAD, id="wl_002", target_id="e_nope")
        _, rejected = self.mod.validate_web_leads(DATA, {"leads": [bad]})
        self.assertIn("不在 data.json", rejected[0]["errors"][0])
        bad2 = dict(GOOD_LEAD, id="wl_003", field="death")
        _, rejected2 = self.mod.validate_web_leads(DATA, {"leads": [bad2]})
        self.assertTrue(any("不在允许列表" in e for e in rejected2[0]["errors"]))

    def test_rejects_spoiler_risk_high(self):
        bad = dict(GOOD_LEAD, id="wl_004", spoiler_risk="high")
        _, rejected = self.mod.validate_web_leads(DATA, {"leads": [bad]})
        self.assertTrue(any("剧透风险" in e for e in rejected[0]["errors"]))

    def test_rejects_missing_source_or_time(self):
        bad = dict(GOOD_LEAD, id="wl_005", sources=[])
        _, rejected = self.mod.validate_web_leads(DATA, {"leads": [bad]})
        self.assertTrue(any("来源" in e for e in rejected[0]["errors"]))
        bad2 = dict(GOOD_LEAD, id="wl_006", sources=[{"url": "https://example.com/x", "retrieved_at": "昨天"}])
        _, rejected2 = self.mod.validate_web_leads(DATA, {"leads": [bad2]})
        self.assertTrue(any("retrieved_at" in e for e in rejected2[0]["errors"]))

    def test_report_writes_markdown_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            leads = out / "web-leads.json"
            payload = {"version": "1.0", "leads": [GOOD_LEAD, dict(GOOD_LEAD, id="wl_009", spoiler_risk="high")]}
            leads.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.mod.cmd_web_report(DATA, leads, out)
            self.assertEqual(rc, 0)
            md = (out / "web-leads.md").read_text(encoding="utf-8")
            self.assertIn("不是原文证据", md)
            self.assertIn("1 条可参考 · 1 条已隔离", md)
            self.assertIn("https://example.com/a", md)
            self.assertIn("剧透风险 high", md)
            self.assertIn("甲", md)


if __name__ == "__main__":
    unittest.main()
