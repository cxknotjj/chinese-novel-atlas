---
name: atlas-export
version: 0.2.0
description: "把拆解结果导出成读者能直接用的东西：读者站、单文件世界档案、Markdown 设定集、角色表、伏笔索引、地图 PNG/SVG。读者/同人/书评考据者拿去查设定；不再产出作者改稿清单。触发词：导出读者站、导出设定集、导出人物表、生成世界档案、做成 Wiki、导出一份设定文档、给我 CSV、atlas export、导出到第 N 章。"
---

> **工作目录**：下文所有 `python scripts/...` 均以 Novel Atlas 仓库根为工作目录。
> 若尚未获取仓库：
> ```bash
> git clone https://github.com/cxknotjj/chinese-novel-atlas.git
> cd chinese-novel-atlas
> ```
> skill 本体只含说明与参考资料，CLI 在仓库的 `scripts/` 下。

# atlas-export · 导出读者世界档案

`data.json` 是内部格式。这个 skill 把它变成读者能直接打开、能按阅读进度截断的产物。

## 六种导出

```powershell
python scripts/export.py --dir output/青云签到三十年/ --format reader
python scripts/export.py --dir output/青云签到三十年/ --format single
python scripts/export.py --dir output/青云签到三十年/ --format md
python scripts/export.py --dir output/青云签到三十年/ --format csv
python scripts/export.py --dir output/青云签到三十年/ --format fs
python scripts/export.py --dir output/青云签到三十年/ --format site
```

`--format all` 一次产出全部；`--out` 可改输出目录（默认 `export/`）。

| format | 产出 | 给谁用 |
|---|---|---|
| **`reader`** | `export/reader/index.html` + `data.js` + `anomalies.json` + `reader-manifest.json` | **读者站主产物**：总览、阅读进度、剧透截断、疑点索引、全书搜索 |
| `single` | `export/设定集.html` | 单文件，发给不用电脑的人；内嵌地图与八视图 |
| `md` | `export/设定集.md` | 贴进笔记、提交到 Wiki |
| `csv` | `export/角色表.csv` | 导入 Excel 做统计 |
| `fs` | `export/伏笔索引.csv` | 书评/考据者查回收率，不再称“作者改稿清单” |
| `site` | `export/site/`（多页静态站） | 挂 GitHub Pages，同人和读者能搜到 |

## `reader` — 读者站（主产物）

```powershell
python scripts/build_reader.py --data samples/fictional/data.json --out demo/reader --single --allow-partial
python scripts/build_reader.py --data output/凡人修仙传/data.json --out output/凡人修仙传/reader --cutoff 500 --allow-partial
```

- 默认要求 `coverage.chapters_done == meta.chapters`；不满足时加 `--allow-partial`（试读/样书），manifest 会写 `publishable: false`。
- `--cutoff N` 生成真正冻结到第 N 章的副本；不传时页面默认全书，读者拖动进度条只在已分析范围内取 `?cutoff=`。
- `--single` 单文件；不加则 external 静态站，入口 `index.html` + `data.js`。
- 页面必须同时有：总览、阅读进度条、全书搜索、疑点视图；未来内容默认锁定，不展开。
- 每本读者站至少产出 `anomalies.json` 和 `reader-manifest.json`；后者记录 coverage、cutoff、地图等级、疑点可见数。

**剧透边界**：静态单文件若内嵌完整 `data.js`，devtools 仍可能看到未来数据；要真正不发布未来内容，用 `--cutoff` 生成冻结副本。UI 截断是投影，不是服务端鉴权。

## `fs` — 伏笔索引（考据用）

文件产出仍叫 `伏笔清单.csv`，但定位改为**读者/书评考据的回收率索引**，不是作者改稿清单。

```csv
id,内容,埋设章,回收章,状态,跨度,线索,重要度,备注
f_yupei,"父亲留下的云纹玉佩，系统无法鉴定",3,87,有回收章,84,身世之谜,1.0,
f_xitong,"签到系统的来源与代价",1,,已超期,119,金手指,0.9,
f_canye,"阿福枕下的半张残页，只剩「血刀门」三字",11,,已超期,109,血刀门,0.85,
```

