"""地图区域表达回归护栏：一级地区由区域面承载，区域名贴底边并避让建筑。"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "template" / "viewer"


class MapRegionExpressionContractTest(unittest.TestCase):
    def test_region_layer_nodes_are_not_drawn_as_points(self):
        scene = (VIEWER / "68-map-scene.js").read_text(encoding="utf-8")
        # 区域入口节点不能只跳过标签、却继续画 marker
        self.assertIn("if (n.unknown || hideMarker(n) || regionLayerIds.has(n.id))", scene)
        self.assertIn("!regionLayerIds.has(n.id)", scene)
        self.assertIn("区域层节点已由区域面承载", scene)

    def test_region_label_is_anchored_to_bottom_with_fallback(self):
        scene = (VIEWER / "68-map-scene.js").read_text(encoding="utf-8")
        self.assertIn("const poly = (r.polygon || []).map(atlasWorldScreen)", scene)
        self.assertIn("maxY - h / 2 - gap", scene)
        self.assertIn("const outsideY = maxY + h / 2 + gap", scene)
        self.assertIn("keptRegionGroups", scene)
        # 区域名必须按实测宽度居中绘制
        overlays = (VIEWER / "65-map-overlays.js").read_text(encoding="utf-8")
        self.assertIn("function drawAtlasRegionLabel", overlays)
        self.assertIn("box.x + box.w / 2 - textW / 2", overlays)
        self.assertIn("ctx.textAlign = 'left'", overlays)

    def test_region_label_uses_exact_place_name(self):
        scene = (VIEWER / "68-map-scene.js").read_text(encoding="utf-8")
        # 一级地区名取 layer 指向地点的原名，不能派生「越国大陆」或截掉括号
        self.assertIn("nodesById.get(r.layer)", scene)
        self.assertIn("regionPlace && regionPlace.name", scene)
        self.assertNotIn("replace(/[（(].*$/, '')", scene)

    def test_node_label_is_centered_under_marker(self):
        overlays = (VIEWER / "65-map-overlays.js").read_text(encoding="utf-8")
        self.assertIn("ctx.translate(cx - size / 2, cy - size / 2)", overlays)
        self.assertIn("textW = ctx.measureText(cand.text).width", overlays)
        self.assertIn("const textX = cand.x - textW / 2", overlays)
        self.assertIn("ctx.textAlign = 'left'", overlays)

    def test_architecture_stamps_are_label_obstacles(self):
        surface = (VIEWER / "60-map-surface.js").read_text(encoding="utf-8")
        scene = (VIEWER / "68-map-scene.js").read_text(encoding="utf-8")
        self.assertIn("architecture: asset.type === 'architecture'", surface)
        self.assertIn("const stampBoxes = stampResult.boxes || []", scene)
        self.assertIn("obstacles = reserved.concat", scene)


if __name__ == "__main__":
    unittest.main()
