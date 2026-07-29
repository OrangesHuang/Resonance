"""中证1000 (512100) V1 量价记忆策略。

与 510300 同构, 中证1000特征:
  - 高频信号 (41 ACCUMULATE / 37 DISTRIBUTE)
  - 高波动, 与科创综指相似
  - 融资敏感型 (小盘股资金驱动)
"""

import math

ZZ_CODE = "512100"

BUY_PP_MAX = 40
SELL_PP_MIN = 75
SELL_VR_MIN = 1.4

MIN_HOLD = 5
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def run_zz_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": ZZ_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
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
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        tp = row.get("_tp")
        mp = row.get("_mp")

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- 买入 (与510300同构 + 恐慌路径) ----
        if position == 0 and cooldown >= COOLDOWN:
            is_accum = td == "ACCUMULATE"
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_extreme = pp is not None and pp <= 10
            sp_ok = sp is not None and sp >= 60
            cp_ok = cp is not None and cp >= 60
            tp_cold = tp is not None and tp <= 10

            if is_accum and pp_low and sp_ok:
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+sp{sp:.0f}"
            elif is_accum and pp_low and tp_cold:
                action = "BUY"
                reason = f"极冷吸筹: pp{pp:.0f}+成交额{tp:.0f}分位"
            elif is_accum and pp_extreme and cp_ok:
                action = "BUY"
                reason = f"极端低位: pp{pp:.0f}+cp{cp:.0f}%"
            # 恐慌暴跌 (中证1000波动大)
            elif chg <= -3 and vr >= 1.5 and pp is not None and pp <= 35:
                action = "BUY"
                reason = f"恐慌接筹: 跌{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"

        # ---- 卖出 (DISTRIBUTE + pp + vr) ----
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
            cooldown = 0
            dist_count = 0
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": f"{reason} [阈值{sell_threshold}]"})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": ZZ_CODE, "trades": trades, "metrics": metrics,
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
