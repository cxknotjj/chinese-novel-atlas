"""章节与卷：补全 chunk-meta 的字数/卷信息，只按已分析章节归卷。"""


def merge_chapters(batches, cm, id_map=None):
    """章节以 chunk-meta 为准补 words / volume；摘要等取模型结果。"""
    id_map = id_map or {}
    meta_ch = {}
    for r in cm.get("chapters", []):
        if isinstance(r.get("ch"), int):
            meta_ch[r["ch"]] = r

    by_ch = {}
    for _, b in batches:
        for c in b.get("chapters", []):
            ch = c.get("ch")
            if isinstance(ch, int) and ch not in by_ch:
                by_ch[ch] = c

    out = []
    for ch in sorted(by_ch):
        c = dict(by_ch[ch])
        m = meta_ch.get(ch)
        if m:
            c["words"] = m.get("words") or c.get("words", 0)
            if m.get("vol"):
                c["volume"] = f"v{m['vol']}"
        c.setdefault("words", 0)
        t = c.get("tension")
        c["tension"] = max(0.0, min(1.0, float(t))) if isinstance(t, (int, float)) else 0.0
        if c.get("hook_type") not in ("悬念", "反转", "冲突", "危机", "爽点", "无"):
            c["hook_type"] = "无"
        if c.get("emotion") not in ("爽", "压抑", "紧张", "温情", "悲", "平"):
            c["emotion"] = "平"
        c["summary"] = (c.get("summary") or "").strip()[:80]
        # 早期批次把战斗参战方写成 s/t，统一成合同里的 a/b
        for b in (c.get("battles") or []):
            if b.get("a") is None and b.get("s") is not None:
                b["a"] = b["s"]
            if b.get("b") is None and b.get("t") is not None:
                b["b"] = b["t"]
            b.pop("s", None); b.pop("t", None)
            b["a"] = id_map.get(b.get("a"), b.get("a"))
            b["b"] = id_map.get(b.get("b"), b.get("b"))
        out.append(c)
    return out


def build_volumes(cm, chapters):
    """只从**已分析章节**归卷，避免只拆前 100 章时把第 3 卷写成 101..100。"""
    names = {}
    for r in cm.get("chapters", []):
        v = r.get("vol")
        if v:
            names.setdefault(v, r.get("vol_name") or f"第{v}卷")

    groups = {}
    for c in chapters:
        v = c.get("volume")
        if not v:
            continue
        num = v[1:] if str(v).startswith("v") else str(v)
        groups.setdefault(num, []).append(c["ch"])

    vols = []
    for num in sorted(groups, key=lambda x: int(x) if str(x).isdigit() else 999):
        chs = groups[num]
        label = names.get(int(num)) if str(num).isdigit() else None
        label = label or names.get(num) or f"第{num}卷"
        vols.append({"id": f"v{num}", "name": label,
                     "ch_start": min(chs), "ch_end": max(chs), "summary": ""})

    if not vols:                      # 章节没标卷时退回 chunk-meta，但仍以已分析章号为界
        live = max((c["ch"] for c in chapters), default=0)
        for r in cm.get("chapters", []):
            v = r.get("vol")
            if not v or r["ch"] > live:
                continue
            if vols and vols[-1]["id"] == f"v{v}":
                vols[-1]["ch_end"] = max(vols[-1]["ch_end"], r["ch"])
            elif not vols or vols[-1]["id"] != f"v{v}":
                if all(x["id"] != f"v{v}" for x in vols):
                    vols.append({"id": f"v{v}", "name": r.get("vol_name") or f"第{v}卷",
                                 "ch_start": r["ch"], "ch_end": r["ch"], "summary": ""})
    return vols
