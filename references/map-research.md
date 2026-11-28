# 地图方案调研：从 “画地图” 到 “证据化空间视图”

> **实现状态（2026-11-27 追加）**：本调研的 §6 结论已部分落地，正文保留调研时点口径，以本段为准。
> - `地图` 视图是第 8 个顶级视图，内部三个子视图：**示意 2D（默认）/ 证据方位 / 拓扑**。示意 2D 用人工/自动近似坐标（`map_layout`，0–100 归一化画布），证据方位只消费带 evidence 的 `direction`/`distance`/`contain`/`adjacent`，拓扑 = `places.parent` 层级图（位置可随机摆放、仅表达包含）。
> - `spatial_relations` 与 `map_layout` 均已进 schema（`references/schema.md`），`validate.py` 有「空间」与「地图」两套规则；`spatial.json` 作为书目录下的可选输入由 merge 接线。
> - 《凡人修仙传》实测：20 条空间关系（13 high / 4 medium / 3 low）、39 个示意节点 / 3 个区域；只有越国层能进证据方位（47 节点 / 15 条边 / 9 个有方向或距离证据 / 38 个进“方位未知”区），乱星海、虚天殿、血色禁地层按 <3 条约束的阈值**自动回退拓扑**。
> - 因此 §0 结论 2「本项目当前只到 M1」与 §6.5「不建议一上来加第八个顶级视图」属于调研时点的判断，已被上面的实现取代；§6.3 的草稿示例里 `evidence` 为字符串、kind 写作 `contains`，实际契约为 `evidence: {ch, quote}` 与 `contain`。
> - 仍未做：真实经纬度、地形/河流/海岸线、图片底图打点、M3 多层、M4 时态。

调研对象是公开可读的小说分析、世界观管理和程序化地图项目。重点不是 “谁的图更漂亮”，而是四个问题：



1. 地理数据从哪里来，存在哪一层；

2. 坐标是文本证据、人工标注，还是程序生成；

3. 地图如何渲染、分层、筛选和导出；

4. 哪些做法适合 `chinese-novel-atlas`，哪些会把 “设定分析” 变成 “设定发明”。



***

## 0. 结论



1. **地图不是一种渲染样式，而是一种证据等级。** 没有方位、距离、边界证据时，只能画拓扑关系图，不能画带东南西北和比例尺的地图。

2. **本项目当前只到 M1。** `places` 只有 `parent` 层级，没有坐标、方位、距离或道路；地点志是一棵树，不是地图。把树强行画成地图，会制造原文没有的地理事实。

3. **最合适的路线是 “M1 拓扑图 → M2 证据化示意地图 → 可选手动底图”。** 先让地点关系可看，再等抽取能稳定产出空间关系，最后才考虑上传官方地图、打点或真实地理模式。

4. **不要直接复制 AI Reader V2 的实现。** 它的约束求解和审计很值得学，但地图模块本身是数千行 Python + 专门前端，且项目是 AGPL-3.0；我们是 MIT，直接搬代码会有许可证和体量双重问题。

5. **如果以后要做程序化地形，只把它当装饰层。** 地形、河流、海岸线不能由地点类型 “推” 出来再冒充原文地理；必须显式标注 “示意底图，不是文本证据”。



***

## 1. 四条技术路线



| 路线          | 代表项目                               | 地理数据来源            | 画法                      | 适合谁               |
| ----------- | ---------------------------------- | ----------------- | ----------------------- | ----------------- |
| 文本约束求解      | AI Reader V2                       | 每章抽取的空间关系         | 约束求解 + SVG/Leaflet 分层渲染 | 已有大量明确方位 / 距离描写的书 |
| 证据化地图规范     | `web-novel-structre-`              | 人工 / 模型抽取 + 证据 ID | M0–M4 分级 + 轻量 SVG       | 契约先行、强调可溯源的项目     |
| 图片底图 + 手动打点 | Projekt Kraken                     | 用户上传地图图片          | 图片 + 标记 / 路径 / 区域 / 轨迹  | 有官方地图、手绘图或作者亲自校准  |
| 程序化世界生成     | Azgaar FMG / civ-atlas / mapwright | 高度图、Voronoi、模拟    | 单元格地图 + 多图层             | 从零生成新世界，不是拆解已有小说  |

这四条路不是互斥的。成熟产品通常是 “文本抽取 / 人工标注提供语义，程序化或图片提供底图，渲染层只负责显示”。



