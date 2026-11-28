---
name: atlas-analyze
version: 0.5.0
description: "把一部已完结长篇小说编译成读者向世界档案：结构化 data.json（人物/关系/章节/伏笔/地点/概念）+ 疑点索引 + 可按阅读进度截断的读者站。支持百万字级长篇，由执行 agent 原生分批抽取，可断点续跑；不调用外部 API、不需要 key。触发词：拆书、拆这本书、拆《XXX》、分析这本小说、分析这本书、生成人物图谱、做个人物关系图、整理这本书的设定、做个读者站、读懂这本书、小说图谱、novel atlas。"
---

> **脚本已内置**：本 skill 自带全部 CLI 与渲染资源，装完即可运行，**不需要 clone 仓库**。
> 下文命令里的 `<SKILL_DIR>` 指本 skill 的安装目录（含 `SKILL.md` 的那一层），
> 常见位置：`~/.claude/skills/atlas-analyze`、`~/.workbuddy/skills/atlas-analyze`；
> 执行时替换成真实绝对路径。产出路径（如 `output/{书名}/`）相对**当前工作目录**。

# atlas-analyze · 拆书成世界档案

把一本已完结小说编译成一套可查询、可按章截断、可发布的世界档案：

```text
output/{书名}/data.json         结构化数据（schema v2.0）
output/{书名}/anomalies.json    疑点索引（规则引擎生成）
output/{书名}/atlas.html        单文件视图，双击打开
output/{书名}/reader/           读者站（总览 + 进度 + 搜索 + 疑点）
```

核心产物是 `data.json` + 证据链，不是 HTML；HTML/读者站只是投影。

---

## 什么时候用

用户给了一个小说文件（.txt / .md / .epub），并且想要：
- 看清人物关系
- 整理设定
- 查询"某人在哪一章出现过"
- 做跨书对比的前置准备

**不适用**：帮用户写小说、续写、改稿、去 AI 味。那些是别的 skill 的事。

---

## 执行流程

按下面的步骤走，**不要跳步，不要自己改流程**。

### 第 0 步 · 前置检查

确认三件事，任何一项不满足就停下来告诉用户：

| 检查项 | 不满足时怎么做 |
|---|---|
| Python 3.9+ | 提示安装 |
| 目标文件存在且是文本 | 提示支持的格式 |
| 分析范围明确 | 全书，或指定前 N 章；长书先和用户确认 |

**不需要 API key。** 先跑 `chunk.py` 拿到真实章数与字数，按每批 10 章报告批次数和分析范围；不要估算金额，也不要伪造固定耗时。

### 第 1 步 · 分章

```bash
python "<SKILL_DIR>/scripts/chunk.py" "<文件路径>" --out output/{书名}/
```

纯字符处理，零 LLM 调用。产出 `chapters/ch-001.txt` … 和 `chunk-meta.json`。

支持 7 种章节模式自动探测：`第X卷 第Y章` / `第X章` / `第X节` / `第X卷` / `一、` / `1.` / `Chapter 1`，全都不中时按字数兜底。

如果识别出的章数明显不对（比如整本只切出 1 章），停下来问用户章节格式，**不要猜**。

### 第 2 步 · 原生分批抽取

由当前执行 agent 直接抽取，不调用外部模型 API。

- 每批 10 章，只读 `chapters/ch-XXX.txt` 的当前批次，按 `<SKILL_DIR>/scripts/prompts/batch_template.md` 的模板写成 `out/batch-XX.json`
- 写完后立即做 JSON 解析和字段自检；每批每一章都要有记录，章号必须与输入一致
- 批次的实体 id 先按本批命名，合并阶段统一由 `merge.py` 做正名/别名归并和 id 重映射
- 已存在且章号完全对得上的批次直接跳过，支持断点续跑
- 写到批次文件后丢弃原文，**不要一次把整本书塞进上下文**
- 不写 `batch-XX.failed.json` 之类的失败留证文件；如果一批反复写不对，标记该批未完成并在最后报告
- 抽取期间每隔约 30 秒向用户报一次进度

`merge.py` 会自动固定 `meta.model=manual`、`meta.cost_cny=0`，不需要额外参数。

### 第 3 步 · 合并与境界

```bash
python "<SKILL_DIR>/scripts/merge.py" output/{书名}/ --genre 仙侠 --platform 起点
```

`merge.py` 做四件事：正名 + 别名归并（`韩老魔 → 韩立`）、关系重映射、伏笔去重与 id 唯一化、按派生规则重算 `status`。

书目录下若有可选的 `spatial.json`（`meta` / `places` / `spatial_relations`，及可选 `map_layout`，字段见 `references/schema.md`），merge 会把其中 data.json 没有的地点 id 追加进 `places`（已存在则报冲突并跳过），`spatial_relations` 与 `map_layout` 原样挂到 data.json 顶层并校验引用的地点 id；没有该文件时，data.json 的 `spatial_relations` 为 `[]`，`map_layout` 缺失则 2D 回退拓扑。

