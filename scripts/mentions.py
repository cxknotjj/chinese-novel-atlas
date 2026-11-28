#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mentions.py — 追踪每条伏笔的关键词在全文中的提及轨迹。

为什么需要它：
    只按「埋设章到当前章跨了多少章」判超期，会产生大量假阳性。
    一个第 7 章埋下、第 196 章还在提的主线伏笔，跨度 190 章，
    但它根本没被遗忘——真正该报警的是「埋下后就不再提」的那种。

    加了「最后一次提及」这个维度后，超期判定才有意义：
        span      = 当前章 - 埋设章          （埋了多久）
        silent    = 当前章 - 最后提及章      （多久没管它）
    判超期看 silent，不看 span。

关键词怎么选：
    优先用伏笔 content 里出现的**实体名/别名**（85% 的伏笔能命中），
    再按稀有度过滤——出现在超过 10% 章节的名字没有区分度
    （"韩立"每章都有，不能当指纹；"抽髓丸"只在 7 章出现，才是好指纹）。

用法：
    python scripts/mentions.py output/凡人修仙传            # 生成 mentions.json
    python scripts/mentions.py output/凡人修仙传 --report   # 顺带打印统计
"""

import argparse
import json
import re
from bisect import bisect_right
from collections import Counter
from pathlib import Path

# 出现在太多章里的名字不能当指纹
MAX_DF_RATIO = 0.10
# 至少这么长才算有效关键词（单字名误报太多）
MIN_KW_LEN = 2


def load_chapters(ch_dir, up_to=None):
    """把所有章节拼成一个大字符串，同时记录每章在其中的区间。

    up_to: 只收章号不超过它的章节。分析只覆盖前 N 章时，必须传 N ——
    否则会把还没分析的后文算进「最后提及」，沉默时长全部失真。
    """
    files = sorted(ch_dir.glob("ch-*.txt"))
    if not files:
        raise SystemExit(f"{ch_dir} 里没有 ch-*.txt，请先跑 chunk.py")

    parts, spans = [], []
    pos = 0
    for p in files:
        m = re.search(r"ch-(\d+)", p.name)
        if not m:
            continue
        ch = int(m.group(1))
        if up_to is not None and ch > up_to:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        spans.append((ch, pos, pos + len(t)))
        parts.append(t)
        pos += len(t) + 1          # +1 对应 join 的换行
    return "\n".join(parts), spans


def chapters_of(corpus, spans, needle):
    """返回 needle 出现过的章号列表（升序去重）。"""
    if not needle:
        return []
    starts = [s[1] for s in spans]
    found = set()
    i = corpus.find(needle)
    while i >= 0:
        idx = bisect_right(starts, i) - 1
        if idx >= 0:
            found.add(spans[idx][0])
        i = corpus.find(needle, i + 1)
    return sorted(found)


def entity_names(data):
    """收集所有实体名与别名。"""
    names = set()
    for e in data.get("entities") or []:
        for n in [e.get("name")] + list(e.get("aliases") or []):
            if n and len(n) >= MIN_KW_LEN:
                names.add(n)
    return names


def pick_keywords(content, names, df, total_ch):
    """从伏笔描述里挑出有区分度的关键词。

    df: {name: 出现在多少章}，由调用方预先算好。
    """
    hits = [n for n in names if n in content]
    # 先按稀有度排（出现章数少的优先），再按长度（长的更具体）
    hits.sort(key=lambda n: (df.get(n, 0), -len(n)))
    limit = max(2, int(total_ch * MAX_DF_RATIO))
    keep = [n for n in hits if df.get(n, 0) <= limit]
    return keep[:3] if keep else hits[:1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", help="书目录（含 data.json 与 chapters/）")
    ap.add_argument("--report", action="store_true", help="打印统计")
    ap.add_argument("--apply", action="store_true",
                    help="把 last_mention_ch 写回 data.json 并重算 status")
    ap.add_argument("--min-silent", type=int, default=50,
                    help="报告里只列沉默超过这么多章的（默认 50）")
    args = ap.parse_args()

    root = Path(args.dir)
    data = json.loads((root / "data.json").read_text(encoding="utf-8"))

    # 沉默时长只能在「已分析到的章」里算。原文有 2443 章、只拆了前 500 章时，
    # 用全 2443 章做分母会让每条伏笔都显示沉默上千章，并把错误的 status 写回去。
    analyzed = max((c.get("ch") or 0 for c in data.get("chapters") or []), default=0) or None
    corpus, spans = load_chapters(root / "chapters", up_to=analyzed)
    total_ch = len(spans)
    live = max(ch for ch, _, _ in spans)

    on_disk = len(list((root / "chapters").glob("ch-*.txt")))
    if analyzed and on_disk > total_ch:
        print(f"注意：原文 {on_disk} 章，只算已分析的 {total_ch} 章（第 {live} 章为止）")

    names = entity_names(data)
    # 先算每个实体的文档频率，用于稀有度过滤
    df = {}
    for n in names:
        df[n] = len(chapters_of(corpus, spans, n))

    out, no_kw = {}, 0
    for f in data.get("foreshadows") or []:
        fid = f.get("id")
        content = f.get("content") or ""
        kws = pick_keywords(content, names, df, total_ch)
        if not kws:
            no_kw += 1
            continue
        chs = sorted(set().union(*(set(chapters_of(corpus, spans, k)) for k in kws)))
        # 只看埋设之后（含埋设章）
        chs = [c for c in chs if c >= (f.get("plant_ch") or 0)]
        last = chs[-1] if chs else None
        out[fid] = {
            "keywords": kws,
            "mentions": chs,
            "last_mention_ch": last,
            "silent": (live - last) if last else None,
        }

    dst = root / "mentions.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"章节 {total_ch} · 已分析到第 {live} 章")
    print(f"伏笔 {len(data.get('foreshadows') or [])} 条，追踪成功 {len(out)} 条"
          f"（{'%d 条无可用关键词' % no_kw if no_kw else '全部命中'}）")
    print(f"输出 {dst}")

    if args.apply:
        # 直接写回 data.json，省掉「merge 要跑两次」的别扭。
        # status 的重算复用 merge.py 的规则，保证只有一处真源。
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from merge import apply_status

        for f in data.get("foreshadows") or []:
            rec = out.get(f.get("id"))
            if rec:
                f["last_mention_ch"] = rec.get("last_mention_ch")
                f["keywords"] = rec.get("keywords") or []
        thr, changed = apply_status(data)
        (root / "data.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写回 data.json：阈值 {thr} 章，{changed} 条状态被修正")

    if args.report:
        rows = [v for v in out.values() if v["silent"] is not None]
        rows.sort(key=lambda v: -v["silent"])
        print(f"\n=== 沉默最久的 {min(12, len(rows))} 条 ===")
        print(f"  {'沉默':>5}  {'最后提及':>8}  关键词")
        for v in rows[:12]:
            print(f"  {v['silent']:>5}  {v['last_mention_ch']:>8}  {'/'.join(v['keywords'])}")
        active = [v for v in rows if v["silent"] <= args.min_silent]
        print(f"\n线索仍活跃（沉默 ≤{args.min_silent} 章）：{len(active)} 条")
        print(f"线索已断（沉默 >{args.min_silent} 章）：{len(rows) - len(active)} 条")


if __name__ == "__main__":
    main()
