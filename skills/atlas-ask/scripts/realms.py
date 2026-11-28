#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
境界体系扫描器 —— 从分章文本中反推修为体系，产出候选表供人工/模型确认。

为什么需要它：
    境界体系是「全局」概念，不能由逐批抽取各自建立。
    10 章一批的抽取视角看不到全貌，各批次独立编号 order 必然冲突，
    结果是「筑基」被排成 order=1，练气丢失，power_history 全空。

    正确流程：先全文扫描 → 确定体系骨架 → 写入 realms.json
             → merge.py 以此为权威，批次内联的 realms 只作补充。

用法：
    python scripts/realms.py output/凡人修仙传                  # 扫描并打印报告
    python scripts/realms.py output/凡人修仙传 --write          # 生成 realms.candidate.json
    python scripts/realms.py output/凡人修仙传 --check realms.json  # 校验数据是否符合体系
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# 通用境界词表（按从低到高的常见序列，仅作候选提示，不预设某本书的顺序）
REALM_WORDS = [
    "炼气", "练气", "引气", "聚气", "凝气",
    "筑基", "开光", "融合", "心动", "灵寂",
    "结丹", "金丹", "元婴", "化神", "炼虚",
    "合体", "大乘", "渡劫", "仙人", "真仙",
    "斗者", "斗师", "大斗师", "斗灵", "斗王", "斗皇", "斗宗", "斗尊", "斗圣", "斗帝",
    "武徒", "武者", "武师", "大武师", "武灵", "武宗", "武尊", "武皇", "武圣", "武帝",
    "凝元", "开元", "通灵", "通神", "先天", "后天",
]

# 层级表述：第一层 / 第三重 / 第五品 / 第七阶
LAYER_RE = re.compile(r"第\s*([一二三四五六七八九十百零〇\d]+)\s*([层重品阶段])")
# 境界 + 小阶段：练气三层 / 筑基中期
STAGE_RE = re.compile(r"([\u4e00-\u9fa5]{2,4}?)\s*([一二三四五六七八九十]{1,3})\s*[层重]")
# 功法名候选：以 功/诀/经/法/术/典/篇 结尾的 2-5 字词
TECH_NAME_RE = re.compile(r"[\u4e00-\u9fa5]{2,4}(?:功|诀|经|法|术|典|篇)")
# 虚词前缀，出现在功法名前说明是误切
STOP_PREFIX = ("这是", "那是", "你能", "我能", "他把", "她把", "并", "但", "则", "而",
               "的", "了", "在", "把", "将", "被", "从", "向", "对", "与", "和")

CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100}


def cn2int(s):
    """中文数字转整数，支持 1-99 与百位。失败返回 None。"""
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    total, section, last = 0, 0, 0
    for ch in s:
        if ch in CN_NUM:
            v = CN_NUM[ch]
            if v == 100:
                section = (section or 1) * 100
                total += section
                section = 0
            elif v == 10:
                section = (section or 1) * 10
            else:
                section += v
                last = v
        else:
            return None
    return total + section


def load_chapters(root):
    ch_dir = Path(root) / "chapters"
    if not ch_dir.exists():
        raise SystemExit(f"找不到 {ch_dir}，请先运行 chunk.py")
    out = []
    for p in sorted(ch_dir.glob("ch-*.txt")):
        m = re.search(r"ch-(\d+)", p.name)
        if not m:
            continue
        out.append((int(m.group(1)), p.read_text(encoding="utf-8", errors="replace")))
    return out


def scan(chapters):
    """返回 {realm_word: {count, first_ch, chapters:set}} 与功法层级候选。"""
    words = defaultdict(lambda: {"count": 0, "first_ch": None, "chapters": set()})
    layers = defaultdict(lambda: {"count": 0, "first_ch": None, "chapters": set(), "max": 0})
    techs = defaultdict(lambda: {"count": 0, "first_ch": None, "max_layer": 0, "chapters": set()})

    # 第一遍：全书功法名候选（按出现频次，用于第二遍就近匹配）
    name_freq = Counter()
    for _, text in chapters:
        for m in TECH_NAME_RE.finditer(text):
            n = m.group(0)
            if not any(n.startswith(p) for p in STOP_PREFIX):
                name_freq[n] += 1
    known_techs = {n for n, c in name_freq.items() if c >= 3}

    for ch, text in chapters:
        for w in REALM_WORDS:
            c = text.count(w)
            if c:
                r = words[w]
                r["count"] += c
                r["chapters"].add(ch)
                if r["first_ch"] is None:
                    r["first_ch"] = ch

        for m in LAYER_RE.finditer(text):
            n = cn2int(m.group(1))
            if not n:
                continue
            key = m.group(2)
            r = layers[key]
            r["count"] += 1
            r["chapters"].add(ch)
            r["max"] = max(r["max"], n)
            if r["first_ch"] is None:
                r["first_ch"] = ch

            # 层数左侧 14 字内找最近的已知功法名
            left = text[max(0, m.start() - 14):m.start()]
            hit = None
            for name in known_techs:
                if name in left and (hit is None or left.rfind(name) > left.rfind(hit)):
                    hit = name
            t = techs[hit or "(未标注功法)"]
            t["count"] += 1
            t["chapters"].add(ch)
            t["max_layer"] = max(t["max_layer"], n)
            if t["first_ch"] is None:
                t["first_ch"] = ch

    return words, layers, techs


