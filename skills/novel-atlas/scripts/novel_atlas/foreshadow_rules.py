"""伏笔超期规则：Python 侧所有入口共用同一套阈值和状态派生。

`viewer.js` 是浏览器运行时，无法直接 import Python；它的同公式实现
仍在模板里，修改规则时必须同步。
"""


def threshold(live, total):
    """阈值 = max(50, 已分析章数 × 0.15)；未分析时退回全书章数。"""
    span = live if live else (total or 0)
    return max(50, int(span * 0.15))


def expected_status(f, live, thr):
    """按 schema 派生状态；dropped 是唯一允许人工保留的覆盖值。"""
    if f.get("status") == "dropped":
        return "dropped"
    payoff = f.get("payoff_ch")
    if payoff and payoff != f.get("plant_ch"):
        return "paid"
    # 看沉默时长：埋了很久但一直在提的长线，不算超期。
    last = f.get("last_mention_ch") or f.get("plant_ch") or 0
    return "overdue" if live - last > thr else "planted"
