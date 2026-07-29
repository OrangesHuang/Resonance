"""中证红利 (515080) V1 量价记忆策略。

与 510300 同构，针对中证红利特征适配:
  - 低波动(1.17-1.65, 区间42%) → 卖出不需要融资门槛, pp+vr确认即可
  - 红利=价值锚定 → pp≤20 即价值底部, 不需要额外份额/成交额确认
  - 量价记忆: sell_threshold = max(2, ceil(2 + vr × 0.55))
"""

import math

DIV_CODE = "515080"

BUY_PP_MAX = 40
SELL_PP_MIN = 75
SELL_VR_MIN = 1.3

MIN_HOLD = 8
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def run_div_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": DIV_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    sell_threshold = 1
    dist_count = 0

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        tp = row.get("_tp")  # 成交额分位 (需外部注入)
        vr = row.get("volume_ratio") or 0

        if d < TRADE_START:
            continue

        action = None
        reason = ""

        # ---- 买入 (与510300同构 + 价值底部路径) ----
        if position == 0:
            is_accum = td == "ACCUMULATE"
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_value = pp is not None and pp <= 20

            # 路径1: ACCUMULATE + 低位 + 份额确认
            if is_accum and pp_low and sp is not None and sp >= 60:
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+sp{sp:.0f}"

            # 路径2: ACCUMULATE + 低位 + 极冷市
            elif is_accum and pp_low and tp is not None and tp <= 10:
                action = "BUY"
                reason = f"极冷吸筹: pp{pp:.0f}+成交额{tp:.0f}分位"

            # 路径3: ACCUMULATE + 价值底部 (中证红利特有: 低估值=买点)
            elif is_accum and pp_value:
                action = "BUY"
                reason = f"价值底部: pp{pp:.0f}(红利低估)"

        # ---- 卖出 (DISTRIBUTE + pp + vr, 不需要融资门槛) ----
        if position == 1:
            hold_days += 1
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_ok = vr >= SELL_VR_MIN

            if is_dist and pp_high and vr_ok:
                dist_count += 1

            if hold_days >= MIN_HOLD and is_dist and dist_count >= sell_threshold:
                reason = (f"出货确认({dist_count}/{sell_threshold})"
                          f"+pp{pp:.0f}+vr{vr:.1f}")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            dist_count = 0
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            tp_cold = tp is not None and tp <= 10
            if tp_cold:
                sell_threshold = 1
            else:
                sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": f"{reason} [阈值{sell_threshold}]"})
        elif action == "SELL":
            position = 0.0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": DIV_CODE, "trades": trades, "metrics": metrics,
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
        "win_rate": round(wins / len(rounds) * 100, 1) if rounds else 0,
        "trade_count": len(trades),
    }
