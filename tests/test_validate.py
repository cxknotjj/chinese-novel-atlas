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

    # ---------- map_layout（2D 示意布局，可选字段） ----------

    def _map_region(self, **overrides):
        reg = {
            "id": "r_one", "name": "东区", "shape": "land",
            "layer": "p_dongyu", "label_at": [20, 30],
            "polygon": [[5, 5], [60, 5], [60, 60], [5, 60]],
        }
        reg.update(overrides)
        return reg

    def _map_node(self, place, **overrides):
        node = {"place": place, "x": 50, "y": 50, "rank": 2, "label": True}
        node.update(overrides)
        return node

    def _map_terrain(self, **overrides):
        terrain = {
            "ridges": [{"points": [[10, 20], [30, 40]], "width": 2.4,
                        "region": "r_one", "name": "太岳山脉"}],
            "rivers": [{"points": [[10, 20], [30, 40]], "width": 1.1,
                        "region": "r_one"}],
            "lakes": [{"polygon": [[10, 10], [20, 10], [15, 20]],
                       "region": "r_one"}],
            "islets": [{"x": 70 + i * 3, "y": 34, "r": 1.6} for i in range(4)],
        }
        terrain.update(overrides)
        return terrain

    def _map_route(self, **overrides):
        route = {"s": "p_dongyu", "t": "p_qingyunshan", "kind": "portal",
                 "curve": [[40, 70], [50, 60]], "label": "古传送阵"}
        route.update(overrides)
        return route

    def _map_layout(self, **overrides):
        layout = {
            "mode": "schematic",
            "note": "人工示意坐标，非经纬度；近似摆放",
            "canvas": [100, 100],
            "regions": [self._map_region()],
            "nodes": [self._map_node(p) for p in
                      ("p_dongyu", "p_qingyunshan", "p_zayiyuan",
                       "p_yanwuchang", "p_houshan")],
            "terrain": self._map_terrain(),
            "routes": [self._map_route()],
        }
        layout.update(overrides)
        return layout

    def _load_layout(self, layout):
        data = copy.deepcopy(self.sample)
        data["map_layout"] = layout
        return data

    def test_map_layout_missing_passes(self):
        data = copy.deepcopy(self.sample)
        data.pop("map_layout", None)
        report = self.check(data)
        self.assertFalse(any(rule == "地图" for rule, _ in report.errors),
                         f"缺失 map_layout 不应报地图错误：{report.errors[:5]}")
        self.assertFalse(any(rule == "地图" for rule, _ in report.warnings),
                         f"缺失 map_layout 不应报地图警告：{report.warnings[:5]}")

    def test_map_mode_invalid_rejected(self):
        report = self.check(self._load_layout(self._map_layout(mode="topo")))
        self.assertTrue(any("mode 必须为 schematic" in msg for _, msg in report.errors),
                        f"没有拒绝非 schematic 模式：{report.errors[:5]}")

    def test_map_canvas_invalid_rejected(self):
        report = self.check(self._load_layout(self._map_layout(canvas=[80, 80])))
        self.assertTrue(any("canvas 必须为 [100,100]" in msg for _, msg in report.errors),
                        f"没有拒绝非 [100,100] 画布：{report.errors[:5]}")

    def test_map_region_coord_out_of_range_rejected(self):
        region = self._map_region(polygon=[[120, 10], [5, 5], [60, 60]])
        report = self.check(self._load_layout(self._map_layout(regions=[region])))
        self.assertTrue(any("坐标越界" in msg for _, msg in report.errors),
                        f"没有拒绝区域越界坐标：{report.errors[:5]}")

    def test_map_node_coord_out_of_range_rejected(self):
        nodes = [self._map_node("p_dongyu", y=-5)]
        report = self.check(self._load_layout(self._map_layout(nodes=nodes)))
        self.assertTrue(any("y 越界" in msg for _, msg in report.errors),
                        f"没有拒绝节点越界坐标：{report.errors[:5]}")

    def test_map_node_place_dangling_rejected(self):
        nodes = [self._map_node("p_no_such_place")]
        report = self.check(self._load_layout(self._map_layout(nodes=nodes)))
        self.assertTrue(any("place 不存在" in msg for _, msg in report.errors),
                        f"没有拒绝悬空 place：{report.errors[:5]}")

    def test_map_node_place_duplicate_rejected(self):
        nodes = [self._map_node("p_dongyu"), self._map_node("p_dongyu")]
        report = self.check(self._load_layout(self._map_layout(nodes=nodes)))
        self.assertTrue(any("place 重复" in msg for _, msg in report.errors),
                        f"没有拒绝重复 place：{report.errors[:5]}")

    def test_map_shape_invalid_rejected(self):
        region = self._map_region(shape="city")
        report = self.check(self._load_layout(self._map_layout(regions=[region])))
        self.assertTrue(any("shape 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 shape：{report.errors[:5]}")

    def test_map_rank_invalid_rejected(self):
        nodes = [self._map_node("p_dongyu", rank=5)]
        report = self.check(self._load_layout(self._map_layout(nodes=nodes)))
        self.assertTrue(any("rank 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 rank：{report.errors[:5]}")

    def test_map_polygon_too_few_points_rejected(self):
        region = self._map_region(polygon=[[1, 1], [2, 2]])
        report = self.check(self._load_layout(self._map_layout(regions=[region])))
        self.assertTrue(any("至少需要 3 个点" in msg for _, msg in report.errors),
                        f"没有拒绝点数不足的 polygon：{report.errors[:5]}")

    def test_map_sparse_warn(self):
        nodes = [self._map_node("p_dongyu"), self._map_node("p_qingyunshan")]
        report = self.check(self._load_layout(self._map_layout(nodes=nodes)))
        self.assertFalse(report.errors, f"稀疏 fixture 不应报错：{report.errors[:5]}")
        self.assertTrue(any("过于稀疏" in msg for _, msg in report.warnings),
                        f"没有提示节点稀疏：{report.warnings[:5]}")

    def test_map_regions_empty_warn(self):
        layout = self._map_layout(regions=[], terrain=None)
        report = self.check(self._load_layout(layout))
        self.assertFalse(report.errors, f"空区域 fixture 不应报错：{report.errors[:5]}")
        self.assertTrue(any("只剩点" in msg for _, msg in report.warnings),
                        f"没有提示缺少区域块：{report.warnings[:5]}")

    def test_map_note_missing_keyword_warn(self):
        report = self.check(self._load_layout(
            self._map_layout(note="精确坐标，不可外推")))
        self.assertFalse(report.errors, f"note fixture 不应报错：{report.errors[:5]}")
        self.assertTrue(any("把示意坐标说成精确坐标" in msg for _, msg in report.warnings),
                        f"没有提示 note 缺少示意字样：{report.warnings[:5]}")

    def test_map_terrain_unknown_key_rejected(self):
        terrain = self._map_terrain(foo=[])
        report = self.check(self._load_layout(self._map_layout(terrain=terrain)))
        self.assertTrue(any("未知子键" in msg for _, msg in report.errors),
                        f"没有拒绝 terrain 未知子键：{report.errors[:5]}")

    def test_map_ridge_points_too_few_rejected(self):
        ridge = {"points": [[1, 1]]}
        terrain = self._map_terrain(ridges=[ridge])
        report = self.check(self._load_layout(self._map_layout(terrain=terrain)))
        self.assertTrue(any("点数应为" in msg for _, msg in report.errors),
                        f"没有拒绝点数不足的 ridge：{report.errors[:5]}")

    def test_map_ridge_coord_out_of_range_rejected(self):
        ridge = {"points": [[120, 10], [1, 1]]}
        terrain = self._map_terrain(ridges=[ridge])
        report = self.check(self._load_layout(self._map_layout(terrain=terrain)))
        self.assertTrue(any("坐标越界" in msg for _, msg in report.errors),
                        f"没有拒绝 ridge 越界坐标：{report.errors[:5]}")

    def test_map_lake_polygon_too_few_rejected(self):
        lake = {"polygon": [[1, 1], [2, 2]]}
        terrain = self._map_terrain(lakes=[lake])
        report = self.check(self._load_layout(self._map_layout(terrain=terrain)))
        self.assertTrue(any("点数应为" in msg for _, msg in report.errors),
                        f"没有拒绝点数不足的 lake：{report.errors[:5]}")

    def test_map_islet_r_invalid_rejected(self):
        islets = [{"x": 70, "y": 34, "r": 9}]
        terrain = self._map_terrain(islets=islets)
        report = self.check(self._load_layout(self._map_layout(terrain=terrain)))
        self.assertTrue(any("r 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 islet 半径：{report.errors[:5]}")

    def test_map_route_dangling_s_rejected(self):
        route = self._map_route(s="p_no_such_place")
        report = self.check(self._load_layout(self._map_layout(routes=[route])))
        self.assertTrue(any("s 不存在" in msg for _, msg in report.errors),
                        f"没有拒绝悬空 route 起点：{report.errors[:5]}")

    def test_map_route_kind_invalid_rejected(self):
        route = self._map_route(kind="adjacent")
        report = self.check(self._load_layout(self._map_layout(routes=[route])))
        self.assertTrue(any("kind 越界" in msg for _, msg in report.errors),
                        f"没有拒绝越界 route kind：{report.errors[:5]}")

    def test_map_route_curve_malformed_rejected(self):
        too_few = self._map_route(curve=[])
        report = self.check(self._load_layout(self._map_layout(routes=[too_few])))
        self.assertTrue(any("点数应为" in msg for _, msg in report.errors),
                        f"没有拒绝点数不足的 curve：{report.errors[:5]}")
        bad_pt = self._map_route(curve=[["a", "b"]])
        report = self.check(self._load_layout(self._map_layout(routes=[bad_pt])))
        self.assertTrue(any("坐标越界或格式错误" in msg for _, msg in report.errors),
                        f"没有拒绝格式错误的 curve：{report.errors[:5]}")

    def test_map_islets_sparse_warn(self):
        terrain = self._map_terrain(islets=[{"x": 70, "y": 34, "r": 1.6}] * 2)
        report = self.check(self._load_layout(self._map_layout(terrain=terrain)))
        self.assertFalse(report.errors, f"稀疏岛链 fixture 不应报错：{report.errors[:5]}")
        self.assertTrue(any("岛链偏少" in msg for _, msg in report.warnings),
                        f"没有提示岛链偏少：{report.warnings[:5]}")

    def test_map_terrain_missing_warn(self):
        report = self.check(self._load_layout(self._map_layout(terrain=None)))
        self.assertFalse(report.errors, f"缺 terrain 不应报错：{report.errors[:5]}")
        self.assertTrue(any("地形骨架" in msg for _, msg in report.warnings),
                        f"没有提示缺少地形骨架：{report.warnings[:5]}")

    def test_map_routes_empty_warn(self):
        report = self.check(self._load_layout(self._map_layout(routes=[])))
        self.assertFalse(report.errors, f"空 routes 不应报错：{report.errors[:5]}")
        self.assertTrue(any("跨区航路未配置" in msg for _, msg in report.warnings),
                        f"没有提示未配置航路：{report.warnings[:5]}")


if __name__ == "__main__":
    unittest.main()
