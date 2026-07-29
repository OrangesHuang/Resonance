"""中证红利 (515080) 右侧量价记忆策略。

核心差异 vs 510300/589680:
  中证红利是均值回归型资产, 不适合左侧抄底。
  被成长板块虹吸时跌幅可以很深很久, pp=20买入可能继续跌到pp=2。

算法:
  Phase 1 — 超卖检测(不买入): 最近10天≥2个ACCUMULATE + pp≤25
  Phase 2 — 右侧确认(触发买入): 连续2天涨+放量, 或单日强反转
  Phase 3 — 系统性危机(左侧买入): 跌≥5%+pp≤25+ACCUMULATE
  Phase 4 — 卖出: DISTRIBUTE集群确认 + 量价记忆
"""

import math

DIV_CODE = "515080"

BUY_PP_MAX = 40
SELL_PP_MIN = 75
SELL_VR_MIN = 1.3

MIN_HOLD = 8
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def _count_recent_accum(rows: list[dict], idx: int, window: int = 10) -> int:
    """统计最近 window 天内 ACCUMULATE 信号数量。"""
    count = 0
    for j in range(max(0, idx - window + 1), idx + 1):
        if rows[j].get("trade_direction") == "ACCUMULATE":
            count += 1
    return count


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
    waiting_for_reversal = False   # 超卖后等待右侧确认

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        tp = row.get("_tp")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0

        if d < TRADE_START:
            continue

        action = None
        reason = ""

        # ---- Phase 1: 超卖检测 ----
        if position == 0 and not waiting_for_reversal:
            is_accum = td == "ACCUMULATE"
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_oversold = pp is not None and pp <= 25
            accum_count = _count_recent_accum(rows, i, 10)

            # 系统性危机: 跌≥3.5%+低位+ACCUMULATE → 直接左侧买入
            # 中证红利波动小, -3.5%已是极端事件
            if is_accum and pp_oversold and chg <= -3.5:
                action = "BUY"
                reason = f"危机左侧: 跌{chg:.1f}%+pp{pp:.0f}(系统性)"

            # 超卖集群: ≥2个ACCUMULATE+pp≤25 → 进入等待确认
            elif accum_count >= 2 and pp_oversold:
                waiting_for_reversal = True

            # 极冷市吸筹 (成交额极低, 中证红利被市场遗忘=买点)
            elif is_accum and pp_low and tp is not None and tp <= 10:
                action = "BUY"
                reason = f"极冷吸筹: pp{pp:.0f}+成交额{tp:.0f}分位"

        # ---- Phase 2: 右侧确认 ----
        if position == 0 and waiting_for_reversal:
            prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
            prev_vr = rows[i - 1].get("volume_ratio") or 0 if i > 0 else 0
            pp_ok = pp is not None and pp <= 40

            # 连续2天涨+放量(第二天需vr>1.0确认)
            two_day_reversal = (chg > 0 and prev_chg > 0
                                and vr > 1.0 and prev_vr > 0.8
                                and pp_ok)

            # 单日强反转
            strong_reversal = chg > 2 and vr > 1.2 and pp_ok

            if two_day_reversal:
                action = "BUY"
                reason = f"右侧确认: 连涨2天+放量 pp{pp:.0f}"
                waiting_for_reversal = False
            elif strong_reversal:
                action = "BUY"
                reason = f"强反转: 涨{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"
                waiting_for_reversal = False
            elif pp is not None and pp > 40:
                # 价格回升太多, 错失确认窗口, 重置
                waiting_for_reversal = False

        # ---- Phase 4: 卖出 (与 V1 同构) ----
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
            waiting_for_reversal = False
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            # 中证红利: 极冷市=价值低估, 不应降低卖出门槛
            # 被市场冷落恰恰说明还有上涨空间, 需要更多出货确认
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
