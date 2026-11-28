"""读者向核心层单元测试：cutoff / anomalies / versions / map levels / annotate。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from novel_atlas.reader.anomalies import build_anomalies  # noqa: E402
from novel_atlas.reader.cutoff import filter_data, reader_meta  # noqa: E402
from novel_atlas.reader.map_levels import compute_map_levels  # noqa: E402
from novel_atlas.reader.publish import annotate  # noqa: E402
from novel_atlas.reader.versions import create_snapshot, diff_snapshots  # noqa: E402


def base_data():
    return {
        "meta": {
            "schema_version": "2.0", "title": "测试书", "author": "测试",
            "chapters": 30, "chars": 300000, "status": "完结",
            "coverage": {"chapters_done": 20},
        },
        "realms": [
            {"id": "r1", "name": "炼气", "order": 1},
            {"id": "r2", "name": "筑基", "order": 2},
            {"id": "r3", "name": "金丹", "order": 3},
        ],
        "entities": [
            {"id": "e1", "name": "甲", "type": "character", "first_ch": 1,
             "last_ch": 25, "power_history": [{"ch": 5, "realm": "r1"}, {"ch": 21, "realm": "r2"}]},
            {"id": "e2", "name": "乙", "type": "character", "first_ch": 12, "last_ch": 20},
            {"id": "e3", "name": "丙", "type": "character", "first_ch": 2, "last_ch": 2,
             "attrs": {"状态": "死亡"}},
            {"id": "i1", "name": "剑", "type": "item", "first_ch": 1},
        ],
        "relations": [
            {"id": "rel1", "s": "e1", "t": "e3", "type": "alliance", "first_ch": 1},
            {"id": "rel2", "s": "e1", "t": "e2", "type": "conflict", "first_ch": 12},
        ],
        "chapters": [
            {"ch": 1, "title": "开始", "summary": "甲与丙出场", "new_entities": ["e1", "e3"]},
            {"ch": 5, "title": "之后", "summary": "丙再次出现", "new_entities": []},
            {"ch": 12, "title": "乙", "summary": "乙出场", "new_entities": ["e2"]},
            {"ch": 20, "title": "二十", "summary": "乙退场", "new_entities": []},
            {"ch": 25, "title": "二十五", "summary": "甲出场", "new_entities": []},
        ],
        "foreshadows": [
            {"id": "f1", "content": "旧信", "plant_ch": 1, "last_mention_ch": 1,
             "payoff_ch": None, "importance": 0.9},
            {"id": "f2", "content": "玉佩", "plant_ch": 2, "last_mention_ch": 2,
             "payoff_ch": 26, "importance": 0.5},
        ],
        "knowledge": [
            {"id": "k1", "fact": "丙没死", "truth_ch": 10,
             "known_by": [{"entity": "e1", "ch": 8}], "reader_known_ch": 10},
        ],
        "places": [
            {"id": "p1", "name": "越国", "first_ch": 1},
            {"id": "p2", "name": "乱星海", "first_ch": 12},
        ],
        "spatial_relations": [
            {"id": "s1", "s": "p1", "t": "p2", "kind": "direction",
             "value": "north_of", "first_ch": 12, "evidence": {"ch": 12, "quote": "越国在北"}},
            {"id": "s2", "s": "p2", "t": "p1", "kind": "direction",
             "value": "north_of", "first_ch": 12, "evidence": {"ch": 12, "quote": "乱星海在北"}},
            {"id": "s3", "s": "p1", "t": "p2", "kind": "distance",
             "value": "1000li", "first_ch": 12},
        ],
        "concepts": [
            {"id": "c1", "name": "灵气", "first_ch": 1},
            {"id": "c2", "name": "元婴", "first_ch": 20},
        ],
        "anomalies": [
            {"id": "a1", "kind": "entity_after_last", "title": "丙在后面出现",
             "chapter_range": [2, 5], "evidence": [{"coordinate": "ch5"}]},
            {"id": "a2", "kind": "later", "title": "未来疑点",
             "chapter_range": [21, 25], "evidence": [{"coordinate": "ch21"}]},
        ],
        "map_layout": {
            "nodes": [
                {"place": "p1", "x": 0.2, "y": 0.3},
                {"place": "p2", "x": 0.8, "y": 0.7},
            ],
            "regions": [{"id": "reg1", "layer": "p1", "shape": "land"}],
            "routes": [{"s": "p1", "t": "p2"}],
        },
    }


class CutoffTest(unittest.TestCase):
    def test_future_entities_and_fields_are_cut(self):
        data = base_data()
        out = filter_data(data, 10)
        self.assertEqual([e["id"] for e in out["entities"]], ["e1", "e3", "i1"])
        self.assertNotIn("e2", {e["id"] for e in out["entities"]})
        self.assertEqual(out["_reader"]["cutoff_ch"], 10)
        self.assertTrue(out["_reader"]["is_spoiler_safe"])
        # 未来 power_history / last_ch 不泄露
        e1 = next(e for e in out["entities"] if e["id"] == "e1")
        self.assertEqual([p["ch"] for p in e1["power_history"]], [5])
        self.assertIsNone(e1["last_ch"])

    def test_virtual_geo_container_survives_cutoff(self):
        """L1 分支容器没有首现章，截断时也必须保留，否则子树会掉回旧根。"""
        data = base_data()
        data["places"].append({
            "id": "p0", "name": "天南", "level": 1, "branch": "continent",
            "virtual": True, "first_ch": 0,
        })
        data["places"][0]["parent"] = "p0"
        out = filter_data(data, 10)
        self.assertIn("p0", {p["id"] for p in out["places"]})

    def test_foreshadow_payoff_and_status_are_derived_at_cutoff(self):
        out = filter_data(base_data(), 10)
        f2 = next(f for f in out["foreshadows"] if f["id"] == "f2")
        self.assertIsNone(f2["payoff_ch"])
        self.assertFalse(any(f.get("payoff_ch") == 26 for f in out["foreshadows"]))

    def test_anomalies_with_future_evidence_are_hidden(self):
        out = filter_data(base_data(), 10)
        self.assertEqual([a["id"] for a in out["anomalies"]], ["a1"])
        self.assertNotIn("a2", {a["id"] for a in out["anomalies"]})

    def test_map_nodes_and_routes_are_cut(self):
        out = filter_data(base_data(), 10)
        self.assertEqual([n["place"] for n in out["map_layout"]["nodes"]], ["p1"])
        self.assertEqual(out["map_layout"]["routes"], [])

    def test_reader_meta(self):
        meta = reader_meta(base_data(), 10)
        self.assertEqual(meta["cutoff_ch"], 10)
        self.assertEqual(meta["total_chapters"], 30)
        self.assertFalse(meta["analysis_complete"])


class AnomalyTest(unittest.TestCase):
    def test_entity_after_last_and_death_upgrade(self):
        report = build_anomalies(base_data(), live=10)
        by_kind = {a["kind"]: a for a in report["anomalies"]}
        self.assertIn("death_reappearance", by_kind)
        self.assertEqual(by_kind["death_reappearance"]["entities"], ["e3"])

    def test_foreshadow_unresolved_uses_live_threshold(self):
        report = build_anomalies(base_data(), live=100)
        self.assertIn("foreshadow_unresolved", report["counts"])
        # f2 有 payoff，不能算未回收
        ids = {a["title"] for a in report["anomalies"]}
        self.assertFalse(any("玉佩" in t for t in ids))

    def test_every_anomaly_has_evidence_and_id(self):
        report = build_anomalies(base_data(), live=10)
        for a in report["anomalies"]:
            self.assertTrue(a["id"])
            self.assertTrue(a["evidence"])

    def test_report_is_reproducible(self):
        """同一份 data.json 必须得到逐字节相同的报告。

        generated_at 取 meta.analyzed_at 而不是构建时刻，否则每次重跑
        build_reader 都会在 data.js 里写进一个新时间戳，产生几百 KB 的假 diff。
        """
        d = base_data()
        d["meta"]["analyzed_at"] = "2026-11-27T12:00:00Z"
        one = json.dumps(build_anomalies(d, live=10), ensure_ascii=False)
        two = json.dumps(build_anomalies(d, live=10), ensure_ascii=False)
        self.assertEqual(one, two)
        self.assertEqual(json.loads(one)["generated_at"], "2026-11-27T12:00:00Z")

    def test_generated_at_defaults_to_empty_and_can_be_overridden(self):
        # 没有 analyzed_at 就留空，不能退回 time.now()
        self.assertEqual(build_anomalies(base_data(), live=10)["generated_at"], "")
        report = build_anomalies(base_data(), live=10, generated_at="2020-01-01T00:00:00Z")
        self.assertEqual(report["generated_at"], "2020-01-01T00:00:00Z")


class MapLevelTest(unittest.TestCase):
    def test_no_places_is_m0(self):
        d = base_data()
        d["places"] = []
        self.assertEqual(compute_map_levels(d)["global"], "M0")

    def test_layout_without_direction_is_m1(self):
        d = base_data()
        d["spatial_relations"] = []
        self.assertEqual(compute_map_levels(d)["global"], "M1")

    def test_three_direction_edges_is_m2(self):
        d = base_data()
        d["places"][1]["parent"] = "p1"
        levels = compute_map_levels(d)
        self.assertEqual(levels["global"], "M2")
        self.assertEqual(levels["layers"][0]["direction_constraints"], 3)

    def test_time_slices_is_m4(self):
        d = base_data()
        d["map_layout"]["time_slices"] = [{"ch": 1}, {"ch": 10}]
        self.assertEqual(compute_map_levels(d)["global"], "M4")


class VersionTest(unittest.TestCase):
    def test_id_drift_is_detected_by_name(self):
        a = base_data()
        b = base_data()
        b["entities"][0]["id"] = "e1_new"
        with tempfile.TemporaryDirectory() as tmp:
            sa = create_snapshot(a, tmp, label="a")
            sb = create_snapshot(b, tmp, label="b")
            diff = diff_snapshots(sa["path"], sb["path"])
        self.assertFalse(diff["id_stability"]["entities"]["stable"])
        self.assertEqual(diff["id_stability"]["entities"]["changed"]["甲"], ["e1", "e1_new"])

    def test_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = create_snapshot(base_data(), tmp, label="x")
            path = Path(snap["path"])
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["label"], "x")


class AnnotateTest(unittest.TestCase):
    def test_annotate_adds_reader_fields_and_filters_anomalies(self):
        out = annotate(base_data(), cutoff=10)
        self.assertEqual(out["_reader"]["cutoff_ch"], 10)
        self.assertIn("_mapLevels", out)
        self.assertIn("_anomalyMeta", out)
        self.assertTrue(all(a["id"] != "a2" for a in out["anomalies"]))


if __name__ == "__main__":
    unittest.main()
