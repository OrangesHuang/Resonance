"""科创综指 (589680) V1 量价记忆策略。

与 510300 同构, 仅两处 KC 特有修改:
  1. 极低位(pp≤15)不要求放量 — 科创量能中枢低, 低量=卖压耗尽
     需 ETF 满 60 天(避免新 ETF 初期噪声)
  2. DISTRIBUTE 确认时排除份额扩张日 — 机构还在买, 出货是假信号

量价记忆: sell_threshold = max(2, ceil(2 + vr × 0.55))
"""

import math

KC_CODE = "589680"

BUY_PP_MAX = 40
PANIC_DROP = -3.0
PANIC_PP_MAX = 35

SELL_PP_MIN = 80
SELL_VR_MIN = 1.4

# 卖出确认: pp阈值 (与510300一致, 5/27的pp=84.9需要被计入)

MIN_HOLD = 5
COOLDOWN = 3
VOL_LOOKBACK = 20
MIN_ETF_AGE = 60         # ETF 至少60天后极低位路径才生效
TRADE_START = "2025-04-01"


def run_kc_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": KC_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]
    etf_birth_idx = next((i for i, r in enumerate(rows) if r["date"] >= TRADE_START), 0)

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

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- 买入 ----
        if position == 0 and cooldown >= COOLDOWN:
            is_accum = td == "ACCUMULATE"
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_extreme_low = pp is not None and pp <= 15

            # 路径1: ACCUMULATE + 低位 (与510300同构, 最可靠信号)
            if is_accum and pp_low:
                action = "BUY"
                reason = f"吸筹买入: pp{pp:.0f}+vr{vr:.1f}"

            # 路径2: 恐慌暴跌
            elif chg <= PANIC_DROP and vr >= 1.3 and pp is not None and pp <= PANIC_PP_MAX:
                action = "BUY"
                reason = f"恐慌接筹: 跌{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"

            # 路径3: 极低位 (KC特有: 低量=卖压耗尽, 需ETF满60天)
            elif pp_extreme_low and (i - etf_birth_idx) >= MIN_ETF_AGE:
                action = "BUY"
                reason = f"极低位: pp{pp:.0f}(卖压耗尽)"

        # ---- 卖出 ----
        if position == 1:
            hold_days += 1
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_high = vr >= SELL_VR_MIN

            if is_dist and pp_high and vr_high:
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
            # 量价记忆 (与510300同构)
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
    return {"code": KC_CODE, "trades": trades, "metrics": metrics,
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
