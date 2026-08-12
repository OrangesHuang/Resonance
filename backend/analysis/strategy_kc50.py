"""科创50 (588000) — 复用科创综指买卖点日期。

核心认知:
  科创50博弈太剧烈, 盘面杂乱, 自身信号噪音大。
  科创综指(589680)体量更小、噪音更少, 更能反映科技板块真实走势,
  且已有成熟的专属策略(strategy_kc.py)。
  科创50自身不产生买卖信号, 完全由科创综指专属策略决定买卖日期,
  再映射到科创50的价格上。

算法:
  1. 对科创综指(589680)运行 strategy_kc.run_kc_strategy
  2. 提取买卖点日期
  3. 在科创50价格序列上查找对应日期, 构建交易记录
"""

KC50_CODE = "588000"
KC_IDX_CODE = "589680"


def run_kc50_strategy(kc50_rows, kc_idx_rows):
    """用科创综指的买卖日期映射到科创50价格。"""
    from analysis.strategy_kc import run_kc_strategy

    kc_result = run_kc_strategy(kc_idx_rows)
    kc_trades = kc_result["trades"]

    kc50_by_date = {r["date"]: r for r in kc50_rows}
    trades = []
    for t in kc_trades:
        d = t["date"]
        if d not in kc50_by_date:
            continue
        row = kc50_by_date[d]
        trades.append({
            "date": d, "action": t["action"],
            "price": row["close_price"],
            "reason": "复用科创综指信号"
        })

    position = 1.0 if trades and trades[-1]["action"] == "BUY" else 0.0
    last_close = kc50_rows[-1].get("close_price", 0) if kc50_rows else 0
    metrics = _calc_metrics(trades, last_close, position)
    return {"code": KC50_CODE, "trades": trades,
            "metrics": metrics, "holding": position > 0}


def _calc_metrics(trades, last_close, position):
    rounds = []
    buy_price = buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price is not None:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append({"buy_date": buy_date, "sell_date": t["date"],
                           "buy_price": buy_price, "sell_price": t["price"],
                           "return_pct": round(ret, 2)})
            buy_price = None
    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append({"buy_date": buy_date, "sell_date": None,
                       "buy_price": buy_price, "sell_price": last_close,
                       "return_pct": round(ret, 2)})
    total_ret = 1.0
    wins = 0
    for r in rounds:
        total_ret *= (1 + r["return_pct"] / 100)
        if r["return_pct"] > 0:
            wins += 1
    n = len(rounds) or 1
    return {"rounds": rounds,
            "total_return_pct": round((total_ret - 1) * 100, 2),
            "round_count": len(rounds), "win_count": wins,
            "win_rate": round(wins / n * 100, 1),
            "trade_count": len(trades)}
