"""组合回测纯函数: 8 标的统一仓位分配逻辑(924 后)。

规则:
- 每份金额 = 当日整体资金(卖出后快照)/标的数(unit), 随净值增长动态变大
- 同日多信号整体分配: 现金够全部 2 份 → 全部买 2 份;
  够全部 1 份 → 前 k 个信号买 2 份其余 1 份(k = (现金-n份)/份, 不赎回);
  不够全部 1 份 → 每信号最多 1 份; 现金 ≈ 半份以上直接全部花掉买入(不动持仓,
  容忍份金额随浮盈磨损), 现金不足半份才转仓腾资(卖旧买新: 优先减半最老 2u
  保底仓, 无 2u 才清最老 1u, 不碰当日买入持仓避免同日来回买卖, 凑够半份即停,
  不对同一持仓连续转出), 仍不足半份则记录 SKIP(资金不足), 不静默丢弃;
  转仓记录 kind=SWITCH 并带 to_code(转入目标)与 action(REDUCE/LIQUIDATE)
- 先卖出 → 再逐信号买入 → 最后余钱升仓(最近买入的先升, 每份成本同样固定)
- 成交时点: 信号在收盘后确认, 只能在下一个交易日按当日收盘价成交

本模块无 I/O 副作用, 数据由调用方注入; 权益归一化为 1.0 起
(100 万初始 × 每份 1 元 = 100 万份)。
"""
from typing import Optional

UNIT = 0.125          # 1 单位 = 整体资金的 12.5%(每份金额 = unit × 当日整体资金)
EPS = 1e-9            # 现金比较容差(浮点)
HALF_UNIT = 0.5       # 现金 ≥ 半份即视为可动用买入(份金额浮盈磨损容差), 低于此才赎回


def simulate(trades_by_code: dict[str, list[dict]],
             price_map: dict[str, dict[str, float]],
             dates: list[str],
             unit: float = UNIT) -> dict:
    """按仓位规则模拟组合, 逐日估值; 信号次日成交。

    trades_by_code: {code: [{date, action(BUY/SELL), price}]}
    price_map:      {code: {date: close}}
    dates:          逐日估值的全部交易日(升序, 含信号日)
    unit:           份数基准 = 1/标的数; 每份金额 = unit × 当日整体资金
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

        # 2) 买入信号: 同日整体规划份额(先到先买, 每份成本 = 当日整体资金/标的数)
        buy_events = [(cd, co, sd) for cd, co, act, sd in day_events
                      if act == "BUY" and co not in positions
                      and not (co in sold_for_cash and co not in sold_by_signal)]
        n = len(buy_events)
        if n:
            cost1 = unit * equity_at(d)   # 卖出后整体资金快照, 当日不变
            cost2 = 2 * cost1
            if cash + EPS >= n * cost2:
                two_limit = n            # 现金够全部 2 份
            elif cash + EPS >= n * cost1:
                # 前 k 个信号 2 份, 其余 1 份, 无需赎回
                two_limit = min(n, int((cash + EPS - n * cost1) / cost1))
            else:
                two_limit = -1           # 每信号最多 1 份, 不足时赎回兜底
        for i, (_, code, sig_date) in enumerate(buy_events):
            if i < two_limit:
                per_cost, buy_units = cost2, 2
            else:
                per_cost, buy_units = cost1, 1
            if cash + EPS < per_cost:
                if cash + EPS < HALF_UNIT * cost1:
                    # 现金不足半份: 赎回最老持仓腾资(优先 2u→1u 保住底仓,
                    # 不碰当日买入持仓避免同日来回买卖), 凑够半份即停,
                    # 绝不对同一持仓连续减仓
                    while cash + EPS < HALF_UNIT * cost1:
                        two_units = [(c, p) for c, p in positions.items()
                                     if p["units"] == 2 and p["buy_date"] != d]
                        if two_units:
                            c, p = min(two_units, key=lambda x: x[1]["buy_date"])
                            px = price_of(c, d)
                            half = p["shares"] / 2
                            p["shares"] -= half
                            p["units"] = 1
                            cash += half * px
                            frozen_cash += half * px
                            sold_for_cash.add(c)
                            trade_log.append({"date": d, "signal_date": sig_date,
                                              "code": c, "kind": "SWITCH",
                                              "to_code": code, "action": "REDUCE",
                                              "units": 1, "price": px,
                                              "amount": round(half, 6)})
                        else:
                            holders = [(c, p) for c, p in positions.items()
                                       if p["buy_date"] != d]
                            if not holders:
                                break
                            c, p = min(holders, key=lambda x: x[1]["buy_date"])
                            px = price_of(c, d)
                            proceeds = p["shares"] * px
                            cash += proceeds
                            frozen_cash += proceeds
                            sold_for_cash.add(c)
                            trade_log.append({"date": d, "signal_date": sig_date,
                                              "code": c, "kind": "SWITCH",
                                              "to_code": code, "action": "LIQUIDATE",
                                              "units": 1, "price": px,
                                              "amount": round(p["shares"], 6)})
                            del positions[c]
                    if cash + EPS < HALF_UNIT * cost1:
                        trade_log.append({"date": d, "signal_date": sig_date,
                                          "code": code, "kind": "SKIP",
                                          "units": 0,
                                          "price": price_of(code, d),
                                          "amount": 0.0})
                        continue
                # 现金≈半份以上(份金额随浮盈磨损导致略不足一份): 全部花掉买,
                # 尽量不动持仓
                per_cost = min(cash, cost1)
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

        # 3) 余钱升仓至 2 单位(最近买入的先升, 不用冻结资金, 每份成本动态)
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
    for h in history:
        peak = max(peak, h["equity"])
        if peak > 0:
            max_dd = max(max_dd, (peak - h["equity"]) / peak)
    empty_days = sum(1 for h in history if h["invested"] == 0)

    final = history[-1]["equity"] if history else 1.0
    return {
        "history": history,
        "trade_log": trade_log,
        "final_equity": final,
        "total_return_pct": round((final - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "empty_days": empty_days,
        "empty_days_pct": round(empty_days / len(history) * 100, 1)
        if history else 0.0,
        "open_positions": [{"code": c, "units": p["units"], "buy_date": p["buy_date"]}
                           for c, p in positions.items()],
    }
