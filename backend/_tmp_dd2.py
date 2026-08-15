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

navs = {}
for code in codes:
    rows = get_by_code(code)[::-1]
    res = compute_trades(code, rows, t_pct=t_pct, m_pct=m_pct, kc_idx_rows=kc_idx, hs300_rows=hs300)
    trades = res["trades"]
    trade_iter = iter(trades)
    next_t = next(trade_iter, None)
    nav = {}
    pos = 0
    cost = 0.0
    base_nav = 1.0  # 买入前的净值基准
    for r in rows:
        d = r["date"]
        while next_t and next_t["date"] == d:
            if next_t["action"] == "BUY":
                pos = 1
                cost = next_t["price"]
                base_nav = nav.get(rows[0]["date"], 1.0) if False else (nav.get(d) if nav else 1.0)
                # 买入当日: 以当日之前的净值作为基准(空仓期恒为最新净值)
                prev = list(nav.values())[-1] if nav else 1.0
                base_nav = prev
            else:
                pos = 0
                # 卖出: 净值定格在卖出日
            next_t = next(trade_iter, None)
        if pos and cost:
            nav[d] = base_nav * ((r["close_price"] or cost) / cost)
        else:
            nav[d] = list(nav.values())[-1] if nav else 1.0
    navs[code] = nav

# 组合净值: 每只从共同起点归一后等权平均
start = max(min(v) for v in navs.values())
common = sorted(set.intersection(*[set(v) for v in navs.values()]))
common = [d for d in common if d >= start]
norms = {}
for c in codes:
    s0 = navs[c][start]
    norms[c] = {d: navs[c][d] / s0 for d in common}
combined = [(d, sum(norms[c][d] for c in codes) / len(codes)) for d in common]

# 最大回撤段
peak = -1
peak_date = None
max_dd = 0
trough_date = None
cur_start = None
segments = []
for d, v in combined:
    if v > peak:
        if cur_start is not None:
            segments.append((cur_start, d, "恢复"))
            cur_start = None
        peak, peak_date = v, d
    else:
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd
            trough_date = d
        if cur_start is None:
            cur_start = d
if cur_start is not None:
    segments.append((cur_start, combined[-1][0], "未恢复"))

print(f"==== 组合(红利+A500+科创综指等权) 净值回撤 ====")
print(f"数据范围: {common[0]} ~ {common[-1]} ({len(common)}交易日)")
print(f"最终净值: {combined[-1][1]:.2f} | 峰值: {peak:.2f} ({peak_date})")
print(f"最深回撤: {max_dd * 100:.1f}% (谷底 {trough_date})")
print(f"最长回撤持续: {max((days(s, e) for s, e, _ in segments), default=0)}天")
print("回撤段明细(>5天):")
for s, e, tag in segments:
    dur = days(s, e)
    if dur > 5 or tag == "未恢复":
        print(f"  {s} -> {e}  {dur}天  {tag}")

# 单轮回本天数(修正: 从买入次日起)
print()
print("==== 单轮: 买入后回到成本线的天数 ====")
for code in codes:
    rows = get_by_code(code)[::-1]
    res = compute_trades(code, rows, t_pct=t_pct, m_pct=m_pct, kc_idx_rows=kc_idx, hs300_rows=hs300)
    trades = res["trades"]
    buy = None
    for t in trades:
        if t["action"] == "BUY":
            buy = t
            continue
        if buy:
            idx = next((i for i, r in enumerate(rows) if r["date"] == buy["date"]), None)
            cost = buy["price"]
            back_date = None
            min_low = 0
            for r in rows[idx + 1 :]:
                if back_date is None and (r["close_price"] or 0) >= cost:
                    back_date = r["date"]
                low = (r["close_price"] or cost) / cost - 1
                if low < min_low:
                    min_low = low
            if back_date is None:
                back_date = rows[-1]["date"]
                tag = "至今未回本"
            else:
                tag = "回本"
            print(
                f"  {names[code]} {buy['date']}买@{cost:.3f}: 最深浮亏{min_low * 100:+.1f}%, 次日之后{max(days(buy['date'], back_date) - 1, 0)}天{tag}"
            )
            buy = None
