# viewer 模块

`template/viewer.js` 只是入口：一个空 IIFE，里面放 `// __VIEWER_MODULES__` 占位。
`scripts/build.py` 会按文件名顺序把本目录的 `*.js` 拼进入口，再内联成单文件页面。

所有模块共享同一个闭包，所以可以按原来单文件的顺序自由引用函数和常量；不要在每个文件里再包一层 IIFE。

## 模块表

| 文件 | 职责 |
| --- | --- |
| `00-foundation.js` | 数据装载、`cutoff_ch` 截断、阅读进度条、调色板、实体索引 |
| `10-graph.js` | 图谱画布、力导向布局、节点/关系线/相机 |
| `20-graph-interaction.js` | 图谱命中、拖拽、缩放、选中与详情面板 |
| `30-views.js` | 视图切换、总览、疑点索引 |
| `40-wiki-geo.js` | 百科分页、地点志树、地点详情 |
| `50-map-model.js` | 地图 M1/M2/2D 模型、分层、缩放变换、`drawMap` 调度 |
| `60-map-surface.js` | 纸底、海陆水洗、地形、山脊、建筑/植被 stamp |
| `65-map-overlays.js` | 路线、图标、地名、题签、印章、免责声明 |
| `68-map-scene.js` | `drawMap2d` 场景合成、标签避让、悬停提示 |
| `70-map-ui.js` | 地图交互、图层/切片选择、编排器、拖拽与保存 |
| `80-analysis.js` | 势力版图、章节节奏、境界表、伏笔 |
| `90-search-boot.js` | 全书搜索、启动参数、动画循环初始化 |

## 修改约定

1. 新逻辑先判断归哪个职责；不要把地图代码塞回 `00-foundation.js`。
2. 新增模块用两位数字前缀保证拼装顺序，文件名保持小写短横线。
3. 模块内不写 `(function () { ... })();`，入口已经提供闭包。
4. 改完跑：

```powershell
node --check template/viewer.js
python scripts/build.py --data samples/fictional/data.json --out demo --name index.html --skip-validate
python -m unittest discover -s tests
```

`node --check template/viewer.js` 只检查空入口；真正产物要用浏览器验收，或从构建出的页面抽出 script 再 `node --check`。
