# Novel Atlas

**把一本 200 万字的网文，做成能边看边查的世界百科——读到第 47 章，就只显示到第 47 章的设定，不剧透后面。**

[![GitHub stars](https://img.shields.io/github/stars/cxknotjj/chinese-novel-atlas?style=social)](https://github.com/cxknotjj/chinese-novel-atlas)
[![contract](https://github.com/cxknotjj/chinese-novel-atlas/actions/workflows/contract.yml/badge.svg)](https://github.com/cxknotjj/chinese-novel-atlas/actions/workflows/contract.yml)
[![MIT](https://img.shields.io/badge/license-MIT-5A7A5E)](LICENSE)
![Skills](https://img.shields.io/badge/Skills-6-5A7A5E)

**[在线试玩：虚构样例《青云签到三十年》](http://deerfect.me/chinese-novel-atlas/demo/)** ·
[数据契约](references/schema.md) ·
[功能文档](docs/功能文档.md) ·
[English](README_EN.md)

![读者世界档案：八个视图共用一份数据](docs/screenshots/reader-home.png)

同一份 `data.json` 投影出八个视图：人物图谱、设定百科、地点志、世界地图、势力版图、节奏曲线、境界轨迹、伏笔台账。拖动顶部进度条，整站内容跟着截断到你读到的那一章。

---

## 为什么是 Skill 而不是网页

- **核心是 6 个 Agent Skill。** 分析、问答、对比、导出、地图、疑点复核都能被 Agent 直接调用；`reader/` 和 `atlas.html` 只是同一份数据的发布面。
- **每条结论都能回到原文。** 人物、地点、关系、伏笔、地图节点都带 `chN:pM` 坐标；没有证据的推断不写入档案。
- **一份 `data.json` 投影成多种产物。** 读者站、单文件八视图、地图、设定集、角色表、跨书指标，共享同一套实体与证据。
- **读者向，不剧透。** 用 `cutoff_ch` 按阅读进度截断人物、关系、伏笔和地图层；未来内容默认锁定。
- **视觉不是贴图。** 地图由 21 件手绘 PNG + 9 类代码/SVG 变量层组成；境界轨迹用多色相时间线，同境界由浅到深，突破后换色重新变浅。

## 用 STAR 看懂

| | |
|---|---|
| **S — Situation** | 一本完本网文动辄几十万到几百万字，人物、地点、伏笔、境界和地图散落在几千章正文里。 |
| **T — Task** | 把整本书拆成可查询、可复核、可按阅读进度发布的世界档案，而不是再做一个读完就忘的摘要页。 |
| **A — Action** | 用 6 个 Skill 跑完「分批抽取 → 合并校验 → 疑点/地图/读者站投影」，所有结论落到 `data.json` 和原文坐标。 |
| **R — Result** | 读者能按进度逛人物、地点、关系、伏笔、境界和地图；研究者能拿同一份数据做问答、对比与二次导出。 |

---

## 效果

截图来自仓库内的虚构样例与《凡人修仙传》500 章真实数据，不是概念图。

| 疑点索引：每条带证据，可标已核实/误报 | 境界轨迹：多色相 + 同境界浅到深 |
|---|---|
| ![疑点索引](docs/screenshots/reader-anomalies.png) | ![境界轨迹](docs/screenshots/realm-colors.png) |

![《凡人修仙传》多层地图：21 件手绘 PNG + 9 类 SVG 变量层](docs/screenshots/map-fanren.png)

读者站与地图在 500px 宽度下可用；地图桌面端右键拖拽平移、移动端单指拖拽平移，缩放百分比实时显示。

---

## 六个 Skill

| Skill | 自然语言入口 | 职责 | 主要产物 |
|---|---|---|---|
| `atlas-analyze` | “分析《我的书》完本” | 分章、批次抽取、合并、校验、快照 | `data.json`、`atlas.html` |
| `atlas-ask` | “韩立第几章筑基？” | 先查结构，再回原文；答案带坐标 | 带 `chN:pM` 的回答 |
| `atlas-compare` | “对比两本书的伏笔回收率” | 节奏、伏笔、战力、势力、疑点密度 | `metrics.md`、`diff.json`、`compare.html` |
| `atlas-export` | “导出《我的书》读者站” | 读者站 / 单文件 / 设定集 / 角色表 | `reader/`、`atlas.html`、MD/CSV |
| `atlas-map` | “给《我的书》做地图” | M0–M4 分级、JSON 编排、地图审计、渲染 | `map_layout`、PNG/SVG、地图页 |
| `atlas-audit` | “复核《我的书》的疑点” | 疑点列表、证据回看、标记已核实/误报 | `anomalies-verdicts.json` |

把 `skills/` 整体挂到 Agent 的 skill root，或让 Agent 直接读取对应 `SKILL.md` 即可；不需要启动服务，也不调用外部模型 API。

---

## 安装

```bash
npx skills add cxknotjj/chinese-novel-atlas -y -g
```

`-g` 全局安装，所有目录可用；去掉 `-g` 只装到当前目录。更新时重跑同一条命令即可。

skill 本体是说明与参考资料，实际干活的 CLI 在仓库里，所以再 clone 一份：

```bash
git clone https://github.com/cxknotjj/chinese-novel-atlas.git
cd chinese-novel-atlas
```

装完后在你正在用的 Agent（Claude Code / Codex / 任何能读 `SKILL.md` 的工具）里，在仓库目录下直接说：

> 拆《我的书》

六个 skill 会按需加载，不需要单独配模型或起服务。也可以让 Agent 直接读 `skills/atlas-analyze/SKILL.md` 手动走流程。

---

## 快速开始（命令行）

### 1. 分析一本完本小说

按 [`skills/atlas-analyze/SKILL.md`](skills/atlas-analyze/SKILL.md) 执行。CLI 负责切分、合并、校验和构建，逐批抽取由执行 Agent 完成：

```powershell
python scripts/chunk.py "D:\path\我的书.txt" --out output/我的书
python scripts/merge.py output/我的书 --genre 仙侠 --platform 起点
python scripts/mentions.py output/我的书 --apply
python scripts/validate.py output/我的书/data.json
python scripts/build.py --data output/我的书/data.json --out output/我的书
```

每批 10 章，抽取结果写成批次 JSON，原文不进入最终档案。

### 2. 问答与对比

```powershell
python scripts/seek.py --data output/我的书/data.json --query "韩立第几章筑基"
python scripts/compare.py --a output/A/data.json --b output/B/data.json --out output/_compare
```

### 3. 疑点索引与复核

```powershell
python scripts/anomalies.py --data output/我的书/data.json
python skills/atlas-audit/scripts/audit.py stats --data output/我的书/data.json
python skills/atlas-audit/scripts/audit.py list  --data output/我的书/data.json --severity warning
```

`--cutoff N` 可只保留证据不晚于第 N 章的疑点；复核结果写入 `anomalies-verdicts.json`，不修改原索引。

### 4. 生成读者站

```powershell
python scripts/build_reader.py --data output/我的书/data.json --out output/我的书/reader --single
python scripts/build_reader.py --data output/我的书/data.json --out output/我的书/reader --cutoff 120 --allow-partial
```

- 默认要求 `coverage.chapters_done == meta.chapters`；只分析了前 N 章时加 `--allow-partial`，manifest 会写 `publishable: false`。
- `--cutoff N` 生成真正冻结到第 N 章的副本；不传时页面默认全书，读者拖动进度条只在已分析范围内取 `?cutoff=`。
- `--single` 单文件；不加则 external 静态站（`index.html` + `data.js`）。
- 读者站同时产出 `anomalies.json` 与 `reader-manifest.json`。

### 5. 地图

```powershell
python skills/atlas-map/scripts/atlas_map.py --project-root . levels --data output/我的书/data.json
python skills/atlas-map/scripts/atlas_map.py --project-root . audit  --data output/我的书/data.json
```

地图是 `atlas-map` 的输出，不是产品入口：

1. **M0–M4 自动分级**：M0 地点索引；M1 拓扑/示意；M2 方向/距离证据 ≥3 条；M3 多层；M4 `time_slices` 时态切片。
2. **网页编排器**：示意 2D 里点「编排」，拖节点、给节点选层、挂/移除 21 件底件、导出 `map-layout.json`；M4 数据出现时间切片下拉；PNG/SVG 导出当前视图。
3. **读者版截断**：只画 `first_ch <= cutoff_ch` 的区域、节点、路线、stamp；未来层不画。
4. **示意坐标不是经纬度**：`map_layout` 坐标是 0–100 的示意坐标，不是原文方位证据；只有 `spatial_relations` 的 direction/distance 才对回原文。
5. **缩放不裁装饰**：地图内容随缩放变化，纸底、题签和工具条保持屏幕尺寸；桌面右键拖拽、移动端单指拖拽平移，缩放百分比实时更新。

---

## 数据契约

`data.json` 是唯一事实源，schema v2.0。读者向派生字段：

| 字段 | 说明 |
|---|---|
| `anomalies` | 疑点数组；每条必须有 `id`、`evidence` |
| `_anomalyMeta` | 阈值、live 章、统计、规则错误 |
| `_mapLevels` | 地图 M0–M4 分级与每层方向约束数 |
| `_reader` | `cutoff_ch / analyzed_ch / chapter_max / total_chapters / analysis_complete / is_spoiler_safe` |

完整字段、`cutoff_ch` 投影规则、疑点对象、`map_layout` 与 `time_slices` 契约见 [`references/schema.md`](references/schema.md)。

**硬规则**：所有实体、地点、关系、伏笔、地图节点都要能回到 `chN:pM`；没有证据不进入结论。疑点只给证据和可能解释，不给“应该怎么改”。

---

## Reader 只是发布面

`atlas-export` 把同一份 `data.json` 投影成读者站。它做三件事：

- **按章截断**：实体、地点、势力、关系、伏笔、地图层、疑点都受 `cutoff_ch` 约束；
- **不剧透**：未来节点不显示，未来命中只提示“第 N 章后解锁”；
- **证据可回看**：疑点、伏笔、地点都带 `chN:pM`，点击可跳到章节。

页面入口：

```text
reader/index.html    静态读者站
atlas.html           单文件八视图
anomalies.json       疑点索引
reader-manifest.json coverage / cutoff / 地图等级 / 疑点可见数
```

---

## 输出结构

```text
output/我的书/
  data.json               schema v2.0；唯一事实源
  anomalies.json          疑点索引
  anomalies-verdicts.json 人工复核（可选，不修改 anomalies.json）
  atlas.html              单文件八视图
  reader/
    index.html            读者站入口
    data.js               external 模式的数据
    anomalies.json
    reader-manifest.json  coverage / cutoff / 地图等级 / 疑点可见数
  versions/
    v1.json / latest.json 版本快照
```

## 版本与重跑

```powershell
python scripts/snapshot.py --data output/我的书/data.json --label 500章
python scripts/snapshot.py --diff output/我的书/versions/v1.json output/我的书/versions/v2.json
```

快照记录 fingerprint、counts、实体/地点/伏笔/概念 `name → id` 映射；`diff` 输出新增、删除、ID 漂移。重跑/换版后同名对象换 ID 会被标出来。

---

## 测试与 CI

```powershell
python -m unittest discover -s tests -v
```

覆盖 schema 校验、图片内联、模块拼装、导出、合并、读者 cutoff、疑点规则、版本 diff、地图 M0–M4、读者站 annotate、地图拖拽/缩放百分比、伏笔状态筛选、境界配色。CI 在 `.github/workflows/contract.yml` 跑样例校验、测试和构建。

---

## 不做什么

- 不写小说、不续写、不改文风。
- 不做作者工作台、连载提醒、改稿清单、编辑审稿流。
- 不做通用 RAG 聊天；先查结构，再回原文，答案必须带坐标。
- 不做精确 GIS；示意地图不承担经纬度、比例尺、真实海岸线。
- 不做 SaaS 书库；默认本地，稿件不上传、不训练。
- 不继续加 tabs；八视图够多，下一步是收口成读者档案。

---

## 目录

```text
skills/               六个 Agent Skill（产品本体）
scripts/              分析、合并、校验、导出、读者站、地图 CLI
references/schema.md  数据契约
atlas-kit/            21 件 PNG + 9 件变量层
template/             读者站渲染模板
template/viewer.js    薄入口，只负责 IIFE 和模块占位
template/viewer/      12 个按职责拆分的渲染模块（地图/图谱/百科/搜索等）
docs/功能文档.md       产品定义与验收标准
docs/screenshots/     README 效果截图
samples/fictional/    虚构样例
output/凡人修仙传/    500 章真实数据示例
tests/                单元测试与契约回归
```

---

如果这套流程帮你把一本网文拆明白了，欢迎回到 [GitHub 仓库](https://github.com/cxknotjj/chinese-novel-atlas) 点一个 ⭐ Star。
