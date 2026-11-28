# 网页地图契约

`data.json` 顶层的 `map_layout` 是地图唯一的数据源。网页只读这一块，不读图片里的文字。

## 顶层

| 字段 | 类型 | 规则 |
|---|---|---|
| `mode` | string | 固定 `"schematic"` |
| `canvas` | `[100,100]` | 固定 0–100 归一化画布，原点左上 |
| `note` | string | ≤120 字，必须含“示意/非经纬度/叙事导航”之一 |
| `regions` | array | 地图的大色块，1–3 个 |
| `nodes` | array | 地点节点，必须有真实 `places` id |
| `terrain` | object | 山脊、河流、湖泊、小岛 |
| `routes` | array | 路线/航路/传送门 |
| `atlas` | object | 题签、印章、标记、景物、配色 |

## regions

```json
{
  "id": "r_yueguo",
  "name": "越国",
  "label": "越国",
  "shape": "land",
  "layer": "p_yueguo",
  "label_at": [18, 68],
  "polygon": [[5,8],[62,10],[66,34],[62,56],[8,76]]
}
```

- `shape`：`land` / `sea` / `void`。`sea` 与 `void` 是明显主体；`land` 只做极淡水洗，不画粗边。
- `layer`：点击层切换后，这个区域只在对应层显示；可为 `null`（全层显示）。
- `polygon`：≥3 个 `[x,y]`，0–100。
- `label_at`：区域名的放置点，不要和节点标记挤在一起。

## nodes

```json
{ "place": "p_qingyunshan", "x": 31, "y": 31, "layer": "p_dongyu", "rank": 1, "label": true }
```

- `place`：必须出现在 `data.places`，且一个 place 只出现一次。
- `rank`：`1` 始终显示标签；`2` 在约 1.25× 以上出现；`3` 更深。
- `label: false`：不显示文字，但仍画标记；适合纯装饰节点。
- `layer`：该节点属于哪个层；层过滤时节点和 attach 建筑一起隐藏。

## terrain

| 字段 | 形状 |
|---|---|
| `ridges` | `{points:[[x,y]...], width, region, name}` |
| `rivers` | 同上，`width` 是线宽 |
| `lakes` | `{polygon:[[x,y]...], region}` |
| `islets` | **必须是对象** `{x,y,r}`，不能写成 `[x,y,r]` 数组 |

`terrain` 只表达氛围和叙事方位，不是精确地形测绘。

## routes

```json
{ "s": "p_jishiji", "t": "p_qingyunshan", "kind": "travel_path", "curve": [[21,48],[24,43],[28,38]], "label": "山路" }
```

- `s` / `t`：必须是 `places` id。
- `kind`：`portal` / `travel_path` / `road` / `river`。
- `curve`：可选控制点，渲染时 Catmull-Rom 平滑；不表示可测量距离。

## atlas

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | object | `{text,x,y,size,direction:"vertical" 或 "horizontal",sealCh}` |
| `seal` | object | `{ch,x,y,size,angle}`；`ch` 必须单字；省略 `x/y` 自动落在题签下方 |
| `compass` | object/false | `{x,y,size,opacity}`；`false` 关闭 |
| `disclaimer` | object | `{text,x,y}`；建议“示意舆图 · 方位与比例非精确” |
| `markers` | object | `{place_id: "city" / "sect" / "secret" / "danger" / "place" / "none"}` |
| `titleByLayer` | object | `{layer_id: {text,sealCh,...}}`；切层时替换题签 |
| `stamps` | array | 21 件 PNG 的摆放 |
| `seaTexture` | bool | 默认 `false`，代码画海面；`true` 叠 `water_sea_01` 纹理 |
| `terrainStamps` | bool | 默认山脊用 `terrain_ridge_01/02` PNG；`false` 回退代码墨线 |
| `palette` | object | 可覆盖颜色 token |

`titleByLayer` 的 key 必须是当前 `regions[].layer` 或 `nodes[].layer` 的真实层 id。切到 `p_luanxinghai` 时题签可以变成“乱星海舆图 / 乱”。

## stamps

```json
{ "asset": "arch_sect_gate_01", "attach": "p_qingyunshan", "w": 8.4, "opacity": 0.86, "markerOffset": 3.0 }
```

| 字段 | 规则 |
|---|---|
| `asset` | 必须是 21 件 PNG 之一 |
| `attach` | 可选；有则跟随节点；节点必须存在且有 `nodes` 项 |
| `x` / `y` | 无 `attach` 时必填，0–100 |
| `w` | 画布宽度百分比，默认按类型 6–14 |
| `opacity` | 0–1，默认 0.86 |
| `rotation` | 角度（度），正值为顺时针 |
| `flip` | 布尔，水平翻转 |
| `anchor` | `"center"` 用中心；否则用资产 pivot（默认 `[0.5,0.875]`） |
| `markerOffset` | 建筑类 stamp 把节点标记往下推的距离，避免建筑压住标记 |
| `order` | 绘制顺序，小的先画 |
| `offsetY` | 仅 `attach` 时有效，相对节点的纵向偏移 |
| `layer` | 无 `attach` 时按层过滤；有 `attach` 时以节点层为准 |

**隐藏层规则**：节点被当前层过滤时，`attach` 的 stamp 直接不画，绝不落到画布中心。

## 21 个网页资产 id

地形 7：`terrain_far_01`、`terrain_far_02`、`terrain_peak_01`、`terrain_peak_02`、`terrain_ridge_01`、`terrain_ridge_02`、`terrain_slope_01`

水 4：`water_cloud_01`、`water_cloud_02`、`water_bank_01`、`water_bank_02`

建筑 6：`arch_sect_gate_01`、`arch_city_wall_01`、`arch_pass_01`、`arch_cave_01`、`arch_village_01`、`arch_dock_01`

植被 4：`veg_pine_01`、`veg_bamboo_01`、`veg_reeds_01`、`veg_dead_tree_01`

支持资产：`ui_paper_ornate`（纸底）、`water_sea_01`（可选海纹）。构建实际内联 23 张：21 + 纸底 + 海纹。

## 颜色 token

| token | 默认 |
|---|---|
| `ink` | `#3B332A` |
| `accent` | `#A66A45` |
| `seal` | `#A93828` |
| `paper` | `#E8DCC5` |
| `water` | `#6E8E96` |
| `route` | `#8A7254` |

## 示意 2D 的摆放边界

- `map_layout` 只表达 `places.parent` 的包含关系；原文没写方位时，节点可以随机/自动摆放，不必留空。
- 随机摆放必须做碰撞避让，不得压住建筑 stamp、题签或其他节点标签；同一份数据用固定种子，避免刷新跳位。
- 随机坐标不是原文方位证据：不写回 `places`，不显示比例尺/经纬网，罗盘只作装饰。

## 不要写进数据的东西

- 固定题签字样、固定印章字、固定路线文字：这些必须来自 `atlas.title` / `atlas.seal` / `routes[].label`。
- 某一本小说的专名：只放世界数据，不放 `viewer.js`。
- 精确经纬度、真实比例尺、真实海岸线：示意地图不承担这些。