境界必须先有权威表，否则各批次各自编号，`筑基` 会被排成第一境：

```bash
python "<SKILL_DIR>/scripts/realms.py" output/{书名}/ --write   # 扫描候选
# 人工/执行 agent 核对后写 realms.json（含 realms 与 power_history）
python "<SKILL_DIR>/scripts/merge.py" output/{书名}/            # 重跑，以此为准
```

### 第 4 步 · 提及追踪（决定超期判得准不准）

```bash
python "<SKILL_DIR>/scripts/mentions.py" output/{书名}/ --apply
```

这一步补 `last_mention_ch`：回全文找每条伏笔的指纹词最后一次出现在第几章。

**为什么必要**：只按「埋了多少章」判超期会大面积误报。第 7 章埋、第 196 章还在提的主线伏笔不该报警，第 20 章埋、第 73 章后再没提的才该。实测同一本书，只用埋设跨度判出 37 条超期，加上沉默时长后是 23 条，且剩下的是真问题。

指纹词的挑法：从伏笔描述里取出现的实体名，按稀有度过滤掉「韩立」这类满篇都有的名字，留 1–3 个只在少数章节出现的（如「抽髓丸」「眨眼剑谱」）。没匹配到实体名的伏笔会退回用埋设章，判定偏保守。

`--apply` 会直接写回 `data.json` 并重算 `status`，不用再跑一次 merge。

### 地图视图（交给 `atlas-map`）

地图渲染已单独封装成 `skills/atlas-map`。拆书阶段只负责生成合法的 `map_layout`，不要在这里维护视觉参数、素材清单或标签字号。

- `map_layout.mode` 固定 `schematic`、`canvas` 固定 `[100,100]`、`note` 含“示意/非经纬度”。
- `regions` 的 `shape` 只用 `land / sea / void`；`nodes[].place`、`regions[].layer`、`routes[].s/t` 必须是已有 `places` id。
- 坐标和路线点位必须人工给定，不得由程序推算或约束求解反推；不得声称精确距离、方位或经纬度。
- 没有原文证据就不写方向、距离或坐标；“旁边”“不远处”“一天路程”不得折算成里数或像素。
- 地图的 atlas 配置、21 件 PNG + 9 件代码/SVG 分工、层筛选、缩放 LOD、构建与浏览器验收，一律读同级 skill `atlas-map` 的 `SKILL.md`。

`map_layout` 的字段规则以 `references/schema.md` 的「地图规则」为准；渲染规则以 `atlas-map` skill 的 `references/web-contract.md` 为准。

### 第 5 步 · 校验

```bash
python "<SKILL_DIR>/scripts/validate.py" output/{书名}/data.json
```

校验失败则报告具体哪条不合法，**不要自行"修一下"**。

空间关系走「空间」规则：`spatial_relations` 两端 id 必须存在且 `s != t`；`kind` / `confidence` 枚举合法；`evidence` 必须是对象，`evidence.ch` 在 1..chapters 内，`evidence.quote` 非空、≤120 字、不含换行；`value` ≤40 字。层内 direction+distance 仅 1–2 条时给 warning，提示证据方位会回退。

`map_layout` 走「地图」规则：`mode` 固定 `schematic`、`canvas` 固定 `[100,100]`；`shape` 枚举 `land` / `sea` / `void`；`layer` / `place` 必须是已有 `places` id，同一 `place` 不重复；坐标 0–100；`note` 含「非经纬度/示意」字样；`terrain` 折点/多边形/岛链坐标合法，`routes[].s` / `t` 存在且 `kind` 在 `portal/travel_path/road/river` 内。规则类别以 `references/schema.md` 的「validate 地图规则」为准。

### 第 6 步 · 构建视图

```bash
python "<SKILL_DIR>/scripts/build.py" --data output/{书名}/data.json --out output/{书名}/
```

把 `data.json` 内嵌进 `template/viewer.html`，构建时按职责拼接 `template/viewer/*.js`，再内联样式和入口，产出单文件 `atlas.html`。
构建前会自动跑一次 `validate.py`，有错误会拒绝出图；确实需要临时预览才加 `--skip-validate`。
加 `--external` 则改为同目录 `data.js` 外链（数据大、要反复重建时用）。
`merge.py` 会同时生成 `merge-log.json`，记录实体归并簇、别名依据、输入/输出数量，便于回查。

### 第 7 步 · 疑点索引与读者站

```bash
python "<SKILL_DIR>/scripts/anomalies.py" --data output/{书名}/data.json
python "<SKILL_DIR>/scripts/build_reader.py" --data output/{书名}/data.json --out output/{书名}/reader --single --allow-partial
```

