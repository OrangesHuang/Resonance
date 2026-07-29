"""V2 信号决策层 + 回测 — 纯函数模块。

将连续信号强度转化为仓位调整动作，并支持回测评估。
"""

import math

from config import (
    SIGNAL_BUY_THRESHOLD, SIGNAL_SELL_THRESHOLD,
    V2_POSITION_MAX, V2_POSITION_STEP, V2_MIN_HOLD_DAYS, V2_COOLDOWN_DAYS,
    V2_COST_RATE,
    BACKTEST_INIT_CAPITAL, TRADING_DAYS_PER_YEAR,
)


def decide_position(
    signal: float,
    current_level: int,
    hold_days: int = 0,
    cooldown_days: int = 0,
) -> tuple[int, str, str]:
    """单日仓位决策。

    Args:
        signal: V2 信号强度 ∈ [-1, 1]
        current_level: 当前仓位份数 (0 ~ V2_POSITION_MAX)
        hold_days: 当前已持仓天数
        cooldown_days: 距上一次交易的天数

    Returns:
        (new_level, action, reason)
    """
    # 交易冷却期：防止信号扎堆导致连续多日重复交易
    if cooldown_days < V2_COOLDOWN_DAYS:
        return (current_level, "HOLD",
                f"冷却期({cooldown_days}/{V2_COOLDOWN_DAYS}天)")

    if hold_days < V2_MIN_HOLD_DAYS and current_level > 0:
        if signal > SIGNAL_BUY_THRESHOLD and current_level < V2_POSITION_MAX:
            return (current_level + V2_POSITION_STEP, "BUY",
                    f"信号={signal:.2f}>买入阈值, 加仓{V2_POSITION_STEP}份")
        return (current_level, "HOLD",
                f"持仓{hold_days}天<{V2_MIN_HOLD_DAYS}天, 禁止卖出")

    if signal > SIGNAL_BUY_THRESHOLD and current_level < V2_POSITION_MAX:
        return (current_level + V2_POSITION_STEP, "BUY",
                f"信号={signal:.2f}>买入阈值, 加仓{V2_POSITION_STEP}份")
    if signal < -SIGNAL_SELL_THRESHOLD and current_level > 0:
        return (max(0, current_level - V2_POSITION_STEP), "SELL",
                f"信号={signal:.2f}<-卖出阈值, 减仓{V2_POSITION_STEP}份")
    return (current_level, "HOLD", "")


def run_backtest_v2(
    signals: list[dict],
    closes: list[float],
    cost_rate: float = V2_COST_RATE,
) -> dict:
    """V2 信号回测。

    Args:
        signals: 升序信号序列 [{"date", "signal"}, ...]
        closes: 等长收盘价序列
        cost_rate: 单边交易成本

    Returns:
        {metrics, benchmark, trades, equity_curve}
    """
    n = len(signals)
    if n == 0:
        return {"metrics": {}, "benchmark": {}, "trades": [], "equity_curve": []}

    level = 0
    hold_days = 0
    cooldown = V2_COOLDOWN_DAYS  # 初始无冷却
    trades = []
    targets = []

    for i in range(n):
        sig = signals[i]
        new_level, action, reason = decide_position(
            sig["signal"], level, hold_days, cooldown)

        if action == "BUY" or action == "SELL":
            hold_days = 0
            cooldown = 0
        else:
            if level > 0:
                hold_days += 1
            cooldown += 1

        if action != "HOLD":
            trades.append({
                "date": sig["date"], "action": action,
                "from_pos": round(level / V2_POSITION_MAX, 2),
                "to_pos": round(new_level / V2_POSITION_MAX, 2),
                "signal": sig["signal"], "price": closes[i],
                "reason": reason,
            })
        level = new_level
        targets.append(level / V2_POSITION_MAX)

    # T+1 执行滞后
    shifted = [0.0, 0.0] + targets[:-2] if len(targets) > 2 else [0.0] * len(targets)
    effective = shifted[:n]

    strat_returns = []
    bench_returns = []
    equity = BACKTEST_INIT_CAPITAL
    equity_curve = []

    for t in range(n):
        if t == 0:
            strat_returns.append(0.0)
            bench_returns.append(0.0)
        else:
            day_r = (closes[t] - closes[t - 1]) / closes[t - 1] if closes[t - 1] else 0.0
            pos = effective[t]
            cost = 0.0
            if t >= 2 and effective[t] != effective[t - 1]:
                cost = abs(effective[t] - effective[t - 1]) * cost_rate
            strat_returns.append(pos * day_r - cost)
            bench_returns.append(day_r)
        equity *= (1 + strat_returns[t])
        equity_curve.append({
            "date": signals[t]["date"], "equity": round(equity, 2),
            "position": effective[t],
        })

    metrics = _compute_metrics(strat_returns, len(trades))
    bench_metrics = _compute_metrics(bench_returns, 0)
    return {"metrics": metrics, "benchmark": bench_metrics,
            "trades": trades, "equity_curve": equity_curve}


def _compute_metrics(returns: list[float], trade_count: int) -> dict:
    n = len(returns)
    if n == 0:
        return {}
    total_ret = 1.0
    peak = 1.0
    dd = 0.0
    for r in returns:
        total_ret *= (1 + r)
        if total_ret > peak:
            peak = total_ret
        d = (peak - total_ret) / peak
        if d > dd:
            dd = d

    total_return = (total_ret - 1) * 100
    years = n / TRADING_DAYS_PER_YEAR if n > 0 else 0.0
    annual_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100 if years > 0 else 0.0

    mean_r = sum(returns) / n if n > 0 else 0.0
    var = sum((r - mean_r) ** 2 for r in returns) / n if n > 1 else 0.0
    daily_vol = math.sqrt(var)
    annual_vol = daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (mean_r / daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)) if daily_vol > 0 else 0.0

    exposure = sum(1 for r in returns if r != 0.0) / n if n else 0.0
    return {
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "annual_vol": round(annual_vol, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(dd * 100, 2),
        "days": n, "exposure_pct": round(exposure * 100, 1),
        "trade_count": trade_count,
    }
