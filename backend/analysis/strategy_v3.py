"""V3 主力资金节奏策略 — 基于国家队行为特征的买卖点。

经实际数据验证的设计:
  买入: 恐慌放量 / 低位吸筹 / 极端低位 — 三个独立触发条件
  卖出: 高位出货 / 止盈 / 追踪止损 / 超时止损 — 四个独立退出条件

与 V2 的本质区别:
  - V2 是统计异常检测，没有"意图"判断，盈亏比倒挂
  - V3 是行为模式匹配：国家队买什么特征？卖什么特征？
"""

import math
from typing import Optional

# ===== 买入参数 (基于2024-01-22/2024-09-20/2025-04-07 真实数据校准) =====
PANIC_DROP = -2.0           # 恐慌跌幅 (%)
PANIC_VR = 2.0              # 恐慌量比
PANIC_PP_MAX = 30.0         # 恐慌位置上限
PANIC_SP_MIN = 65.0         # 恐慌份额下限

ACCUM_PP_MAX = 35.0         # 吸筹位置上限
ACCUM_SP_MIN = 65.0         # 吸筹份额下限
ACCUM_VR_MIN = 1.8          # 吸筹量比下限

EXTREME_PP_MAX = 20.0       # 极端低位位置上限
EXTREME_VR_MIN = 1.5        # 极端低位量比下限

# ===== 卖出参数 =====
DIST_PP_MIN = 80.0          # 出货位置下限
DIST_VR_MIN = 1.5           # 出货量比下限
TAKE_PROFIT_PCT = 15.0      # 止盈 (%)
TRAIL_STOP_PCT = 8.0        # 追踪回撤 (%)
STOP_LOSS_PCT = -8.0        # 硬止损 (%)
MAX_HOLD_DAYS = 90          # 最大持仓天数

MIN_HOLD = 5                # 最短持仓
COOLDOWN = 8                # 交易冷却期


def _calc_ma(closes: list[float], idx: int, period: int) -> float:
    start = max(0, idx - period + 1)
    return sum(closes[start:idx + 1]) / (idx - start + 1)


def run_v3_strategy(rows: list[dict]) -> dict:
    """执行 V3 策略。

    Args:
        rows: ETF 日线数据 (升序)，需包含 date, close_price, change_pct,
              volume, volume_ratio, price_position, share_prob, trade_direction

    Returns:
        {code, trades, metrics, holding}
    """
    n = len(rows)
    if n < 60:
        return {"code": "", "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]
    code = rows[0].get("code", "") if rows else ""

    trades: list[dict] = []
    position = 0.0
    buy_idx = 0
    cooldown_days = COOLDOWN
    hold_days = 0
    peak_since_buy = 0.0

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        chg = row.get("change_pct") or 0
        vr = row.get("volume_ratio") or 0
        pp = row.get("price_position")
        sp = row.get("share_prob")
        td = row.get("trade_direction")

        cooldown_days += 1
        action: Optional[str] = None
        reason = ""

        # ---- 买入 ----
        if position == 0 and cooldown_days >= COOLDOWN:
            is_accum = td == "ACCUMULATE"

            # P: 恐慌放量 — 暴跌+天量+份额暴增（国家队接飞刀）
            panic = (chg <= PANIC_DROP and vr >= PANIC_VR
                     and pp is not None and pp <= PANIC_PP_MAX
                     and sp is not None and sp >= PANIC_SP_MIN
                     and is_accum)

            # A: 低位吸筹 — 缩量或温和放量中悄悄吸筹
            accum = (is_accum and pp is not None and pp <= ACCUM_PP_MAX
                     and sp is not None and sp >= ACCUM_SP_MIN
                     and vr >= ACCUM_VR_MIN)

            # E: 极端低位 — 价格极度低迷+放量（跌无可跌）
            extreme = (is_accum and pp is not None and pp <= EXTREME_PP_MAX
                       and vr >= EXTREME_VR_MIN)

            if panic:
                action = "BUY"
                reason = (f"恐慌接筹: 跌{chg:.1f}%+量比{vr:.1f}"
                          f"+位置{pp:.0f}+份额{sp:.0f}")
            elif accum:
                action = "BUY"
                reason = (f"低位吸筹: 位置{pp:.0f}+份额{sp:.0f}"
                          f"+量比{vr:.1f}")
            elif extreme:
                action = "BUY"
                reason = f"极端低位: 位置{pp:.0f}+量比{vr:.1f}"

        # ---- 卖出 ----
        elif position > 0:
            hold_days += 1
            peak_since_buy = max(peak_since_buy, close)
            buy_price = trades[-1]["price"] if trades else close
            profit_pct = (close - buy_price) / buy_price * 100
            trail_dd = ((peak_since_buy - close) / peak_since_buy * 100
                        if peak_since_buy > 0 else 0)

            if hold_days < MIN_HOLD:
                continue

            # 检查各退出条件
            is_dist = td == "DISTRIBUTE"
            distrib_sell = (is_dist and pp is not None
                            and pp >= DIST_PP_MIN and vr >= DIST_VR_MIN)
            profit_take = profit_pct >= TAKE_PROFIT_PCT
            trail_sell = profit_pct > 3 and trail_dd >= TRAIL_STOP_PCT
            stop_loss = profit_pct <= STOP_LOSS_PCT
            time_out = hold_days >= MAX_HOLD_DAYS

            if distrib_sell:
                action = "SELL"
                reason = (f"高位出货: 位置{pp:.0f}+量比{vr:.1f}"
                          f"+浮盈{profit_pct:.0f}%")
            elif profit_take:
                action = "SELL"
                reason = f"止盈: +{profit_pct:.0f}%"
            elif trail_sell:
                action = "SELL"
                reason = f"追踪止损: 回撤{trail_dd:.1f}%"
            elif stop_loss:
                action = "SELL"
                reason = f"硬止损: {profit_pct:.0f}%"
            elif time_out:
                action = "SELL"
                reason = f"超时: 持仓{hold_days}天+收益{profit_pct:.0f}%"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            buy_idx = i
            cooldown_days = 0
            peak_since_buy = close
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": reason})
        elif action == "SELL":
            position = 0.0
            cooldown_days = 0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": code, "trades": trades, "metrics": metrics,
            "holding": position > 0}


def _calc_metrics(trades: list[dict], last_close: float,
                  position: float) -> dict:
    rounds = []
    buy_price = None
    buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price is not None:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append({
                "buy_date": buy_date, "sell_date": t["date"],
                "buy_price": buy_price, "sell_price": t["price"],
                "return_pct": round(ret, 2)})
            buy_price = None

    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append({
            "buy_date": buy_date, "sell_date": None,
            "buy_price": buy_price, "sell_price": last_close,
            "return_pct": round(ret, 2)})

    total_ret = 1.0
    wins = 0
    for r in rounds:
        total_ret *= (1 + r["return_pct"] / 100)
        if r["return_pct"] > 0:
            wins += 1

    total_ret_pct = round((total_ret - 1) * 100, 2)
    return {
        "rounds": rounds,
        "total_return_pct": total_ret_pct,
        "round_count": len(rounds),
        "win_count": wins,
        "win_rate": (round(wins / len(rounds) * 100, 1)
                     if rounds else 0),
        "trade_count": len(trades),
    }
