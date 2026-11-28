"""空间数据（spatial.json）加载：人工证据化地点、拓扑/方位关系与示意布局。

- 每本书目录下可有 `spatial.json`：`{ meta, places, spatial_relations, map_layout }`；
- 文件不存在时返回空结果，管线仍会在 data.json 顶层写 `spatial_relations: []`；
- `map_layout` 缺省时返回 None，管线**不写**该键，让视图回退拓扑；
- 本模块只负责读入，id 冲突跳过、父级解析等由管线编排处理。
"""

import json
from pathlib import Path


def load_spatial(root):
    """读取 `<root>/spatial.json`，返回 `(extra_places, relations, map_layout)`。

    - `extra_places`：spatial.json 里补充的地点 dict 列表；
    - `relations`：spatial_relations 条目列表（原样挂到 data.json 顶层）；
    - `map_layout`：2D 示意布局 dict；字段缺失时为 None，管线不写该键。
    文件缺失、损坏或字段缺失时按空处理，不抛异常打断合并。
    """
    root = Path(root)
    path = root / "spatial.json"
    if not path.is_file():
        return [], [], None

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"  警告：spatial.json 解析失败（{exc}），按无空间数据处理")
        return [], [], None

    places = doc.get("places") or []
    relations = doc.get("spatial_relations") or []
    if not isinstance(places, list) or not isinstance(relations, list):
        print("  警告：spatial.json 字段形态异常，按无空间数据处理")
        return [], [], None

    map_layout = doc.get("map_layout")
    if map_layout is not None and not isinstance(map_layout, dict):
        print("  警告：map_layout 形态异常，按未提供示意坐标处理")
        map_layout = None
    return list(places), list(relations), map_layout