***

## 2. AI Reader V2：把地图 “解” 出来

### 2.1 数据从文本关系来

AI Reader V2 不只抽地点名，还抽 `SpatialRelationship`：



* `direction`：`north_of` / `south_of` / `east_of` / `west_of` / 四向斜角；

* `distance`：路程、日程、里数，另有 `distance_class`（near / medium / far / very\_far）；

* `contains` / `located_in`：包含与位于；

* `adjacent` / `separated_by`：相邻、相隔；

* `in_between`：A 在 B 与 C 之间；

* `travel_path`：带 `waypoints` 的旅行路径；

* `cluster`、`terrain`、`relative_scale` 等旧类型。

每条关系带 `confidence`、`narrative_evidence`、`confidence_score` 和章节证据；层级关系与拓扑关系分开归类，层级树只消费 `contains/located_in`，不会把 “相邻” 误当成 “包含”。这是整个地图的地基。

### 2.2 布局是约束求解，不是随手力导向

`map_layout_service.py` 里的 `ConstraintSolver` 做了几件事：



* 以力导向布局生成初始种子；

* 把方向、距离、包含、相邻、相隔、居中、旅行路径、聚类等写成能量项；

* 用差分进化（`differential_evolution`）在画布边界内求解；

* 约束不足 3 条、或求解失败时，回退到层级树布局；

* 支持用户手动锁定位置，锁定点作为强边界；

* 地点多时分批求解，前一批锁定的位置作为后一批的锚点。

这不是 “画得好看” 的布局，而是 “尽量满足文本约束” 的布局。它也解释了为什么同样叫地图，有的只是关系图，有的能表达 “青云宗在七玄门东南三百里”。

### 2.3 求解之后还有语义审计

`map_plausibility.py` 是只读审计，检查五类问题：



1. 地名自带方位（东 / 南 / 西 / 北 + 洲 / 海 / 洋 / 岛）是否落在画布对应区域；

2. 同一父级、同一层级的兄弟地点是否挤成一团；

3. 高置信度 `contains` 的父子是否相距过远；

4. 明确的方向约束最终是否被违反；

5. 海域是否被放到了陆地上。

这份代码的注释记录了一个很有说服力的失败案例：《西游记》地图曾把东胜神洲、南赡部洲、北俱芦洲挤在 54–75px 内，北俱芦洲零约束，大唐国离长安 3000px。也就是说，**没有语义审计的自动地图，会非常自信地画错。**

### 2.4 渲染与回退说明



* 真实地理模式用 Leaflet + GeoNames；

* 幻想 / 多层世界用 D3 + SVG，分层图、程序化地形、河流、大陆架、人物轨迹；

* 接口返回 `layout_mode`、`layout_reason`、`geo_coverage`；

* 前端提供 “自动 / 地理 / 层级” 切换，回退时明确说明原因，不静默换图。

`layout_reason` 这个字段很关键：地图不仅要能画，还要能解释 “为什么这样画”。

### 2.5 值得学与不该照搬

值得学：



* 空间关系独立成表，带证据与置信度；

* 约束求解 + 层级回退 + 人工锁定；

* 语义审计，不只看布局能量；

* `layout_reason` / `geo_coverage` 这类可解释字段；

* 真实地理与幻想分层两种模式分开。

不该照搬：



* 地图模块体量很大：`map_layout_service.py` 约 5300 行，前端地图组件十余万字节；

* 依赖差分进化、NumPy/SciPy、Pillow、Leaflet/GeoNames 等；

* 地形由噪声生成，地点类型只做偏置，不是文本证据；

* 项目是 AGPL-3.0，代码复用会带来 copyleft 义务。

**结论：把它当算法与质量审计的参考，不要当代码模板。**



***

## 3. `web-novel-structre-`：地图成熟度分级

这个公开仓库和本项目的定位最接近：也是 “证据化拆书”，也处理地点、势力、路线、章节和冲突。它的地图规范比实现更值得学。

### 3.1 M0–M4



