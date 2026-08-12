"""中证A500 (159352) — 复用沪深300买卖点日期。

核心认知:
  A500与沪深300成分股高度重叠, 走势几乎一致。A500自身不产生买卖信号,
  完全由沪深300(510300)的v5策略决定买卖日期, 再映射到A500的价格上。

  A500的数据仅用于展示(价格/收益), 不参与信号生成。

算法:
  1. 对510300运行v5通用策略(pp+吸筹/出货+成交额分位+融资分位)
  2. 提取买卖点日期集合
  3. 在A500价格序列上查找对应日期, 构建A500交易记录
  4. 计算A500口径的收益指标
"""

from __future__ import annotations

import math

A500_CODE = "159352"
HS300_CODE = "510300"

SELL_PP = 80
SELL_MP = 90
MIN_HOLD = 10
VOL_LOOKBACK = 20
V5_TRADE_START = "2024-10-08"


def _run_v5_dates(rows, t_pct, m_pct):
    """在任意ETF上运行v5逻辑, 返回 {日期: 'BUY'/'SELL'} 映射。"""
    trade_map = {}
    position = 0.0
    hold_days = 0
    sell_threshold = 1
    dist_count = 0

    for i, row in enumerate(rows):
        d = row["date"]
        if d not in t_pct and d not in m_pct:
            continue
        close = row.get("close_price")
        if close is None:
            continue
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        tp = t_pct.get(d, {}).get("percentile")
        mp = m_pct.get(d, {}).get("percentile")

        action = None

        if position == 0 and d >= V5_TRADE_START:
            pp_green = pp is not None and pp <= 40
            pp_extreme = pp is not None and pp <= 10
            td_green = td == "ACCUMULATE"
            sp_green = sp is not None and sp >= 65
            tp_cold = tp is not None and tp <= 10
            cp_high = cp is not None and cp > 50
            if (
                pp_green
                and sp_green
                and td_green
                or pp_green
                and td_green
                and tp_cold
                or pp_extreme
                and td_green
                and cp_high
            ):
                action = "BUY"

        if position == 1:
            hold_days += 1
            if td == "DISTRIBUTE" and pp is not None and pp >= SELL_PP and mp is not None and mp >= SELL_MP:
                dist_count += 1
            if hold_days >= MIN_HOLD and td == "DISTRIBUTE" and dist_count >= sell_threshold:
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            dist_count = 0
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0 for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            sell_threshold = 1 if tp_cold else max(2, math.ceil(2 + ratio * 0.55))
            trade_map[d] = "BUY"
        elif action == "SELL":
            position = 0.0
            trade_map[d] = "SELL"

    return trade_map


def run_a500_strategy(a500_rows, hs300_rows, t_pct, m_pct):
    """用沪深300的买卖日期映射到A500价格。"""
    trade_map = _run_v5_dates(hs300_rows, t_pct, m_pct)

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
