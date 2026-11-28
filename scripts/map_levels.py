#!/usr/bin/env python3
"""map_levels.py — 输出地图 M0–M4 成熟度分级。"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_atlas.reader.map_levels import compute_map_levels  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    args = ap.parse_args()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    print(json.dumps(compute_map_levels(data), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
