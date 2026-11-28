"""批次文件读取：只负责找到并解析 batch-*.json。"""

import json
from pathlib import Path


def load_batches(d):
    """读取目录下所有 batch-*.json，返回 [(文件名, JSON 对象)]。"""
    files = sorted(Path(d).glob("batch-*.json"))
    if not files:
        raise SystemExit(f"{d} 下没有 batch-*.json")
    batches = []
    for f in files:
        if f.name.endswith(".failed.json"):
            continue
        try:
            batches.append((f.name, json.loads(f.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as e:
            print(f"  ⚠ 跳过 {f.name}：JSON 解析失败（{e}）")
    if not batches:
        raise SystemExit(f"{d} 下没有可用的 batch-*.json")
    return batches
