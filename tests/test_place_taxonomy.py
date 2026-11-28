"""地点 L1–L4 地理层级回归测试。

数据契约见 `references/place-taxonomy.md`。输出目录不进 git，所以在只 clone
代码的环境里跳过真实书数据，只校验仓库里的 sample。
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCHES = {"continent", "ocean", "realm"}


def check_places(testcase: unittest.TestCase, data: dict, label: str) -> None:
    places = {p.get("id"): p for p in data.get("places") or []}
    testcase.assertTrue(places, f"{label} 没有地点")

    for pid, p in places.items():
        lv = p.get("level")
        testcase.assertIn(lv, (1, 2, 3, 4), f"{label}: {pid} level 缺失或越界")
        testcase.assertIn(p.get("branch"), BRANCHES, f"{label}: {pid} branch 越界")
        if lv == 1:
            testcase.assertFalse(p.get("parent"), f"{label}: L1 {pid} 不应有 parent")
        else:
            testcase.assertIn(p.get("parent"), places, f"{label}: {pid} 缺少 parent")
            parent = places[p["parent"]]
            testcase.assertLessEqual(
                lv, parent["level"] + 1,
                f"{label}: {pid} 从 L{parent['level']} 跳到 L{lv}",
            )
            testcase.assertEqual(
                p["branch"], parent["branch"],
                f"{label}: {pid} branch 与父级不一致",
            )

    # 每条路径都必须落到 L1，且不能成环
    for pid, p in places.items():
        seen = set()
        cur = p
        while cur.get("parent") in places and cur["id"] not in seen:
            seen.add(cur["id"])
            cur = places[cur["parent"]]
        testcase.assertNotIn(cur["id"], seen, f"{label}: {pid} parent 成环")
        testcase.assertEqual(cur.get("level"), 1, f"{label}: {pid} 未落到 L1")


class PlaceTaxonomyTest(unittest.TestCase):
    def test_sample(self):
        path = ROOT / "samples" / "fictional" / "data.json"
        check_places(self, json.loads(path.read_text(encoding="utf-8")), "sample")

    def test_real_book_if_present(self):
        path = ROOT / "output" / "凡人修仙传" / "data.json"
        if not path.exists():
            self.skipTest("output 目录未生成")
        check_places(self, json.loads(path.read_text(encoding="utf-8")), "凡人修仙传")

    def test_taxonomy_doc_exists(self):
        doc = (ROOT / "references" / "place-taxonomy.md").read_text(encoding="utf-8")
        for token in ("L1 不能空", "不跨级", "virtual", "map_layer"):
            self.assertIn(token, doc)


if __name__ == "__main__":
    unittest.main()
