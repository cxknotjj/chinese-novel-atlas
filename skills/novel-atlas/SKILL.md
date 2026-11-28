---
name: novel-atlas
version: 1.0.0
description: "把一部网文编译成可查、可分享、按阅读进度不剧透的世界档案。六个流程共用同一份 data.json：拆书成结构化档案（analyze）、带原文坐标的书内问答（ask）、疑点复核（audit）、跨书指标对比（compare）、导出读者站/设定集/角色表（export）、小说地图编排与渲染（map）。适用于拆书、做人物关系图与知识图谱、整理设定、按章节查角色境界与伏笔回收、核对设定矛盾、比较两本书的节奏与伏笔回收率、生成读者站或世界地图。触发词：拆书、拆这本书、拆《XXX》、分析这本小说、生成人物图谱、人物关系图、整理设定、做个读者站、这本书里XX是谁、问书、查设定、XX现在什么境界、XX在第几章出现、XX和XX什么关系、有没有提到XX、伏笔回收、疑点、考据、矛盾、死亡又出现、战力倒退、对比这两本书、跨书比较、哪本书节奏更好、伏笔回收率对比、导出读者站、导出设定集、导出人物表、给我 CSV、导出到第 N 章、小说地图、生成地图、地图渲染、map_layout、世界地图、势力地图、novel atlas。"
---

> **脚本已内置**：本 skill 自带全部 CLI 与渲染资源，装完即可运行，**不需要 clone 仓库**。
> 下文命令里的 `<SKILL_DIR>` 指本 skill 的安装目录（含 `SKILL.md` 的那一层），
> 常见位置：`~/.claude/skills/novel-atlas`、`~/.workbuddy/skills/novel-atlas`；
> 执行时替换成真实绝对路径。产出路径（如 `output/{书名}/`）相对**当前工作目录**。

# Novel Atlas · 网文世界档案

一部小说 → 一份 `data.json`（人物 / 关系 / 章节 / 伏笔 / 地点 / 概念，每条都带 `chN:pM` 原文坐标）→ 六个流程共用它。

## 先认意图，再只读那一份流程

| 用户想做的事 | 读这个文件 | 入口 |
|---|---|---|
| 拆一本新书、补批次、重跑合并与校验、生成图谱页 | `references/analyze.md` | `chunk.py` → 分批抽取 → `merge.py` |
| 问书里的人和事：谁、第几章出场、什么境界、和谁什么关系 | `references/ask.md` | `seek.py` + `data.json` |
| 复核疑点、标已核实 / 误报、可选联网核对 | `references/audit.md` | `audit.py` |
| 两本或多本书横向比节奏、伏笔、战力 | `references/compare.md` | `compare.py` |
| 导出读者站 / 单文件 / 设定集 / 角色表 / CSV | `references/export.md` | `export.py`、`build_reader.py` |
| 给书画地图、补 `map_layout`、排查渲染 | `references/map.md` | `atlas_map.py` + `atlas-kit` |

**只读需要的那一份。** 六份加起来约 900 行，一次全读会挤掉正文预算；流程之间没有隐藏依赖，按意图取用即可。地图流程额外需要一份完整仓库（`atlas-kit/` 素材约 20MB），其余五个装完即用。

## 四条共同契约

1. **先找数据。** 一切从这里开始：`output/{书名}/data.json`。找不到就是还没拆，走 analyze。
2. **证据要能回原文。** 结论必须落到 `chN:pM`；结构化字段查不到才回原文，回原文必须给坐标。
3. **默认只读。** 除用户明确要求，不直接改 `data.json`；要改走 `merge.py`、`mentions.py` 这类带校验的入口。
4. **不调外部 API。** 抽取、问答、复核都由执行 agent 自己完成；脚本只做确定性处理，不需要 key。

## 最短路径

```bash
# 1) 分章（抽取由 agent 读 chapters/ 完成，模板见 scripts/prompts/batch_template.md）
python "<SKILL_DIR>/scripts/chunk.py" "<文件路径>" --out output/{书名}/

# 2) 合并批次 → 全局境界 → 重跑合并 → 提及追踪 → 校验
python "<SKILL_DIR>/scripts/merge.py" output/{书名}/ --genre 仙侠 --platform 起点
python "<SKILL_DIR>/scripts/realms.py" output/{书名}/ --write
python "<SKILL_DIR>/scripts/merge.py" output/{书名}/
python "<SKILL_DIR>/scripts/mentions.py" output/{书名}/ --apply
python "<SKILL_DIR>/scripts/validate.py" output/{书名}/data.json

# 3) 出页面：单文件档案 / 按进度截断的读者站
python "<SKILL_DIR>/scripts/build.py" --data output/{书名}/data.json --out output/{书名}/
python "<SKILL_DIR>/scripts/build_reader.py" --data output/{书名}/data.json --out output/{书名}/reader --single --allow-partial
```

## 数据契约

字段、证据格式、`status` 判定规则统一在 `references/schema.md`；地图前端契约在 `references/web-contract.md`，视觉与排错见 `references/style-and-qa.md`、`references/troubleshooting.md`。

一次安装覆盖全部六个流程，不需要为「问书」「导出」再装别的 skill。
