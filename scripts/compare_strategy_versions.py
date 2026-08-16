# ruff: noqa
# mypy: ignore-errors
"""双版本买卖点自动比对: 检查 Beta 是否漏掉正式版的买点。

用法: python3 scripts/compare_strategy_versions.py [code] [--base YYYY-MM-DD]

规则:
  - 对比基准日(默认 2024-10-08, 正式版 TRADE_START)之后的买卖点
  - Beta 独有的"基准前持仓了结卖出"(如 924 前夜轮)不视为差异
  - 输出: 逐笔差异 + 两版累计收益对比
退出码: 0=一致或Beta更好, 1=存在漏笔(买入点不一致)
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from base.analysis.sentiment.core import enrich_turnover, percentile_series, turnover_value
from base.analysis.strategy.router import compute_trades
from base.config import SENTIMENT_ZONE_MIN_PTS, SENTIMENT_ZONE_WINDOW
from base.store.daily_repo import get_by_code
from base.store.sentiment_repo import get_margin_series, get_turnover_series

CODE = sys.argv[1] if len(sys.argv) > 1 else "510300"
BASE = "2024-10-08"
if "--base" in sys.argv:
    BASE = sys.argv[sys.argv.index("--base") + 1]

rows = list(reversed(get_by_code(CODE)))
rows = [r for r in rows if r.get("composite_prob") is not None]
turnover = enrich_turnover(get_turnover_series())
margin = get_margin_series()
t_pct = percentile_series(
    [r.get("date") for r in turnover], [turnover_value(r) for r in turnover], SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
)
m_pct = percentile_series(
    [r.get("date") for r in margin], [r.get("fin_balance_yi") for r in margin], SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
)
res_s = compute_trades(CODE, rows, t_pct=t_pct, m_pct=m_pct, version="stable")
res_b = compute_trades(CODE, rows, t_pct=t_pct, m_pct=m_pct, version="beta")

def seg(res):
    out = []
    for i, t in enumerate(res["trades"]):
        if t["date"] < BASE:
            continue
        out.append((t["date"], t["action"], round(t["price"], 3), (t.get("reason") or "")[:20]))
    return out

bs, bb = seg(res_s), seg(res_b)
# Beta 的"基准前持仓了结卖出"(无对应正式版持仓)不视为差异
bb_clean = [x for x in bb if not (x[0] == BASE and x[1] == "SELL")]
bb_clean = [x for x in bb_clean if not (x[1] == "SELL" and x[0] < "2024-11-01" and not any(y[1] == "BUY" and y[0] < x[0] and y[0] >= BASE for y in bb_clean))]

print("%s 版本对比(基准 %s 之后):" % (CODE, BASE))
print("  正式版 %d 笔, Beta %d 笔" % (len(bs), len(bb_clean)))

leaks = []
if len(bs) != len(bb_clean):
    leaks = ["笔数不同"]
else:
    for i in range(len(bs)):
        if bs[i][:2] != bb_clean[i][:2]:
            leaks.append("第%d笔: 正式版 %s vs Beta %s" % (i, bs[i][:2], bb_clean[i][:2]))

if leaks:
    print("  差异:")
    for l in leaks:
        print("   ", l)
    # 打印完整明细辅助定位
    print("  正式版明细:")
    for x in bs:
        print("   ", x)
    print("  Beta明细:")
    for x in bb_clean:
        print("   ", x)
    sys.exit(1)
else:
    print("  逐笔一致 ✓ (Beta 未漏正式版买点)")

# 全历史收益对比
def total(res):
    geom = 1.0
    for i, t in enumerate(res["trades"]):
        if t["action"] == "BUY":
            sell = res["trades"][i + 1] if i + 1 < len(res["trades"]) and res["trades"][i + 1]["action"] == "SELL" else None
            if sell:
                geom *= sell["price"] / t["price"]
    return (geom - 1) * 100

ts_, tb_ = total(res_s), total(res_b)
print("全历史累计: 正式版 %+.1f%% vs Beta %+.1f%%" % (ts_, tb_))
if tb_ < ts_:
    print("⚠ Beta 跑输正式版! 无发布价值")
    sys.exit(2)
print("Beta >= 正式版 ✓")
sys.exit(0)
