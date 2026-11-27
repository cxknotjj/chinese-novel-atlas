"""空间关系（spatial.json）加载：人工证据化整理的地点补充与拓扑/方位关系。

- 每本书目录下可有 `spatial.json`：`{ meta, places, spatial_relations }`；
- 文件不存在时返回空结果，管线仍会在 data.json 顶层写 `spatial_relations: []`；
- 本模块只负责读入，id 冲突跳过、父级解析等由管线编排处理。
"""

import json
from pathlib import Path


def load_spatial(root):
    """读取 `<root>/spatial.json`，返回 `(extra_places, relations)`。

    - `extra_places`：spatial.json 里补充的地点 dict 列表；
    - `relations`：spatial_relations 条目列表（原样挂到 data.json 顶层）。
    文件缺失、损坏或字段缺失时按空处理，不抛异常打断合并。
    """
    root = Path(root)
    path = root / "spatial.json"
    if not path.is_file():
        return [], []

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"  警告：spatial.json 解析失败（{exc}），按无空间关系处理")
        return [], []

    places = doc.get("places") or []
    relations = doc.get("spatial_relations") or []
    if not isinstance(places, list) or not isinstance(relations, list):
        print("  警告：spatial.json 字段形态异常，按无空间关系处理")
        return [], []
    return list(places), list(relations)
