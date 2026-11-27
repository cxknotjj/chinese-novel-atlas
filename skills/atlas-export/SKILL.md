---
name: atlas-export
version: 0.1.0
description: "把拆解结果导出成别的格式：伏笔清单 CSV、Markdown 设定集、可挂 GitHub Pages 的静态百科、单文件 HTML。作者拿去做改稿对照，读者和同人拿去查设定。触发词：导出设定集、导出伏笔清单、导出人物表、生成百科、做成 Wiki、导出一份设定文档、给我 CSV、atlas export。"
---

# atlas-export · 导出设定集

`data.json` 是内部格式。这个 skill 把它变成能直接用的东西。

## 五种导出

```bash
python scripts/export.py --dir output/青云签到三十年/ --format fs
python scripts/export.py --dir output/青云签到三十年/ --format md
python scripts/export.py --dir output/青云签到三十年/ --format csv
python scripts/export.py --dir output/青云签到三十年/ --format site
python scripts/export.py --dir output/青云签到三十年/ --format single
```

`--format all` 一次产出五种；`--out` 可改输出目录（默认 `export/`）。

| format | 产出 | 给谁用 |
|---|---|---|
| **`fs`** | `export/伏笔清单.csv` | **作者改稿对照**，最重要的一种 |
| `md` | `export/设定集.md` | 贴进笔记、提交到 Wiki |
| `csv` | `export/角色表.csv` | 导入 Excel 做统计 |
| `site` | `export/site/`（多页静态站） | 挂 GitHub Pages，同人和读者能搜到 |
| `single` | `export/设定集.html` | 单文件，发给不用电脑的人 |

## `fs` — 伏笔清单（作者最需要）

```csv
id,内容,埋设章,回收章,状态,跨度,线索,重要度,备注
f_yupei,"父亲留下的云纹玉佩，系统无法鉴定",3,87,有回收章,84,身世之谜,1.0,
f_xitong,"签到系统的来源与代价",1,,已超期,119,金手指,0.9,
f_canye,"阿福枕下的半张残页，只剩「血刀门」三字",11,,已超期,109,血刀门,0.85,
```

按状态排序（超期 → 待回收 → 有回收章 → 已放弃），跨度 = 回收章（未回收则按已分析章数）− 埋设章。文件用 UTF-8 BOM，Excel 双击不乱码。

**状态口径**：只有存在 `payoff_ch`（且不早于 `plant_ch`）才写「有回收章」；`last_mention_ch` 只用于判断沉默/超期，单独一次“再次提及”不算回收。

**用途**：作者可以直接把这个 CSV 拖进 Excel，当作改稿清单，一条条划掉。

## `md` — Markdown 设定集

```markdown
# 青云签到三十年 · 设定集

> 示例作者 · 92 万字 · 300 章 · 仙侠 · 番茄
> 由 Novel Atlas 生成于 2026-11-27

## 角色（14）

### 林云
云哥、林师弟、林师兄

主角。穿越前是程序员，附身青云宗杂役……（第 1 章登场）

**境界**：练气三层（第 1 章）→ 筑基初期（第 45 章）→ 金丹初期（第 98 章）

**关系**
- 苏清 — 相知（情感）
- 李长老 — 师徒（师承）
- 赵虎 — 宿怨（敌对）

**档案**：性格 · 谨慎、护短 / 金手指 · 签到系统

---

### 苏清
…

## 境界体系（4 级）
## 势力（3）
## 地点（6）
## 设定（5）
## 伏笔台账（12）
```

按关系数（degree）降序——重要的排前面，卡片上标 `group` 阵营。

角色条目必须带**境界轨迹**，这是网文设定集和古典小说设定集最大的区别。

## `site` — 静态站

```
export/site/
  index.html          总览 + 伏笔总表（按阵营分组的角色卡片）
  style.css
  character/
    e_linyun.html     人物 / 势力各一页
  place/
    p_qingyun.html    地点一页
  concept/
    c_xitong.html     设定一页
```

每人一页的好处：**能被搜索引擎收录**。网文同人搜"林云 境界"时，可能落到你的页面上。

## 硬性约束

1. **不要导出原文。** 只导出结构化数据，`evidence` 坐标保留，正文不带。
2. **不要丢掉 `meta`。** 每个导出物顶部都要有书名、作者、题材、平台、章数、生成时间——否则别人拿到一份设定集不知道是哪来的。
3. **CSV 要处理逗号和引号。** 中文简介里有逗号，必须加引号；内容里已有「」的不要再套引号。
4. **伏笔状态要现算。** 用 `plant_ch` / `payoff_ch` / 阈值派生，不要照抄存储的 `status`。

## 与其他 skill 的关系

```
atlas-analyze → data.json ─┬→ atlas-ask
                           ├→ atlas-compare
                           └→ atlas-export → fs / md / csv / site / single
```

`export` 是终点，不产出新的 `data.json`。

## 扩展点

想加新格式（PDF、Notion、Obsidian vault），在 `scripts/export.py` 里加一个 `export_<format>()` 函数，并在 `main()` 的 `formats` 分支注册。**不要改核心数据结构。**
