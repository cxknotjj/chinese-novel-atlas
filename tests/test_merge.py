"""合并层单元测试：实体归并、伏笔状态、地点父节点。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from novel_atlas.merge.entities import merge_entities, normalize_groups  # noqa: E402
from novel_atlas.merge.foreshadows import apply_status, merge_foreshadows  # noqa: E402
from novel_atlas.merge.places import merge_places  # noqa: E402


class MergeEntitiesTest(unittest.TestCase):
    def test_name_and_alias_cluster_into_one_record(self):
        batches = [
            ("batch-01.json", {"entities": [
                {"id": "e_han", "name": "韩立", "type": "character", "group": "七玄门",
                 "aliases": ["韩老魔"], "first_ch": 2, "desc": "少年"},
                {"id": "e_old", "name": "韩老魔", "type": "character", "group": "七玄门",
                 "first_ch": 8, "desc": "外人眼中的韩立"},
            ]}),
            ("batch-02.json", {"entities": [
                {"id": "e_han2", "name": "韩立", "type": "character", "group": "七玄门",
                 "aliases": ["韩跑跑"], "first_ch": 1, "desc": "山村少年，后入七玄门"},
            ]}),
        ]
        ents, id_map, log = merge_entities(batches)

        self.assertEqual(len(ents), 1)
        self.assertEqual(ents[0]["id"], "e_han")
        self.assertEqual(ents[0]["first_ch"], 1)
        self.assertEqual(ents[0]["desc"], "山村少年，后入七玄门")
        self.assertIn("韩跑跑", ents[0]["aliases"])
        self.assertEqual(id_map["e_han2"], "e_han")
        self.assertEqual(id_map["e_old"], "e_han")
        self.assertEqual(log["summary"]["output_entities"], 1)

    def test_generic_group_name_is_not_used_as_faction(self):
        ents = [
            {"id": "e_han", "name": "韩立", "type": "character", "group": "七玄门"},
            {"id": "e_zhang", "name": "张铁", "type": "character", "group": "韩立"},
        ]
        normalize_groups(ents)
        self.assertEqual(ents[1]["group"], "七玄门")


class ForeshadowTest(unittest.TestCase):
    def test_near_identical_content_merges_even_with_different_thread(self):
        batches = [
            ("batch-01.json", {"foreshadows": [
                {"id": "f_a", "content": "韩立身上的神秘小瓶尚未解开", "thread": "小瓶", "plant_ch": 2},
                {"id": "f_b", "content": "韩立身上的神秘小瓶尚未解开", "thread": "身世", "plant_ch": 2},
            ]}),
            ("batch-02.json", {"foreshadows": [
                {"id": "f_c", "content": "韩立身上的神秘小瓶尚未解开", "thread": "小瓶", "plant_ch": 3},
            ]}),
        ]
        out = merge_foreshadows(batches)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "f_a")

    def test_status_uses_last_mention_and_keeps_manual_drop(self):
        data = {
            "meta": {"chapters": 200},
            "chapters": [{"ch": i} for i in range(1, 201)],
            "foreshadows": [
                {"plant_ch": 10, "payoff_ch": 30, "status": "planted"},
                {"plant_ch": 5, "last_mention_ch": 190, "status": "overdue"},
                {"plant_ch": 5, "status": "planted"},
                {"plant_ch": 5, "status": "dropped"},
            ],
        }
        thr, changed = apply_status(data)
        self.assertEqual(thr, 50)
        self.assertEqual(data["foreshadows"][0]["status"], "paid")
        self.assertEqual(data["foreshadows"][1]["status"], "planted")
        self.assertEqual(data["foreshadows"][2]["status"], "overdue")
        self.assertEqual(data["foreshadows"][3]["status"], "dropped")
        self.assertEqual(changed, 3)


class PlacesTest(unittest.TestCase):
    def test_parent_name_and_entity_name_are_resolved(self):
        batches = [
            ("batch-01.json", {"places": [
                {"id": "p_cave", "name": "山洞", "parent": None},
                {"id": "p_valley", "name": "山谷", "parent": "山洞"},
                {"id": "p_sect", "name": "宗门", "parent": "e_huang"},
            ]}),
        ]
        out = merge_places(
            batches,
            taken_ids={"e_huang"},
            entity_names={"e_huang": "黄枫谷"},
        )
        by_name = {p["name"]: p for p in out}
        self.assertEqual(by_name["山谷"]["parent"], "p_cave")
        self.assertIsNone(by_name["宗门"]["parent"])
        self.assertEqual(by_name["宗门"]["attrs"]["所属势力"], "黄枫谷")


if __name__ == "__main__":
    unittest.main()
