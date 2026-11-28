"""世界模型版本快照与重跑对比。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _counts(data: dict) -> dict:
    return {
        "entities": len(data.get("entities") or []),
        "relations": len(data.get("relations") or []),
        "chapters": len(data.get("chapters") or []),
        "foreshadows": len(data.get("foreshadows") or []),
        "places": len(data.get("places") or []),
        "concepts": len(data.get("concepts") or []),
        "spatial_relations": len(data.get("spatial_relations") or []),
    }


def _ids(data: dict) -> dict:
    def pick(kind: str) -> dict[str, str]:
        out = {}
        for x in data.get(kind) or []:
            if x.get("id"):
                out[x["id"]] = x.get("name") or x.get("content") or x.get("fact") or ""
        return out
    return {
        "entities": pick("entities"),
        "places": pick("places"),
        "foreshadows": pick("foreshadows"),
        "concepts": pick("concepts"),
    }


def _name_to_id(data: dict) -> dict:
    """name → id，用来检测同名对象是否在重跑后换了 id。"""
    def pick(kind: str) -> dict[str, str]:
        out = {}
        for x in data.get(kind) or []:
            name = x.get("name") or x.get("content") or x.get("fact")
            if name and x.get("id"):
                out[str(name)] = x["id"]
        return out
    return {
        "entities": pick("entities"),
        "places": pick("places"),
        "foreshadows": pick("foreshadows"),
        "concepts": pick("concepts"),
    }


def fingerprint(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_snapshot(data: dict, out_dir: str | Path, label: str = "") -> dict:
    root = Path(out_dir)
    versions = root / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    existing = sorted(versions.glob("v*.json"))
    n = 1
    while (versions / f"v{n}.json").exists():
        n += 1
    snap = {
        "version": n,
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_title": (data.get("meta") or {}).get("title"),
        "source_file": (data.get("meta") or {}).get("source_file"),
        "coverage": (data.get("meta") or {}).get("coverage"),
        "fingerprint": fingerprint(data),
        "counts": _counts(data),
        "ids": _ids(data),
        "data": data,
    }
    path = versions / f"v{n}.json"
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = versions / "latest.json"
    latest.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"version": n, "path": str(path), "latest": str(latest), "fingerprint": snap["fingerprint"]}


def _load_snapshot(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    return obj.get("data", obj)


def diff_snapshots(a_path: str | Path, b_path: str | Path) -> dict:
    a = _load_snapshot(a_path)
    b = _load_snapshot(b_path)

    def setdiff(kind: str, key: str = "id") -> dict:
        ids_a = {x.get(key) for x in a.get(kind) or [] if x.get(key)}
        ids_b = {x.get(key) for x in b.get(kind) or [] if x.get(key)}
        return {"added": sorted(ids_b - ids_a), "removed": sorted(ids_a - ids_b),
                "common": len(ids_a & ids_b)}

    names_a, names_b = _name_to_id(a), _name_to_id(b)
    stability = {}
    for kind in ("entities", "places", "foreshadows", "concepts"):
        common_names = set(names_a[kind]) & set(names_b[kind])
        changed = {
            name: [names_a[kind][name], names_b[kind][name]]
            for name in common_names
            if names_a[kind][name] != names_b[kind][name]
        }
        stability[kind] = {"changed": changed, "stable": not changed}

    rels_a = a.get("relations") or []
    rels_b = b.get("relations") or []
    if all("id" in r for r in rels_a + rels_b):
        relations = setdiff("relations")
    else:
        relations = {"a": len(rels_a), "b": len(rels_b), "note": "relations 无 id，按数量对比"}

    return {
        "a": str(a_path), "b": str(b_path),
        "counts": {"a": _counts(a), "b": _counts(b), "relations": relations},
        "entities": setdiff("entities"),
        "places": setdiff("places"),
        "foreshadows": setdiff("foreshadows"),
        "concepts": setdiff("concepts"),
        "id_stability": stability,
    }
