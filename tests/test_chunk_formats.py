"""chunk.py 的输入格式回归：md 的 ## 标题、epub 的 spine 顺序、短篇兜底。"""

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNK = ROOT / "scripts" / "chunk.py"


def chapter(title: str, paragraphs: int = 300) -> str:
    return title + "\n\n" + "\n".join("正文内容%d。" % i for i in range(paragraphs)) + "\n"


def run(src: Path, out: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(CHUNK), str(src), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    return proc.stdout + proc.stderr


def chapters_made(out: Path) -> list[str]:
    return sorted(p.name for p in (out / "chapters").glob("ch-*.txt"))


class ChunkFormatTest(unittest.TestCase):
    def test_markdown_heading_marker_does_not_break_detection(self):
        """`## 第X章` 曾让识别失败：锚点要求行首是「第」，被 # 挡住。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "book.md"
            src.write_text("".join(f"## 第{i}章 标题{i}\n\n" + chapter("x") for i in range(1, 5)),
                           encoding="utf-8")
            out = Path(tmp) / "out"
            log = run(src, out)
            self.assertEqual(len(chapters_made(out)), 4, log)

    def test_epub_follows_spine_order_not_filename(self):
        """文件名是 z_last / a_first，但 spine 里 z_last 在前。"""
        def page(title: str) -> str:
            return ('<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml">'
                    f'<head><title>{title}</title></head><body><h1>{title}</h1>'
                    + "".join(f"<p>正文内容{i}。</p>" for i in range(300))
                    + "</body></html>")

        opf = ('<?xml version="1.0" encoding="utf-8"?><package version="3.0">'
               '<manifest>'
               '<item id="c1" href="z_last.xhtml" media-type="application/xhtml+xml"/>'
               '<item id="c2" href="a_first.xhtml" media-type="application/xhtml+xml"/>'
               '</manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "book.epub"
            with zipfile.ZipFile(src, "w") as z:
                z.writestr("mimetype", "application/epub+zip")
                z.writestr("OEBPS/content.opf", opf)
                z.writestr("OEBPS/z_last.xhtml", page("第一章 开端"))
                z.writestr("OEBPS/a_first.xhtml", page("第二章 承接"))
            out = Path(tmp) / "out"
            log = run(src, out)
            made = chapters_made(out)
            self.assertEqual(len(made), 2, log)
            self.assertIn("开端", (out / "chapters" / made[0]).read_text(encoding="utf-8"),
                          "第一章应来自 spine 首位（z_last.xhtml），不是文件名字典序")

    def test_short_book_falls_back_to_fixed_size(self):
        """不足 3 章无法判断递增率，退化成按字数切——这是设计，不是故障。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "short.txt"
            src.write_text(chapter("第一章 只有两章", 300) + chapter("第二章 结束", 300),
                           encoding="utf-8")
            out = Path(tmp) / "out"
            log = run(src, out)
            self.assertIn("fallback", log + (out / "chunk-meta.json").read_text(encoding="utf-8"),
                          "两章的文件应走固定字数兜底并记录在 meta 里")


if __name__ == "__main__":
    unittest.main()
