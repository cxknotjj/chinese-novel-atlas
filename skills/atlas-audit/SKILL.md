---
name: atlas-audit
description: "复核 Novel Atlas 的读者向疑点索引：查看 anomalies.json、按严重度/规则筛选、回到原文坐标核对、把某条标为已核实或误报，并输出考据统计。适用于读者考据、书评作者核对设定矛盾、维护疑点误报库、给读者站补疑点说明。触发词：疑点、考据、矛盾、伏笔没回收、死亡又出现、战力倒退、越级战斗、atlas-audit、anomalies.json、误报标记。"
---

# atlas-audit · 疑点复核

`atlas-audit` 不重新分析小说，只消费 `anomalies.json` 和 `data.json`。它回答的是“这条疑点值不值得信、原文在哪、是不是误报”，不是“作者该怎么改”。

## 先定位项目根

项目根必须同时包含：

```text
scripts/anomalies.py
scripts/novel_atlas/reader/anomalies.py
template/viewer.html
```

默认从当前目录向上找；也可以显式传：

```powershell
python "<SKILL_DIR>\scripts\audit.py" stats --project-root "D:\Desktop\project\chinese-novel-atlas"
```

`SKILL_DIR` 是本 skill 所在目录。不要在本 skill 目录里找 `data.json`。

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

```powershell
python scripts/anomalies.py --data output/凡人修仙传/data.json --out output/凡人修仙传/anomalies.json
```

只有数据变化后才需要重跑。读者站的 `build_reader.py` 也会自动生成。

### 2. 看统计与清单

```powershell
python "<SKILL_DIR>\scripts\audit.py" stats --project-root "D:\Desktop\project\chinese-novel-atlas" --data output/凡人修仙传/data.json
python "<SKILL_DIR>\scripts\audit.py" list --data output/凡人修仙传/data.json --severity warning
```

### 3. 回原文核对

先读 `evidence[].coordinate`，再到 `data.json` 的 `chapters[].summary` / `hook` / `battles` / `entities.power_history` 找对应记录。

- `chN:pM`：段落坐标；如果数据源没有段落，`quote` 只能是章节摘要，要明确告诉用户“只有章节级证据”。
- `chN`：章节级证据；不要伪装成段落级。
- 多条证据互相矛盾时，先列证据，再给可能解释。

### 4. 标记复核结果

```powershell
python "<SKILL_DIR>\scripts\audit.py" mark --data output/凡人修仙传/data.json --id an_fs_xxx --status verified --note "第 73 章确有回收，误报"
python "<SKILL_DIR>\scripts\audit.py" mark --data output/凡人修仙传/data.json --id an_x_xxx --status rejected
```

复核结果写到 `anomalies-verdicts.json`，不修改 `anomalies.json`，方便重跑后保留人工判断。

### 5. 输出考据摘要

给读者的摘要必须包含：

1. 疑点总数、按 kind 的数量；
2. 高优先/待复核各几条；
3. 每条只给“标题 + 证据坐标 + 可能解释”；
4. 明确“这是数据候选，不是对作者的判决”；
5. 不输出“应该改成什么”“作者写错了”这类改稿建议。

## 规则边界

- 伏笔未回收只看 `plant_ch`、`payoff_ch`、`last_mention_ch` 与当前阈值；不要把“作者留白”直接判成错误。
- 战力倒退可能是跌境/重修/伪装；死亡再出现可能是回忆/残魂/同名；关系反转可能有时序事件支撑。
- `confidence=low` 的别名候选、器物断线、时间线疑点，默认只作线索，不作结论。
- 地图 M 等级只表示证据能力，不表示地图好坏；M1 不是失败。

## 常见故障

| 现象 | 先查 |
|---|---|
| 疑点全部是 `rule_error` | 用 `python scripts/anomalies.py ... --list` 看具体规则异常 |
| 伏笔未回收数量暴增 | `meta.coverage.chapters_done` 是否只覆盖前 N 章；阈值是否按 live 章计算 |
| 死亡再出现全是误报 | `entities.attrs` 是否把“假死/残魂/回忆”写成死亡；`last_ch` 是否偏早 |
| 读者站疑点为空 | 构建时是否用了旧版 `anomalies.json`；`build_reader` 是否注入了 `anomalies` |
