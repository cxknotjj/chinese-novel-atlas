"""地图交互回归护栏：拖拽平移用 Pointer Events，缩放百分比跟随 drawMap 更新。

这类行为主要发生在浏览器里，单测不做完整 DOM 仿真；这里锁定源码契约，
防止后续拆分模块时把 pointer 处理器或百分比同步改回静态控件。
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "template" / "viewer"


class MapInteractionContractTest(unittest.TestCase):
    def test_pointer_drag_and_live_zoom_label(self):
        ui = (VIEWER / "70-map-ui.js").read_text(encoding="utf-8")
        model = (VIEWER / "50-map-model.js").read_text(encoding="utf-8")
        css = (ROOT / "template" / "viewer.css").read_text(encoding="utf-8")

        for handler in ("onpointerdown", "onpointermove", "onpointerup", "onpointercancel"):
            self.assertIn(handler, ui, f"缺少 {handler}：触屏/鼠标拖拽会失效")
        self.assertNotIn("onmousedown", ui, "不应回退到只在空白处生效的 mouse 拖拽")
        self.assertIn("mapPanning = !mapDragNode", ui)
        self.assertIn("e.button === 2", ui, "桌面端缺少右键平移分支")
        self.assertIn("oncontextmenu", ui, "右键平移必须拦截浏览器右键菜单")
        self.assertIn("mapView.x += dx", ui)
        self.assertIn("mapView.y += dy", ui)

        self.assertIn("function syncMapZoomLabel", model)
        self.assertIn("syncMapZoomLabel();", model)
        self.assertIn("Math.round(mapZoomScale() * 100)", model)
        self.assertIn("mapZoomValue", ui)
        self.assertIn("touch-action: none", css, "画布需禁用浏览器默认触控手势")


if __name__ == "__main__":
    unittest.main()
