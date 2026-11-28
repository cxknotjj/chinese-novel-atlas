# 代码 / SVG 组件

这 9 件是“会随小说变化”的组件，默认不再用固定 PNG 承担。

| 文件 | 类型 | 用法 |
|---|---|---|
| `routes/route_land.svg` | 陆路线型样本 | 仅示意虚线、粗细、端点；实际路线用 `world.routes` 坐标生成 |
| `routes/route_sea.svg` | 海路线型样本 | 同上，颜色取 `theme.water` |
| `ui/compass.svg` | 罗盘 | 可整件缩放；方向文字由组件内置“北”字 |
| `ui/cartouche_frame.svg` | 题签框 | 空框；书名/图名由 `world.ui[].text` 写入 |
| `ui/seal_frame.svg` | 印章框 | 空框；印文由 `world.ui[].text` 写入 |
| `markers/marker_city.svg` | 城标记 | `type: "city"` |
| `markers/marker_sect.svg` | 宗门标记 | `type: "sect"` |
| `markers/marker_secret.svg` | 秘境标记 | `type: "secret"` |
| `markers/marker_danger.svg` | 危险标记 | `type: "danger"` |

## 统一规则

- 标记使用 `0 0 100 100` viewBox，图形脚点/视觉中心都在 `(50, 50)`，缩放时不需要额外偏移。
- 颜色只取主题 token：`ink / accent / seal / paper / water / route`；换风格包时替换颜色即可。
- 题签、印章、地名的文字**不烘焙**进 SVG；这样同一套组件可以服务多本小说。
- `route_land.svg` 和 `route_sea.svg` 是线型样本，不是可拼接的固定路线。真正的路线来自 `world.json` 的 `layers.routes` 点列，渲染器会自动做 Catmull-Rom 平滑和虚线。

## 重新生成

```powershell
cd D:\Desktop\project\chinese-novel-atlas\atlas-kit
python _source\build_vectors.py
```

生成逻辑在 `../vector_lib.py`；示例地图和 SVG 叠加层共用同一套图元，避免 PNG 与 SVG 两套风格漂移。
