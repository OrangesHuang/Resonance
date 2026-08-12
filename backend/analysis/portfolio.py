"""组合回测纯函数: 8 标的统一仓位分配逻辑(924 后)。

规则:
- 同一天的所有买入信号作为整体处理, 不逐个触发降仓
- 同日 N 个新买: 优先各 2 单位(25%), 钱不够则各 1 单位(12.5%)
- 仍不够时清仓最早 1 单位持仓腾出资金
- 先卖出 → 再批量买入 → 最后余钱升仓(最近买入的先升)
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
    sold_for_cash: set[str] = set()
    frozen_cash = 0.0
    for d in dates:
        # 当日事件
        day_events = []
        while idx < len(events) and events[idx][0] == d:
            day_events.append(events[idx])
            idx += 1

        sold_by_signal: set[str] = set()

        # 1) 卖出信号
        for _, code, action, sig_date in day_events:
            if action != "SELL" or code not in positions:
                continue
            px = price_of(code, d)
            p = positions.pop(code)
            proceeds = p["shares"] * px
            cash += proceeds
            frozen_cash += proceeds
            sold_by_signal.add(code)
            trade_log.append({"date": d, "signal_date": sig_date,
                              "code": code, "kind": "SELL",
                              "units": p["units"], "price": px,
                              "amount": round(p["shares"], 6)})

        # 2) 买入信号: 同日所有 BUY 作为整体处理
        buy_events = [(cd, co, sd) for cd, co, act, sd in day_events
                      if act == "BUY" and co not in positions
                      and not (co in sold_for_cash and co not in sold_by_signal)]
        if buy_events:
            n = len(buy_events)
            eq = equity_at(d)
            cost2 = 2 * unit * eq
            cost1 = unit * eq
            per_cost = cost2
            buy_units = 2
            if cash + EPS < cost2 * n:
                per_cost = cost1
                buy_units = 1
            # 资金不足时: 先清仓旧 1u 持仓, 再按可用资金买尽可能多
            if cash + EPS < per_cost * n:
                while cash + EPS < per_cost:
                    one_unit = [(c, p) for c, p in positions.items()
                                if p["units"] == 1]
                    if not one_unit:
                        break
                    oldest = min(one_unit, key=lambda x: x[1]["buy_date"])
                    c, p = oldest
                    px = price_of(c, d)
                    cash += p["shares"] * px
                    sold_for_cash.add(c)
                    trade_log.append({"date": d,
                                      "signal_date": buy_events[0][2],
                                      "code": c, "kind": "LIQUIDATE",
                                      "units": 1, "price": px,
                                      "amount": round(p["shares"], 6)})
                    del positions[c]
                # 按可用资金买尽可能多(不再 all-or-nothing)
                affordable = min(n, int((cash + EPS) / per_cost))
                buy_events = buy_events[:affordable]
            for _, code, sig_date in buy_events:
                px = price_of(code, d)
                shares = per_cost / px
                cash -= per_cost
                frozen_cash = max(0.0, frozen_cash - per_cost)
                positions[code] = {"shares": shares, "units": buy_units,
                                   "buy_date": d}
                sold_for_cash.discard(code)
                trade_log.append({"date": d, "signal_date": sig_date,
                                  "code": code, "kind": "BUY",
                                  "units": buy_units, "price": px,
                                  "amount": round(shares, 6)})

        # 3) 余钱升仓至 2 单位(最近买入的先升, 不用冻结资金)
        while True:
            cost = unit * equity_at(d)
            available = cash - frozen_cash
            if available + EPS < cost:
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

        sold_for_cash.clear()

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