| 等级 | 名称    | 允许表达什么              | 不允许做什么           |
| -- | ----- | ------------------- | ---------------- |
| M0 | 地点索引  | 地点名、出现章节、父级未知       | 不生成坐标图           |
| M1 | 拓扑图   | 包含、相邻、可达、传送         | 坐标只用于避让，不表达方位和距离 |
| M2 | 二维方位图 | 东南西北、边界、道路、局部坐标、区域  | 不把自动布局回写成事实坐标    |
| M3 | 多层地图  | 位面、上下界、星域、楼层、父地图下钻  | z 轴没有叙事依据就不上 3D  |
| M4 | 时态地图  | 地点状态、国界、控制权、路线随章节变化 | 不用修改旧数据的方式隐藏变化   |

> 本项目落地口径（2026-11）：示意 2D 允许按 `places.parent` 包含关系随机/自动摆放；M1 的“坐标只用于避让”指不表达证据方位，不限制示意布局。随机坐标仍不写回 `places`，不作为证据。

它明确写了两句话：



* “地图不是美术设定图，也不是把出场地点随机摆放成漂亮画面。”

* “没有方向证据时省略 geometry，交给拓扑布局；不要把自动布局结果回写为事实坐标。”

这正好对应本项目现在的状态：`places.parent` 能表达包含，所以是 M1；没有方向 / 距离证据，所以不能进 M2。

### 3.2 数据分层

它不把所有对象塞进一个 `nodes` 列表，而是分成：



* `layers`：世界、位面、星域、楼层；

* `places`：有空间身份的地点；

* `spatial_relations`：道路、河流、边界、可达、传送；

* `overlays.faction_areas`：控制 / 声明 / 争夺区域；

* `overlays.routes`：人物路线，按 `steps` 记录顺序、章节、事件；

* `overlays.events`：事件位置；

* `overlays.chapters`：篇章覆盖；

* `timeline`：随章节发生的地图状态变化。

人物、势力、事件只存 ID 引用，不复制档案。这一点和本项目 “实体 / 关系 / 章节分离” 的思路一致。

### 3.3 坐标与置信度



* 坐标是 0–100 的示意坐标，不暗示真实经纬度；

* `coordinate_space: global | parent` 区分全局与父地图局部坐标；

* 置信度用 `F`（明确事实）、`I2`（强推断）、`I1`（弱推测）、`U`（未知）、`C`（冲突）；

* `I1/U` 用虚线或低透明度，`C` 用红色冲突标记；

* 自动布局节点额外画虚线圈，详情里写 “自动拓扑布局，不是地理事实”。

这套视觉语法比 “画得好不好看” 重要：读者一眼能看出哪些是证据、哪些是推测。

### 3.4 渲染



* 默认输出自包含 SVG 页面；

* 支持搜索、类型 / 世界层 / 比例层级 / 置信度筛选；

* 点、线、面、势力区域、人物路线、事件位置；

* 详情面板显示层级路径、证据 ID、置信度、坐标性质；

* 只有多层且 z 轴有叙事意义时才用 Three.js，同时保留 SVG。

实现很轻：`model.py` 519 行、`render_svg.py` 163 行、CLI 58 行，适合单文件交付。

### 3.5 许可证警告

这个仓库根目录没有 `LICENSE` 文件。公开可读不等于开源；按默认版权规则，不能直接复制代码。**只学它的规范与结构，不搬实现。**



***

## 4. Projekt Kraken：图片底图 + 手动标注 + 时间轴

Projekt Kraken 是 GPLv3 的桌面世界观工具，地图路线与 AI Reader 相反：



* 地图 = 用户上传的图片；

* 在图片上手动放置 marker、path、region；

* 支持人物 trajectory：带日期的地点、移动、停留、瞬移；

* 支持地图层级：父地图上的 footprint、旋转、缩放、局部子地图；

* 支持要素的存在时间、势力区域、图层组、栅格图层；

* 时间轴移动时，地图显示对应时间的地理状态。

它解决的是 “作者已经有一张地图，或者想亲手校准” 的场景。坐标是人工锚定的，不是从文本推出来的，所以不存在 “算法猜错” 的问题，但也不具备自动抽取能力。

值得学：



* 地图要素可以有 “存在时间”，不只是静态点；

* 人物路线应记录顺序、章节、事件，而不是一串地名；

* 子地图 / 局部地图用 footprint 挂到父地图，适合 “世界 → 大陆 → 宗门 → 山峰”；

* 手动锚点可以作为自动布局的修正层。

不适合直接搬：



* GPLv3，代码复用有 copyleft 义务；

* 桌面应用 + SQLite + Qt，和本项目的单文件 HTML 交付形态差异很大；

