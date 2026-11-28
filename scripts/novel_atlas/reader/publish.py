"""读者站构建：anomalies + map levels + 按进度截断 + 单文件/静态站。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .anomalies import build_anomalies
from .cutoff import filter_data, reader_meta
from .map_levels import compute_map_levels
from .versions import create_snapshot


ROOT = Path(__file__).resolve().parents[3]


def _anomaly_known(a: dict, cutoff: int) -> bool:
    rng = a.get("chapter_range") or []
    if rng and int(rng[-1]) > cutoff:
        return False
    for ev in a.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        ch = ev.get("ch")
        if not isinstance(ch, int):
            m = re.match(r"ch(\d+)", str(ev.get("coordinate") or ""))
            ch = int(m.group(1)) if m else None
        if ch is not None and ch > cutoff:
            return False
    return True


def annotate(data: dict, *, cutoff: int | None = None, anomalies: dict | None = None) -> dict:
    report = anomalies or build_anomalies(data)
    out = filter_data(data, cutoff)
    c = (out.get("_reader") or {}).get("cutoff_ch") or 0
    out["anomalies"] = [a for a in report["anomalies"] if _anomaly_known(a, c)]
    out["_anomalyMeta"] = {k: v for k, v in report.items() if k != "anomalies"}
    out["_mapLevels"] = compute_map_levels(out)
    out["_reader"] = reader_meta(out, cutoff)
    return out


def build_reader(data: dict, out_dir: str | Path, *, name: str = "index.html",
                 cutoff: int | None = None, external: bool = True,
                 snapshot: bool = False, label: str = "",
                 require_complete: bool = False) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = data.get("meta") or {}
    coverage = meta.get("coverage") or {}
    if require_complete and coverage.get("chapters_done") != meta.get("chapters"):
        raise SystemExit(
            f"发布要求 100% 覆盖：当前 {coverage.get('chapters_done')} / {meta.get('chapters')} 章；"
            "补齐批次后重跑，或加 --allow-partial"
        )
    report = build_anomalies(data)
    annotated = annotate(data, cutoff=cutoff, anomalies=report)

    anomalies_path = out / "anomalies.json"
    anomalies_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if snapshot:
        snap = create_snapshot(data, out, label=label)
    else:
        snap = None

    tmp = out / "_reader_data.json"
    tmp.write_text(json.dumps(annotated, ensure_ascii=False), encoding="utf-8")
    cmd = [
        sys.executable, str(ROOT / "scripts" / "build.py"),
        "--data", str(tmp), "--out", str(out), "--name", name,
        "--skip-validate",
    ]
    if external:
        cmd.append("--external")
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True,
                              capture_output=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "reader build failed").strip())
    finally:
        if tmp.exists():
            tmp.unlink()

    manifest = {
        "product": "Novel Atlas Reader",
        "title": (data.get("meta") or {}).get("title"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": (annotated.get("meta") or {}).get("coverage"),
        "source_coverage": (data.get("meta") or {}).get("coverage"),
        "coverage_complete": bool(
            ((annotated.get("meta") or {}).get("coverage") or {}).get("chapters_done")
            == (annotated.get("meta") or {}).get("chapters")
        ),
        "publishable": annotated.get("_reader", {}).get("analysis_complete", False),
        "reader": annotated.get("_reader"),
        "anomalies": {
            "total": report.get("total"),
            "visible": len(annotated.get("anomalies") or []),
            "counts": report.get("counts"),
            "path": "anomalies.json",
        },
        "map_levels": annotated.get("_mapLevels"),
        "entry": name,
        "data": "data.js" if external else "embedded",
        "snapshot": snap,
        "counts": {
            "entities": len(annotated.get("entities") or []),
            "relations": len(annotated.get("relations") or []),
            "places": len(annotated.get("places") or []),
            "chapters": len(annotated.get("chapters") or []),
            "foreshadows": len(annotated.get("foreshadows") or []),
        },
    }
    (out / "reader-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"out": str(out), "entry": str(out / name), "manifest": manifest,
            "anomalies": report, "stdout": proc.stdout}
