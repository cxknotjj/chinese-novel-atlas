"""CSV 导出：伏笔清单与角色表。"""

import csv

from .common import STATUS_CN, TYPE_CN, degree_map, foresight_rows


def export_fs(d, out_dir):
    out = out_dir / "伏笔清单.csv"
    live = d["_live"]
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        # 「沉默」是判超期的依据，「跨度」只是埋了多久——两者差很远，都要给
        w.writerow(["id", "内容", "埋设章", "回收章", "最后提及", "沉默", "状态",
                    "跨度", "线索", "重要度", "备注"])
        for f, st, span in foresight_rows(d):
            last = f.get("last_mention_ch")
            silent = "" if f.get("payoff_ch") else (live - (last or f.get("plant_ch") or 0))
            w.writerow([f.get("id"), f.get("content"), f.get("plant_ch"),
                        f.get("payoff_ch") or "", last or "", silent, STATUS_CN[st], span,
                        f.get("thread") or "", f.get("importance"), f.get("note") or ""])
    return out


def export_csv(d, out_dir):
    out = out_dir / "角色表.csv"
    deg = degree_map(d)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "名称", "类型", "阵营", "别名", "首次登场", "最后登场",
                    "关系数", "简介"])
        for e in sorted(d.get("entities") or [], key=lambda x: -deg[x["id"]]):
            w.writerow([e.get("id"), e.get("name"), TYPE_CN.get(e.get("type"), e.get("type")),
                        e.get("group"), "、".join(e.get("aliases") or []),
                        e.get("first_ch"), e.get("last_ch") or "",
                        deg[e["id"]], (e.get("desc") or "").replace("\n", " ")])
    return out
