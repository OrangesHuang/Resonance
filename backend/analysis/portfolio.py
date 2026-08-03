"""组合回测纯函数: 8 标的统一仓位分配逻辑(924 后)。

规则:
- 每个标的买入信号 → 至少持有 1 单位(12.5%)
- 余钱充足时仓位可升至 2 单位(25%)
- 其他标的发出买入信号 → 原有 2 单位仓位降至 1 单位释放资金
- 先卖出 → 再买入 → 最后余钱升仓(最近买入的先升)
- 成交时点: 信号在收盘后确认, 只能在下一个交易日按当日收盘价成交

本模块无 I/O 副作用, 数据由调用方注入; 权益归一化为 1.0 起
(100 万初始 × 每份 1 元 = 100 万份)。
"""
from typing import Optional

UNIT = 0.125          # 1 单位 = 总权益 12.5%
EPS = 1e-9            # 现金比较容差(浮点)


def simulate(trades_by_code: dict[str, list[dict]],
             price_map: dict[str, dict[str, float]],
             dates: list[str],
             unit: float = UNIT) -> dict:
    """按仓位规则模拟组合, 逐日估值; 信号次日成交。

    trades_by_code: {code: [{date, action(BUY/SELL), price}]}
    price_map:      {code: {date: close}}
    dates:          逐日估值的全部交易日(升序, 含信号日)
    """
    # 信号日 → 下一个交易日(成交日)
    next_day: dict[str, Optional[str]] = {}
    for i, d in enumerate(dates):
        next_day[d] = dates[i + 1] if i + 1 < len(dates) else None

    # 事件流: 信号次日成交, 同日先卖后买
    events = []
    for code, trades in trades_by_code.items():
        for t in trades:
            exec_d = next_day.get(t["date"])
            if exec_d is None:
                continue  # 最后一个交易日无次日, 无法成交
            events.append((exec_d, code, t["action"], t["date"]))
    events.sort(key=lambda e: (e[0], 0 if e[2] == "SELL" else 1))

    def price_of(code: str, d: str) -> float:
        px = price_map.get(code, {}).get(d)
        if px is not None:
            return px
        prev = [price_map[code][x] for x in dates
                if x <= d and price_map[code].get(x) is not None]
        return prev[-1] if prev else 0.0

    positions: dict[str, dict] = {}   # code -> {shares, units(1/2), buy_date}
    cash = 1.0
    trade_log: list[dict] = []
    history: list[dict] = []

    def equity_at(d: str) -> float:
        total = cash
        for code, p in positions.items():
            total += p["shares"] * price_of(code, d)
        return total

    idx = 0
    for d in dates:
        # 当日事件
        day_events = []
        while idx < len(events) and events[idx][0] == d:
            day_events.append(events[idx])
            idx += 1

        # 1) 卖出信号
        for _, code, action, sig_date in day_events:
            if action != "SELL" or code not in positions:
                continue
            px = price_of(code, d)
            p = positions.pop(code)
            cash += p["shares"] * px
            trade_log.append({"date": d, "signal_date": sig_date,
                              "code": code, "kind": "SELL",
                              "units": p["units"], "price": px,
                              "amount": round(p["shares"], 6)})

        # 2) 买入信号: 需要至少 1 单位
        for _, code, action, sig_date in day_events:
            if action != "BUY" or code in positions:
                continue
            # 先降仓释放资金: 所有 2 单位降至 1 单位
            for c, p in list(positions.items()):
                if p["units"] == 2:
                    sell_shares = p["shares"] / 2
                    p["shares"] -= sell_shares
                    p["units"] = 1
                    cash += sell_shares * price_of(c, d)
                    trade_log.append({"date": d, "signal_date": sig_date,
                                      "code": c, "kind": "REDUCE",
                                      "units": 1, "price": price_of(c, d),
                                      "amount": round(sell_shares, 6)})
            cost = unit * equity_at(d)
            if cash + EPS < cost:
                continue  # 现金不足(满配 8×12.5%=100% 时不会发生)
            px = price_of(code, d)
            shares = cost / px
            cash -= cost
            positions[code] = {"shares": shares, "units": 1, "buy_date": d}
            trade_log.append({"date": d, "signal_date": sig_date,
                              "code": code, "kind": "BUY",
                              "units": 1, "price": px, "amount": round(shares, 6)})

        # 3) 余钱升仓至 2 单位(最近买入的先升)
        while True:
            cost = unit * equity_at(d)
            if cash + EPS < cost:
                break
            one_unit = [c for c, p in positions.items() if p["units"] == 1]
            if not one_unit:
                break
            c = max(one_unit, key=lambda x: positions[x]["buy_date"])
            px = price_of(c, d)
            shares = cost / px
            cash -= cost
            positions[c]["shares"] += shares
            positions[c]["units"] = 2
            trade_log.append({"date": d, "signal_date": d,
                              "code": c, "kind": "TOPUP",
                              "units": 2, "price": px, "amount": round(shares, 6)})

        # 逐日估值
        equity = equity_at(d)
        invested = equity - cash
        history.append({"date": d,
                        "equity": round(equity, 6),
                        "invested": round(invested, 6),
                        "position_pct": round(invested / equity * 100, 1)
                        if equity > 0 else 0.0})

    peak = 0.0
    max_dd = 0.0
    invested_sum = 0.0
    for h in history:
        peak = max(peak, h["equity"])
        if peak > 0:
            max_dd = max(max_dd, (peak - h["equity"]) / peak)
        invested_sum += h["position_pct"]
    avg_position = invested_sum / len(history) if history else 0.0

    final = history[-1]["equity"] if history else 1.0
    return {
        "history": history,
        "trade_log": trade_log,
        "final_equity": final,
        "total_return_pct": round((final - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "avg_position_pct": round(avg_position, 1),
        "open_positions": [{"code": c, "units": p["units"], "buy_date": p["buy_date"]}
                           for c, p in positions.items()],
    }
