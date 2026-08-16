"""沪深300 策略输出组装: 轮次指标 + 危险区(纯函数, 无 I/O)。"""

from __future__ import annotations


def calc_metrics(trades: list[dict], last_close: float, position: float) -> dict:
    rounds = []
    buy_price = None
    buy_date = None
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

    return {
        "rounds": rounds,
        "total_return_pct": round((total_ret - 1) * 100, 2),
        "round_count": len(rounds),
        "win_count": wins,
        "win_rate": round(wins / len(rounds) * 100, 1) if rounds else 0,
        "trade_count": len(trades),
    }


def build_danger_zone(rows: list[dict], first_buy_idx: int | None) -> dict | None:
    # 危险区: 首个买点之前的空仓段(2021-01-04 数据起点 ~ 2022-04-20, 15个月无买点):
    # 2021 全年 ma250 未预热且处历史大顶回落(2021-02-10 5.39); 2022-01-28 绝望底被
    # 份额承接门槛拦(sp66<75, 买入后 3 月 -15%); 2022-03-15 政策底被 sp47 拦
    # (4 月还有市场底)。每次拦截都避免了一次亏损, 该段策略主动空仓。
    if first_buy_idx is None or first_buy_idx <= 0 or not rows:
        return None
    return {
        "start": rows[0]["date"],
        "end": rows[first_buy_idx - 1]["date"],
        "label": "危险区·无买点",
        "reason": "跌势未成熟/承接不足, 策略判定无博弈机会, 主动空仓",
    }
