"""源文件定位、书名解析和全文字数统计。"""

import re
from pathlib import Path


def parse_source_name(source):
    """《凡人修仙传》【精校全本】作者：忘语.txt → (书名, 作者)"""
    stem = Path(source).stem
    stem = re.sub(r"【[^】]*】", "", stem).strip()
    author = ""
    m = re.search(r"作者[：:]\s*(.*)$", stem)
    if m:
        author = m.group(1).strip()
        stem = stem[:m.start()].strip()
    title = stem.strip("《》 ").strip()
    return title or "未知书名", author


def find_source_file(root, name):
    """在 book 目录的上级 / novals/ 里找原始 txt，用于统计全书字数。"""
    if not name:
        return None
    cands = [
        root.parent / name,
        root.parent / "novals" / name,
        root.parent.parent / "novals" / name,
        Path.cwd() / "novals" / name,
        Path.cwd() / name,
    ]
    for p in cands:
        if p.is_file():
            return p
    return None


def count_chars(path):
    """按常见中文编码尝试解码，返回去空白后的字数；失败返回 None。"""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "utf-16"):
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        sample = text[:8000]
        if sample and sum(1 for c in sample if "\u4e00" <= c <= "\u9fff") / len(sample) > 0.15:
            return len(re.sub(r"\s", "", text))
    return None
