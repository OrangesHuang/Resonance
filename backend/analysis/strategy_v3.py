"""V3 主力资金节奏策略 — 自适应卖出参数。

核心改进(v3.1): 卖出规则不再一刀切，根据买入场景自适应:
  - 政策底买入(pp<20): 不止损、延长持仓、等政策响应
  - 天量资金买入(份额>3%): 提高止盈、放宽回撤、跟大资金共进退
  - 普通买入: 标准止盈止损
"""

from typing import Optional

# ===== 买入参数 =====
PANIC_DROP = -2.0
PANIC_VR = 2.0
PANIC_PP_MAX = 30.0
PANIC_SP_MIN = 65.0

ACCUM_PP_MAX = 35.0
ACCUM_SP_MIN = 65.0
ACCUM_VR_MIN = 1.8

EXTREME_PP_MAX = 20.0
EXTREME_VR_MIN = 1.5

# ===== 卖出参数 — 默认(普通买入) =====
TAKE_PROFIT = 15.0
TRAIL_STOP = 8.0
STOP_LOSS = -8.0
MAX_HOLD = 90
MIN_HOLD = 5
COOLDOWN = 8

# ===== 卖出参数 — 政策底模式(pp<20 买入) =====
POLICY_TAKE = 22.0
POLICY_TRAIL = 12.0
POLICY_STOP = None          # 政策底不止损
POLICY_MAX_HOLD = 180
POLICY_MIN_HOLD = 10

# ===== 卖出参数 — 天量资金模式(份额>3% 买入) =====
WHALE_TAKE = 28.0
WHALE_TRAIL = 15.0
WHALE_STOP = None           # 大资金在场不止损
WHALE_MAX_HOLD = 150
WHALE_MIN_HOLD = 15

# ===== 卖出信号参数 =====
DIST_PP_MIN = 80.0
DIST_VR_MIN = 1.5


def _calc_ma(closes: list[float], idx: int, period: int) -> float:
    start = max(0, idx - period + 1)
    return sum(closes[start:idx + 1]) / (idx - start + 1)


def _sell_params(
    pp_buy: Optional[float],
    sp_buy: Optional[float],
) -> dict:
    """根据买入时的市场状态，选择对应的卖出参数。

    政策底: price_position < 20 → 市场在"国家队必救"区域，不止损等政策
    天量资金: share_prob > 80 (对应份额变动>3%) → 大资金进场后不会快速离场
    普通: 标准止盈止损
    """
    if sp_buy is not None and sp_buy >= 80:
        return {
            "take": WHALE_TAKE, "trail": WHALE_TRAIL,
            "stop": WHALE_STOP, "max_hold": WHALE_MAX_HOLD,
            "min_hold": WHALE_MIN_HOLD, "label": "天量资金",
        }
    if pp_buy is not None and pp_buy < 20:
        return {
            "take": POLICY_TAKE, "trail": POLICY_TRAIL,
            "stop": POLICY_STOP, "max_hold": POLICY_MAX_HOLD,
            "min_hold": POLICY_MIN_HOLD, "label": "政策底",
        }
    return {
        "take": TAKE_PROFIT, "trail": TRAIL_STOP,
        "stop": STOP_LOSS, "max_hold": MAX_HOLD,
        "min_hold": MIN_HOLD, "label": "普通",
    }


def run_v3_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 60:
        return {"code": "", "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]
    code = rows[0].get("code", "") if rows else ""

    trades: list[dict] = []
    position = 0.0
    cooldown_days = COOLDOWN
    hold_days = 0
    peak_since_buy = 0.0
    sell_cfg = {}  # 当前持仓的卖出参数

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

            panic = (chg <= PANIC_DROP and vr >= PANIC_VR
                     and pp is not None and pp <= PANIC_PP_MAX
                     and sp is not None and sp >= PANIC_SP_MIN
                     and is_accum)

            accum = (is_accum and pp is not None and pp <= ACCUM_PP_MAX
                     and sp is not None and sp >= ACCUM_SP_MIN
                     and vr >= ACCUM_VR_MIN)

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

            if action == "BUY":
                sell_cfg = _sell_params(pp, sp)
                reason += f" [{sell_cfg['label']}模式]"

        # ---- 卖出 (使用自适应参数) ----
        elif position > 0:
            hold_days += 1
            peak_since_buy = max(peak_since_buy, close)
            buy_price = trades[-1]["price"] if trades else close
            profit_pct = (close - buy_price) / buy_price * 100
            trail_dd = ((peak_since_buy - close) / peak_since_buy * 100
                        if peak_since_buy > 0 else 0)

            min_h = sell_cfg.get("min_hold", MIN_HOLD)
            if hold_days < min_h:
                continue

            is_dist = td == "DISTRIBUTE"
            pp_ok = pp is not None and pp >= DIST_PP_MIN
            vr_ok = vr >= DIST_VR_MIN

            # 高位出货 — 天量资金模式下禁用(大资金不可能2个月内出完)
            if sell_cfg.get("label") == "天量资金":
                distrib_sell = False  # 只靠止盈+追踪止损退出
            elif sell_cfg.get("label") == "政策底":
                distrib_sell = is_dist and pp_ok and vr_ok and profit_pct > 3
            else:
                distrib_sell = is_dist and pp_ok and vr_ok and profit_pct > 0

            # 止盈
            take = sell_cfg.get("take", TAKE_PROFIT)
            profit_take = profit_pct >= take

            # 追踪止损 (仅在浮盈>3%后生效)
            trail = sell_cfg.get("trail", TRAIL_STOP)
            trail_sell = profit_pct > 3 and trail_dd >= trail

            # 硬止损 (政策底/天量模式下可能禁用)
            stop = sell_cfg.get("stop", STOP_LOSS)
            stop_loss = (stop is not None and profit_pct <= stop)

            # 超时
            max_h = sell_cfg.get("max_hold", MAX_HOLD)
            time_out = hold_days >= max_h

            # 深度亏损保护 (任何模式下，-20%无条件退出)
            deep_loss = profit_pct <= -20

            if deep_loss:
                action = "SELL"
                reason = f"深度亏损保护: {profit_pct:.0f}%"
            elif distrib_sell:
                action = "SELL"
                reason = (f"高位出货: 位置{pp:.0f}+量比{vr:.1f}"
                          f"+浮盈{profit_pct:.0f}%")
            elif profit_take:
                action = "SELL"
                reason = f"止盈: +{profit_pct:.0f}% (阈值+{take:.0f}%)"
            elif trail_sell:
                action = "SELL"
                reason = f"追踪止损: 回撤{trail_dd:.1f}% (阈值{trail:.0f}%)"
            elif stop_loss:
                action = "SELL"
                reason = f"硬止损: {profit_pct:.0f}%"
            elif time_out:
                action = "SELL"
                reason = (f"超时: 持仓{hold_days}天+收益{profit_pct:.0f}%"
                          f" [{sell_cfg.get('label', '')}]")

        if action == "BUY":
            position = 1.0
            hold_days = 0
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

    return {
        "rounds": rounds,
        "total_return_pct": round((total_ret - 1) * 100, 2),
        "round_count": len(rounds),
        "win_count": wins,
        "win_rate": (round(wins / len(rounds) * 100, 1) if rounds else 0),
        "trade_count": len(trades),
    }
