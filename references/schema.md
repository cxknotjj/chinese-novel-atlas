# 数据契约 · schema v2.0

面向**中文长篇网络小说**设计。不追求兼容古典小说——目标单一，字段才能贴紧网文的真实结构。

- 参考实现：`samples/fictional/`（虚构网文《青云签到三十年》，覆盖全部字段）
- 校验脚本：`scripts/lib/schema.py`
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
  "concepts":    [ /* 世界观 / 金手指 / 功法 / 品阶 */ ]
}
```

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
| `model` | string | ✓ | 抽取所用模型；手工填 `"manual"` |
| `cost_cny` | number | | 花费（元） |
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

`gap` = 双方境界 `order` 差（正数表示 a 更强）。**这是检测"战力崩坏"的原始数据**：主角越 5 个境界打赢，要么是爽点设计，要么是崩了，需要作者自己判断。

### 派生指标（不存储，由 viewer / compare 现算）

| 指标 | 计算方式 | 平台基准 |
|---|---|---|
| 章末钩子率 | `hook` 非空章数 / 总章数 | 番茄 ≥ 80%，起点 ≥ 60% |
| 爽点间隔 | 相邻 `emotion=爽` 章号差的中位数 | 番茄 3 章，起点 10 章 |
| 平均章字数 | `words` 均值 | 番茄 4000，起点 6000 |
| 情绪曲线 | 按章号绘制 `emotion` 序列 | — |

**这些是产品卖点，不是学术指标。** README 里要直接展示"你的钩子率 62%，番茄基准 80%"。

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
| `status` | enum | | `planted` / `paid` / `overdue` / `dropped`。**派生字段**，见下 |
| `thread` | string | | 所属线索，便于分组查看 |
| `importance` | number | ✓ | 0–1，影响告警优先级 |
| `note` | string | | 补充说明 |

### status 判定规则

**`status` 是派生字段，不是源头数据。** 存储时写入的是快照，校验器会用下面的规则重算并比对，不一致直接报错。

| status | 条件 |
|---|---|
| `paid` | `payoff_ch` 非空 |
| `dropped` | 作者明确放弃（**唯一需要人工标注的状态**） |
| `overdue` | `payoff_ch` 为空 **且** `当前分析到的最大章号 - plant_ch > 阈值` |
| `planted` | 其余情况 |

**阈值 = max(50, 总章数 × 0.15)**。1000 章的书阈值 150 章；120 回的名著阈值 50 回。

**这个阈值必须动态**。固定值对短书太松、对长书太紧，告警就没人看了。

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
8. `chapters[].ch` 唯一且覆盖 1..chapters，缺失的章节记入 `coverage.chapters_skipped`
9. `foreshadows.payoff_ch` 若存在必须 ≥ `plant_ch`
10. `coverage.chapters_done + chapters_skipped == chapters`

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