def report(words, layers, techs, chapters):
    print(f"扫描 {len(chapters)} 章，共 {sum(len(t) for _, t in chapters):,} 字\n")

    if words:
        print("=== 境界词（按首次出现章排序）===")
        print(f"  {'境界':<6} {'次数':>5}  {'首现':>5}  {'覆盖章数':>6}")
        for w, r in sorted(words.items(), key=lambda x: (x[1]["first_ch"], -x[1]["count"])):
            print(f"  {w:<6} {r['count']:>5}  {r['first_ch']:>5}  {len(r['chapters']):>6}")
    else:
        print("=== 境界词 ===\n  未命中任何常见境界词")

    print()
    if layers:
        print("=== 层级表述（第X层/重/品）===")
        for k, r in sorted(layers.items(), key=lambda x: -x[1]["count"]):
            print(f"  「{k}」 出现 {r['count']} 次，最大层数 {r['max']}，首现 ch{r['first_ch']}")
    else:
        print("=== 层级表述 ===\n  未命中")

    print()
    if techs:
        print("=== 功法层级（功法名 + 第X层）===")
        for k, r in sorted(techs.items(), key=lambda x: -x[1]["count"])[:15]:
            print(f"  {k:<10} 出现 {r['count']:>4} 次，最高第 {r['max_layer']} 层，首现 ch{r['first_ch']}")
    else:
        print("=== 功法层级 ===\n  未命中")

    print("\n--- 提示 ---")
    if layers and not words:
        print("本书用「第X层」表述修为，未出现标准境界词。")
        print("推论：层级序列本身就是境界骨架，realm.order 应按层数排。")
    elif words and layers:
        print("同时出现境界词与层级词，可能是「境界 + 小阶段」结构：")
        print("  realms[].stages 装层数，realm.order 装境界高低。")


def check(root, spec_path):
    """校验 data.json 的 power_history 是否符合给定体系。"""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    order = {r["id"]: r.get("order", 99) for r in spec.get("realms", [])}
    stages = {r["id"]: set(r.get("stages") or []) for r in spec.get("realms", [])}

    data = json.loads((Path(root) / "data.json").read_text(encoding="utf-8"))
    errs, warns = [], []

    for e in data["entities"]:
        ph = e.get("power_history") or []
        for i, p in enumerate(ph):
            if p.get("realm") not in order:
                errs.append(f"{e['name']}: 境界 {p.get('realm')} 不在体系中")
            elif p.get("stage") and stages[p["realm"]] and p["stage"] not in stages[p["realm"]]:
                errs.append(f"{e['name']}: 小阶段 {p['stage']} 不属于 {p['realm']}")
            if i and p["ch"] <= ph[i - 1]["ch"]:
                errs.append(f"{e['name']}: ch{p['ch']} 章号未递增")
            if i and order.get(p["realm"], 99) < order.get(ph[i - 1]["realm"], 99):
                warns.append(f"{e['name']}: ch{p['ch']} 由 {ph[i-1]['realm']} 降到 {p['realm']}（跌境？）")

    print(f"校验 {len(data['entities'])} 个实体")
    print("\n".join(errs) if errs else "无错误")
    if warns:
        print("\n降境警告：")
        print("\n".join(warns))
    return 0 if not errs else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--write", action="store_true", help="生成 realms.candidate.json")
    ap.add_argument("--check", default="", help="校验 data.json 是否符合指定体系文件")
    args = ap.parse_args()

    if args.check:
        raise SystemExit(check(args.dir, args.check))

    chapters = load_chapters(args.dir)
    words, layers, techs = scan(chapters)
    report(words, layers, techs, chapters)

    if args.write:
        cand = {
            "note": "自动扫描的候选体系，需人工确认 order 与 stages 后再用于 merge",
            "realm_words": [
                {"name": w, "count": r["count"], "first_ch": r["first_ch"]}
                for w, r in sorted(words.items(), key=lambda x: x[1]["first_ch"] or 0)
            ],
            "layer_max": {k: v["max"] for k, v in layers.items()},
            "techniques": [
                {"name": k, "max_layer": v["max_layer"], "first_ch": v["first_ch"]}
                for k, v in sorted(techs.items(), key=lambda x: -x[1]["count"])[:30]
            ],
        }
        out = Path(args.dir) / "realms.candidate.json"
        out.write_text(json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