* 功能面很宽，学习成本高。

**结论：如果以后要支持 “上传官方地图打点”，它是 UX 和时空模型的最佳参考。**



***

## 5. 程序化地图：Azgaar、civ-atlas、mapwright

### 5.1 Azgaar Fantasy Map Generator

Azgaar 的核心不是 “画图”，而是 “先生成一个世界状态，再渲染”：



* `PackedGraph` 用并行数组存 Voronoi 单元格：拓扑、邻接、顶点、多边形、高度、地形、河流、特征、人口、文化、生物群系、国家、省、宗教等；

* 另有实体数组：河流、地貌、城镇、国家、文化、路线、宗教、区域、标记、事件、冰层等；

* 生成器负责高度图、侵蚀、河流、气候、生物群系、文化、国家、城镇、路线；

* 渲染器是独立层，`layers.ts` 用注册表管理图层顺序、显隐、持久 ID、draw/erase；

* 导出支持 PNG/SVG/JSON，GIS 导出可把 cells/routes/rivers/markers/zones 写成 GeoJSON；

* 官方架构说明明确分成 world data /generators/editors /renderers，数据层不写逻辑和渲染。

值得学：



* 数据与渲染彻底分离；

* 图层注册表：顺序、显隐、持久 ID、绘制 / 擦除成对；

* 单元格数据 + 实体数据分开；

* 导出不是截图，而是从世界状态重新生成。

不适合本项目：



* 它是 “生成新世界”，不是 “还原已有小说”；

* Voronoi + 地形 + 气候 + 国家模拟是另一条产品线；

* TypeScript 代码库很大，MVP 不需要。

许可证是 MIT，代码可以复用（需保留版权声明），但没必要为了一个地图视图搬整套引擎。

### 5.2 civ-atlas（文明与地图）

中文项目，浏览器内生成星球并推演历史：



* 球面泊松圆盘采样 + 球面 Delaunay，默认约 3.6 万个不规则地块；

* 板块、侵蚀、河流、气候、洋流、生物群系、民族、国家、战争、王朝；

* 地图与文明分离：先做地图，再换文明种子；

* 数据与画风 / 投影分离，切换底图不重新生成；

* 手绘、卫星、地理图、白模、数据图层、多种投影、3D 地球仪；

* AGPL-3.0。

它证明了一件事：**真正好用的 “世界地图” 背后是一个世界模拟器，而不是一个绘图函数。** 这也反过来说明，给一本已有小说做地图，不应该从零模拟一个世界。

### 5.3 mapwright

纯 Python + NumPy 的程序化奇幻地图库：



* Voronoi 地形、水力侵蚀、生物群系、河流、Markov 地名、阴影浮雕 SVG；

* 输出中性数据（cells、biomes、rivers、polygons）和自包含 SVG；

* MIT；纯 Python、仅依赖 NumPy、种子确定；用 “中性数据 + 可换主题渲染” 解耦地形和应用模型。

如果以后真要做 “程序化装饰地形”，它比直接搬 Azgaar 更适合 Python 后端。但它仍然不能提供文本证据，只能提供底图。



***

## 6. 对本项目的判断

### 6.1 现在是什么等级

`places` 当前字段：



```
{ "id": "p_qingyunzong", "name": "青云宗", "parent": null,
  "desc": "……", "first_ch": 1, "attrs": { "所属": "东域" } }
```



* 有 `parent`：能表达 “谁包含谁”，所以不是 M0；

* 没有方位、距离、道路、边界、坐标：不能表达 “在东边多远”，所以不是 M2；

* 结论：**M1，拓扑层级**。

《凡人修仙传》样例有 38 个地点，足以画一张层级关系图，但不足以画一张地理地图。若直接画成 “大陆 + 国家 + 山脉 + 河流”，地形和方位全是编的。

### 6.2 四种可选档位



| 方案             | 数据要求                | 交付形态                       | 风险               | 建议         |
| -------------- | ------------------- | -------------------------- | ---------------- | ---------- |
| A. M1 地点关系图    | 现有 `parent` 即可      | 地点志内切换 “层级 / 关系图”          | 低；但只是关系图，不是地图    | **先做**     |
| B. M2 证据化示意地图  | 明确方向 / 距离 / 道路 / 边界 | 独立 SVG 地图，带置信度样式           | 中；需要改 schema 和抽取 | **数据够了再做** |
| C. 图片底图 + 手动打点 | 用户提供地图图片            | 图片上打点、路径、区域                | 中；需要资源内联和编辑器     | 有官方图时做     |
| D. 真实地理模式      | 真实地名 / 坐标           | Leaflet/MapLibre + GeoJSON | 高；只适合现实题材        | 暂不做        |

