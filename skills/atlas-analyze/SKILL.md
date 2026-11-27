---
name: atlas-analyze
version: 0.4.0
description: "把一部长篇小说拆成可点击、可查询的世界图谱。产出结构化 JSON（人物 / 关系 / 事件 / 地点 / 概念）和一个自包含 HTML，双击即可浏览。支持百万字级长篇，由执行 agent 原生分批抽取，可断点续跑；不调用外部 API、不需要 key。触发词：拆书、拆这本书、拆《XXX》、分析这本小说、分析这本书、生成人物图谱、做个人物关系图、整理这本书的设定、做个设定集、读懂这本书、小说图谱、novel atlas。"
---

# atlas-analyze · 拆书成图

把一本小说拆成一张图。产出两个文件：

```
output/{书名}/data.json     结构化数据（schema v2.0）
output/{书名}/atlas.html    单文件视图，双击打开
```

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
python scripts/chunk.py "<文件路径>" --out output/{书名}/
```

纯字符处理，零 LLM 调用。产出 `chapters/ch-001.txt` … 和 `chunk-meta.json`。

支持 7 种章节模式自动探测：`第X卷 第Y章` / `第X章` / `第X节` / `第X卷` / `一、` / `1.` / `Chapter 1`，全都不中时按字数兜底。

如果识别出的章数明显不对（比如整本只切出 1 章），停下来问用户章节格式，**不要猜**。

### 第 2 步 · 原生分批抽取

由当前执行 agent 直接抽取，不调用外部模型 API。

- 每批 10 章，只读 `chapters/ch-XXX.txt` 的当前批次，按 `scripts/prompts/batch_template.md` 的模板写成 `out/batch-XX.json`
- 写完后立即做 JSON 解析和字段自检；每批每一章都要有记录，章号必须与输入一致
- 批次的实体 id 先按本批命名，合并阶段统一由 `merge.py` 做正名/别名归并和 id 重映射
- 已存在且章号完全对得上的批次直接跳过，支持断点续跑
- 写到批次文件后丢弃原文，**不要一次把整本书塞进上下文**
- 不写 `batch-XX.failed.json` 之类的失败留证文件；如果一批反复写不对，标记该批未完成并在最后报告
- 抽取期间每隔约 30 秒向用户报一次进度

`merge.py` 会自动固定 `meta.model=manual`、`meta.cost_cny=0`，不需要额外参数。

### 第 3 步 · 合并与境界

```bash
python scripts/merge.py output/{书名}/ --genre 仙侠 --platform 起点
```

`merge.py` 做四件事：正名 + 别名归并（`韩老魔 → 韩立`）、关系重映射、伏笔去重与 id 唯一化、按派生规则重算 `status`。

书目录下若有可选的 `spatial.json`（`meta` / `places` / `spatial_relations` 三段，字段见 `references/schema.md`），merge 会把其中 data.json 没有的地点 id 追加进 `places`（已存在则报冲突并跳过），`spatial_relations` 原样挂到 data.json 顶层并校验两端 id；没有该文件时，data.json 的 `spatial_relations` 为 `[]`。

境界必须先有权威表，否则各批次各自编号，`筑基` 会被排成第一境：

```bash
python scripts/realms.py output/{书名}/ --write   # 扫描候选
# 人工/执行 agent 核对后写 realms.json（含 realms 与 power_history）
python scripts/merge.py output/{书名}/            # 重跑，以此为准
```

### 第 4 步 · 提及追踪（决定超期判得准不准）

```bash
python scripts/mentions.py output/{书名}/ --apply
```

这一步补 `last_mention_ch`：回全文找每条伏笔的指纹词最后一次出现在第几章。

**为什么必要**：只按「埋了多少章」判超期会大面积误报。第 7 章埋、第 196 章还在提的主线伏笔不该报警，第 20 章埋、第 73 章后再没提的才该。实测同一本书，只用埋设跨度判出 37 条超期，加上沉默时长后是 23 条，且剩下的是真问题。

指纹词的挑法：从伏笔描述里取出现的实体名，按稀有度过滤掉「韩立」这类满篇都有的名字，留 1–3 个只在少数章节出现的（如「抽髓丸」「眨眼剑谱」）。没匹配到实体名的伏笔会退回用埋设章，判定偏保守。

`--apply` 会直接写回 `data.json` 并重算 `status`，不用再跑一次 merge。

### 地图分级（M1 / M2）

视图里的「地图」tab 分 M1 / M2 两套渲染，**默认只承诺 M1**：

- **M1 拓扑/层级图**：只表达包含、传送、航线、随机落点、区域归属；节点位置仅用于避让，不代表原文方位，不画指北针、比例尺、经纬网。
- **M2 证据化示意地图**：只有某层 `spatial_relations` 里 direction+distance 约束 **≥3 条**才允许出 M2；不足 3 条自动回退 M1。没有方向或距离证据的节点进「方位未知」独立区，不硬塞四象限；M2 坐标是 0–100 示意坐标，不是真实经纬度。
- 抽取/整理阶段不得为了凑地图编方位、距离或坐标；没有原文句子就不写关系，宁可 M1 稀疏。「旁边」「不远处」「一天路程」不得折算成里数或像素距离；乱星海层、虚天殿层、血色禁地层这类只做 M1 航线/传送拓扑，不硬做 M2。

### 第 5 步 · 校验

```bash
python scripts/validate.py output/{书名}/data.json
```

校验失败则报告具体哪条不合法，**不要自行"修一下"**。

空间关系走「空间」规则：`spatial_relations` 两端 id 必须存在且 `s != t`；`kind` / `confidence` 枚举合法；`evidence` 必须是对象，`evidence.ch` 在 1..chapters 内，`evidence.quote` 非空、≤120 字、不含换行；`value` ≤40 字。层内 direction+distance 仅 1–2 条时给 warning，提示 M2 会回退。规则清单以 `references/schema.md` 的「validate 空间规则」为准。

### 第 6 步 · 构建视图

```bash
python scripts/build.py --data output/{书名}/data.json --out output/{书名}/
```

把 `data.json` 内嵌进 `template/viewer.html`，构建时再内联 `viewer.css` / `viewer.js`，产出单文件 `atlas.html`。
构建前会自动跑一次 `validate.py`，有错误会拒绝出图；确实需要临时预览才加 `--skip-validate`。
加 `--external` 则改为同目录 `data.js` 外链（数据大、要反复重建时用）。
`merge.py` 会同时生成 `merge-log.json`，记录实体归并簇、别名依据、输入/输出数量，便于回查。

完成后告诉用户：

```
已生成：
  output/青云签到三十年/data.json      35.2 KB
  output/青云签到三十年/atlas.html     449 KB  ← 双击打开