按状态排序（超期 → 待回收 → 有回收章 → 已放弃），跨度 = 回收章（未回收则按已分析章数）− 埋设章。文件用 UTF-8 BOM，Excel 双击不乱码。

**状态口径**：只有存在 `payoff_ch`（且不早于 `plant_ch`）才写「有回收章」；`last_mention_ch` 只用于判断沉默/超期，单独一次“再次提及”不算回收。

**用途**：书评/考据者可以按状态筛选“埋下后一直没提”的支线，回到原文坐标核对；不产出改稿建议。

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

角色条目必须带**境界轨迹**，这是网文设定集和古典小说设定集最大的区别。轨迹配色：每个境界独立色相；同一境界内由浅到深表示小阶成长；突破到下一境界后换色并重新从浅色开始。未记录到的小阶不推断为巅峰。

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

## 地图视图的导出口径

`single` / `reader` 内嵌的 `data.json` 包含完整地图视图（示意 2D / 证据方位 / 拓扑 + 层筛选 + 编排 + PNG/SVG 导出）。导出口径与 `atlas-map` 的 `web-contract.md` 一致：

- **示意 2D（默认）**：`map_layout` 的人工近似坐标叠加在 `atlas-kit` 纸底与 21 件景物 stamp 上；坐标是 0–100 归一化的**示意坐标，非经纬度、非原文证据**；题签/印章/免责文案保留。
- **证据方位**：只画带 `direction / distance / contain / adjacent` 证据的关系；层内 direction+distance 约束 <3 条时自动回退拓扑，导出物显示回退原因，不画假坐标。
- **拓扑**：`places.parent` 层级/拓扑树，节点位置仅用于避让，不代表原文方位。
- 每个层显示 M0–M4；M4 只在 `map_layout.time_slices` 有数据时出现，不硬造时间切片。
- `map_layout` 缺失时 2D 回退拓扑并显示原因；`spatial_relations` 的 `evidence.ch` 与 `quote`（≤120 字）用于溯源。
- `fs` / `md` / `csv` / `site` 不展开空间关系正文与示意坐标，也不携带位图资源。

## 位图内联（single / reader 单文件）

- 单文件 HTML 必须把当前消费的位图资产内联：`template/assets/map/atlas/` 的 21 件 webp + 纸底 + 海纹；占位符 `__ASSET__:map/...` 由 `build.py` 转 base64，缺失或残留时构建**直接失败**。
- 当前内联 23 张，原始约 1,075 KB，base64 后约 1.44 MB；样例单文件约 1.7 MB，凡人 500 章约 2.3 MB，满足 <3 MB 预算。
- `fs` / `md` / `csv` / `site` 不内联图片，也不导出位图资源。

## 硬性约束

1. **不要导出章节原文。** 只导出结构化数据，`evidence` 坐标保留，正文不带。空间关系的 `evidence.quote` 是契约允许的短原文片段（≤120 字），随 `spatial_relations` 用于点节点溯源，不属于整章正文导出。
2. **不要丢掉 `meta`。** 每个导出物顶部都要有书名、作者、题材、平台、章数、生成时间——否则别人拿到一份设定集不知道是哪来的。
3. **CSV 要处理逗号和引号。** 中文简介里有逗号，必须加引号；内容里已有「」的不要再套引号。
4. **伏笔状态要现算。** 用 `plant_ch` / `payoff_ch` / 阈值派生，不要照抄存储的 `status`。

## 与其他 skill 的关系

```
atlas-analyze → data.json ─┬→ atlas-ask
                           ├→ atlas-compare
                           ├→ atlas-audit
                           └→ atlas-export → reader / single / md / csv / fs / site
```

`export` 是终点，不产出新的 `data.json`；`reader` 的截断副本只写输出目录，不改源数据。

## 扩展点

想加新格式（PDF、Notion、Obsidian vault），在 `novel_atlas/export/` 下新建一个导出模块，实现 `export_<format>(data, out_dir)`，再到 `scripts/export.py` 的 `exporters` 字典和 `--format` choices 里注册。**不要改核心数据结构。**
