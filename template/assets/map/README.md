# 人界舆图 · 地图美术资源

由 seedream 5.5 生成，2026-11-27。全部为项目内自制素材，不含外部底图或版权图片；用于《凡人修仙传》图谱的地图视图，属于**示意美术**，不是地理事实。

## 视觉口径

当前采用 **空图 + 小徽记**，不使用地形底图：

- 空图只提供羊皮纸纹、做旧边缘、双层细边框和四角如意云纹；不画山脉、河流、海岸线、树木。
- 势力徽章、人物小像、地点标记作为可叠加的小资产，负责组织画面和信息。
- 地图上不烘焙任何文字；标题题签、地名、朱印、云纹分隔均由 `viewer.js` 叠加。
- 朱砂只用于要地、印章和航路，避免满屏红点。
- 示意坐标来自 `spatial.json` 的 `map_layout`，只用于叙事导航，不是经纬度。

## 文件

### 空图背景

`backgrounds/web/`

| 文件 | 尺寸 | 用途 |
| --- | --- | --- |
| `blank-map-ornate.webp` | 1920×1080 | **当前默认**：双层细边框 + 四角如意云纹，画面内无文字、无地形 |
| `blank-map-light.webp` | 1920×1080 | 无边框旧纸底，只有纸纹和水痕；需要自绘边框时用 |
| `blank-map-dark.webp` | 1920×1080 | 深青灰纸面，深色主题备用 |

### 势力徽章

`icons/factions/web/`，448px 透明底，圆形水墨徽记：

| 文件 | 势力 |
| --- | --- |
| `huangfenggu.webp` | 黄枫谷 |
| `qingxumen.webp` | 清虚门 |
| `yanyuezong.webp` | 掩月宗 |
| `jujianmen.webp` | 巨剑门 |
| `lingshoushan.webp` | 灵兽山 |
| `huadaowu.webp` | 化刀坞 |
| `tianquebao.webp` | 天阙堡 |
| `xinggong.webp` | 星宫 |
| `hehuanzong.webp` | 合欢宗 |

建议 56–92px；缩到 40px 以下会损失淡彩小景细节。

### 人物小像

`icons/characters/web/`，512px 透明底，圆形半身像：

| 文件 | 人物 | 页面用途 |
| --- | --- | --- |
| `hanli.webp` | 韩立 | 主角，地图高亮，96–168px |
| `nangongwan.webp` | 南宫婉 | 左下角小头像，56–96px |
| `modafu.webp` | 墨大夫 | 左下角小头像，56–96px |

### 地点标记

`icons/markers/web/`，256px 透明底，圆形印章式：

| 文件 | 标记 |
| --- | --- |
| `city.webp` | 城池 |
| `sect.webp` | 宗门 |
| `market.webp` | 坊市 |
| `secret.webp` | 秘境 |
| `portal.webp` | 传送阵 |
| `danger.webp` | 险地 |

地图小点建议 22–32px；需要文字说明时在图标下加 11px 标签。

### 装饰件

`ornaments/`，透明底 WebP：

| 文件 | 尺寸 | 用途 |
| --- | --- | --- |
| `corner-cloud.webp` | 700×699 | 如意云角饰，可旋转/缩放贴四角或边缘 |
| `divider-cloud.webp` | 1700×212 | 云纹分隔，压在地名或题签下方 |

## 页面用法

1. 空图全出血铺满容器，`cover` 裁切；不要出现白色页边。
2. 势力徽章放成“越国七派 / 乱星海·魔道”两个松散簇，不排规则网格；簇间只留一条虚线航路。
3. 人物像不铺满地图：韩立放主位，南宫婉、墨大夫收左下角小头像条。
4. 地点小点按 `map_layout` 放，带 11px 地名标签；虚天殿只留 1 个秘境标记，避免重复。
5. 当前页面在左上画竖排题签“人界舆图”+“凡”朱印；越国、乱星海、虚天殿各加一枚小朱印；区域名下方压云纹分隔。
6. 图例卡不画在画布内，避免压住右下角云纹；标记含义放在页脚或详情面板。

## 单文件导出

`scripts/build.py` 已支持 `__ASSET__:map/...` 占位替换为 base64 data URI。当前 `atlas.html` 单文件内联了空图、徽章、人物、标记、罗盘、云纹等实际用到的资源，不依赖外部图片目录。

## 样张

- `output/凡人修仙传/_contract/map-icons-shots/map-final4-1440x900.png`
- `output/凡人修仙传/_contract/map-icons-shots/map-final4-1920x1080.png`

## 旧地形资产

`web/base-clean.webp`、`web/base-parchment.webp`、`web/sea-ink.webp`、`web/mountain-range.webp`、`web/forest-cluster.webp`、`web/floating-isle.webp` 是早期“地形底图”方向，已被当前空图方案取代；保留仅作历史参考，页面不再使用。
