"""境界体系：读取权威 realms.json（或批次并集），并应用人工核过的战力时间线。"""

import json
from pathlib import Path

from ..names import norm


def load_realms(root, batches):
    """境界体系以全文扫描出的 realms.json 为权威；没有就退回批次并集。"""
    spec = root / "realms.json"
    if spec.exists():
        raw = json.loads(spec.read_text(encoding="utf-8"))
        realms = raw["realms"] if isinstance(raw, dict) else raw
        orders = [r.get("order") for r in realms]
        if orders != list(range(1, len(realms) + 1)):
            raise SystemExit(f"{spec} 的 order 必须从 1 连续递增，当前 {orders}")
        # 用批次里的信息补 first_ch / desc
        seen = {norm(r.get("name", "")): r for r in realms}
        for _, b in batches:
            for r in b.get("realms", []):
                t = seen.get(norm(r.get("name", "")))
                if t is None:
                    continue
                if not t.get("first_ch") and r.get("first_ch"):
                    t["first_ch"] = r["first_ch"]
                if not t.get("desc") and r.get("desc"):
                    t["desc"] = r["desc"]
        print(f"  境界体系 {len(realms)} 级（来自 realms.json）")
        ph = raw.get("power_history") if isinstance(raw, dict) else {}
        return realms, (ph or {})

    # 没有权威文件：批次各自编号，冲突必然发生
    seen, collected = set(), []
    for _, b in batches:
        for r in b.get("realms", []):
            key = norm(r.get("name", ""))
            if key and key not in seen:
                seen.add(key)
                collected.append(dict(r))
    if len(collected) < 2:
        if collected:
            print("  ⚠ 只抽到 1 个境界，无法构成有序体系，realms 留空。"
                  "请先跑 scripts/realms.py 生成 realms.json")
        return [], {}
    orders = sorted({r.get("order") for r in collected})
    if len(orders) != len(collected):
        print("  ⚠ 批次间 order 冲突，realms 留空。请先跑 scripts/realms.py 确认体系")
        return [], {}
    collected.sort(key=lambda x: x.get("order", 99))
    return collected, {}


def apply_power_history(ents, id_map, realms, realm_ph):
    """realms.json 里的战力时间线是人工核过原文的，优先于批次模型结果。"""
    if not realm_ph:
        return 0
    by_id = {e["id"]: e for e in ents}
    applied = 0
    order = {r["id"]: r.get("order", 99) for r in realms}
    stages = {r["id"]: set(r.get("stages") or []) for r in realms}
    for old_id, timeline in realm_ph.items():
        target = by_id.get(id_map.get(old_id, old_id)) or by_id.get(old_id)
        if not target:
            print(f"  ⚠ realms.json 里的 {old_id} 在实体表中不存在，跳过")
            continue
        clean = []
        for p in timeline:
            if p.get("realm") not in order:
                print(f"  ⚠ {target['name']}: 境界 {p.get('realm')} 不在体系中，跳过")
                continue
            if p.get("stage") and stages[p["realm"]] and p["stage"] not in stages[p["realm"]]:
                print(f"  ⚠ {target['name']}: 小阶段 {p['stage']} 不属于 {p['realm']}，跳过")
                continue
            clean.append({k: v for k, v in p.items() if k in ("ch", "realm", "stage", "note")})
        target["power_history"] = sorted(clean, key=lambda x: x["ch"])
        applied += 1
    print(f"  战力时间线 {applied} 人（来自 realms.json）")
    return applied