### 6.3 推荐的最小实现

**第一步：M1 地点关系图**



* 不改 `places` 的语义，只从 `parent` 生成父子边；

* 用树形 / 径向布局，节点按阶段或势力着色，大小按出现频次 / 子节点数；

* 边上不写 “东 / 南 / 西 / 北”，不画比例尺、指北针、山脉、河流；

* 详情面板继续用现有地点详情，增加 “父级路径” 和 “子地点”；

* 明确标注 “层级关系图；位置仅用于避让，不代表原文方位”。

这一步的价值不是 “好看”，而是让 38 个地点的归属和层级一眼可读，且不引入任何虚假地理。

**第二步：M2 证据化示意地图**

只有在抽取能稳定产出下列字段后才做：



```
"spatial_relations": [
  {
    "id": "sr_qingyun_qixuan",
    "s": "p_qingyunzong",
    "t": "p_qixuanmen",
    "kind": "direction",          // direction | distance | adjacent | road | river | portal | travel_path | separated_by | in_between
    "value": "southeast_of",      // 或 "三百里"、"三天路程"
    "confidence": "high",         // high | medium | low
    "first_ch": 12,
    "evidence": "ch12:p3",
    "note": "原文：青云宗位于七玄门东南三百里"
  }
]
```

要点：



* `s` / `t` 用现有实体 ID，不复制名字；

* 只记录原文明确说出的关系；地名带 “东 / 南 / 西 / 北” 只能算弱先验，不能自动当事实；

* `confidence` 和 `evidence` 必填；

* 关系类型不够时宁可 `low`，不要编；

* 布局结果不写回 `places`，单独作为构建产物：



```
"map_layout": {
  "mode": "constraint",           // constraint | hierarchy | manual
  "reason": "12 条方向约束，3 条距离约束",
  "canvas": [1000, 700],
  "nodes": [{ "id": "p_qingyunzong", "x": 620, "y": 310 }],
  "satisfaction": { "direction": "10/12", "containment": "8/8" }
}
```

渲染规则：



* `high` 实线，`medium` 虚线，`low` 点线 / 低透明度；

* 冲突用红色标记，不静默选一个；

* 没有方向证据的节点放 “方位未知” 区，不硬塞进四个象限；

* 没有 `spatial_relations` 时自动回退 M1，并显示原因；

* 地图上的每个点都能点回现有地点详情和证据。

**第三步：可选图片底图**

如果用户有官方地图 / 手绘图：



```
"map": {
  "mode": "image",
  "image": "maps/world.webp",
  "width": 2000,
  "height": 1400,
  "placements": [
    { "place": "p_qingyunzong", "x": 0.62, "y": 0.31, "source": "manual" }
  ]
}
```

`placements` 是人工标注，不是文本抽取；要和 `spatial_relations` 分开。图片可以内联进单文件 HTML，也可以作为同目录资源；前者便于分享，后者便于大图。

**暂不做：真实地理模式**

除非题材是都市 / 历史 / 现实向，且地名能可靠映射到真实坐标。幻想世界用 Leaflet/OSM 只会得到 “看起来像地图” 的假精度。若以后要做，也应该作为可选插件，不进入核心契约。

### 6.4 质量门禁

无论做哪一档，至少检查：



* `spatial_relations` 两端 ID 存在；

* `parent` 无环（已有校验）；

* `contains` 的子节点在父节点半径内；

* 同父同层节点不重叠、不过度拥挤；

* 方向约束满足率可计算、可显示；

* 每个自动布局节点带 `layout_kind=auto`，详情里写明 “不是地理事实”；

* 计算出的 `x/y` 不写回 `places`；

* M0/M1 不画指北针、比例尺、经纬网；

* 筛选后，详情面板不残留已隐藏节点；

* 导出 SVG/PNG 与屏幕显示一致。

### 6.5 UI 落点

不建议一上来加第八个顶级视图。更稳妥的做法：



* 在 “地点志” 标题栏加一个 `层级 / 关系图` 切换；

* 关系图用现有 SVG/Canvas 技术栈，不引入 D3；

