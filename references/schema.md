# 数据契约 · schema v2.0

面向**中文长篇网络小说**设计。不追求兼容古典小说——目标单一，字段才能贴紧网文的真实结构。

- 参考实现：`samples/fictional/`（虚构网文《青云签到三十年》，覆盖全部字段）
- 校验脚本：`scripts/validate.py`
- 版本规则：破坏性变更升主版本号；新增可选字段升次版本号

**题材差异**：玄幻/仙侠的 `realms` 必填；都市/悬疑可为空数组。但 `chapters` 和 `foreshadows` 对所有网文类型都必填——**没有伏笔的长篇网文不存在**，只是埋得深浅不同。

**v2.0 相对 v1.0 的破坏性变更**：移除 `events`（由 `chapters` 替代），新增 `volumes` / `realms` / `chapters` / `foreshadows` / `knowledge`。见文末迁移说明。

---

## 顶层结构

```jsonc
{
  "meta":        { /* 元信息 */ },
  "volumes":     [ /* 分卷 */ ],
  "realms":      [ /* 境界 / 修为等级链 */ ],
  "entities":    [ /* 人物 / 势力 / 器物 / 异兽 */ ],
  "relations":   [ /* 实体之间的关系 */ ],
  "chapters":    [ /* 逐章摘要，全量覆盖 */ ],
  "foreshadows": [ /* 伏笔台账 */ ],
  "knowledge":   [ /* 三界认知：谁知道什么 */ ],
  "places":      [ /* 地点，支持层级 */ ],
  "spatial_relations": [ /* 空间关系，可选；每条带原文证据 */ ],
  "map_layout":  { /* 2D 示意坐标，可选；人工近似摆放，非经纬度、非证据 */ },
  "concepts":    [ /* 世界观 / 金手指 / 功法 / 品阶 */ ]
}
```

---

## 读者向派生字段（v2.0-reader，可选）

`data.json` 仍是唯一事实源；下面四个字段由 `novel_atlas.reader` 在构建读者站时注入，
**不是作者手写字段，也不进入 `validate.py` 的原始数据校验**。

| 字段 | 生成者 | 说明 |
|---|---|---|
| `anomalies` | `reader.anomalies.build_anomalies` | 疑点索引；见 5.3 对象结构 |
| `_anomalyMeta` | `reader.publish.annotate` | 疑点统计、阈值、live 章、规则错误等 |
| `_mapLevels` | `reader.map_levels.compute_map_levels` | 地图 M0–M4 分级；按层给 `direction_constraints` |
| `_reader` | `reader.cutoff.reader_meta` | `cutoff_ch / analyzed_ch / chapter_max / total_chapters / analysis_complete / is_spoiler_safe` |

**按章截断**：`filter_data(data, cutoff)` 返回 UI 投影，只保留
`first_ch <= cutoff` 的实体/地点/关系/概念、`truth_ch/reader_known_ch <= cutoff`
的认知记录、`plant_ch <= cutoff` 的伏笔（未来 `payoff_ch` 置 null）、
`first_ch <= cutoff` 的地图节点/区域/路线/stamp，以及证据章不晚于 cutoff 的疑点。
这是**前端投影**，不替代服务端鉴权；真正不发布未来内容时应按 cutoff 生成静态副本。

**疑点对象**（每条必须有 `id` 和至少一条 `evidence`）：

```jsonc
{
  "id": "an_fs_001",
  "kind": "foreshadow_unresolved",
  "kind_cn": "伏笔未回收",
  "severity": "info",          // high / warning / info
  "confidence": "high",        // high / medium / low
  "title": "抽髓丸：第 20 章埋下，第 73 章后未再提",
  "detail": "沉默 427 章，超过当前阈值 75 章",
  "chapter_range": [20, 73],
  "entities": ["f_chousuiwan"],
  "evidence": [
    {"coordinate": "ch20:p8", "quote": "……"},
    {"coordinate": "ch73", "quote": "第 73 章后未再出现"}
  ],
  "reader_note": "可能是作者有意留白；读者自行判断",
  "verified": false,
  "silent_chapters": 427
}
```

坐标口径：源数据有段落坐标时用 `chN:pM`；当前 `chapters` 只有摘要、没有段落表，
规则引擎会退化为 `chN` 章节级证据。**不允许伪造 `pM`。** 无证据的条目不会进入索引。

---

## meta

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | ✓ | 固定 `"2.0"` |
| `title` | string | ✓ | 书名 |
| `author` | string | ✓ | 作者 |
| `genre` | string | ✓ | 题材：`玄幻` `仙侠` `都市` `悬疑` `历史` `言情` `名著` … |
| `platform` | string | | 首发平台：`起点` `番茄` `晋江` `七猫` `其他` |
| `status` | enum | | `连载中` / `完结` / `太监` |
| `source_file` | string | | 源文件名（不含路径） |
| `chars` | int | ✓ | 正文字数 |
| `chapters` | int | ✓ | 总章数 |
| `analyzed_at` | string | ✓ | ISO 8601 UTC |
| `model` | string | ✓ | 抽取方式标记；当前由执行 agent 原生抽取，固定 `"manual"` |
| `cost_cny` | number | | 兼容字段；当前固定 `0`，不参与分析 |
| `elapsed_sec` | int | | 耗时（秒） |
| `coverage` | object | ✓ | `{ chapters_done, chapters_skipped }` |
| `note` | string | | 备注 |

**网文特有**：`genre` 和 `platform` 不是装饰。番茄读者要"3 章 1 小爽"，起点可以"前 50 万字铺伏笔"——**节奏评分标准必须按平台区分**，这两个字段是判定基准。

---

## volumes

```json
[{ "id": "v1", "name": "青云宗", "ch_start": 1, "ch_end": 120, "summary": "主角入门至筑基" }]
```

网文以"卷"为结构单位，卷纲是作者的核心资产。没有 `volumes`，节奏分析只能按全书平均，看不出"某一卷开始水了"。

---

## realms（境界体系）· 网文核心

