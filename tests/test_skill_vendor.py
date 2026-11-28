"""skill 自包含与提及追踪口径的回归护栏。

两个约定，破一个用户就装不上或算错：

1. `skills/<name>/` 必须与 `scripts/` 同步，否则 `npx skills add` 装到的是旧代码。
2. `mentions.py` 只能在「已分析章」范围内判沉默时长，否则未分析的后文会被算进来。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mentions  # noqa: E402


class SkillVendorTest(unittest.TestCase):
    def test_vendored_skills_match_source(self):
        """副本与源码必须逐字节一致；改了 scripts/ 忘了同步，这里会失败。"""
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_skills.py"), "--check"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0,
                         "skill 副本与源码不一致，跑 python scripts/sync_skills.py\n"
                         + proc.stdout + proc.stderr)

    def _docs(self):
        """入口 + 六份按需流程文档。

        schema.md / web-contract.md 等是数据契约，里面谈仓库根的 `scripts/`
        是正常的；只有流程文档里的命令必须在安装后的 skill 里跑得通。
        """
        root = ROOT / "skills"
        flows = ("analyze", "ask", "audit", "compare", "export", "map")
        return sorted(root.glob("*/SKILL.md")) + [
            root / "novel-atlas" / "references" / f"{name}.md" for name in flows]

    def test_skill_docs_do_not_point_at_repo_root(self):
        """文档里不能出现 `python scripts/x.py`——skill 装完没有仓库根。"""
        for p in self._docs():
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("python scripts/", text, f"{p.name} 仍指向仓库根")

    def test_script_entries_exist_in_skill(self):
        """文档提到的每个脚本都必须真的在 skill 目录里。"""
        missing = []
        for p in self._docs():
            skill_root = p.parent if p.name == "SKILL.md" else p.parent.parent
            text = p.read_text(encoding="utf-8")
            for rel in set(__import__("re").findall(r"<SKILL_DIR>/scripts/([A-Za-z0-9_]+\.py)", text)):
                if not (skill_root / "scripts" / rel).exists():
                    missing.append(f"{skill_root.name}/{rel}")
        self.assertEqual(missing, [], f"skill 里缺这些脚本：{missing}")

    def test_one_skill_routes_to_six_workflows(self):
        """上传界面一次只能选一个 SKILL.md，六个流程必须在一个 skill 内。"""
        root = ROOT / "skills"
        entries = sorted(root.glob("*/SKILL.md"))
        self.assertEqual([p.parent.name for p in entries], ["novel-atlas"])
        d = root / "novel-atlas"
        skill = entries[0].read_text(encoding="utf-8")
        for name in ("analyze", "ask", "audit", "compare", "export", "map"):
            self.assertTrue((d / "references" / f"{name}.md").exists(), f"缺流程 {name}")
            self.assertIn(f"references/{name}.md", skill, f"入口没路由到 {name}")
        self.assertTrue((d / "scripts" / "audit.py").exists())
        self.assertTrue((d / "scripts" / "atlas_map.py").exists())

    def test_prune_protects_skill_owned_scripts(self):
        """prune 曾把 skill 自有的 audit.py 当成「多余文件」删掉。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "sync_skills", ROOT / "scripts" / "sync_skills.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        root = ROOT / "skills" / "novel-atlas"
        self.assertTrue(mod.is_own(root, root / "scripts" / "audit.py"))
        self.assertTrue(mod.is_own(root, root / "scripts" / "atlas_map.py"))
        self.assertTrue(mod.is_own(root, root / "SKILL.md"))
        self.assertTrue(mod.is_own(root, root / "references" / "analyze.md"))
        # 同步进来的文件不享受保护，否则漂移永远清不掉
        self.assertFalse(mod.is_own(root, root / "scripts" / "anomalies.py"))
        self.assertTrue((root / "scripts" / "audit.py").exists(),
                        "audit.py 是 skill 自有脚本，不该被同步流程删除")


class MentionsScopeTest(unittest.TestCase):
    """只分析了前 5 章时，第 8 章的提及不能算数。"""

    def _make_book(self, tmp: str) -> Path:
        book = Path(tmp)
        (book / "chapters").mkdir()
        for ch in range(1, 11):
            body = "第%d章\n" % ch + ("抽髓丸出现了。" if ch in (1, 8) else "无关内容。")
            (book / "chapters" / f"ch-{ch:04d}.txt").write_text(body, encoding="utf-8")
        data = {
            "meta": {"title": "测试书", "chapters": 10,
                     "coverage": {"chapters_done": 5}},
            "chapters": [{"ch": c, "summary": ""} for c in range(1, 6)],
            "entities": [{"id": "e1", "name": "抽髓丸", "type": "concept"}],
            "foreshadows": [{"id": "f1", "content": "抽髓丸的下落", "plant_ch": 1}],
        }
        (book / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return book

    def test_chapters_are_truncated_to_analyzed_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = self._make_book(tmp)
            corpus, spans = mentions.load_chapters(book / "chapters", up_to=5)
            self.assertEqual([s[0] for s in spans], [1, 2, 3, 4, 5])
            self.assertEqual(mentions.chapters_of(corpus, spans, "抽髓丸"), [1],
                             "第 8 章还没分析，不应计入最后提及")

    def test_apply_keeps_last_mention_inside_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = self._make_book(tmp)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "mentions.py"), str(book), "--apply"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            saved = json.loads((book / "data.json").read_text(encoding="utf-8"))
            fs = saved["foreshadows"][0]
            self.assertEqual(fs["last_mention_ch"], 1)
            # 已分析 5 章、阈值 50（下限），所以不该判超期
            self.assertNotEqual(fs["status"], "overdue")


if __name__ == "__main__":
    unittest.main()
