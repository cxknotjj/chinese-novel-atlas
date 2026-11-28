---
name: atlas-map
description: "把小说地图作为结构化数据渲染成网页，而不是生成一张固定图片。使用 atlas-kit 的 21 件手绘 PNG 景物层与 9 件代码/SVG 变量层，产出可缩放、可切层、可点击的浅绛淡彩水墨地图；支持多本小说共用同一套底件。适用于给小说做地图、给 data.json 补 map_layout、把地图接入 atlas.html、修改地图视觉与标签层级、排查地图渲染问题。触发词：小说地图、生成地图、地图渲染、地图视图、map_layout、atlas-map、世界地图、势力地图、把地图接入网页、给这本书做地图、world map、novel atlas map。"
---

> **本 skill 需要一份完整仓库**：地图渲染依赖 `atlas-kit/` 的 21 件手绘素材（约 20MB），
> 没法随 skill 一起分发。所以它和其余五个 skill 不同——脚本只负责编排，
> 真正的地图资源在**项目根**里。
> ```bash
> git clone https://github.com/cxknotjj/chinese-novel-atlas.git
> ```
> 下文 `<SKILL_DIR>` 指本 skill 的安装目录（含 `SKILL.md` 的那一层），
> `--project-root` 指上面 clone 下来的仓库根。产出路径相对当前工作目录。

# atlas-map · 小说地图渲染

地图是**数据 + 渲染器 + 一套共用底件**，不是一张提前画好的图。不要用像素生成模型“画”地图；要改的是 `data.json` 里的 `map_layout`，再由 `template/viewer/50-map-model.js` 与 `60-map-surface.js` / `65-map-overlays.js` / `68-map-scene.js` 的 atlas 渲染段画出来。

## 先定位项目根

项目根必须同时包含：

```text
atlas-kit/manifest.json
scripts/build.py
template/viewer.js
template/viewer/
```

默认从当前目录向上找；也可以显式传：

```powershell
python "<SKILL_DIR>\scripts\atlas_map.py" info --project-root "<项目根>"
```

`SKILL_DIR` 是本 skill 所在目录。项目根不是本 skill 目录；不要在里面找 `atlas-kit`。

## 地图的三层结构

| 层 | 内容 | 谁负责 |
|---|---|---|
| 世界数据 | `map_layout.regions / nodes / terrain / routes / atlas` | 写 `data.json` |
| 共用底件 | 21 件手绘 PNG（地形 7 / 水 4 / 建筑 6 / 植被 4）+ 纸底 / 海纹 | `atlas-kit/` |
| 变量渲染 | 路线、标记、题签、印章、罗盘、海面、标签避让、缩放 LOD | `template/viewer.js` 的 atlas 段 |

21 件 PNG 只作为 `stamps` 摆放，不是整张底图。9 件变量组件全部由 Canvas 画：航线/道路 2 类、题签/印章/罗盘 3 类、地点标记 4 类。**不要把地名、题签、印章、路线文字烘焙进图片。**

## 工作流

### 1. 先读世界数据

读 `data.json` 的 `places` 与 `spatial_relations`，再决定地图层级：

- `places` 是节点来源；每个 `map_layout.nodes[].place` 必须存在。
- `spatial_relations` 只能作为“原文有方位/距离证据”的依据，不能反推精确经纬度。
- 坐标是 0–100 归一化画布上的**叙事示意位置**，不是地理坐标，也不是原文精确方位。
- 没有证据时不要编方向、距离或坐标；题签免责声明写“示意舆图 · 方位与比例非精确”。

### 2. 写 `map_layout`

最小结构：

```json
{
  "mode": "schematic",
  "canvas": [100, 100],
  "note": "示意坐标、非经纬度、叙事导航用；0–100 归一化画布，原点左上，不代表原文精确方位",
  "regions": [],
  "nodes": [],
  "terrain": {},
  "routes": [],
  "atlas": {}
}
```

顺序建议：

