这是执行 agent 在本地分批抽取时使用的批次模板。输入是同一本书连续的若干章原文，任务是把它们变成可校验的 JSON。

写 `out/batch-XX.json` 时只写一个 JSON 对象，不要解释、不要 Markdown 代码块、不要前后缀。

## 硬规则

1. **宁缺毋滥**：原文没写的关系、身份、境界不要猜。抽不到就留空数组。
2. **复用 id**：下面「已登场实体目录」里的角色/势力/器物，必须沿用它的 id，不要为同一个人另起新 id。
3. **每条关系两端都必须是实体**：`s` / `t` 只能是本批 entities 或目录里的 id。
4. **逐章全量**：本批每一章都要有一条 `chapters` 记录，章号必须与输入一致。
5. **摘要 ≤ 80 字，章末钩子 ≤ 30 字**，超了会被校验器打回。
6. 所有 `ch` / `first_ch` / `plant_ch` / `payoff_ch` 都是**全书章号**，不是批内序号。

## 本书已确认的境界体系（权威，不要改动 order）

{{REALMS}}

- 体系为空时：只有本批原文明确出现等级词才填 `realms`，否则给 `[]`，不要自创修炼等级。
- 体系非空时：`power_history.realm` 必须用这里的 `id`，`stage` 必须在该境界的 `stages` 里。

## 已登场实体目录（id｜正名｜类型｜别名）

{{CATALOG}}

## 尚未回收的伏笔（id｜内容｜埋设章）

{{OPEN_FORESHADOWS}}

如果本批**回收**了其中某条，输出同一条 `foreshadows`（同 id），填上 `payoff_ch` 和 `payoff_quote`（形如 `ch87:p3`）。这是伏笔台账最重要的数据，漏了整条线索就永远显示"未回收"。

## 本批章节：第 {{CH_START}}–{{CH_END}} 章

{{CHAPTERS}}

## 输出结构

```json
{
  "entities": [
    {"id":"e_xxx","name":"正名","type":"character|org|item|creature","group":"阵营",
     "parent":null,"aliases":["别名"],"desc":"≤100字","first_ch":1,"last_ch":null,
     "attrs":{"身份":"…","所修":"…"},"power_history":[{"ch":9,"realm":"r_lianqi","stage":"一层","note":"…"}],
     "ranks":[]}
  ],
  "relations": [
    {"s":"e_a","t":"e_b","type":"kinship|marriage|romance|service|mentorship|alliance|conflict|social",
     "label":"师徒","weight":0.9,"first_ch":5,"evidence":["ch05:p3"]}
  ],
  "chapters": [
    {"ch":1,"title":"章名","words":2400,"volume":"v1","summary":"≤80字",
     "hook":"≤30字","hook_type":"悬念|反转|冲突|危机|爽点|无","emotion":"爽|压抑|紧张|温情|悲|平",
     "tension":0.6,"new_entities":["e_xxx"],"new_foreshadows":["f_xxx"],"battles":[]}
  ],
  "foreshadows": [
    {"id":"f_xxx","content":"≤50字","plant_ch":12,"plant_quote":"ch12:p8",
     "payoff_ch":null,"payoff_quote":null,"status":"planted","thread":"身世之谜",
     "importance":0.85,"note":"…"}
  ],
  "realms": [],
  "places": [
    {"id":"p_xxx","name":"青云宗","parent":null,"desc":"…","first_ch":1,"attrs":{"所属":"东域"}}
  ],
  "concepts": [
    {"id":"c_xxx","kind":"worldview|golden_finger|technique|item_grade|organization_rule|prophecy",
     "name":"签到系统","desc":"…","first_ch":1,"rules":["…"],"limits":["…"]}
  ]
}
```

补充要求：

- `entities` 只收本批**首次登场**或**信息有实质更新**的；`item` 不要泛滥，只收推动剧情的关键器物（功法、技能归 `concepts`，不要当 item）。
- `places` 收宗门、城池、山川、秘境这类**可复用的地点**；`concepts` 收功法、金手指、品阶体系、组织制度。这两个表是"设定百科"的数据源，别整批空着。
- `born` / `battles`：有明确交手才填，`gap` 用双方境界 `order` 差（a 比 b 强为正）。
- 不写 `status` 以外的派生字段；`status` 先填 `planted` 或 `paid`，最终由合并脚本重算。
