"""共振仓位管理策略 — 纯函数，无 I/O。

仓位模型: 本金分 3 份，红灯共振每次减 1 份，绿灯共振每次加 1 份。
"""

import math

from config import (
    RESONANCE_VERDICT_N,
    BACKTEST_INIT_CAPITAL,
    BACKTEST_COST_RATE,
    BACKTEST_RISK_FREE,
    TRADING_DAYS_PER_YEAR,
)

TRANCHES = 3
TRANCHE_SIZE = 1.0 / TRANCHES


def step(level: int, red: int, green: int) -> tuple[int, str, str]:
    """单日决策。level = 当前持有份数(0~3)。

    返回 (new_level, action, reason)。
    """
    danger = red >= RESONANCE_VERDICT_N
    opp = green >= RESONANCE_VERDICT_N

    if danger and level > 0:
        return level - 1, "SELL", f"危险共振(red≥{RESONANCE_VERDICT_N})→减1/3"
    if opp and level < TRANCHES:
        return level + 1, "BUY", f"机会共振(green≥{RESONANCE_VERDICT_N})→加1/3"
    return level, "HOLD", ""


def _shift_targets(targets: list[float]) -> list[float]:
    """T+1 执行滞后: day-t 收益使用 target[t-2] 仓位。"""
    shifted = [0.0, 0.0]
    shifted.extend(targets[:-2])
    return shifted


def compute_metrics(
    returns: list[float],
    init_capital: float = BACKTEST_INIT_CAPITAL,
) -> dict:
    n = len(returns)
    if n == 0:
        return {"total_return": 0, "annual_return": 0, "annual_vol": 0,
                "sharpe": 0, "max_drawdown": 0, "days": 0}

    equity = init_capital
    peak = init_capital
    max_dd = 0.0
    for r in returns:
        equity *= (1 + r)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    total_return = (equity - init_capital) / init_capital
    years = n / TRADING_DAYS_PER_YEAR
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / n if n > 1 else 0.0
    daily_vol = math.sqrt(var)
    annual_vol = daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)

    rf_daily = BACKTEST_RISK_FREE / TRADING_DAYS_PER_YEAR
    excess = mean_r - rf_daily
    sharpe = (excess / daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)) if daily_vol > 0 else 0.0

    return {
        "total_return": round(total_return * 100, 2),
        "annual_return": round(annual_return * 100, 2),
        "annual_vol": round(annual_vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "days": n,
    }


def run_backtest(
    signals: list[dict],
    closes: list[float],
    dates: list[str],
    cost_rate: float = BACKTEST_COST_RATE,
) -> dict:
    """执行回测。

    signals: [{red, green}, ...] 与 dates/closes 等长、同序(升序)。
    返回 {metrics, benchmark, trades, positions, equity_curve}。
    """
    n = len(signals)
    targets: list[float] = []
    trades: list[dict] = []
    level = 0

    for i in range(n):
        sig = signals[i]
        new_level, action, reason = step(level, sig["red"], sig["green"])
        if action != "HOLD":
            trades.append({
                "date": dates[i],
                "action": action,
                "from_pos": round(level * TRANCHE_SIZE, 2),
                "to_pos": round(new_level * TRANCHE_SIZE, 2),
                "red": sig["red"],
                "green": sig["green"],
                "reason": reason,
                "price": closes[i],
            })
        level = new_level
        targets.append(level * TRANCHE_SIZE)

    effective = _shift_targets(targets)

    strat_returns: list[float] = []
    bench_returns: list[float] = []
    equity = BACKTEST_INIT_CAPITAL
    equity_curve: list[dict] = []

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
            sr = pos * day_r - cost
            strat_returns.append(sr)
            bench_returns.append(day_r)

        equity *= (1 + strat_returns[t])
        equity_curve.append({"date": dates[t], "equity": round(equity, 2),
                             "position": effective[t]})

    exposure = sum(1 for p in effective if p > 0) / n if n else 0.0
    metrics = compute_metrics(strat_returns)
    metrics["exposure_pct"] = round(exposure * 100, 1)
    metrics["trade_count"] = len(trades)

    bench_metrics = compute_metrics(bench_returns)

    return {
        "metrics": metrics,
        "benchmark": bench_metrics,
        "trades": trades,
        "positions": effective,
        "equity_curve": equity_curve,
    }