```json
[
  { "id": "r_qi", "name": "练气", "order": 1,
    "stages": ["一层","二层","三层","四层","五层","六层","七层","八层","九层"],
    "first_ch": 1, "desc": "引气入体，共九层" },
  { "id": "r_zhuji", "name": "筑基", "order": 2,
    "stages": ["初期","中期","后期"], "first_ch": 45, "desc": "筑就道基" }
]
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `r_` 前缀 |
| `name` | string | ✓ | 境界名 |
| `order` | int | ✓ | **严格递增的序数**，从 1 开始，决定强弱 |
| `stages` | string[] | ✓ | 小阶段，可为空数组 |
| `first_ch` | int | | 首次出现章号 |
| `desc` | string | | 说明 |

**为什么必须是独立表**：`order` 是「有序链」。放进无序的 `concepts` 里，后面每次比较都要写特例。境界是网文战力的唯一标尺，必须一等公民。

**都市/悬疑类**：`realms: []`，此时 `power_history` 也留空，战力对比退化为"势力对比"。

### ⚠ 境界体系必须全局定义，禁止逐批各自建立

这是 v2.1 用真实文本踩出来的坑，写进规范：

**逐批抽取会系统性毁掉境界数据。** 每批只看 10 章，看不到体系全貌；各批 `order` 独立编号，合并后必然错乱。实测《凡人修仙传》前 100 章，10 个批次里 9 个 `realms` 为空，剩下 1 个建了「筑基 order:1」——**把筑基排成了最低境界**，且 105 个实体`power_history` 全空，境界甘特图完全空白。

正确做法是三步：

| 步骤 | 工具 | 产出 |
|---|---|---|
| 1. 全文扫描 | `scripts/realms.py <dir>` | 境界词、层级表述、功法层级的候选统计 |
| 2. 人工/执行 agent 确认 | 核对原文关键章 | `output/<书名>/realms.json`（体系 + 修为时间线） |
| 3. merge 注入 | `scripts/merge.py` | 权威定义覆盖批次数据，`power_history` 由实在原文的节点注入 |

`realms.json` 结构：

```json
{
  "realms": [ /* 与上文 realms 同结构 */ ],
  "power_history": {
    "e_hanli": [
      { "ch": 9,  "realm": "r_lianqi", "stage": "一层", "note": "练成第一层", "quote": "ch09" },
      { "ch": 96, "realm": "r_lianqi", "stage": "八层", "note": "可连发火弹术上百次", "quote": "ch96" }
    ]
  }
}
```

**`power_history` 的每一条都必须能对回原文**，`quote` 记章号；推断出的节点（如"第七层突破未明写，按 ch96 已到八层"）要在 `note` 里说清楚。这是这份数据能否被作者信任的分界线。

**扫描器的判定逻辑**：境界词命中经常是假阳性（"后天""心动""融合"在中文里都是普通词），层级表述（第 X 层 / 重 / 品）才是强信号。若全书只出现层级、不出现标准境界词，说明作者用「功法层数」代替境界名，此时 `realms.name` 用功法对应的通用境界，`stages` 直接装层数，并在 `mapping` 字段写明换算依据。

校验：`python scripts/realms.py <dir> --check output/<书名>/realms.json`

---

## entities

```json
{
  "id": "e_linyun",
  "name": "林云",
  "type": "character",
  "group": "青云宗",
  "parent": "e_qingyunzong",
  "aliases": ["云哥", "林师弟"],
  "desc": "……",
  "first_ch": 1,
  "last_ch": null,
  "attrs": { "性格": "谨慎", "金手指": "签到系统" },
  "power_history": [
    { "ch": 1,   "realm": "r_qi",    "stage": "三层", "note": "开局" },
    { "ch": 45,  "realm": "r_zhuji", "stage": "初期", "note": "服筑基丹" }
  ],
  "ranks": ["外门弟子", "内门弟子", "真传弟子"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `e_` 前缀，小写+下划线 |
| `name` | string | ✓ | 正名 |
| `type` | enum | ✓ | `character` / `org` / `item` / `creature` |
| `group` | string | ✓ | 阵营，决定节点颜色，建议 ≤ 10 种 |
| `parent` | string | | **上级势力**（宗门下的分宗、分宗下的堂口），构成势力树 |
| `aliases` | string[] | ✓ | 别名（称号、外号、尊称），可为空 |
| `desc` | string | ✓ | 简介，≤ 100 字 |
| `first_ch` | int | ✓ | 首次登场章 |
| `last_ch` | int \| null | | 最后出现章；`null` 表示仍未退场 |
| `attrs` | object | | 自由键值 |
| `power_history` | array | | **战力时间线**，见下 |
| `ranks` | string[] | | 仅 `org`：内部等级（宗主/长老/弟子），由低到高 |

### power_history（战力时间线）

```json
[{ "ch": 1, "realm": "r_qi", "stage": "三层", "note": "开局" }]
```

| 字段 | 说明 |
|---|---|
| `ch` | 达到该境界的章号，**严格递增** |
| `realm` | 对应 `realms[].id` |
| `stage` | 小阶段名，须在对应 `realms[].stages` 内 |
| `note` | 突破契机（"服筑基丹"） |

**这个字段能回答三个问题**：
1. 平均多少章升一级（节奏指标）
2. 第 N 章时某人是什么境界（战力对比）
3. 两章之间是否出现**境界倒退**（吃设定）

**名著不用这个字段**——网文的战力体系是核心设定，没它就没有"越级战胜"这种爽点结构。

---

## relations

与 v1.0 一致，**8 类封闭枚举不变**。

```json
{ "s": "e_linyun", "t": "e_suqing", "type": "mentorship",
  "label": "师徒", "weight": 0.9, "first_ch": 5,
  "evidence": ["ch05:p12"] }
```

| type | 中文 | 判定 |
|---|---|---|
| `kinship` | 血亲 | 血缘、宗族 |
| `marriage` | 婚姻 | 夫妻、道侣、婚约 |
| `romance` | 情感 | 爱慕、暧昧（不含已成婚/道侣） |
| `service` | 从属 | 主仆、上下级、门客 |
| `mentorship` | 师承 | 授业、传功 |
| `alliance` | 同盟 | 结盟、合作、恩义 |
| `conflict` | 敌对 | 仇怨、对抗、追杀 |
| `social` | 交游 | 同门、道友、泛交 |

**多关系叠加**：`weight` 最高者画线，其余在详情列出。

**不要往这里塞伏笔或战斗记录**——那会污染这个封闭枚举，跨书对比直接失效。伏笔走 `foreshadows`，战斗见 `chapters[].battles`。

---

## chapters（逐章摘要）· 全量覆盖

```json
{
  "ch": 1,
  "title": "穿越成废物",
  "words": 3200,
  "volume": "v1",
  "summary": "林云穿越到青云宗杂役身上，激活签到系统……",
  "hook": "系统提示：七日內未签到，宿主将彻底死亡",
  "hook_type": "危机",
  "emotion": "压抑",
  "tension": 0.6,
  "new_entities": ["e_linyun", "e_xitong"],
  "new_foreshadows": ["f_yupei"],
  "battles": []
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ch` | int | ✓ | 章号 |
| `title` | string | ✓ | 章节标题（已清洗） |
| `words` | int | ✓ | 本章字数 |
| `volume` | string | | 所属卷 id |
| `summary` | string | ✓ | 摘要，**≤ 80 字** |
| `hook` | string | | 章末钩子，**≤ 30 字**；无钩子留空 |
| `hook_type` | enum | | `悬念` `反转` `冲突` `危机` `爽点` `无` |
| `emotion` | enum | | `爽` `压抑` `紧张` `温情` `悲` `平` |
| `tension` | number | ✓ | 0–1 情节强度 |
| `new_entities` | string[] | | 本章首次登场的实体 |
| `new_foreshadows` | string[] | | 本章埋下的新伏笔 |
| `battles` | array | | 战斗记录，见下 |

### battles（战斗记录）

```json
[{ "a": "e_linyun", "b": "e_wanghu", "result": "win",
   "gap": 2, "note": "越两个小境界取胜" }]
```

`a` / `b` 必须是 `entities` 里已有的 id，不能是同一个人；旧字段 `s` / `t` 已废弃，校验器会直接拒绝。`gap` = 双方境界 `order` 差（正数表示 a 更强）。**这是检测"战力崩坏"的原始数据**：主角越 5 个境界打赢，要么是爽点设计，要么是崩了，需要作者自己判断。

### 派生指标（不存储，由 viewer / compare 现算）

| 指标 | 计算方式 | 平台基准 |
|---|---|---|
| 章末钩子率 | `hook` 非空章数 / 总章数 | 番茄 ≥ 80%，起点 ≥ 60% |
| 爽点间隔 | 相邻 `emotion=爽` 章号差的中位数 | 番茄 3 章，起点 10 章 |
| 平均章字数 | `words` 均值 | 番茄 4000，起点 6000 |
| 情绪曲线 | 按章号绘制 `emotion` 序列 | — |

**这些是产品卖点，不是学术指标。** README 里要直接展示"你的钩子率 62%，番茄基准 80%"。

**非全量分析**：`coverage.chapters_done` 记录**已分析的章数**，`chapters` 数组可以只存关键章。两者不一致时（`len(chapters) < chapters_done`），节奏指标必须标注"不完整"，也不能拿去跨书对比。

---

## foreshadows（伏笔台账）· 网文最痛的痛点

```json
{
  "id": "f_yupei",
  "content": "集市救下的乞丐塞给他一枚刻着云纹的玉佩",
  "plant_ch": 12,
  "plant_quote": "ch12:p8",
  "payoff_ch": 87,
  "payoff_quote": "ch87:p3",
  "status": "paid",
  "thread": "身世之谜",
  "importance": 0.85,
  "note": "玉佩是青云宗掌门信物"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `f_` 前缀 |
| `content` | string | ✓ | 埋了什么，**≤ 50 字** |
| `plant_ch` | int | ✓ | 埋设章 |
| `plant_quote` | string | | 坐标 `ch12:p8` |
| `payoff_ch` | int \| null | | 回收章；未回收为 `null` |
| `payoff_quote` | string | | 坐标 |
| `last_mention_ch` | int \| null | | 最后一次被提及的章，由 `scripts/mentions.py` 生成 |
| `keywords` | string[] | | 用于追踪提及的指纹词（自动挑选的稀有实体名） |
| `status` | enum | | `planted` / `paid` / `overdue` / `dropped`。**派生字段**，见下 |
| `thread` | string | | 所属线索，便于分组查看 |
| `importance` | number | ✓ | 0–1，影响告警优先级 |
| `note` | string | | 补充说明 |

### status 判定规则

**`status` 是派生字段，不是源头数据。** 存储时写入的是快照，校验器会用下面的规则重算并比对，不一致直接报错。

| status | 条件 |
|---|---|
| `paid` | `payoff_ch` 非空，且与 `plant_ch` 不同 |
| `dropped` | 作者明确放弃（**唯一需要人工标注的状态**） |
| `overdue` | `payoff_ch` 为空 **且** `当前章 - 最后提及章 > 阈值` |
| `planted` | 其余情况 |

**只有明确的回收章才算 `paid`。** 仅 `last_mention_ch` 更新、没有 `payoff_ch` 的，仍按沉默时长归入 `overdue` 或 `planted`；viewer 会把这类记作「最后提及 · 仅提及」，不会显示成已回收。

**判超期看「沉默时长」，不看「埋了多久」。** 这是 v2.2 的关键修正：

```
span   = 当前章 - plant_ch        埋了多久
silent = 当前章 - last_mention_ch  多久没管它   ← 判定用这个
```

第 7 章埋、第 196 章还在提的主线伏笔（如《凡人修仙传》的神秘小瓶），跨度 190 章但不是遗忘；而第 20 章埋、第 73 章后再没提的支线（抽髓丸），沉默 127 章才是真问题。**只按 span 判会把 37 条判成超期，加上 silent 后降到 23 条，且剩下的是真该补的。**

`last_mention_ch` 由 `scripts/mentions.py` 生成：从伏笔描述里提取实体名作关键词，按稀有度筛掉"韩立"这类满篇都有的名字，再回全文定位每次提及的章号。

**阈值 = max(50, 已分析章数 × 0.15)**。全书分析时「已分析章数」就是总章数：1000 章的书阈值 150 章；120 回的名著阈值 50 回。只拆前 200 章时按 200 算，否则用总章数的 15% 会让所有坑永远不超期。

**这个阈值必须动态**。固定值对短书太松、对长书太紧，告警就没人看了。

**Python 侧必须统一调用** `scripts/novel_atlas/foreshadow_rules.py` 的阈值和状态派生；`template/viewer.js` 是浏览器运行时，必须同步同一套公式。曾经因为 view 用全书章数、脚本用已分析章数，界面显示 0 条超期而导出文件写 37 条，同一个数据两套结论。

**为什么派生**：如果 `status` 是手写死的，作者每更新一章都要回头改一遍所有伏笔状态，必然漏。派生规则保证"当前章一推进，超期告警自动更新"。

### 这一张表是产品的核心卖点

作者打开报告，第一眼要看到的是"**你有 7 个伏笔超过阈值还没回收**"，而不是一张人物关系图。

图谱是给读者看的，伏笔台账是给作者看的。后者才是付费点。

---

## knowledge（三界认知隔离）

```json
{
  "id": "k_zhuansheng",
  "fact": "林云是穿越者，前世是程序员",
  "truth_ch": 1,
  "reader_known_ch": 1,
  "known_by": [
    { "entity": "e_linyun", "ch": 1 },
    { "entity": "e_suqing", "ch": 156 }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `truth_ch` | 客观真相确立的章（作者视角） |
| `reader_known_ch` | 读者何时知道 |
| `known_by` | 哪些角色在何时知道 |

**用途：检测"配角开天眼"。** 如果某角色在 `ch 30` 说出了 `truth_ch: 1` 但 `known_by` 记录他 `ch 50` 才知道的事，就是剧透穿帮。

这是 P1 功能，但**字段要先定**——后加会要求全量重跑。

---

## places

与 v1.0 一致。

```json
{ "id": "p_qingyunzong", "name": "青云宗", "parent": null,
  "desc": "……", "first_ch": 1, "attrs": { "所属": "东域" } }
```

网文常见多层级：`大陆 → 域 → 国 → 城 → 宗门 → 山峰`。`parent` 链任意深，但**不能成环**。

`places` 只有 `parent` 包含关系，**没有坐标、方位、距离字段**。视图渲染时计算的布局坐标只用于避让或示意，不写回 `places`，也不写进 data.json。

---

## spatial_relations（空间关系与地图分级）· 可选

### 地图成熟度分级 M0–M4

地图不是一种渲染样式，而是一种证据等级：没有方位、距离、边界证据时，只能画拓扑关系图，不能画带东南西北和比例尺的地图。分级表述参考公开的证据化拆书规范（调研见 `references/map-research.md` §3.1）：

| 等级 | 名称 | 允许表达 | 不允许做 |
|---|---|---|---|
| M0 | 地点索引 | 地点名、出现章节、父级未知 | 不生成坐标图 |
| M1 | 拓扑图 | 包含、相邻、可达、传送 | 坐标只用于避让，不表达方位和距离 |
| M2 | 二维方位图 | 东南西北、边界、道路、局部坐标、区域 | 不把自动布局回写成事实坐标 |
| M3 | 多层地图 | 位面、上下界、星域、楼层、父地图下钻 | z 轴没有叙事依据就不上 3D |
| M4 | 时态地图 | 地点状态、国界、控制权、路线随章节变化 | 不用修改旧数据的方式隐藏变化 |

**「地图」tab 当前含三个子视图**，默认进示意 2D：

| 子视图 | 定位 | 数据 | 默认 |
|---|---|---|---|
| **示意 2D（map2d）** | 默认地图视图。人工近似坐标的示意布局，用于叙事导航；有 `atlas.stamps` 时叠 21 件手绘底件 | `map_layout.nodes` + `.regions`；连线来自 `spatial_relations` | ✅ 打开「地图」即进入 |
| **证据方位**（原 M2） | 只消费带原文证据的 `direction` / `distance` / `contain`(带位置值) / `adjacent` | `spatial_relations` | 手动切换 |
| **拓扑（topo）**（原 M1） | 次要视图。保留 `places.parent` 层级/拓扑树，不做美化 | `places.parent` | 手动切换 |

M0 只有地点列表；M1 只有示意坐标/拓扑；M2 由证据方位视图承接（层内 ≥3 条方向/距离约束才开放）；M3 用**层筛选**下钻父地图；M4 在示意 2D 里出现**时间切片**下拉，由 `map_layout.time_slices` 驱动。M3/M4 只在数据里真有显式层/切片时显示，不硬造。

### 层（layer）

一层 = 一个根地点（`parent` 为 null 的地点）及其整棵子树。

- 拓扑：默认显示某层子树；另有「全部」视图。
- 证据方位：只对**带 ≥3 条 direction/distance 约束**的层开放；不足时显示回退卡片（`该层方位证据不足（N 条方向/距离约束），已回退到 M1 拓扑图`），不得硬画。
- 示意 2D 层筛选选项：`越国` / `乱星海` / `虚天殿` / `全部`，**默认 `全部`**（两簇同框：左「越国 · 七派并立」、右「乱星海 · 海外势力」，虚天殿收成右下小簇/卡片）。归属判定：`nodes[].layer` 或 `regions[].layer` 指向的根地点子树包含该节点；没有 `layer` 的节点归 `全部`。切层时只显示该层节点/区域；「全部」显示整体关系。

### 条目结构

```json
{
  "id": "sr_lanzhou_jiayuan_center",
  "s": "p_lanzhou",
  "t": "p_jiayuancheng",
  "kind": "contain",
  "value": "center",
  "confidence": "high",
  "first_ch": 100,
  "evidence": { "ch": 100, "quote": "嘉元城位于岚州中部" },
  "note": "越国宏观；区域块内位置"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `sr_` 前缀，全局唯一，蛇形小写 |
| `s` / `t` | string | ✓ | 必须是 `places` 里的 id，`s != t` |
| `kind` | enum | ✓ | 枚举见下 |
| `value` | string | ✓ | ≤40 字，含义随 kind（见下） |
| `confidence` | enum | ✓ | `high` / `medium` / `low` |
| `first_ch` | int | ✓ | 1..`meta.chapters` 的整数 |
| `evidence.ch` | int | ✓ | 1..`meta.chapters` 的整数 |
| `evidence.quote` | string | ✓ | 原文片段，≤120 字，不含换行，不得改写原文 |
| `note` | string | | ≤60 字 |

### kind 枚举与 value 语义

方向语义统一为「s 位于 t 的该方位」。

| kind | value | 进证据方位？ |
|---|---|---|
| `direction` | `north_of` `south_of` `east_of` `west_of` `northeast_of` `northwest_of` `southeast_of` `southwest_of` | 是 |
| `distance` | 原文距离/时长短语，如 `百余里`、`一天一夜`、`三天路程` | 是（弱约束） |
| `contain` | `north_part` `south_part` `east_part` `west_part` `center` `edge` `northeast_edge` 等区域位置；s=父，t=子 | 是（区域提示，不进象限） |
| `adjacent` | `borders` 或 `nearby` | 是（软约束） |
| `portal` | 自由短语，如 `古传送阵`、`随机降落` | 否，只画拓扑 |
| `travel_path` | 自由短语，如 `神风舟一天一夜` | 否，只画拓扑 |
| `road` / `river` | 自由短语 | 否，只画拓扑 |
| `separated_by` | 分隔物短语，如 `山脉` | 否 |
| `in_between` | `p_x|p_y`（两个已有地点 id） | 否 |

### 可选性与回退

`spatial_relations` **可选**：缺失或空 list 时证据方位自动回退拓扑，不算错误。没有 `spatial.json` 时，data.json 的 `spatial_relations` 为 `[]`（保持字段存在，便于视图判断）。

### map_layout（示意坐标）· 可选

`map_layout` 位于 data.json 顶层，是示意 2D 视图的人工近似布局；源头是书目录下的 `spatial.json`。2D 的视觉层由 `map_layout.atlas` 控制：21 件手绘 PNG 作为 `stamps` 景物层，9 件代码/SVG 作为路线、标记、题签、印章、罗盘。

```json
"map_layout": {
  "mode": "schematic",
  "note": "人工示意坐标（0–100 归一化画布，原点左上），非经纬度；坐标为叙事导航用近似摆放",
  "canvas": [100, 100],
  "regions": [
    { "id": "r_yueguo", "name": "越国大陆", "shape": "land", "layer": "p_yueguo",
      "label_at": [22, 46], "polygon": [[4,14],[50,10],[52,74],[8,80]] },
    { "id": "r_luanxing", "name": "乱星海", "shape": "sea", "layer": "p_luanxinghai",
      "label_at": [76, 44], "polygon": [[56,10],[97,12],[95,78],[58,74]] },
    { "id": "r_xutian", "name": "虚天殿（秘境）", "shape": "void", "layer": "p_xutian_dian",
      "label_at": [74, 91], "polygon": [[62,82],[90,82],[90,98],[62,98]] }
  ],
  "nodes": [
    { "place": "p_yuejing", "x": 44, "y": 50, "layer": "p_yueguo", "rank": 1, "label": true }
  ]
}
```

| 字段 | 规则 |
|---|---|
| `mode` | 必填，固定 `schematic` |
| `note` | 必填，≤120 字，必须含「非经纬度/示意」字样 |
| `canvas` | 必填，`[w,h]`，固定 `[100,100]`（归一化） |
| `regions[].id` | `r_` 前缀，唯一 |
| `regions[].name` | 非空 |
| `regions[].shape` | 枚举 `land` / `sea` / `void`（void=秘境小簇/卡片） |
| `regions[].layer` | 可空；若有必须是已有 `places` id（用来做层筛选归属） |
| `regions[].polygon` | ≥3 个 `[x,y]`，每点 0–100 |
| `regions[].label_at` | 可选 `[x,y]`，0–100 |
| `nodes[].place` | 必填，必须是已有 `places` id；同一 place 只能出现一次 |
| `nodes[].x` / `y` | 必填，0–100 |
| `nodes[].layer` | 可空；若有必须是已有 `places` id |
| `nodes[].rank` | 可选，1=关键（低缩放显示）、2=次级、3=细节；默认 2 |
| `nodes[].label` | 可选布尔，默认 `true`（受 LOD 控制） |

#### terrain（可选，2D 会渲染）

`terrain` 是示意 2D 的代码地形层。山脊默认摆 `terrain_ridge_01/02` 手绘 stamp；河流、湖泊、岛链由代码绘制。坐标 0–100：

```json
"terrain": {
  "ridges": [ { "points": [[x,y],...], "width": 2.4, "region": "r_yueguo", "name": "太岳山脉" } ],
  "rivers": [ { "points": [[x,y],...], "width": 1.1, "region": "r_yueguo", "name": "…" } ],
  "lakes":  [ { "polygon": [[x,y],...], "region": "r_yueguo" } ],
  "islets": [ { "x": 70, "y": 34, "r": 1.6 } ]
}
```

| 字段 | 规则 |
|---|---|
| `ridges[]` | 可选山脉脊线：`points` 为 ≥2 个 `[x,y]` 折线点，0–100；`width` 线宽；`region` 可空，若有必须是已有 `regions[].id`；`name` 可空 |
| `rivers[]` | 可选河流：`points` 折线点 0–100；`width` 线宽；`region` 可空；`name` 可空 |
| `lakes[]` | 可选湖泊：`polygon` ≥3 个 `[x,y]`，0–100；`region` 可空 |
| `islets[]` | 可选岛链：`x` / `y` 0–100；`r` 半径；必须是对象，不能写成 `[x,y,r]` 数组 |

`terrain` 缺失不报错；`atlas.terrainStamps=false` 时山脊回退代码墨线。

#### routes（弯曲航路，可选）

```json
"routes": [
  { "s": "p_yueguo", "t": "p_luanxinghai", "kind": "portal", "curve": [[40,70],[50,60]], "label": "古传送阵" }
]
```

| 字段 | 规则 |
|---|---|
| `routes[].s` / `t` | 必填，必须是已有 `places` id |
| `routes[].kind` | 枚举 `portal` / `travel_path` / `road` / `river` |
| `routes[].curve` | 可选 `[x,y]` 控制点列表，0–100；无则自动弧度 |
| `routes[].label` | 可选短语，如 `古传送阵`、`一天一夜` |

网页端把 `s/t` 点列和 `curve` 一起做 Catmull-Rom 平滑，按 `kind` 区分线型、端点、虚线和箭头。`routes` 缺失则不画航路；弯曲虚线表达的是传送/航线，**不是可测量的距离**。

#### time_slices（时态地图，可选，M4）

`map_layout.time_slices` 是“按章节切片”的显式数据。有它才升级 M4；没有就不硬造时间轴。

```json
"time_slices": [
  {
    "ch": 120,
    "label": "越国篇",
    "note": "韩立离开越国前",
    "regions": ["r_yueguo"],
    "nodes": ["p_yuejing", "p_huangfenggu"],
    "routes": ["rt_yueguo_luanxinghai"]
  },
  {
    "ch": 500,
    "label": "乱星海篇",
    "regions": ["r_luanxinghai"],
    "nodes": ["p_luanxinghai"]
  }
]
```

| 字段 | 规则 |
|---|---|
| `ch` | 必填，切片对应的读者章号；`first_ch` 可作为兼容回退 |
| `label` / `note` | 可选，给读者看的切片名与说明 |
| `regions` / `nodes` / `routes` | 可选，引用已有 id；读者版按 cutoff 只保留 `ch <= cutoff` 的切片 |

M4 只表示“数据里有时态切片”，不表示渲染器必须做动画。读者站按 `cutoff` 隐藏未来切片，并在示意 2D 工具栏提供切片下拉：`全部` 或 `第 N 章 · 切片名`；选中切片后按 `regions` / `nodes` / `routes` 过滤。没有 `time_slices` 时不显示该控件。

#### atlas（视觉风格包，可选）

`map_layout.atlas` 是示意 2D 的“风格包 + UI 配置”。不写时使用默认纸面、代码罗盘和自动题签：

```json
"atlas": {
  "title": { "text": "越国舆图", "x": 4.2, "y": 8.8, "size": 3.1, "direction": "vertical", "sealCh": "越" },
  "seal": { "ch": "越", "size": 2.55, "angle": -0.035 },
  "compass": { "x": 8.5, "y": 88, "size": 6.2, "opacity": 0.38 },
  "disclaimer": { "text": "示意舆图 · 方位与比例非精确", "x": 1.7, "y": 95.5 },
  "markers": { "p_yuejing": "city", "p_huangfenggu": "sect", "p_xutian_dian": "secret" },
  "titleByLayer": { "p_luanxinghai": { "text": "乱星海舆图", "sealCh": "乱" } },
  "stamps": [
    { "asset": "terrain_peak_02", "x": 28, "y": 32, "w": 13, "opacity": 0.6, "layer": "p_yueguo" },
    { "asset": "arch_city_wall_01", "attach": "p_yuejing", "w": 8.5, "markerOffset": 2.2 }
  ],
  "seaTexture": false,
  "terrainStamps": true
}
```

| 字段 | 规则 |
|---|---|
| `title` | `text`、`x` / `y` 0–100、`size` 占画布宽百分比、`direction: vertical/horizontal`、`sealCh` 回退印章字 |
| `seal` | 单字 `ch` 必填（不含空白）；`size`、`angle`；`x/y` 省略时自动落在题签正下方，题签变长也不会压住末字 |
| `compass` | `{x,y,size,opacity}` 或 `false` 关闭；固定 UI，不随地图缩放 |
| `disclaimer` | 左下免责小印：`text` / `x` / `y` |
| `markers` | `place_id → "city" / "sect" / "secret" / "danger" / "place" / "none"`；`none` 不画标记，也不占标签保留框 |
| `titleByLayer` | 层 id → 题签覆盖项（`text` / `sealCh` / 可选 `size`）；只在该层筛选时生效 |
| `stamps[]` | 见下表 |
| `seaTexture` | 默认 `false`；`true` 时把 `water_sea_01.webp` 叠在海面，仍保留代码波纹与湿边 |
| `terrainStamps` | 默认 `true`；`false` 时山脊改用代码墨线 |
| `palette` | 可选颜色 token 覆盖：`ink` / `accent` / `seal` / `paper` / `water` / `route` |

**`stamps[]` 字段**：

| 字段 | 规则 |
|---|---|
| `asset` | 必填，必须是 21 件网页资产之一（见下） |
| `attach` | 可选，必须是已有 `places` id；吸附到节点坐标，节点被层筛选隐藏时整个 stamp 一并隐藏 |
| `x` / `y` | 无 `attach` 时必填，0–100 绝对坐标 |
| `w` | 可选，占画布宽百分比；默认按资产类型（地形 14 / 水 10 / 建筑 8 / 植被 6） |
| `opacity` | 可选 0–1，默认 0.86 |
| `rotation` | 可选，角度 |
| `flip` | 可选布尔，水平翻转 |
| `anchor` | 可选 `center`；默认用资产 manifest 的 pivot（多为脚底 `[0.5,0.875]`） |
| `markerOffset` | 可选，建筑 stamp 会让节点点击标记向下让位的百分比 |
| `order` / `offsetY` / `layer` | 可选绘制顺序、Y 偏移、层归属 |

**21 件网页资产**：

| 类型 | id |
|---|---|
| 地形 7 | `terrain_far_01` `terrain_far_02` `terrain_peak_01` `terrain_peak_02` `terrain_ridge_01` `terrain_ridge_02` `terrain_slope_01` |
| 水 4 | `water_cloud_01` `water_cloud_02` `water_bank_01` `water_bank_02` |
| 建筑 6 | `arch_sect_gate_01` `arch_city_wall_01` `arch_pass_01` `arch_cave_01` `arch_village_01` `arch_dock_01` |
| 植被 4 | `veg_pine_01` `veg_bamboo_01` `veg_reeds_01` `veg_dead_tree_01` |

另有两件 support asset：`ui_paper_ornate`（纸底，始终全幅绘制）、`water_sea_01`（可选海纹）。

#### 位图资源与内联约定（asset）

示意 2D 的网页素材在 `template/assets/map/atlas/`，由 `scripts/prepare_atlas_web.py` 从 `atlas-kit/manifest.json` 生成：

- 21 件 PNG 转 webp（质量 86，保持 640 画布与 pivot），复制 `ui_paper_ornate.webp`、`water_sea_01.webp`；
- 生成网页侧 `manifest.json`，字段 `id / name / type / pivot / size / file / source / bytes`；
- `template/viewer/60-map-surface.js` 的资产表读这份 manifest；缺图时构建失败。

**内联机制**：模板 JS 用占位符 `__ASSET__:map/atlas/terrain_peak_02.webp`；`scripts/build.py` 构建时按 `template/assets/<相对路径>` 读文件，转 `data:<mime>;base64,…` 内联进单文件 HTML。占位符残留或图片缺失时构建**直接失败**；构建日志打印「内联 N 张 / 原始 KB / base64 后约 KB」。

**体积预算**：21 件 PNG 原始约 11 MB，转 webp 后约 1.07 MB；构建内联 23 张，原始 1,075 KB，base64 后约 1.44 MB。实测单文件：虚构样例 **1.66 MB**，凡人 500 章 **2.24 MB**。

**缺失行为**：`map_layout` 缺失时不报错，2D 视图显示「未提供示意坐标，已回退拓扑视图」并给切换按钮。`atlas` 缺失时用默认纸面、自动题签、代码罗盘。

#### 示意坐标 ≠ 证据坐标（含纸面免责）

- `map_layout` 的坐标是**人工近似摆放**，用于叙事导航，**不是原文方位证据**；只有 `spatial_relations` 里的 `direction` / `distance` 才是原文方位证据。
- 节点若在 `spatial_relations` 里存在 `kind ∈ {direction, distance}` 且以它为端点 → 徽标 `有原文方位证据`；其余节点 → 徽标 `近似摆放`。
- 示意坐标不写回 `places`，不进证据方位/拓扑的约束求解；不得渲染成证据坐标，不得显示比例尺/经纬网。
- 纸面上的山、海、建筑是**视觉底件**，不表达真实地理；`map_layout` 整体仍是人工示意坐标（非经纬度、非证据）。界面免责小印 `示意舆图 · 方位与比例非精确` 常在。

### validate 地图规则

规则标签「地图」。规则类别如下（error/warning 具体条数以 `validate.py` 实际实现为准）：

- **error 类别**：`mode` 非 `schematic`；`canvas` 非 `[100,100]`；`note` 超长或缺「非经纬度/示意」字样；`regions` / `nodes` 条目非对象；`regions[].id` 缺 `r_` 前缀或重复；`shape` 不在 `land/sea/void`；`layer` 指向不存在的 `places` id；`polygon` 不足 3 点或坐标越出 0–100；`nodes[].place` 不存在或重复；`x` / `y` 越出 0–100；`terrain` 内 `ridges` / `rivers` 折点不足或越界、`lakes.polygon` 不足 3 点、`islets` 必须是 `{x,y,r}` 对象且坐标/半径越界、`region` 指向不存在的 region id；`routes[].s` / `t` 不存在，`kind` 不在 `portal/travel_path/road/river`，`curve` 控制点越出 0–100；`atlas.title` / `atlas.seal` / `atlas.markers` / `atlas.stamps` 条目非对象、`seal.ch` 非单字、`asset` 不在 21 件、`attach` 指向不存在节点、`stamps[].x/y` 无 `attach` 时缺失或越界。
- **warning 类别**：`label_at` 坐标越界或格式异常；`rank` / `label` 取值非法；`islets` 少于 4 个时海面可能偏空（以实现为准）。`terrain` 缺失不触发回退告警。

### validate 空间规则

规则标签「空间」。必须报 error：

1. `spatial_relations` 存在时必须是 list；条目必须是对象。
2. `id` 前缀 `sr_`、唯一。
3. `s` / `t` 不是已有地点 id，或 `s == t`。
4. `kind` 不在枚举内；`direction` 的 value 不在方位词表内。
5. `confidence` 不在 `high/medium/low`。
6. `first_ch` 非 1..chapters 的整数。
7. `evidence` 不是对象，或 `evidence.ch` 越界/非整数，或 `evidence.quote` 为空/超过 120 字/含换行。
8. `value` 为空或超过 40 字。

报 warning：

9. `evidence.ch` 与 `first_ch` 不一致（`证据章 220 与 first_ch 144 不一致`）。
10. 层内 direction+distance 约束数为 1–2（`该层仅 N 条方向/距离约束，M2 会回退`）。

### spatial.json（书目录下的可选输入文件）

每本书目录下可有 `spatial.json`，结构含 `meta` / `places` / `spatial_relations`，以及可选的 `map_layout`：

```json
{ "meta": { "note": "人工证据化整理" },
  "places": [ { "id": "p_yuanwuguo", "name": "元武国", "parent": null, "desc": "...", "first_ch": 144, "attrs": {} } ],
  "spatial_relations": [ ... ],
  "map_layout": { ... } }
```

merge 行为：

- `places` 里 data.json 没有的 id 追加进 `places`（已存在则报冲突并跳过）；
- `spatial_relations` 原样挂到 data.json 顶层（并校验两端 id）；
- `map_layout` 原样挂到 data.json 顶层（并校验其中引用的 `places` id）；
- 没有 `spatial.json` 时，data.json 的 `spatial_relations` 为 `[]`；`map_layout` 缺失时 2D 回退拓扑，不算错误。

### 禁忌

- 不把自动布局或示意坐标写回 `places`，也不把它们当成事实坐标展示。
- 不把「旁边」「不远处」「一天路程」折算成里数或像素距离。
- 不给无原文证据的地点编方位；没有原文句子就不写、不进证据方位。
- 不把 `map_layout` 示意坐标当证据坐标；不显示比例尺/经纬网/指北针。空图上不存在任何地形，不得补成原文没有的山脉、河流、海岸轮廓；`terrain` 是装饰性示意，只在数据显式给出时绘制，不得按原文没有的地形补骨架或把它当原文地理。

---

## concepts

```json
{ "id": "c_xitong", "kind": "golden_finger", "name": "签到系统",
  "desc": "……", "first_ch": 1,
  "rules": ["每日签到得随机奖励", "连续签到有额外加成"],
  "limits": ["不能签到自己没有的东西"] }
```

`kind` 枚举：

| kind | 含义 | 例子 |
|---|---|---|
| `worldview` | 世界规则 | 灵气复苏、位面法则 |
| `golden_finger` | 金手指 | 签到系统、老爷爷、重生记忆 |
| `technique` | 功法/技能 | 九转玄功 |
| `item_grade` | 品阶体系 | 黄玄地天、凡品灵品仙品 |
| `organization_rule` | 组织规则 | 宗门贡献点制度 |
| `prophecy` | 预言/谶语 | 判词、天命 |

`rules` / `limits` 只对 `golden_finger` 必填——**金手指必须有代价，否则剧情没张力**。这一条能帮作者自查。

---

## 校验规则

1. 所有引用（`relations.s/t`、`chapters.new_entities`、`foreshadows.id` 被引用、`places.parent`、`entities.parent`、`power_history.realm`）必须存在
2. `id` 全局唯一，跨 entities / places / concepts / realms / foreshadows 不重复
3. `relations.type` 必须在 8 类内
4. `weight` / `tension` / `importance` 在 0–1
5. `realms.order` 唯一且从 1 连续递增
6. `power_history[].ch` 严格递增，`stage` 必须在对应 `realms.stages` 内
7. `places.parent` 与 `entities.parent` 各自不能成环
8. `chapters[].ch` 唯一且都落在 1..chapters；全量分析时须覆盖 1..已分析章数，摘要摘录时允许断档（校验器给警告）
9. `foreshadows.payoff_ch` 若存在必须 ≥ `plant_ch`
10. `coverage.chapters_done + chapters_skipped == chapters`

空间关系（`spatial_relations`）的校验规则见上文「spatial_relations（空间关系与地图分级）· 可选」一节的「validate 空间规则」清单（规则标签「空间」）；`map_layout` 的校验见同节「validate 地图规则」（规则标签「地图」）。

---

## v1.0 → v2.0 迁移

| v1.0 | v2.0 |
|---|---|
| `events[]` | 删除。关键节点 = `chapters` 里 `tension ≥ 0.75` 的章 |
| `meta.author` 等 | 保留，新增 `genre` / `platform` / `status` |
| `entities[].attrs` | 保留，新增 `parent` / `power_history` / `ranks` |
| `concepts[]` | 新增 `kind`（必填） |
| — | 新增 `volumes` / `realms` / `chapters` / `foreshadows` / `knowledge` |

v1.0 的古典小说样例已归档到 `samples/_archive/`，不再维护，不参与校验。

---

## 版本历史

| 版本 | 变更 |
|---|---|
| 1.0 | 初版。6 个顶层字段，8 类关系，古典小说样本（已归档） |
| 2.0 | 面向中文网文。新增境界/伏笔/逐章/分卷/认知隔离；移除 events |
| 2.1 | 境界体系改为**全局定义**（`realms.json` + `scripts/realms.py`）。禁止逐批建立 `realms`，`power_history` 须逐条对回原文 |
| 2.2 | 伏笔新增 `last_mention_ch` / `keywords`。超期判定从「埋了多久」改为「多久没提」，四处实现统一口径 |
| 2.3 | 新增可选 `spatial_relations`（每条带 `evidence` 章号 + 原文片段）与「地图」视图（M1 拓扑 / M2 证据化示意）；`places` 语义不变、无坐标字段；M2 约束不足自动回退 M1 |
| 2.4 | 地图视图调整为三子视图：示意 2D（默认，可选 `map_layout` 人工近似坐标）/ 证据方位（原 M2）/ 拓扑（原 M1，次要）；示意坐标与原文方位证据分开标注，缺失 `map_layout` 时 2D 回退拓扑 |
| 2.5 | `map_layout` 新增可选 `terrain`（装饰地形：脊线/河流/湖泊/岛链）与 `routes`（弯曲航路）；地形与海岸轮廓标注为装饰性示意、非原文地理事实，印章 `示意地图 · 非精确比例` |
| 2.6 | 2D 改为位图底图（`template/assets/map/web/`，`__ASSET__` 占位符构建内联）；`terrain` 字段保留但当前视图不渲染；默认层改「全部」；字号/节点半径/LOD 按 1920 底图尺度更新 |
| 2.7 | 2D 改为空地图背景（`backgrounds/web/blank-map-light.webp` / `blank-map-dark.webp`）+ 图标组织（徽章/头像/标记）；撤掉地形底图、浮空岛、祥云、山林等资产（保留备用、当前不消费）；两簇构图、仅一条远海航路；印章改 `空图示意 · 非精确比例`；体积预算按当前消费资产重算（原始约 0.95MB / base64 后约 1.27MB） |
| 2.8 | 读者向：新增 `_reader` / `anomalies` / `_mapLevels` / `_anomalyMeta` 派生字段；支持 `cutoff_ch` 投影、疑点索引、M0–M4 分级、`time_slices` 时态切片 |
| 2.9 | 地图编排器内置拖拽节点、节点分层、挂/移除 21 件底件并导出 map-layout；示意 2D 显示 M 等级、层筛选、时间切片下拉与 PNG/SVG |
