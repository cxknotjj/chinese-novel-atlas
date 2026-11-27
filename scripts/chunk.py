#!/usr/bin/env python3
"""chunk.py — 把整本 txt 切成章节文件。

设计原则：**不假设任何一本书的格式**。

网文 txt 的章节标题千奇百怪，硬编码一种正则必然失效。这里用「模式库 + 自动探测 + 兜底」：

1. 内置 7 种常见模式，逐一对全文扫描
2. 按「命中数 / 章号递增率 / 章长合理性」给每种模式打分
3. 选分最高的模式切分
4. 全都不合格时，按固定字数切（并明确告知）

诊断信息会打印出来，能一眼看出分章是否正确。

用法：
    python scripts/chunk.py novals/某书.txt --out output/某书/ --limit 100
"""

import argparse
import json
import re
import sys
from pathlib import Path

ENCODINGS = ["utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "utf-16"]
NUM = r"[零〇一二两三四五六七八九十百千万\d]+"

# 每种模式都必须有 num（章号）和 title（标题）两个命名组；vol/volname 可选。
MODES = [
    # 第X卷 卷名 第Y章 章名 —— 卷章同行（凡人修仙传）
    ("vol_chapter",
     re.compile(rf"^\s*第(?P<vol>{NUM})[卷部]\s*(?P<volname>.+?)[\s\u3000]+"
                rf"第(?P<num>{NUM})[章回]\s*[：:]?\s*(?P<title>.*)$"),
     "第X卷 卷名 第Y章 章名"),

    # 第X章 章名 —— 最通用
    ("chapter_zh",
     re.compile(rf"^\s*第(?P<num>{NUM})[章回]\s*[：:·]?\s*(?P<title>.*)$"),
     "第X章 章名"),

    # 第X节 / 第X集 / 第X篇
    ("section_zh",
     re.compile(rf"^\s*第(?P<num>{NUM})[节集篇幕场]\s*[：:]?\s*(?P<title>.*)$"),
     "第X节 标题"),

    # 卷一 / 卷1 / （第一卷）
    ("volume_only",
     re.compile(rf"^\s*[（(]?第(?P<num>{NUM})[卷部][）)]?\s*[：:]?\s*(?P<title>.*)$"),
     "第X卷 卷名"),

    # 一、标题
    ("cn_numbered",
     re.compile(r"^\s*(?P<num>[一二三四五六七八九十百零〇]+)[、．.]\s*(?P<title>\S.*)$"),
     "一、标题"),

    # 1. 标题 / 001 标题 / 1、标题
    ("numbered",
     re.compile(r"^\s*(?P<num>\d{1,5})\s*[\.．、]\s*(?P<title>\S.*)$"),
     "1. 标题"),

    # CHAPTER 1 / Chapter 1: Title
    ("english",
     re.compile(r"^\s*(?:CHAPTER|Chapter|chapter)\s+(?P<num>\d{1,4})\s*[：:.、]?\s*(?P<title>.*)$"),
     "CHAPTER 1"),
]

# 无章号的结构性标题（楔子、番外、完本感言等），单独处理
SPECIAL = re.compile(
    r"^\s*(?P<title>楔子|引子|序[言章曲]?|番外[^，。]{0,12}|后记|尾声|完本感言|大结局)\s*$")

# 出现在标题位置时视为噪音
NOISE = re.compile(
    r"(声明|版权所有|仅供试读|请删除|文学社区|小说网|首发|最新网址|"
    r"本章未完|点击下一页|手机用户请|求月票|求推荐票|求订阅|"
    r"上架感言|请假条|公告|章节错误|举报|防盗|字数统计)")

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def cn2int(s):
    """'一千二百三十四' → 1234；'12' → 12。无法解析返回 None。"""
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total = section = digit = 0
    for ch in s:
        if ch in CN_DIGITS:
            digit = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if unit == 10000:
                total += (section + digit) * unit
                section = digit = 0
            else:
                section += (digit if digit else 1) * unit
                digit = 0
        else:
            return None
    return total + section + digit


def read_text(path):
    raw = Path(path).read_bytes()
    best = None
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        # 用汉字占比二次确认，避免 GB18030 把 UTF-8 也解出来
        sample = text[:8000]
        if not sample:
            continue
        han = sum(1 for c in sample if "\u4e00" <= c <= "\u9fff")
        ratio = han / max(len(sample), 1)
        if ratio > 0.15:
            return text, enc
        if best is None:
            best = (text, enc)
    if best:
        return best
    raise SystemExit("无法识别文件编码")


def scan_mode(lines, pat):
    """返回该模式的命中列表 [(line_idx, num, title, vol, volname)]"""
    hits = []
    for i, line in enumerate(lines):
        t = line.strip()
        if not t or len(t) > 70:
            continue
        if NOISE.search(t):
            continue
        m = pat.match(t)
        if not m:
            continue
        gd = m.groupdict()
        num = cn2int(gd.get("num") or "")
        if num is None:
            continue
        hits.append({
            "line": i,
            "num": num,
            "title": (gd.get("title") or "").strip(),
            "vol": cn2int(gd["vol"]) if gd.get("vol") else None,
            "volname": (gd.get("volname") or "").strip() or None,
        })
    return hits


def score(hits, total_lines):
    """给一个模式打分。返回 (score, 诊断字典)。"""
    n = len(hits)
    if n < 3:
        return 0, {"hits": n, "reason": "命中太少"}

    nums = [h["num"] for h in hits]
    # 递增率：相邻两章章号严格 +1 的比例
    inc = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
    inc_rate = inc / max(len(nums) - 1, 1)

    # 章长合理性：平均每章行数
    spans = [b["line"] - a["line"] for a, b in zip(hits, hits[1:])]
    avg_lines = sum(spans) / len(spans) if spans else 0

    s = n
    if inc_rate > 0.85:
        s *= 1.6
    elif inc_rate > 0.6:
        s *= 1.1
    else:
        s *= 0.4
    # 平均每章 2~300 行算合理
    if not (2 <= avg_lines <= 300):
        s *= 0.5

    return s, {
        "hits": n,
        "inc_rate": round(inc_rate, 3),
        "avg_lines": round(avg_lines, 1),
        "max_num": max(nums),
    }


def detect(lines):
    """遍历所有模式，返回最优结果与全部候选诊断。"""
    diag = []
    best = None
    for name, pat, desc in MODES:
        hits = scan_mode(lines, pat)
        s, d = score(hits, len(lines))
        d.update({"mode": name, "desc": desc, "score": round(s, 1)})
        diag.append(d)
        if s > 0 and (best is None or s > best[0]):
            best = (s, name, desc, hits, d)
    return best, diag


def merge_special(hits, lines):
    """把楔子/番外这类无编号标题，按行号插入章节序列。"""
    specials = []
    for i, line in enumerate(lines):
        t = line.strip()
        if not t or len(t) > 20:
            continue
        m = SPECIAL.match(t)
        if m and not any(h["line"] == i for h in hits):
            specials.append({"line": i, "num": None,
                             "title": m.group("title"), "vol": None, "volname": None})
    if not specials:
        return hits
    merged = sorted(hits + specials, key=lambda x: x["line"])
    # 给无编号的补一个序号：取前一个编号，没有则从 0 起
    last = 0
    for h in merged:
        if h["num"] is None:
            last += 1
            h["num"] = last
        else:
            last = h["num"]
    return merged


def fallback_split(lines, target_chars=3000):
    """识别不到章节时的兜底：按累计字数切。"""
    chunks, buf, count = [], [], 0
    for line in lines:
        buf.append(line)
        count += len(line)
        if count >= target_chars:
            chunks.append(buf)
            buf, count = [], 0
    if buf:
        chunks.append(buf)
    out = []
    for idx, c in enumerate(chunks, 1):
        out.append({"line": -1, "num": idx, "title": f"第 {idx} 段",
                    "vol": None, "volname": None, "_body": "\n".join(c)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-chars", type=int, default=300)
    ap.add_argument("--mode", default="", help="强制指定模式名，跳过自动探测")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    text, enc = read_text(args.src)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    if args.mode:
        hit = [m for m in MODES if m[0] == args.mode]
        if not hit:
            raise SystemExit(f"未知模式 {args.mode}，可选：{[m[0] for m in MODES]}")
        name, pat, desc = hit[0]
        hits = scan_mode(lines, pat)
        diag = [{"mode": name, "desc": desc, "hits": len(hits), "score": "-"}]
    else:
        best, diag = detect(lines)
        if best:
            _, name, desc, hits, _ = best
        else:
            name, desc, hits = "fallback", "固定字数兜底", []

    # 过滤：只保留章号递增的序列，剔除误匹配
    if hits:
        hits = merge_special(hits, lines)
        clean, expect = [], 1
        for h in hits:
            if h["num"] >= expect:
                clean.append(h)
                expect = h["num"] + 1
        hits = clean

    used_fallback = False
    if not hits:
        used_fallback = True
        chunks = fallback_split(lines)
    else:
        for idx, h in enumerate(hits):
            h["start"] = h["line"] + 1
            h["end"] = hits[idx + 1]["line"] if idx + 1 < len(hits) else len(lines)
            h["_body"] = "\n".join(lines[h["start"]:h["end"]]).strip()
        chunks = hits

    # 前言：第一个章节标题之前的内容（简介、序、盗版声明）
    front = ""
    if hits and hits[0]["line"] > 0:
        front = "\n".join(lines[:hits[0]["line"]]).strip()

    total_found = len(chunks)   # 全书识别到的章数（limit 之前）

    if args.limit:
        chunks = [c for c in chunks if c["num"] <= args.limit]

    out_dir = Path(args.out)
    ch_dir = out_dir / "chapters"
    ch_dir.mkdir(parents=True, exist_ok=True)
    for old in ch_dir.glob("ch-*.txt"):
        old.unlink()

    records, total, skipped = [], 0, 0
    for c in chunks:
        body = re.sub(r"\n{3,}", "\n\n", c.get("_body", "")).strip()
        chars = len(re.sub(r"\s", "", body))
        if chars < args.min_chars:
            skipped += 1
            continue
        name_f = f"ch-{c['num']:04d}.txt"
        (ch_dir / name_f).write_text(body, encoding="utf-8")
        records.append({
            "ch": c["num"], "vol": c.get("vol"), "vol_name": c.get("volname"),
            "title": c["title"], "file": name_f, "words": chars,
        })
        total += chars

    if front:
        (out_dir / "front-matter.txt").write_text(front, encoding="utf-8")

    meta = {
        "source": Path(args.src).name,
        "encoding": enc,
        "detected_mode": name,
        "detected_desc": desc,
        "used_fallback": used_fallback,
        "candidates": diag,
        "chapters_found": total_found,
        "chapters_written": len(records),
        "chapters_skipped": skipped,
        "total_chars": total,
        "volume_count": len({r["vol"] for r in records if r["vol"]}),
        "has_front_matter": bool(front),
        "chapters": records,
    }
    (out_dir / "chunk-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.quiet:
        print(f"{name}\t{len(records)}\t{total}")
        return

    print(f"编码        {enc}")
    print(f"采用模式    {name}（{desc}）" + ("  ⚠ 兜底切分" if used_fallback else ""))
    if not args.mode:
        print("候选诊断")
        for d in sorted(diag, key=lambda x: str(x.get("score")), reverse=True)[:4]:
            mark = " ←" if d["mode"] == name else ""
            print(f"  {d['mode']:<14} 命中 {d['hits']:>5}  "
                  f"递增率 {d.get('inc_rate', '-'):<6}  得分 {d.get('score', '-')}{mark}")
    print(f"写出章节    {len(records)}（跳过 {skipped} 个过短章）")
    print(f"总字数      {total:,}")
    if records:
        ws = [r["words"] for r in records]
        print(f"章字数      {min(ws)} ~ {max(ws)}，平均 {total // len(records)}")
        print(f"首章        {records[0]['vol_name'] or ''} {records[0]['title']}".strip())
        print(f"末章        {records[-1]['vol_name'] or ''} {records[-1]['title']}".strip())
    if front:
        print(f"前言        front-matter.txt（{len(re.sub(chr(92) + 's', '', front))} 字）")
    print(f"输出        {ch_dir}")


if __name__ == "__main__":
    main()
