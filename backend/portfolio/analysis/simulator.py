"""组合回测纯函数: 等权满仓调度。

规则(等权槽位模型):
- 初始 100% 现金; 首个 BUY → 全仓买入即满仓
- 新 BUY → 与现有持仓按总权益严格等权(1/m):
    target = pool / (现持仓数 + 新仓数), pool = 现金 + Σ持仓市值
    2a TRIM 超配持仓减至 target → 2b 逐个建新仓各 target → 2c REFILL 低配补至 target,
    完成后现金 ≈ 0(满仓恒等式)。同日多个 BUY 批量一次分配(终态与逐个串行
    等权相同, 但避免 TRIM 笔数二次方爆炸)
- SELL → 整仓清掉回现金, 剩余持仓【不再平衡上去】; 回款闲置,
  直到下一个 BUY 信号并入分配池(资金利用率自动恢复满仓)
- 同日同标的 SELL+BUY: 先清仓, BUY 允许重新建仓
- 成交时点: 信号收盘后确认, 下一交易日按当日收盘价成交

本模块无 I/O 副作用, 数据由调用方注入; 权益归一化为 1.0 起。
"""

from __future__ import annotations

REL_EPS = 1e-6  # 平衡容差: 市值偏离 target 超过该相对比例才 TRIM/REFILL
ZERO_EPS = 1e-9  # 现金归零容差(浮点)


def simulate(trades_by_code: dict[str, list[dict]], price_map: dict[str, dict[str, float]], dates: list[str]) -> dict:
    """按等权满仓规则模拟组合, 逐日估值; 信号次日成交。

    trades_by_code: {code: [{date, action(BUY/SELL), price}]}
    price_map:      {code: {date: close}}
    dates:          逐日估值的全部交易日(升序, 含信号日)
    """
    next_day: dict[str, str | None] = {}
    for i, d in enumerate(dates):
        next_day[d] = dates[i + 1] if i + 1 < len(dates) else None

    # 事件流: 信号次日成交; 同日先卖后买, 买入按代码序串行
    events = []
    for code, trades in trades_by_code.items():
        for t in trades:
            exec_d = next_day.get(t["date"])
            if exec_d is None:
                continue  # 最后一个交易日无次日, 无法成交
            events.append((exec_d, code, t["action"], t["date"]))
    events.sort(key=lambda e: (e[0], 0 if e[2] == "SELL" else 1, e[1]))

    def price_of(code: str, d: str) -> float:
        m = price_map.get(code, {})
        px = m.get(d)
        if px is not None:
            return px
        prev = [m[x] for x in dates if x <= d and m.get(x) is not None]
        return prev[-1] if prev else 0.0  # 缺失用最近前值填充

    positions: dict[str, dict] = {}  # code -> {shares, buy_date}
    cash = 1.0
    trade_log: list[dict] = []
    history: list[dict] = []

    def equity_at(d: str) -> float:
        total = cash
        for c, p in positions.items():
            total += p["shares"] * price_of(c, d)
        return total

    idx = 0
    for d in dates:
        day_events = []
        while idx < len(events) and events[idx][0] == d:
            day_events.append(events[idx])
            idx += 1
        if not day_events:
            equity = equity_at(d)
            invested = equity - cash
            history.append(
                {
                    "date": d,
                    "equity": round(equity, 6),
                    "invested": round(invested, 6),
                    "position_pct": round(invested / equity * 100, 1) if equity > 0 else 0.0,
                }
            )
            continue

        day_logs: list[dict] = []

        # 1) SELL: 整仓清掉回现金, 剩余持仓不再平衡上去
        for _, code, action, sig_date in day_events:
            if action != "SELL" or code not in positions:
                continue
            px = price_of(code, d)
            p = positions.pop(code)
            proceeds = p["shares"] * px
            cash += proceeds
            day_logs.append(
                {"date": d, "signal_date": sig_date, "code": code, "kind": "SELL", "price": px, "amount": proceeds}
            )

        # 2) BUY 批量等权: pool 含 SELL 闲置资金 → 自动"追加上一个卖点的钱"
        new_buys = [(code, sd) for _, code, action, sd in day_events if action == "BUY" and code not in positions]
        if new_buys:
            target = equity_at(d) / (len(positions) + len(new_buys))
            trig_sig = new_buys[0][1]  # TRIM/REFILL 归属的触发信号日
            # 2a TRIM: 超配持仓减至 target(回款 + 现金恰够建全部新仓 + 补低配)
            for c, p in list(positions.items()):
                cpx = price_of(c, d)
                val = p["shares"] * cpx
                if val > target * (1 + REL_EPS):
                    cut = val - target
                    p["shares"] -= cut / cpx
                    cash += cut
                    day_logs.append(
                        {"date": d, "signal_date": trig_sig, "code": c, "kind": "TRIM", "price": cpx, "amount": cut}
                    )
            # 2b 建新仓: 各花 target
            for code, sig_date in new_buys:
                px = price_of(code, d)
                if px <= 0:
                    continue
                buy_amt = min(target, cash)
                cash -= buy_amt
                positions[code] = {"shares": buy_amt / px, "buy_date": d}
                day_logs.append(
                    {"date": d, "signal_date": sig_date, "code": code, "kind": "BUY", "price": px, "amount": buy_amt}
                )
            # 2c REFILL: 低配持仓补至 target, 现金恰耗尽
            for c, p in positions.items():
                cpx = price_of(c, d)
                val = p["shares"] * cpx
                if val < target * (1 - REL_EPS) and cash > ZERO_EPS:
                    top = min(target - val, cash)
                    p["shares"] += top / cpx
                    cash -= top
                    day_logs.append(
                        {
                            "date": d,
                            "signal_date": trig_sig,
                            "code": c,
                            "kind": "REFILL",
                            "price": cpx,
                            "amount": top,
                        }
                    )

        if cash < ZERO_EPS:
            cash = 0.0

        # 成交后权重: 该仓市值 / 总权益
        equity = equity_at(d)
        for log in day_logs:
            pos = positions.get(log["code"])
            log["weight_pct"] = round(pos["shares"] * log["price"] / equity * 100, 2) if pos else 0.0
        trade_log.extend(day_logs)

        invested = equity - cash
        history.append(
            {
                "date": d,
                "equity": round(equity, 6),
                "invested": round(invested, 6),
                "position_pct": round(invested / equity * 100, 1) if equity > 0 else 0.0,
            }
        )

    peak = 0.0
    max_dd = 0.0
    for h in history:
        peak = max(peak, h["equity"])
        if peak > 0:
            max_dd = max(max_dd, (peak - h["equity"]) / peak)
    empty_days = sum(1 for h in history if h["invested"] <= ZERO_EPS)

    final = history[-1]["equity"] if history else 1.0
    return {
        "history": history,
        "trade_log": trade_log,
        "final_equity": final,
        "total_return_pct": round((final - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "empty_days": empty_days,
        "empty_days_pct": round(empty_days / len(history) * 100, 1) if history else 0.0,
        "open_positions": [{"code": c, "shares": p["shares"], "buy_date": p["buy_date"]} for c, p in positions.items()],
    }