* 节点点击复用现有地点详情；

* 顶部筛选：阶段、势力、地点类型、置信度；

* 底部图例：实线 = 明确，虚线 = 推断，点线 = 未知，红色 = 冲突；

* 右侧或底部显示 “布局原因 / 约束满足率 / 未定位地点数”。

等 M2 数据稳定后，再考虑升级为独立 “地图” 视图；M3 多层（人界 / 仙界 / 灵界）和 M4 时态（按章节切片）再往后排。



***

## 7. 许可证核对



| 项目                    | 许可证             | 能否复用代码      | 备注                            |
| --------------------- | --------------- | ----------- | ----------------------------- |
| AI Reader V2          | AGPL-3.0        | 不建议         | 复用后整体需按 AGPL 分发；与保持 MIT 许可不兼容 |
| `web-novel-structre-` | 仓库无 LICENSE     | 不能          | 公开可读≠开源；只学规范                  |
| Projekt Kraken        | GPLv3           | 不建议         | copyleft；桌面 Qt 架构也不匹配         |
| Azgaar FMG            | MIT             | 可以（保留声明）    | 但代码体量大，没必要整套搬                 |
| civ-atlas             | AGPL-3.0        | 不建议         | 世界模拟器，不是拆书工具                  |
| mapwright             | MIT             | 可以（保留声明）    | Python + NumPy，适合可选地形生成       |
| Kanka                 | Commons Clause  | 不可销售 / 复用受限 | source-available，不是 OSI 开源    |
| Chronicler            | PolyForm Shield | 商用 / 再分发受限  | source-available，不是 OSI 开源    |

对本项目最安全的做法：**学思路、重写实现、保留来源说明。** 只有 Azgaar /mapwright 这类 MIT 代码可以在明确署名后复用。



***

## 8. 建议的提交拆分

如果后续实现，按主题提交，不按文件数量拆：



1. `docs(map): 调研开源小说地图方案`（本文件）

2. `feat(schema): 增加可选空间关系与地图元数据`

3. `feat(map): 增加 M1 地点关系图`

4. `feat(map): 支持证据化示意布局与手动锚点`

每个提交都能独立解释、独立回滚，避免 “一个文件一个 commit”。



***

## 9. 参考来源



* AI Reader V2：[https://github.com/mouseart2025/AI-Reader-V2](https://github.com/mouseart2025/AI-Reader-V2)


  * 地图说明：`README.md`

  * 空间关系模型：`backend/src/models/chapter_fact.py`

  * 约束求解与地形：`backend/src/services/map_layout_service.py`

  * 语义审计：`backend/src/services/map_plausibility.py`

  * 地图接口：`backend/src/api/routes/map.py`

* `web-novel-structre-`：[https://github.com/jackiechou1/web-novel-structre-](https://github.com/jackiechou1/web-novel-structre-)


  * 地图规范：`references/map-model.md`

  * 数据契约：`references/world-map.schema.json`

  * 轻量渲染：`scripts/maplib/model.py`、`scripts/maplib/render_svg.py`

* Projekt Kraken：[https://github.com/cmintert/ProjektKraken](https://github.com/cmintert/ProjektKraken)


  * 地图文档：`docs/user/maps.md`

  * 项目说明：`README.md`

* Azgaar Fantasy Map Generator：[https://github.com/Azgaar/Fantasy-Map-Generator](https://github.com/Azgaar/Fantasy-Map-Generator)


  * 架构说明：`README.md`

  * 数据模型：`src/types/packed-graph.ts`

  * 图层注册表：`src/renderers/layers.ts`

  * GIS 导出：[https://github.com/Azgaar/Fantasy-Map-Generator/wiki/GIS-data-export](https://github.com/Azgaar/Fantasy-Map-Generator/wiki/GIS-data-export)

* civ-atlas：[https://github.com/guaner-334/civ-atlas](https://github.com/guaner-334/civ-atlas)

* mapwright：[https://pypi.org/project/mapwright/](https://pypi.org/project/mapwright/)

* Kanka 地图标记：[https://docs.kanka.io/en/latest/entries/maps/markers.html](https://docs.kanka.io/en/latest/entries/maps/markers.html)

* Kanka 许可证：[https://github.com/owlchester/kanka/blob/main/LICENSE](https://github.com/owlchester/kanka/blob/main/LICENSE)