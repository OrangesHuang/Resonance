"""科创综指 (589680) V1 量价记忆策略。

基于 510300 V1 策略的同构设计，参数针对科创综指高波动特征微调：
  - 买入: ACCUMULATE + 低位 + (份额确认 / 情绪极冷 / 极端低位)
  - 卖出: 累计 DISTRIBUTE 确认次数 ≥ 量价记忆阈值
  - 量价记忆: 买入时量比 → 卖出所需确认次数
"""

import math

KC_CODE = "589680"

# 针对科创综指高波动特征微调
BUY_PP_MAX = 40           # 买入位置上限 (与510300一致)
BUY_SP_MIN = 60            # 份额概率下限 (比510300的65稍宽)
SELL_PP_MIN = 85           # 卖出位置下限 (比510300的80更严)
SELL_MP_MIN = 85           # 融资分位下限 (比510300的90稍宽)
MIN_HOLD = 8               # 最短持仓 (比510300的10稍短)
VOL_LOOKBACK = 20
TRADE_START = "2025-04-01"  # 科创综指ETF上市较晚


def run_kc_strategy(rows: list[dict]) -> dict:
    """V1 量价记忆策略 — 科创综指版。"""
    n = len(rows)
    if n < 30:
        return {"code": KC_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    sell_threshold = 1
    dist_count = 0

    # 需要融资分位和成交额分位 (市场级数据)
    # 从etf_daily的idx_chg字段无法获取，用volume_ratio代理市场温度
    # 极冷市: volume_ratio < 0.7 且 price_position < 20

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        vr = row.get("volume_ratio") or 0

        if d < TRADE_START:
            continue

        action = None
        reason = ""

        # ---- 买入 (三条路径，与510300 V1同构) ----
        if position == 0:
            is_accum = td == "ACCUMULATE"
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_extreme = pp is not None and pp <= 10
            sp_ok = sp is not None and sp >= BUY_SP_MIN
            cp_ok = cp is not None and cp >= 60
            # 恐慌: 低位+放量+吸筹 (新ETF初期份额数据可能不完整)
            vr_panic = vr >= 1.5 and pp is not None and pp <= 30

            if is_accum and pp_low and sp_ok:
                action = "BUY"
                reason = f"低位吸筹: 位置{pp:.0f}+份额{sp:.0f}"
            elif is_accum and vr_panic:
                action = "BUY"
                reason = f"恐慌接筹: 位置{pp:.0f}+量比{vr:.1f}"
            elif is_accum and pp_extreme and cp_ok:
                action = "BUY"
                reason = f"极端低位: 位置{pp:.0f}+概率{cp:.0f}%"

        # ---- 卖出 ----
        if position == 1:
            hold_days += 1
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_elevated = vr >= 1.5   # 放量确认

            if is_dist and pp_high and vr_elevated:
                dist_count += 1

            if hold_days >= MIN_HOLD and is_dist and dist_count >= sell_threshold:
                reason = (f"出货确认({dist_count}/{sell_threshold})"
                          f"+位置{pp:.0f}+量比{vr:.1f}")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            dist_count = 0
            # 量价记忆: 买入量比 → 卖出阈值
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            # 量价记忆: 极冷市(量比<0.8)买入 → 快进快出
            if vr < 0.8:
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