覆盖 120/300 章，识别 18 个角色、25 条关系、4 级境界、12 条伏笔。
其中 7 条伏笔已超期。
```

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
6. **不要编造空间方位。** 抽取不到方向/距离就留空；M2 只吃带原文证据的 `direction` / `distance` / `contain` / `adjacent`，证据不足的层留在 M1 拓扑，不给无证据地点编方位，也不把自动布局坐标写回 `places`。

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
| 数据契约 `references/schema.md` | ✅ 完成（v2.3，含可选 `spatial_relations`） |
| 虚构样例 `samples/fictional/` | ✅ 完成（18 角色 / 25 关系 / 12 伏笔） |
| 视图模板 `template/viewer.*` | ✅ 完成（HTML 骨架 + CSS + JS，构建时内联为单文件；八视图，含地图 M1/M2） |
| `scripts/chunk.py` | ✅ 分章 + 编码探测 + 模式打分 + 兜底 |
| `scripts/prompts/batch_template.md` | ✅ 执行 agent 的批次输出模板 |
| `scripts/realms.py` | ✅ 境界扫描 / 候选生成 / 体系校验 |
| `scripts/merge.py` + `novel_atlas/merge/` | ✅ 归并 + 别名消解 + 伏笔去重 + status 派生 |
| `scripts/mentions.py` | ✅ 伏笔提及追踪（沉默时长判定 + `--apply` 回写） |
| `scripts/validate.py` | ✅ schema 全量校验（含「空间」规则：两端 id、枚举、evidence 完整性） |
| `scripts/build.py` | ✅ 单文件内嵌 / 外链 data.js |

**当前阶段**：契约、视图、分章 / 原生抽取 / 合并 / 校验 / 出图均已可用。项目不包含外部 API 客户端、key 配置和费用估算；抽取必须按批读取、按批落盘，不要整本进上下文。
