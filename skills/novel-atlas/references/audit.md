# 疑点复核

> 本文件是 `novel-atlas` 的「疑点复核」流程，按需读取；公共契约见 `SKILL.md`。

本流程不重新分析小说，只消费 `anomalies.json` 和 `data.json`。它回答的是“这条疑点值不值得信、原文在哪、是不是误报”，不是“作者该怎么改”。

## 数据在哪

本 skill 只读两个文件，不关心仓库结构：

```text
data.json          # 由 analyze 流程产出
anomalies.json     # 默认取 data.json 同目录，由本 skill 的 anomalies.py 生成
```

`--data` 传绝对路径最稳；传相对路径时先按当前目录解析，若当前目录在仓库内则按仓库根解析。不需要指定项目根，也不需要仓库存在。

默认只读；`--web` 模式只写 `review/`，不修改 `data.json` 或 `anomalies.json`。

## 疑点的语义

每条疑点都是候选，不是判决。字段：

| 字段 | 含义 |
|---|---|
| `kind` / `kind_cn` | 规则与中文名 |
| `severity` | `high` / `warning` / `info` |
| `confidence` | `high` / `medium` / `low` |
| `chapter_range` | 涉及的章节范围 |
| `entities` | 相关实体/地点/伏笔 id |
| `evidence` | `coordinate` + `quote`；优先 `chN:pM`，没有段落时退化为 `chN` |
| `reader_note` | 可能解释，不是改稿建议 |
| `verified` | 生成时的默认值；人工复核结果另存 |

**没有证据的条目不应进入索引。** 如果 `evidence` 为空，直接指出数据不合格，不要替它编原文。

## 工作流

### 1. 生成/刷新疑点

```bash
python "<SKILL_DIR>/scripts/anomalies.py" --data output/凡人修仙传/data.json --out output/凡人修仙传/anomalies.json
```

只有数据变化后才需要重跑。读者站的 `build_reader.py` 也会自动生成。

### 2. 看统计与清单

```bash
python "<SKILL_DIR>/scripts/audit.py" stats --data output/凡人修仙传/data.json
python "<SKILL_DIR>/scripts/audit.py" list --data output/凡人修仙传/data.json --severity warning
```

### 3. 回原文核对

先读 `evidence[].coordinate`，再到 `data.json` 的 `chapters[].summary` / `hook` / `battles` / `entities.power_history` 找对应记录。

- `chN:pM`：段落坐标；如果数据源没有段落，`quote` 只能是章节摘要，要明确告诉用户“只有章节级证据”。
- `chN`：章节级证据；不要伪装成段落级。
- 多条证据互相矛盾时，先列证据，再给可能解释。

### 4. 标记复核结果

```bash
python "<SKILL_DIR>/scripts/audit.py" mark --data output/凡人修仙传/data.json --id an_fs_xxx --status verified --note "第 73 章确有回收，误报"
python "<SKILL_DIR>/scripts/audit.py" mark --data output/凡人修仙传/data.json --id an_x_xxx --status rejected
```

复核结果写到 `anomalies-verdicts.json`，不修改 `anomalies.json`，方便重跑后保留人工判断。

### 5. 输出考据摘要

给读者的摘要必须包含：

1. 疑点总数、按 kind 的数量；
2. 高优先/待复核各几条；
3. 每条只给“标题 + 证据坐标 + 可能解释”；
4. 明确“这是数据候选，不是对作者的判决”；
5. 不输出“应该改成什么”“作者写错了”这类改稿建议。

## 联网核对模式（`--web`，可选）

默认关闭，只产出**外部线索**，不写 `data.json`，也不改变疑点索引。它只处理规则引擎判不了、原文又没直说的字段：别名、类型、上级、术语、写法。

### 1. 生成核对清单

```bash
python "<SKILL_DIR>/scripts/audit.py" --web --data output/凡人修仙传/data.json --limit 24
```

产出 `review/web-questions.json` 和 `review/web-questions.md`。问题只来自数据缺口：

- 关系多但没有别名的角色/势力；
- `alias_candidate` 这类低置信别名候选；
- 没有归属的早期根地点；
- 功法 / 品阶类术语的归类。

### 2. 联网搜索（执行 agent 做，脚本不联网）

- 用 agent 自带的 WebSearch / WebFetch，不要给脚本加 API key 或网络客户端。
- **只查白名单字段**：`aliases` / `type` / `parent` / `terminology` / `spelling`。
- **不查剧情**：死亡、退场、结局、伏笔回收、战力终值。外站默认覆盖全书，看到也别写进线索。
- 每条线索至少 1 个 `http(s)` 来源，带 `retrieved_at`；同一说法尽量找两个独立来源。
- `claim` 只写字段本身，≤ 600 字，不要整段复制百科。
- 结果写到 `review/web-leads.json`，schema 见 `web-questions.json` 里的 `leads_schema`。

### 3. 汇总与隔离

```bash
python "<SKILL_DIR>/scripts/audit.py" --web --data output/凡人修仙传/data.json --leads output/凡人修仙传/review/web-leads.json
```

产出 `review/web-leads.md`。以下情况进「已隔离」，不混进可参考区：

- 目标 id 不在 `data.json`；
- 字段不在白名单（例如 `death` / `ending` / `payoff`）；
- 来源缺失、URL 不是 http(s)、没有 `retrieved_at`；
- `spoiler_risk=high`。

报告始终标注「外部线索不是原文证据」。确认后由人手工改 `data.json`，再跑 `merge.py` / `validate.py`；**脚本不自动改**。

### 4. 什么时候值得跑

- 角色称号多、改名多，搜索老是漏；
- 两个名字疑似同一人，规则引擎只给了低置信候选；
- 术语或势力归类影响百科与战力体系；
- 地图、结局、伏笔回收这类剧情字段**不要**用外部资料补。

## 规则边界

- 伏笔未回收只看 `plant_ch`、`payoff_ch`、`last_mention_ch` 与当前阈值；不要把“作者留白”直接判成错误。
- 战力倒退可能是跌境/重修/伪装；死亡再出现可能是回忆/残魂/同名；关系反转可能有时序事件支撑。
- `confidence=low` 的别名候选、器物断线、时间线疑点，默认只作线索，不作结论。
- 地图 M 等级只表示证据能力，不表示地图好坏；M1 不是失败。

## 常见故障

| 现象 | 先查 |
|---|---|
| 疑点全部是 `rule_error` | 用 `python "<SKILL_DIR>/scripts/anomalies.py" ... --list` 看具体规则异常 |
| 伏笔未回收数量暴增 | `meta.coverage.chapters_done` 是否只覆盖前 N 章；阈值是否按 live 章计算 |
| 死亡再出现全是误报 | `entities.attrs` 是否把“假死/残魂/回忆”写成死亡；`last_ch` 是否偏早 |
| 读者站疑点为空 | 构建时是否用了旧版 `anomalies.json`；`build_reader` 是否注入了 `anomalies` |
