"""科创综指 (589680) 独立买卖点策略。

基于历史买卖点反推规则，针对科创综指高波动特征设计：
- 买入：回撤驱动（恐慌放量 / 缩量低位 / 趋势回踩 / 极端回撤）
- 卖出：量能高潮 / 动量停滞 / 追踪止盈 / 均线破位
"""

KC_CODE = "589680"

# 买入参数
KC_DRAWDOWN_BUY = 12.0
KC_DRAWDOWN_TREND = 8.0
KC_DRAWDOWN_EXTREME = 20.0
KC_VOL_PANIC = 1.5
KC_VOL_DRY = 1.0
KC_CP_FEAR = 25.0
KC_CP_GREED = 45.0
KC_TREND_MA_FAST = 20
KC_TREND_MA_SLOW = 60
KC_OVEREXTEND_LIMIT = 45.0
KC_REENTRY_COOLDOWN = 5

# 卖出参数
KC_VOL_CLIMAX = 2.2
KC_VOL_CLIMAX_MIN_HOLD = 20
KC_TRAIL_STOP = 10.0
KC_MIN_HOLD = 5
KC_PROFIT_THRESHOLD = 15.0
KC_MA_FAST = 5
KC_MA_SLOW = 10
KC_BREAKDOWN_VOL = 1.3

# 条件 E：放量吸筹启动（买入）
KC_ACCUM_VR = 2.0
KC_ACCUM_CP = 65.0
KC_ACCUM_PP_MAX = 50.0

# 条件 W：高位出货（卖出）
KC_DIST_PP_MIN = 95.0
KC_DIST_PROFIT_MIN = 25.0


def _calc_drawdown(closes: list[float], idx: int, window: int = 60) -> float:
    start = max(0, idx - window + 1)
    hi = max(closes[start: idx + 1])
    if hi == 0:
        return 0.0
    return (hi - closes[idx]) / hi * 100


def _calc_ma(closes: list[float], idx: int, period: int) -> float:
    start = max(0, idx - period + 1)
    window = closes[start: idx + 1]
    return sum(window) / len(window)