1. **区域**：先画 1–3 个 `shape` 为 `land / sea / void` 的区域；每个区域给 `polygon`、`label_at`、`layer`。海域和秘境要成为明显主体；陆地不要只画一个带粗边的多边形。
2. **节点**：按叙事重要性给 `rank: 1/2/3`；`label: false` 用于纯装饰或不想出字的地点。`layer` 指向一个可见的层节点（通常是区域入口）。
3. **地形**：`terrain.ridges / rivers / lakes / islets` 只做水洗与氛围，不承担精确地理。`islets` 必须是 `{x,y,r}` 对象，不能写成数组。
4. **路线**：`routes[].s/t` 必须是 `places` id；`kind` 只能是 `portal / travel_path / road / river`；`curve` 是 0–100 的控制点，渲染时平滑，不表示可测量距离。
5. **atlas**：题签、印章、罗盘、免责声明、标记类型、stamps、配色。

详细字段、21 个资产 id、`stamps` 规则见 [references/web-contract.md](references/web-contract.md)。

### 2.5 地图成熟度 M0–M4

地图等级表示**证据能力**，不是视觉好坏。先跑：

```powershell
python "<SKILL_DIR>\scripts\atlas_map.py" --project-root "<项目根>" levels --data output/青云签到三十年/data.json
```

| 等级 | 条件 | 渲染行为 |
|---|---|---|
| **M0** | 没有地点，或只有地点索引、没有坐标/层级 | 只给地点列表；不画假地图 |
| **M1** | `places.parent` 拓扑 或 有 `map_layout` 但方向/距离证据 <3 | 拓扑/示意图；必须标注“节点位置仅用于避让/叙事导航” |
| **M2** | 某一根层有 ≥3 条 `direction` / `distance` 证据 | 证据方位；不足 3 条自动回退 M1 |
| **M3** | ≥2 个显式 `layer`（位面/父地图下钻/星域） | 多层地图；层筛选，不把不同层硬塞进一张平面 |
| **M4** | `map_layout.time_slices` 非空且切片带章号 | 时态地图；读者版按 cutoff 隐藏未来切片 |

规则：

- 没有数据就不升级：不要为了“看起来高级”硬造 z 轴、时间切片或方向证据。
- M2 的约束数按根层统计；同一对地点的重复描述去重后计数。
- 每个层要在选择器里显示 `· M2` 之类等级；全局等级写在页脚/免责条。
- `time_slices` 字段契约见 `references/schema.md` 的「time_slices（时态地图）」。
- 示意坐标永远不写回 `places`，不显示比例尺/经纬网/指北针。

### 3. 摆放景物

只从 21 个 id 里选：


- 山体：`terrain_peak_01/02`、`terrain_ridge_01/02`、`terrain_far_01/02`、`terrain_slope_01`
- 水：`water_cloud_01/02`、`water_bank_01/02`
- 建筑：`arch_sect_gate_01`、`arch_city_wall_01`、`arch_pass_01`、`arch_cave_01`、`arch_village_01`、`arch_dock_01`
- 植被：`veg_pine_01`、`veg_bamboo_01`、`veg_reeds_01`、`veg_dead_tree_01`

摆放规则：

- 建筑优先 `attach` 到地点节点，`markerOffset` 控制与标记的距离；节点被层筛选隐藏时，建筑自动不画。
- 山体/云雾/植被用 `x/y` 自由摆放，`w` 是画布宽度百分比；山不要大到压住全部节点。
- 海面默认 `seaTexture: false`，由代码画渐变、椭圆水彩斑、横向波纹和模糊海岸；只有确实需要纹理时才开 `water_sea_01`。
- 陆地区域只保留极淡暖色水洗，不画明显多边形边界；海/虚空才是主体。
- 题签 `seal.x/y` 省略时自动落在题签正下方；不要手写一个会压住末字的坐标。

视觉与验收规则见 [references/style-and-qa.md](references/style-and-qa.md)。

### 4. 审计

```powershell
python "<SKILL_DIR>\scripts\atlas_map.py" audit --project-root "<项目根>" --data "samples\fictional\data.json"
```

审计会检查：

- `mode/canvas/note`
- 区域、节点、地形、路线引用
- `atlas.markers` 类型
- `atlas.stamps.asset` 是否属于 21 件
- `attach` 是否有对应节点
- 题签/印章/罗盘/免责声明的必填项

有 `x` 错误就停下来修数据，不要先构建。审计通过后再跑项目全量校验：

