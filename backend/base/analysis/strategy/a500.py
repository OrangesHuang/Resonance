"""中证A500 (159352) — 复用沪深300买卖点日期。

核心认知:
  A500与沪深300成分股高度重叠, 走势几乎一致。A500自身不产生买卖信号,
  完全由沪深300(510300)的通用策略决定买卖日期, 再映射到A500的价格上。

  A500的数据仅用于展示(价格/收益), 不参与信号生成。

算法:
  1. 对510300运行通用策略 `_run_default`(与页面「共振买卖点」同一实现,
     含 P1-P5 全部买入路径 — 曾因 a500 内嵌旧版 v5 逻辑漏掉 P5 恐慌吸筹
     导致买卖点与 510300 不一致, 如 2026-03-23 买入缺失)
  2. 提取买卖点日期集合
  3. 在A500价格序列上查找对应日期, 构建A500交易记录
  4. 计算A500口径的收益指标
"""

from __future__ import annotations

A500_CODE = "159352"
HS300_CODE = "510300"


def run_a500_strategy(a500_rows, hs300_rows, t_pct, m_pct):
    """用沪深300的买卖日期映射到A500价格(信号来源与 router._run_default 完全一致)。"""
    from base.analysis.strategy.router import _run_default

    hs_result = _run_default(hs300_rows, t_pct, m_pct)
    trade_map = {t["date"]: t["action"] for t in hs_result.get("trades", [])}

    a500_by_date = {r["date"]: r for r in a500_rows}
    trades = []
    for d in sorted(trade_map):
        if d not in a500_by_date:
            continue
        row = a500_by_date[d]
        trades.append({"date": d, "action": trade_map[d], "price": row["close_price"], "reason": "复用沪深300信号"})

    position = 1.0 if trades and trades[-1]["action"] == "BUY" else 0.0
    last_close = a500_rows[-1].get("close_price", 0) if a500_rows else 0
    metrics = _calc_metrics(trades, last_close, position)
    return {"code": A500_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}


def _calc_metrics(trades, last_close, position):
    rounds = []
    buy_price = buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price is not None:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append(
                {
                    "buy_date": buy_date,
                    "sell_date": t["date"],
                    "buy_price": buy_price,
                    "sell_price": t["price"],
                    "return_pct": round(ret, 2),
                }
            )
            buy_price = None
    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append(
            {
                "buy_date": buy_date,
                "sell_date": None,
                "buy_price": buy_price,
                "sell_price": last_close,
                "return_pct": round(ret, 2),
            }
        )
    total_ret = 1.0
    wins = 0
    for r in rounds:
        total_ret *= 1 + r["return_pct"] / 100
        if r["return_pct"] > 0:
            wins += 1
    n = len(rounds) or 1
    return {
        "rounds": rounds,
        "total_return_pct": round((total_ret - 1) * 100, 2),
        "round_count": len(rounds),
        "win_count": wins,
        "win_rate": round(wins / n * 100, 1),
        "trade_count": len(trades),
    }
