"""中证红利 (515080) 独立买卖点策略。

红利指数低波动、缓上行、回撤浅，规则相应放宽回撤、收紧止盈：
- 买入仅在 trade_direction == ACCUMULATE 时触发
- 卖出仅在 trade_direction == DISTRIBUTE 时触发
"""

DIV_CODE = "515080"

# 买入参数（防守板块，与资金狂热背离，不依赖共振）
DIV_PANIC_VR = 3.0         # 恐慌放量阈值
DIV_WASHOUT_PP = 10.0      # 深度洗盘位置上限（极低位置买入）
DIV_PULLBACK_PP = 35.0     # 趋势回踩位置上限
DIV_TREND_MA_FAST = 20     # 趋势均线（快）
DIV_TREND_MA_SLOW = 60     # 趋势均线（慢）

# 卖出参数
DIV_MIN_HOLD = 5           # 最短持仓天数
DIV_CLIMAX_HOLD = 15       # 量能高潮最短持仓
DIV_CLIMAX_VR = 2.5        # 量能高潮量比
DIV_CLIMAX_CP = 65.0       # 量能高潮共振
DIV_CLIMAX_PROFIT_MIN = 8.0  # 量能高潮浮盈下限
DIV_TRAIL_HOLD = 10        # 追踪止盈最短持仓
DIV_TRAIL_STOP = 6.0       # 追踪止盈回撤（低波动收紧）
DIV_DIST_PP_MIN = 90.0     # 高位出货位置下限
DIV_DIST_PROFIT_MIN = 10.0  # 高位出货浮盈下限
DIV_MA_FAST = 5
DIV_MA_SLOW = 10
DIV_BREAKDOWN_VR = 1.5


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


def run_div_strategy(rows: list[dict]) -> dict:
    closes = [r["close_price"] for r in rows]
    n = len(closes)
    if n == 0:
        return {"code": DIV_CODE, "trades": [], "metrics": {}, "holding": False}

    trades: list[dict] = []
    position = 0.0
    hold_days = 0
    peak_since_buy = 0.0

    for i in range(n):
        row = rows[i]
        close = closes[i]
        vr = row.get("volume_ratio") or 0
        cp = row.get("composite_prob") or 0
        sp = row.get("shares_delta_pct")
        td = row.get("trade_direction")
        pp = row.get("price_position")
        d = row["date"]

        action = None
        reason = ""

        if position == 0 and td == "ACCUMULATE":
            # 条件 A：恐慌放量抄底
            if vr >= DIV_PANIC_VR:
                action = "BUY"
                reason = f"恐慌抄底:vr={vr:.2f}+共振{cp:.0f}"
            # 条件 B：深度洗盘（极低位置，防守板块被错杀）
            elif pp is not None and pp <= DIV_WASHOUT_PP:
                action = "BUY"
                reason = f"深度洗盘:位置{pp:.0f}+vr={vr:.2f}"
            # 条件 C：趋势回踩（上升趋势中的回调，排除下跌趋势反弹）
            elif pp is not None and pp <= DIV_PULLBACK_PP:
                ma_f = _calc_ma(closes, i, DIV_TREND_MA_FAST)
                ma_s = _calc_ma(closes, i, DIV_TREND_MA_SLOW)
                if ma_f > ma_s:
                    action = "BUY"
                    reason = f"趋势回踩:位置{pp:.0f}+MA{DIV_TREND_MA_FAST}>MA{DIV_TREND_MA_SLOW}"

        elif position == 1:
            hold_days += 1
            peak_since_buy = max(peak_since_buy, close)
            trail_dd = (peak_since_buy - close) / peak_since_buy * 100 if peak_since_buy > 0 else 0
            profit = (close - trades[-1]["price"]) / trades[-1]["price"] * 100 if trades else 0

            if td == "DISTRIBUTE":
                ma_fast = _calc_ma(closes, i, DIV_MA_FAST)
                ma_slow = _calc_ma(closes, i, DIV_MA_SLOW)

                # 条件 X：量能高潮
                if (hold_days >= DIV_CLIMAX_HOLD and vr >= DIV_CLIMAX_VR
                        and cp >= DIV_CLIMAX_CP and profit >= DIV_CLIMAX_PROFIT_MIN):
                    recent_hi = max(closes[max(0, i - 9): i + 1])
                    if close >= recent_hi * 0.99:
                        action = "SELL"
                        reason = f"量能高潮:vr={vr:.2f}+共振{cp:.0f}+近高点"

                # 条件 W：高位出货
                if (action is None and hold_days >= DIV_MIN_HOLD
                        and pp is not None and pp >= DIV_DIST_PP_MIN
                        and profit >= DIV_DIST_PROFIT_MIN):
                    sp_note = f"+份额{sp:.1f}%" if sp is not None else ""
                    action = "SELL"
                    reason = f"高位出货:位置{pp:.0f}+浮盈{profit:.0f}%{sp_note}"

                # 条件 Y：追踪止盈
                if action is None and hold_days >= DIV_TRAIL_HOLD and trail_dd >= DIV_TRAIL_STOP:
                    action = "SELL"
                    reason = f"追踪止盈:从{peak_since_buy:.3f}回落{trail_dd:.1f}%"

                # 条件 Z：均线破位
                if action is None and hold_days >= DIV_MIN_HOLD:
                    if close < ma_fast < ma_slow and vr >= DIV_BREAKDOWN_VR:
                        action = "SELL"
                        reason = f"均线破位:价格<MA5<MA10+放量{vr:.2f}"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            peak_since_buy = close
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": DIV_CODE, "trades": trades, "metrics": metrics, "holding": position == 1}


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
