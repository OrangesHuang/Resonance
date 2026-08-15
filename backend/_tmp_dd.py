# ruff: noqa
# mypy: ignore-errors
# 临时回测分析脚本 — 不纳入 ruff/mypy 门槛
from datetime import datetime
from base.store.daily_repo import get_by_code
from base.store.sentiment_repo import get_turnover_series, get_margin_series
from base.analysis.sentiment.core import enrich_turnover, percentile_series, turnover_value
from base.config import SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
from base.analysis.strategy.router import compute_trades


def days(a, b):
    return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days


turnover = enrich_turnover(get_turnover_series())
margin = get_margin_series()
t_pct = percentile_series(
    [r.get("date") for r in turnover],
    [turnover_value(r) for r in turnover],
    SENTIMENT_ZONE_WINDOW,
    SENTIMENT_ZONE_MIN_PTS,
)
m_pct = percentile_series(
    [r.get("date") for r in margin],
    [r.get("fin_balance_yi") for r in margin],
    SENTIMENT_ZONE_WINDOW,
    SENTIMENT_ZONE_MIN_PTS,
)
kc_idx = get_by_code("589680")[::-1]
hs300 = get_by_code("510300")[::-1]

codes = ["515080", "159352", "589680"]
names = {"515080": "红利", "159352": "A500", "589680": "科创综指"}

# 1) 各标的策略状态序列(每日: 是否持仓 + 净值)
navs = {}  # code -> {date: nav}
for code in codes:
    rows = get_by_code(code)[::-1]
    res = compute_trades(code, rows, t_pct=t_pct, m_pct=m_pct, kc_idx_rows=kc_idx, hs300_rows=hs300)
    trades = res["trades"]
    # 构建持仓区间
    holding = {}  # date -> 1/0 (信号次日生效, 简化: 当日生效)
    pos = 0
    buy_price = 0
    for t in trades:
        if t["action"] == "BUY":
            pos, buy_price = 1, t["price"]
        else:
            pos = 0
    # 逐日净值: 持仓=价格/买入价, 空仓=1.0(现金)
    nav = {}
    cur_pos = 0
    cost = 0
    trade_iter = iter(trades)
    next_t = next(trade_iter, None)
    for r in rows:
        d = r["date"]
        while next_t and next_t["date"] == d:
            if next_t["action"] == "BUY":
                cur_pos, cost = 1, next_t["price"]
            else:
                cur_pos = 0
            next_t = next(trade_iter, None)
        if cur_pos and cost:
            nav[d] = (r["close_price"] or cost) / cost
        else:
            nav[d] = 1.0
    navs[code] = nav

# 2) 组合净值: 三只等权(共同日期)
common = sorted(set.intersection(*[set(v) for v in navs.values()]))
combined = [(d, sum(navs[c][d] for c in codes) / len(codes)) for d in common]


# 3) 最大回撤分析
def drawdown_metrics(series):
    peak = -1
    peak_date = None
    max_dd = 0
    trough_date = None
    trough_val = None
    # 最长回撤持续(未恢复前持续天数)与最深回撤
    longest_unrecovered = 0
    unrecovered_start = None
    cur_dd_start = None
    results = []
    for d, v in series:
        if v > peak:
            peak = v
            peak_date = d
            # 如果之前有未恢复的回撤, 记录它
            if cur_dd_start is not None:
                results.append(("recovered", cur_dd_start, d))
                cur_dd_start = None
        else:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
                trough_date = d
                trough_val = v
            if cur_dd_start is None:
                cur_dd_start = d
    if cur_dd_start is not None:
        results.append(("open", cur_dd_start, series[-1][0]))
    return max_dd, trough_date, results


md, td, recs = drawdown_metrics(combined)
print(f"==== 组合(红利+A500+科创综指等权) 净值回撤 ====")
print(f"数据范围: {common[0]} ~ {common[-1]} ({len(common)}交易日)")
print(f"最深回撤: {md * 100:.1f}% (谷底日 {td})")
print(f"回撤段(起点->恢复/未恢复):")
for kind, s, e in recs:
    tag = "未恢复" if kind == "open" else ""
    print(f"  {s} -> {e}  {days(s, e)}天 {tag}")

# 4) 单轮: 买入后回到成本线的天数 + 最大浮亏
print()
print("==== 单轮: 买入后回撤天数(回到成本线) ====")
for code in codes:
    rows = get_by_code(code)[::-1]
    res = compute_trades(code, rows, t_pct=t_pct, m_pct=m_pct, kc_idx_rows=kc_idx, hs300_rows=hs300)
    trades = res["trades"]
    by_date = {r["date"]: r for r in rows}
    buy = None
    for t in trades:
        if t["action"] == "BUY":
            buy = t
            continue
        if buy:
            # 买入日索引
            idx = next((i for i, r in enumerate(rows) if r["date"] == buy["date"]), None)
            cost = buy["price"]
            # 找回到成本线的日期
            back_date = None
            min_low = 0
            for r in rows[idx:]:
                if back_date is None and (r["close_price"] or 0) >= cost:
                    back_date = r["date"]
                low = (r["close_price"] or cost) / cost - 1
                if low < min_low:
                    min_low = low
            if back_date:
                print(
                    f"  {names[code]} {buy['date']}买@{cost:.3f}: 最深浮亏{min_low * 100:+.1f}%, {days(buy['date'], back_date)}天后回本(次日或当日)"
                )
            else:
                print(f"  {names[code]} {buy['date']}买@{cost:.3f}: 最深浮亏{min_low * 100:+.1f}%, 至今未回本")
            buy = None