def run_kc_strategy(rows: list[dict]) -> dict:
    closes = [r["close_price"] for r in rows]
    n = len(closes)
    if n == 0:
        return {"code": KC_CODE, "trades": [], "metrics": {}, "holding": False}

    trades: list[dict] = []
    position = 0.0
    hold_days = 0
    peak_since_buy = 0.0
    days_since_sell = 999

    for i in range(n):
        row = rows[i]
        close = closes[i]
        vr = row.get("volume_ratio") or 0
        cp = row.get("composite_prob") or 0
        sp = row.get("shares_delta_pct")
        td = row.get("trade_direction")
        pp = row.get("price_position")
        d = row["date"]

        dd = _calc_drawdown(closes, i)
        days_since_sell += 1

        action = None
        reason = ""

        if position == 0 and td == "ACCUMULATE":
            # 条件 D：极端回撤无条件买入
            if dd >= KC_DRAWDOWN_EXTREME:
                action = "BUY"
                reason = f"极端回撤{dd:.1f}%≥{KC_DRAWDOWN_EXTREME:.0f}%"
            # 条件 A：恐慌放量抄底
            elif dd >= KC_DRAWDOWN_BUY and vr >= KC_VOL_PANIC and cp >= KC_CP_GREED:
                action = "BUY"
                reason = f"恐慌抄底:回撤{dd:.1f}%+放量{vr:.2f}+共振{cp:.0f}"
            # 条件 B：缩量低位买入
            elif (dd >= KC_DRAWDOWN_BUY and vr <= KC_VOL_DRY and cp <= KC_CP_FEAR
                  and days_since_sell >= KC_REENTRY_COOLDOWN):
                action = "BUY"
                reason = f"缩量低位:回撤{dd:.1f}%+vr={vr:.2f}+悲观{cp:.0f}"
            # 条件 C：趋势回踩买入（排除过度拉升后的假回踩 + 卖出冷却期）
            elif (dd >= KC_DRAWDOWN_TREND and vr <= KC_VOL_DRY and cp <= 35
                  and days_since_sell >= KC_REENTRY_COOLDOWN):
                ma_f = _calc_ma(closes, i, KC_TREND_MA_FAST)
                ma_s = _calc_ma(closes, i, KC_TREND_MA_SLOW)
                lo_60 = min(closes[max(0, i - 59): i + 1])
                gain_from_low = (close - lo_60) / lo_60 * 100 if lo_60 > 0 else 0
                if ma_f > ma_s and gain_from_low < KC_OVEREXTEND_LIMIT:
                    action = "BUY"
                    reason = f"趋势回踩:回撤{dd:.1f}%+MA{KC_TREND_MA_FAST}>MA{KC_TREND_MA_SLOW}+缩量"
            # 条件 E：放量吸筹启动（浅回撤但量价共振强，位置仍低）
            if (action is None and vr >= KC_ACCUM_VR and cp >= KC_ACCUM_CP
                    and pp is not None and pp <= KC_ACCUM_PP_MAX):
                action = "BUY"
                reason = f"放量吸筹:vr={vr:.2f}+共振{cp:.0f}+位置{pp:.0f}"

        elif position == 1:
            hold_days += 1
            peak_since_buy = max(peak_since_buy, close)
            trail_dd = (peak_since_buy - close) / peak_since_buy * 100 if peak_since_buy > 0 else 0
            profit = (close - trades[-1]["price"]) / trades[-1]["price"] * 100 if trades else 0

            if td == "DISTRIBUTE":
                ma_fast = _calc_ma(closes, i, KC_MA_FAST)
                ma_slow = _calc_ma(closes, i, KC_MA_SLOW)

                # 条件 X：量能高潮（需持仓较久，避免趋势初期误卖）
                if hold_days >= KC_VOL_CLIMAX_MIN_HOLD and vr >= KC_VOL_CLIMAX:
                    recent_hi = max(closes[max(0, i - 9): i + 1])
                    if close >= recent_hi * 0.99:
                        sp_neg = sp is not None and sp < 0
                        if sp_neg or cp >= 65:
                            action = "SELL"
                            reason = f"量能高潮:vr={vr:.2f}+近高点+{'份额转负' if sp_neg else f'共振{cp:.0f}'}"

                # 条件 Y：追踪止盈
                if action is None and hold_days >= KC_MIN_HOLD * 2 and trail_dd >= KC_TRAIL_STOP:
                    action = "SELL"
                    reason = f"追踪止盈:从{peak_since_buy:.3f}回落{trail_dd:.1f}%"

                # 条件 Z：均线破位
                if action is None and hold_days >= KC_MIN_HOLD:
                    if close < ma_fast < ma_slow and vr >= KC_BREAKDOWN_VOL:
                        action = "SELL"
                        reason = f"均线破位:价格<MA5<MA10+放量{vr:.2f}"

                # 条件 W：高位出货（极端高位+份额净赎回+浮盈充足）
                if (action is None and hold_days >= KC_MIN_HOLD
                        and pp is not None and pp >= KC_DIST_PP_MIN
                        and sp is not None and sp < 0
                        and profit >= KC_DIST_PROFIT_MIN):
                    action = "SELL"
                    reason = f"高位出货:位置{pp:.0f}+份额{sp:.1f}%+浮盈{profit:.0f}%"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            peak_since_buy = close
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            days_since_sell = 0
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": KC_CODE, "trades": trades, "metrics": metrics, "holding": position == 1}


def _calc_metrics(trades: list[dict], last_close: float, position: float) -> dict:
    rounds = []
    buy_price = None
    buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append({"buy_date": buy_date, "sell_date": t["date"],
                           "buy_price": buy_price, "sell_price": t["price"], "return_pct": round(ret, 2)})
            buy_price = None

    if position == 1 and buy_price:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append({"buy_date": buy_date, "sell_date": None,
                       "buy_price": buy_price, "sell_price": last_close, "return_pct": round(ret, 2)})

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
    }
