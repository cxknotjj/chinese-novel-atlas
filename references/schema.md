# 数据契约 · schema v1.0

所有 skill 共用这一份 JSON 结构。**改动这里，四个 skill 全部要跟着改。**

- 参考实现：`samples/honglou/data.json`（红楼梦，手工金标准）
- 校验脚本：`scripts/lib/schema.py`
- 版本规则：破坏性变更升主版本号；新增可选字段升次版本号

---

## 完整结构

```jsonc
{
  "meta":      { /* 元信息 */ },
  "entities":  [ /* 人物 / 组织 / 器物 / 异兽 */ ],
  "relations": [ /* 实体之间的关系 */ ],
  "events":    [ /* 章节级事件 */ ],
  "places":    [ /* 地点，支持层级 */ ],
  "concepts":  [ /* 概念、设定、器物说明 */ ]
}
```

---

## meta

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | ✓ | 固定 `"1.0"` |
| `title` | string | ✓ | 书名 |
| `title_en` | string | | 英文名，用于国际化展示 |
| `author` | string | ✓ | 作者 |
| `source_file` | string | | 源文件名（不含路径，避免泄露本地路径） |
| `chars` | int | ✓ | 正文字数 |
| `chapters` | int | ✓ | 总章数 |
| `analyzed_at` | string | ✓ | ISO 8601 UTC 时间 |
| `model` | string | ✓ | 抽取所用模型；手工样本填 `"manual"` |
| `cost_cny` | number | | 本次分析花费（元） |
| `elapsed_sec` | int | | 耗时（秒） |
| `coverage` | object | ✓ | `{ chapters_done, chapters_skipped }` |
| `note` | string | | 自由备注 |

**约束**：`coverage.chapters_done + chapters_skipped == chapters`。不一致说明跑漏了章节，viewer 会在顶部提示。

---

## entities

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `e_` 前缀 + 小写拼音/英文，全局唯一 |
| `name` | string | ✓ | 正名 |
| `type` | enum | ✓ | `character` / `org` / `item` / `creature` |
| `group` | string | ✓ | 阵营/家族，决定节点颜色。建议 ≤ 10 种 |
| `aliases` | string[] | ✓ | **别名，可为空数组**。别名消解的核心字段 |
| `desc` | string | ✓ | 简介，**建议 ≤ 100 字**，超出 viewer 会截断 |
| `first_ch` | int | ✓ | 首次登场章号 |
| `last_ch` | int | | 最后出现章号；已死亡角色必填 |
| `attrs` | object | | 自由键值对，展示在详情面板 |
| `degree` | int | | 关系数。**可省略**，viewer 会现算 |

**id 命名规则**：
- 前缀 `e_`
- 只用小写字母、数字、下划线
- 一旦发布不可修改（下游 skill 会引用）

**group 建议值**（可按书调整）：家族名 / 势力名 / `"其他"` / `"仆役"`

---

## relations

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `s` | string | ✓ | 起点 entity id |
| `t` | string | ✓ | 终点 entity id |
| `type` | enum | ✓ | 见下表，**只能取这 8 个值** |
| `label` | string | | 具体称谓，如「木石前盟」「母子」 |
| `weight` | number | ✓ | 0–1，关系强度。同两人多条关系时取最高者画线 |
| `first_ch` | int | ✓ | 关系确立的章号 |
| `evidence` | string[] | | 证据坐标 `ch03:p12`（第 3 章第 12 段） |

### 关系类型（封闭枚举）

**这 8 类是跨书对比的前提，不允许扩展。**

| type | 中文 | 判定标准 | 典型 |
|---|---|---|---|
| `kinship` | 血亲 | 血缘或宗族关系 | 父子、兄妹、叔侄 |
| `marriage` | 婚姻 | 夫妻、妾室、婚约 | 结发、纳妾、定亲 |
| `romance` | 情感 | 爱慕、暧昧、痴情，**不含已成婚** | 木石前盟、单恋 |
| `service` | 主从 | 主仆、上下级、门客 | 丫鬟、家仆、属官 |
| `mentorship` | 师承 | 授业、传艺、提携 | 塾师、师父 |
| `alliance` | 同盟 | 结盟、合作、恩义 | 结拜、救命之恩 |
| `conflict` | 敌对 | 仇怨、对抗、倾轧 | 陷害、逼婚、逐出 |
| `social` | 交游 | 同僚、社友、泛泛之交 | 诗社、同窗 |

**边界规则**：
- 两人既是夫妻又是血亲（如近亲联姻），画 `marriage`，`kinship` 在详情面板列出
- 主仆之间有情感，画 `romance`，`service` 并列
- 一段关系从交游变敌对，`type` 取**最终状态**，`label` 写转变（如「先友后敌」）

---

## events

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ch` | int | ✓ | 章号 |
| `title` | string | ✓ | 事件标题，**≤ 14 字** |
| `summary` | string | ✓ | 摘要，**≤ 80 字**，viewer 用于时间线 |
| `tension` | number | ✓ | 0–1，情节强度，用于画曲线 |
| `entities` | string[] | | 涉及的 entity id |

**tension 打分参考**（让不同书的曲线可比）：

| 区间 | 含义 |
|---|---|
| 0.0–0.3 | 铺垫、日常、交代 |
| 0.3–0.6 | 推进、小冲突 |
| 0.6–0.8 | 转折、重要揭示 |
| 0.8–1.0 | 高潮、死亡、决裂 |

---

## places

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `p_` 前缀 |
| `name` | string | ✓ | 地名 |
| `parent` | string \| null | ✓ | 上级地点 id，顶层为 `null` |
| `desc` | string | ✓ | 说明 |
| `first_ch` | int | ✓ | 首次出现章号 |
| `attrs` | object | | 如 `{ 主人: "贾宝玉" }` |

`parent` 构成树，viewer 画成可折叠的地点树。**不允许成环**，校验脚本会检测。

---

## concepts

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | `c_` 前缀 |
| `name` | string | ✓ | 名称 |
| `desc` | string | ✓ | 说明 |
| `first_ch` | int | ✓ | 首次出现章号 |

用于放"设定类"的东西：金手指、功法体系、核心器物、组织宗旨。与 `entities(type=item)` 的区别：
- **有明确归属者**的实物 → `entities`（如通灵宝玉在宝玉身上）
- **抽象设定 / 体系 / 传说** → `concepts`（如木石前盟、护官符）

---

## 校验规则（`scripts/lib/schema.py` 会检查）

1. 所有 `relations[].s/t`、`events[].entities[]`、`places[].parent` 必须能在对应集合里找到
2. `id` 全局唯一，跨 entities / places / concepts 不重复
3. `relations[].type` 必须在上表 8 个值内
4. `weight`、`tension` 必须在 0–1
5. `places` 的 `parent` 链不能成环
6. `coverage` 两项之和等于 `chapters`
7. 同一对 `(s, t, type)` 不能重复出现

---

## 版本历史

| 版本 | 变更 |
|---|---|
| 1.0 | 初版。8 类关系、6 个顶层字段、红楼梦金标准样本 |
