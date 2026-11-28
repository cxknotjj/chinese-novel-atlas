# 东方国风地图通用底件库 v0.2

这不是一张“成图”，而是一套能跨多本小说拼装的地图积木：

- **21 件手绘 PNG**：地形、水、建筑、植被。负责笔触、纸纹和体积感。
- **9 件代码 / SVG**：路线、标记、罗盘、题签框、印章框。负责会随小说变化的文字、坐标、颜色和尺寸。
- **packs/**：5 套配色 token，换纸色、墨色、强调色，不重画构图。
- **worlds/**：每本小说只写地名、势力、坐标、题签文字。
- **render_map.py**：同一套底件 + 不同 `world.json`，输出不同小说地图，也能导出透明 SVG 叠加层。

当前两个示例世界：

- `preview/world-fanren-map.png`：《凡人修仙传》越国示意。
- `preview/world-test-map.png`：虚构《苍梧洲》示意。
- `preview/base-contact-sheet.png`：21 件手绘 PNG 总览。
- `preview/vector-contact-sheet.png`：9 件代码 / SVG 总览。
- `preview/world-fanren-vector.svg`、`world-test-vector.svg`：纯路线 / 标记 / UI 的透明 SVG 叠加层。

## 目录

```text
atlas-kit/
  base/
    terrain/        远山、主峰、山脊、坡脚          PNG
    water/          云雾、水岸、海面纹理（可选）    PNG
    architecture/   山门、城郭、关隘、洞府、村落、码头 PNG
    vegetation/     松林、竹林、芦苇、枯树          PNG
    routes/         旧版路线 PNG（仅作可选手绘 stamp）
    ui/             纸底、云纹；旧版 UI PNG（可选 stamp）
    markers/        旧版标记 PNG（可选 stamp）
  vector/
    routes/         陆路 / 海路线型样本 SVG
    ui/             罗盘、题签框、印章框 SVG
    markers/        城、宗门、秘境、危险 SVG
    tokens.json     SVG 组件色板与 viewBox
    README.md       代码 / SVG 组件说明
  packs/
    ink-light/      浅绛，默认
    ink-mono/       墨骨
    ink-green/      青绿
    ink-snow/       雪景
    ink-night/      夜色，实验性
  worlds/
    fanren/         《凡人修仙传》数据
    test-novel/     虚构小说数据
  preview/
  manifest.json
  render_map.py
  vector_lib.py     同一套图元：PIL 渲染 + SVG 导出
  README.md
  LICENSE.md
```

## 快速使用

在本机 PowerShell：

```powershell
cd D:\Desktop\project\chinese-novel-atlas\atlas-kit
python render_map.py --world worlds\fanren\world.json --out preview\world-fanren-map.png --width 1600 --height 900
```

同时导出透明 SVG 叠加层：

```powershell
python render_map.py --world worlds\fanren\world.json --out preview\world-fanren-map.png --svg-out preview\world-fanren-vector.svg
```

换成另一本小说：

1. 复制 `worlds/test-novel/` 为 `worlds/你的小说id/`。
2. 改 `world.json` 里的书名、地名、势力、坐标、`theme`。
3. 需要专属地标时，放到 `overrides/`，在 `world.json` 里引用。
4. 运行同一条渲染命令。

**不需要重画通用山、城、树、云。**

## 21 件 PNG 与 9 件 SVG 的分工

| 层 | 默认实现 | 原因 |
|---|---|---|
| 地形 / 水 / 建筑 / 植被 | PNG | 水墨笔触、纸纹、山石体积，代码画不出同等质感 |
| 路线 | `world.layers.routes` 坐标 → 代码平滑 + 虚线 | 固定 PNG 路线不能连接任意节点 |
| 标记 | `type: city / sect / secret / danger` → SVG | 位置、大小、数量随小说变化 |
| 罗盘 / 题签 / 印章 | SVG 框 + 代码文字 | 书名、图名、印文必须可改 |
| 海 | `water_bodies` 多边形 + 代码水色/波纹 | 海岸线是数据，不是固定 stamp；`water_sea_01.png` 可选叠加纹理 |

9 件旧 PNG（`base/routes`、`base/ui`、`base/markers`）仍保留为**可选手绘 stamp**。只有当某本小说需要特别手绘的路线/标记/UI 时，在 `world.json` 项里写 `"style": "png"` 才会走 PNG 分支；默认不读取。

## 资产规则

- PNG 统一 640×640 透明画布、统一左上柔光、地标脚点 `(50%, 87.5%)`，云 / 水 / UI 用中心点。
- 平视偏俯 15–25°，不要等距透视。
- 不烘焙文字、不出现专名、不画人物脸。
- 题签、印章、地名、路线、标记优先代码 / SVG。
- 每件资产在 `manifest.json` 里区分 `media: "png"` 或 `media: "vector"`；SVG 件带 `viewBox` 和 `vector` 类型。
- 换风格包只换颜色 token；`vector/tokens.json` 记录 SVG 组件色板。

## 图层顺序

`paper → water_bodies → terrain → water → architecture → vegetation → 旧版 route_stamps（可选）→ routes → markers → labels → ui`

`world.json` 的 `layers` 按这个顺序读取；新增小说只动数据，不动层规则。

## 多小说复用边界

- 这套是**东方国风 base kit**，覆盖仙侠、武侠、古言、玄幻。
- 如果多本里有西幻、科幻，另开 `western/`、`scifi/` base kit，不强行混。
- 每本小说建议只做 **10–20 个专属覆盖件**（特殊山门、主城、秘境、人物框），其余 80% 用通用底件。
- 势力徽章、人物像建议只做**空白框 / 印章框**，人物脸和专属纹样放到 `worlds/<id>/overrides/`。

## 风格包

`packs/*/theme.json` 是 token，不是另一套画。用法：

```json
"theme": {
  "paper": "#E8DCC5",
  "paper_image": "base/ui/paper_ornate.webp",
  "paper_tint": "#C49A62",
  "paper_tint_alpha": 0.035,
  "ink": "#3B332A",
  "accent": "#A66A45",
  "seal": "#A93828",
  "water": "#6E8E96",
  "route": "#8A7254",
  "label": "#2F2922"
}
```

夜色包是实验性的：深纸会把浅色雾面提亮，使用时把地形 / 水体不透明度降到 0.7 左右。

## 复用验收

`preview/reuse-report.json` / `reuse-report.md` 的当前结果：

- 手绘 PNG：21 件，两个世界实际用到 21 件（21/21）。
- 代码 / SVG：9 件，两个世界实际用到 9 件（9/9）。
- 两个世界共享 PNG 9 件、SVG 8 件。
- 只出现在《凡人》：PNG 5 件。
- 只出现在《苍梧》：PNG 7 件、SVG 1 件（危险标记）。

这说明底件不是“为《凡人》画的一套图”，而是两个不同世界都能共用的积木；同时，会随小说变化的 9 件已经交给代码 / SVG。

## 网页接入

网页地图不是另画一套，而是直接消费这套底件：

```powershell
cd D:\Desktop\project\chinese-novel-atlas
python scripts\prepare_atlas_web.py
python scripts\build.py --data samples\fictional\data.json --out demo\ --name index.html
```

- `prepare_atlas_web.py` 读本目录 `manifest.json`，把 21 件 PNG 转成 webp（质量 86，保持 640 画布和 pivot），再复制 `paper_ornate.webp`、`water_sea_01.webp`，输出到 `template/assets/map/atlas/`。
- `viewer.js` 的资产表读网页侧 `manifest.json`；路线、标记、题签、印章、罗盘全部用 Canvas 代码绘制，不消费固定 PNG。
- `build.py` 构建单文件时内联 23 张图（21 件 + 纸底 + 海纹）；网页地图数据来自 `map_layout` 的 `regions / nodes / terrain / routes / atlas`。
- 网页裁剪/摆放与 Python 渲染器共用同一套 `asset id`、pivot 和 21+9 分工。

## 重新生成

```powershell
cd D:\Desktop\project\chinese-novel-atlas\atlas-kit
python _source\build_vectors.py       # 生成 vector/ 下 9 件 SVG
python _source\build_contact_sheets.py # 生成两张总览表
python _source\rebuild_meta.py         # 更新 manifest + 复用报告
```

## 下一步扩展

优先补这 5 类，仍然保持通用：

1. 山体：雪山、火山、石林、沙丘。
2. 水：瀑布、湖泊、渡口、海礁。
3. 建筑：书院、寺庙、塔、桥、驿站、集市。
4. 特殊：战场、祭坛、矿洞、废墟、传送门。
5. UI：势力旗、人物框、名牌、图例、比例尺。

每加一个，先在 `manifest.json` 注册，再用至少两个 `worlds/*/world.json` 验证复用，不通过就不进 base。
