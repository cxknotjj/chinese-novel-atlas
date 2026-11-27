---
name: atlas-export
version: 0.1.0
description: "把拆解结果导出成别的格式：Markdown 设定集、单页 HTML、CSV 人物表、可挂 GitHub Pages 的静态 Wiki。用于分享、归档、二次加工。触发词：导出设定集、导出人物表、生成百科、做成 Wiki、导出一份设定文档、给我 CSV、导出成 Markdown、atlas export。"
---

# atlas-export · 导出设定集

`data.json` 是内部格式。这个 skill 把它变成别人能看、能用的东西。

## 四种导出

```bash
python scripts/export.py --dir output/红楼梦/ --format md
python scripts/export.py --dir output/红楼梦/ --format site
python scripts/export.py --dir output/红楼梦/ --format csv
python scripts/export.py --dir output/红楼梦/ --format single
```

| format | 产出 | 用途 |
|---|---|---|
| `md` | `export/设定集.md` | 贴进笔记、提交到 Wiki |
| `site` | `export/site/`（多页静态站） | 挂 GitHub Pages，可被别人检索到 |
| `csv` | `export/人物表.csv` | 导入 Excel、做二次统计 |
| `single` | `export/设定集.html` | 单文件，发给不用电脑的人 |

## 各格式的结构

### `md` — Markdown 设定集

```markdown
# 红楼梦 · 设定集

> 曹雪芹 · 73 万字 · 120 回
> 由 Novel Atlas 生成于 2026-11-27

## 人物（51）

### 贾宝玉
怡红公子、绛洞花主、宝二爷

全书主角，衔通灵宝玉而生……（第 2 回登场）

**关系**
- 林黛玉 — 木石前盟（情感）
- 薛宝钗 — 成婚（婚姻）
- 袭人 — 主仆（主从）

**档案**：身份 · 贾政次子 / 结局 · 中举后出家

---

### 林黛玉
…

## 地点（10）
## 概念与器物（6）
## 大事记
```

按 `group` 分组，组内按 `degree` 降序——**重要的排前面**。

### `site` — 静态站

```
export/site/
  index.html          总览（图谱缩略 + 统计）
  character/
    e_baoyu.html      每人一页
    e_daiyu.html
  place/
  concept/
  assets/
```

每人一页的好处：**能被搜索引擎收录**。有人搜"贾宝玉 人物关系"，可能落到你的页面上。

### `csv` — 人物表

```csv
name,aliases,group,first_ch,degree,desc
贾宝玉,"怡红公子|绛洞花主|宝二爷",荣国府,2,19,"全书主角……"
```

别名用 `|` 分隔（Excel 里逗号会串列）。

## 硬性约束

1. **不要导出原文。** 只导出结构化数据，`evidence` 坐标保留，正文不带。
2. **不要丢掉 `meta`。** 每个导出物顶部都要有书名、作者、生成时间、来源标记——否则别人拿到一份设定集不知道是哪来的。
3. **CSV 要处理逗号和换行。** 简介里有中文逗号，必须加引号。

## 与其他 skill 的关系

```
atlas-analyze → data.json → atlas-export → md / site / csv / single
                           → atlas-ask
                           → atlas-compare
```

`export` 是终点，不产出 `data.json` 的变体。

## 扩展点

想加新格式（PDF、Notion、Obsidian vault），在 `scripts/export.py` 加一个 `export_<format>()` 函数，注册到 `FORMATS` 字典即可。**不要改核心数据结构。**
