# 故障排查

## 建筑跑到画布中心

`attach` 的 place 必须同时满足：

1. 出现在 `data.places`
2. 有 `map_layout.nodes` 项
3. 当前层未被过滤

三者任一不满足，渲染器会直接不画，而不是落到 `(50,50)`。如果看到中心堆图，先检查 stamp 的 `layer` 和 attach 节点的 `layer` 是否一致。无 attach 的 stamp 用 `x/y`；有 attach 的 stamp 不要依赖默认坐标。

## 1920 题签末字被印章压住

- `atlas.seal` 不要写固定 `x/y`；省略后自动落在题签正下方。
- `title.size` 上限 `0.053`，超过就会在 1920 把末字顶到印章。
- 印章 `size` 不要跟着题签字号一起放大。
- 如果题签改成横排，重新看一次 1920，不要只看 1440。

## 海面有贴图接缝 / 岸边发脏

- 默认 `seaTexture: false`，用代码海面。
- 要开纹理时，`water_sea_01` 必须用 cover 绘制（`drawBoxCover`），不能给带 `x/y` 的 bbox 用 `drawCover`；`drawCover` 只适合画在 `(0,0)`。
- 海岸模糊和波纹是代码层；海纹只是叠加，不应替代海色。
- 海面太满时减少 `islets`，不是加更多山。

## 标签重叠 / 标签消失

- 先查区域 `label_at` 是否压在节点标记上；被压的区域标签会被整体丢弃。
- `atlas.markers` 为 `none` 的节点不应占标签保留框；否则会挤掉旁边 `青云山` 这类真标签。
- rank2/3 太多时，先减 `label: true` 的节点，不要只改字号。
- 标签越界会被剔除；把节点往内框挪，不要关掉安全区。

## 缩放异常 / 100% 复位不对

- 缩放上下限必须是相对 fit 的 `[0.35×fit, 6×fit]`，不能写死绝对 `6`。
- `100%` 按钮要回到 `fitKx/fitKy`，不能 `k=1; mapFit()`。
- 1.25× 看不到 rank2，先检查当前 `k` 是否真的到了 fit 的 1.25 倍，而不是绝对 1.25。

## 拖拽完全不动 / 触屏拖不动

- 拖拽必须绑定 Pointer Events（`pointerdown/move/up/cancel`），不能只绑 `mousedown/mousemove`；触屏和触控笔不会触发 mouse 事件。
- 桌面端右键拖拽平移（拦截 `contextmenu`）；移动端单指拖拽平移。浏览态拖节点起点也应平移，编辑态才拖节点。
- 画布 CSS 必须有 `touch-action: none;`，否则浏览器会把触屏手势当成页面滚动。
- 百分比不随缩放变化时，检查 `drawMap()` 开头是否调用 `syncMapZoomLabel()`，以及 `#mapZoomValue` 是否还带 `data-zoom="one"`。

## 层切换后题签没变

- `titleByLayer` 的 key 必须是真实层 id，不能写区域 id。
- 每个层 spec 至少给 `text`；`sealCh` 可选，没给会回退到全局 `seal.ch`。
- 切层后如果题签仍是全局书名，检查 `map2dLayer` 是否真的等于那个 key。

## 构建报“找不到占位图片”

- `template/assets/map/atlas/manifest.json` 缺资产，或 21 件 webp 没生成。
- 先跑：

```powershell
python "<SKILL_DIR>\scripts\atlas_map.py" prepare --project-root "<项目根>"
```

- 构建日志应显示内联 23 张；如果只有 21 张，检查纸底 `ui_paper_ornate.webp` 与海纹 `water_sea_01.webp`。

## 审计报 asset 不在 21 件

- `atlas.stamps[].asset` 必须是 `atlas-kit/manifest.json` 里 `media: png` 的 id。
- 不要写文件路径、不要写 `terrain_ridge`（少了序号）、不要写 `water_sea_01` 当普通 stamp；海纹走 `seaTexture`。
- 9 件代码/SVG 组件不是 stamp，不要塞进 `stamps`。

## 地图全空 / 只有一个色块

- 检查 `regions[].polygon` 是否 ≥3 点且都在 0–100。
- 检查 `nodes` 的 place 是否真的在 `places` 里。
- 检查 `atlas.title` 是否有 `text`，`atlas.seal.ch` 是否单字。
- 检查 `seaTexture` 是否误开导致海纹覆盖。

## 代码里出现书名专名

在 `template/viewer.js` 的 atlas 段搜“越国 / 乱星海 / 虚天殿 / 黄枫谷 / 人界舆图”。除势力版图示例数据外，地图段不应有这些硬编码；题签、印章、层名全部来自数据。