```powershell
python scripts\validate.py samples\fictional\data.json
```

### 4.5 网页编排器 / 发布

`template/viewer.html` 的地图页内置轻量编排器：

1. 切到「示意 2D」，点工具栏「编排」进入编辑；点节点选中，拖拽改 `x/y`。
2. 选中节点后，下方检查器可改 `layer`、从 21 件底件里选一件 `attach` 到该节点，或移除该节点的底件。
3. 「导出」下载 `<书名>-map-layout.json`，包含节点、区域、路线、地形、atlas、time_slices。这是示意坐标，不是证据坐标；合并回 `data.json` 前先跑 `atlas_map.py audit`。
4. 「PNG / SVG」导出当前视图；SVG 当前是位图封装，不是矢量重绘。
5. M3 用层筛选下钻；M4 数据出现 `时间切片` 下拉（全部 / 第 N 章），选中后按切片过滤。读者版地图受 `cutoff_ch` 约束，未来层/节点/路线/切片不画。

**发布边界**：地图 PNG/SVG 是传播物；`map_layout` 仍是唯一可编辑源。不要把导出图当数据源反向 OCR。

### 5. 构建页面


```powershell
python "<SKILL_DIR>\scripts\atlas_map.py" build `
  --project-root "<项目根>" `
  --data "samples\fictional\data.json" `
  --out "demo" `
  --name "index.html"
```

`build` 会自动：审计 → 需要时把 21 件 PNG 转成网页 webp → 调 `scripts/build.py` 内联页面。正式书页把 `--out` 换成书目录、`--name` 换成 `atlas.html`：

```powershell
python "<SKILL_DIR>\scripts\atlas_map.py" build `
  --project-root "<项目根>" `
  --data "output\凡人修仙传\data.json" `
  --out "output\凡人修仙传" `
  --name "atlas.html"
```

数据很大或要反复改时加 `--external`，页面只引用同目录 `data.js`，不把数据塞进 HTML。

### 6. 浏览器验收

至少看四种画面：

1. 1440×900 默认全图
2. 1920×1080 默认全图
3. 390×844 移动端
4. 切到每个 `layer` 的单层视图

再检查：

- 100% 复位能回到 fit，不是回到 `k=1`
- 桌面右键拖拽、移动端单指拖拽都能平移；百分比读数随缩放变化
- 1.25× 时 rank2 开始出现
- 1.95× 时只剩中心附近标签，且无重叠
- 题签/印章/罗盘/免责声明不压地图内容
- 建筑不会因为层切换掉到画布中心
- 控制台无 JS 报错

## 不要做

- 不要用图片生成模型产出一张“看起来像地图”的 PNG 当交付；文字、路线、标记会不可维护。
- 不要把某一本小说的专名写进渲染代码或底件；多本书共用同一套 21 件 + 9 类变量。
- 不要为了填满画面编造原文没有的地点、方位、距离或海岸线。
- 不要把 `spatial_relations` 的方向/距离直接换算成像素；示意图不承担测量。
- 不要在 `template/viewer/` 里硬编码“越国/乱星海/虚天殿/黄枫谷”；这类内容只放在 `data.json` 和 `titleByLayer`。

## 常见故障

先看 [references/troubleshooting.md](references/troubleshooting.md)。最常见的三个：

- **层切换后建筑全跑到画布中心**：`attach` 的节点被当前层过滤了，或 `attach` 根本不是节点。给 stamp 加正确的 `layer`，并确认 attach 的 place 有 `map_layout.nodes`。
- **1920 题签末字被印章压住**：不要给 `seal` 写固定 `x/y`，省略后让它自动落在题签下方；同时把 `title.size` 控制在 `≤0.053`。
- **海面出现贴图接缝**：先关 `seaTexture`，用代码海面；只有确实需要纹理时才开，且确保 `water_sea_01` 走 cover 绘制而不是普通 draw。

## 资源

- 契约与字段：[references/web-contract.md](references/web-contract.md)
- 视觉、构图、验收：[references/style-and-qa.md](references/style-and-qa.md)
- 故障排查：[references/troubleshooting.md](references/troubleshooting.md)
- 命令行：[scripts/atlas_map.py](scripts/atlas_map.py)
