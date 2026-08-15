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
t_pct = percentile_series([r.get("date") for r in turnover], [turnover_value(r) for r in turnover], SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
m_pct = percentile_series([r.get("date") for r in margin], [r.get("fin_balance_yi") for r in margin], SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
kc_idx = get_by_code("589680")[::-1]
hs300 = get_by_code("510300")[::-1]

def simulate(rows, buys, sell_rule, target=0.0):
    """用策略的 BUY 信号 + 自定义卖出规则模拟轮次。sell_rule: 收盘价>=成本*(1+target) 即卖(当日收盘价成交)。跌破成本不卖。"""
    closes = [r.get("close_price") or 0 for r in rows]
    by_date = {r["date"]: r for r in rows}
    rounds = []
    i = 0
    n = len(rows)
    while i < n:
        d = rows[i]["date"]
        if d in buys:
            cost = rows[i]["close_price"] or 0
            buy_date = d
            # 找卖出日: 从下一日起, 收盘 >= 成本*(1+target) 即卖
            sell_date = None
            sell_price = None
            j = i + 1
            while j < n:
                c = closes[j]
                if sell_rule == "profit" and c >= cost * (1 + target):
                    sell_date, sell_price = rows[j]["date"], c
                    break
                j += 1
            if sell_date:
                ret = (sell_price - cost) / cost * 100
                rounds.append((buy_date, sell_date, ret))
                i = j  # 跳到卖出日后继续找下一个买入信号
            else:
                # 持有至今
                last_c = closes[-1]
                ret = (last_c - cost) / cost * 100
                rounds.append((buy_date, None, ret))
                break
        i += 1
    return rounds

codes = ["515080", "159352", "589680"]
names = {"515080": "红利", "159352": "A500", "589680": "科创综指"}

results = {}
for rule_name, target in [("原策略", None), ("有利润就卖(+0%)", 0.0), ("利润+2%卖", 0.02), ("利润+5%卖", 0.05), ("利润+10%卖", 0.10)]:
    all_sells = []
    detail = []
    for code in codes:
        rows = get_by_code(code)[::-1]
        res = compute_trades(code, rows, t_pct=t_pct, m_pct=m_pct, kc_idx_rows=kc_idx, hs300_rows=hs300)
        if rule_name == "原策略":
            rounds = [(r["buy_date"], r.get("sell_date"), r["return_pct"]) for r in res.get("metrics", {}).get("rounds", [])]
        else:
            buys = set(t["date"] for t in res["trades"] if t["action"] == "BUY")
            rounds = simulate(rows, buys, "profit", target)
        for b, s, ret in rounds:
            detail.append((names[code], b, s, ret))
            if s:
                all_sells.append(s)
    all_sells.sort()
    gaps = [days(all_sells[i-1], all_sells[i]) for i in range(1, len(all_sells))]
    max_gap = max(gaps) if gaps else 0
    n_rounds = len(detail)
    rets = [r for _, _, _, r in detail if r is not None]
    total = sum(max(r, 0) for r in rets)  # 简单累计(非复利)
    results[rule_name] = {"n": n_rounds, "max_gap": max_gap, "detail": detail}
    print(f"{rule_name}: {n_rounds}轮 | 最长断档 {max_gap}天 | 轮次明细:")
    for name, b, s, r in sorted(detail, key=lambda x: x[1]):
        print(f"    {name} {b} -> {s or '持有中'}  {r:+.1f}%")
    print()