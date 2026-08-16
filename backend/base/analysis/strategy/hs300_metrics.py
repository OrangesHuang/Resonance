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


def build_danger_zone(rows: list[dict], trades: list[dict], zone_start: str, min_gap_days: int = 60) -> dict | None:
    """危险区: zone_start 后第一段长空仓(卖出后 >=min_gap 个交易日无买点)。

    数据驱动无时间硬编码: 2021-03-05 顶部卖出 2 日后 03-09 重新买入属轮间
    衔接不标; 2021-07-27 假低位轮认错卖出后 9 个月无买点(熊市初期+崩盘
    前夜, 绝望底门槛持续拦截)才标危险区。zone_start 之前的区段不标。
    """
    if not rows or not trades:
        return None
    idx = {r["date"]: i for i, r in enumerate(rows)}
    sell_d, buy_d = None, None
    for t in trades:
        if t["date"] < zone_start:
            continue
        if t["action"] == "SELL":
            sell_d, buy_d = t["date"], None
        elif sell_d is not None:
            gap = idx.get(t["date"], 0) - idx.get(sell_d, 0)
            if gap >= min_gap_days:
                buy_d = t["date"]
                break
            sell_d, buy_d = None, None
    if not sell_d or not buy_d:
        return None
    bi = idx.get(buy_d, 0)
    return {
        "start": sell_d,
        "end": rows[bi - 1]["date"] if bi > 0 else buy_d,
        "label": "危险区·无买点",
        "reason": "跌势未成熟/承接不足, 策略判定无博弈机会, 主动空仓",
    }