- `anomalies.json` 只产疑点，不给改稿建议；每条必须有 `evidence`，没有证据不进入索引。
- `build_reader.py` 默认要求 100% 覆盖；试读/当前只分析前 N 章时加 `--allow-partial`，manifest 会写 `publishable: false`。
- 要真正冻结到第 N 章，加 `--cutoff N`；否则页面默认全书，读者拖动进度条只在已分析范围内取 `?cutoff=`。
- 读者站必须有总览、阅读进度、全书搜索、疑点视图；未来内容默认锁定。
- 疑点复核交给 `skills/atlas-audit`，不要在 analyze 里做“已修/误报”工作流。

---

## 参数

| 参数 | 作用 | 默认 |
|---|---|---|
| `--range ch1-ch50` | 只分析指定章节范围 | 全部 |
| `--batch-size 10` | 每批读取章数（执行 agent 的批次边界） | 10 |
| `--resume` | 续跑，已完成批次跳过 | 开 |

---

## 硬性约束

1. **不要把整本原文塞进上下文。** 抽取由执行 agent 按批（约 10 章）读取 `chapters/` 下的单章文件，写完批次 JSON 就丢弃原文。哪怕用户要求“你先读一遍整本”，也拒绝并解释：百万字读不进上下文，分批才可靠。
2. **不要调用外部模型 API。** 这个 skill 不包含 API 客户端、key、代理地址或费用配置；用户要求“用 API 跑”时，说明该功能已移除，改用当前 agent 原生抽取。
3. **不要内嵌原文到产物。** `atlas.html` 只含结构化数据，原文用坐标引用（`ch03:p12`）。
4. **不要跳过校验。** 数据不合法时 viewer 会崩，用户只会看到白屏。
5. **不要自己编造人物关系。** 抽取不到就留空，宁可图谱稀疏，也不要幻觉。
6. **不要编造空间方位。** 抽取不到方向/距离就留空；证据方位只吃带原文证据的 `direction` / `distance` / `contain` / `adjacent`，证据不足的层留在拓扑，不给无证据地点编方位。`map_layout` 近似坐标必须人工给定、不得程序推算，示意坐标不写回 `places`，也不当成证据坐标展示。

---

## 失败处理

| 情况 | 处理 |
|---|---|
| 分章数明显错误 | 停下问用户章节格式 |
| 单批 JSON 不合法 | 重写该批；连续失败则标记未完成，最后报告"共 N 批失败" |
| 别名消解召回率低 | 报告给用户，人工补 aliases 后重跑 merge |
| 中途中断 | 已完成批次保留，重跑只补缺失/未完成批次 |
| 校验失败 | 报告具体字段，不自行修改 |

---

## 已知限制（要主动告知用户）

- 超长篇的耗时取决于执行 agent、机器和章节长度，不提供固定分钟数
- 别名消解在人物超过 500 个时准确率会下降
- 古文 / 半文言作品的实体抽取质量明显低于现代白话
- 第一版不支持 epub 里的图片和注释
- 只拆部分章节时，超期阈值按已拆章数算（不是全书），沉默时长也只统计到已拆章为止
- 约 20% 的伏笔描述匹配不到实体名，退化成按埋设章判定，会偏保守

---

## 实现状态

| 组件 | 状态 |
|---|---|
| 数据契约 `references/schema.md` | ✅ 完成（v2.4，含可选 `spatial_relations` / `map_layout`） |
| 虚构样例 | ✅ 完成（仓库 `samples/fictional/`，18 角色 / 25 关系 / 12 伏笔） |
| 视图模板 `template/viewer.*` | ✅ 完成（HTML 骨架 + CSS + JS，构建时内联为单文件；八视图，含地图三子视图：示意 2D / 证据方位 / 拓扑） |
| `scripts/chunk.py` | ✅ 分章 + 编码探测 + 模式打分 + 兜底 |
| `scripts/prompts/batch_template.md` | ✅ 执行 agent 的批次输出模板 |
| `scripts/realms.py` | ✅ 境界扫描 / 候选生成 / 体系校验 |
| `scripts/merge.py` + `novel_atlas/merge/` | ✅ 归并 + 别名消解 + 伏笔去重 + status 派生 |
| `scripts/mentions.py` | ✅ 伏笔提及追踪（沉默时长判定 + `--apply` 回写） |
| `scripts/validate.py` | ✅ schema 全量校验（含「空间」规则：两端 id、枚举、evidence 完整性；「地图」规则：map_layout 枚举、引用 id 与坐标范围） |
| `scripts/build.py` | ✅ 单文件内嵌 / 外链 data.js |

**当前阶段**：契约、视图、分章 / 原生抽取 / 合并 / 校验 / 出图均已可用。项目不包含外部 API 客户端、key 配置和费用估算；抽取必须按批读取、按批落盘，不要整本进上下文。
