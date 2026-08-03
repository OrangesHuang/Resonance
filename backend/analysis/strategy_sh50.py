"""上证50 (510050) K线摆动匹配策略。

核心认知:
  上证50是国家队份额主战场, 权重蓝筹慢牛, 波动中等。
  K线主观买卖点(大波段):
    B1 2024-01-17 雪球崩盘底 → S1 2024-05-20 年内高点
    B2 2024-09-13 924前深底   → S2 2024-10-08 924顶
    B3 2025-04-07 关税暴跌底  → S3 2026-01-06 2026初顶
    B4 2026-03-23 回调底      → S4 2026-05-13 5月顶
    B5 2026-07-17 回调底      → 持有
  关键认知: 上证50的顶大多是 NEUTRAL(无DISTRIBUTE信号, 如2024-05/2026-01),
  "出货计数"类卖出永远匹配不上 → 卖出必须用趋势止盈(持仓最高收盘回落5%)
  + 巨额赎回日(≥10亿)快速离场。
  历史教训:
  1. 2024-01-22 雪球崩盘 ACCUMULATE+国家队长枪(单日+15.56亿)是绝佳买点,
     距高点仅11天 → P2 允许 单日申购≥10亿 豁免距高点要求
  2. 2024-08-05 距高点11天(07-19刚创近高即急跌)买入会-4.25%止损出局
     → 距高点用30日窗口+12天门槛(60日窗口会把急跌初期误判为下跌末期)
  3. 2025-06-10 份额-5.3亿 是小幅换手, 若卖出会错过 2025 慢牛
     → 巨额赎回门槛 10亿, 2025全年不触发
  4. 2026-01-15 单日 -28.47亿 巨额赎回 + pp69 → 立即卖出@3.18
     (主观 S3 顶 01-06 @3.235, 差1.7%)
  5. 2026-05-11 单日 -11.36亿 + pp81 → 卖出@3.116 (主观 S4 顶 05-13
     @3.123, 差2天0.2%)
  6. 卖出差价的诚实说明: S1(主观05-20@2.43 vs 止盈06-25@2.30)、
     S2(主观10-08@2.84 vs 止盈10-11@2.66) — 无信号顶只能靠回落确认,
     卖不到最高点是趋势止盈的固有代价

算法:
  买入(4路径):
    P1 单日恐慌: 跌≥5%+ACCUMULATE+pp≤30+非集群+sd>0 → 2025-04-07 @2.491
    P2 低位吸筹: ACCUMULATE+pp≤40+非集群+sd>0
       + (距30日高点≥12天 或 当日申购≥10亿豁免)
       → 2024-01-22 / 2024-09-20 / 2026-03-23 / 2026-07-17
    极低位: pp≤10+跌≥2%+距高点≥12+sd>0 (备用)
    P3 集群右侧: 10天≥2个ACCUMULATE → 等反弹确认 (备用)
  卖出(2规则):
    T1 止盈: 持仓≥10天 + 收盘 < 持仓期最高收盘×0.95 → 卖
       (2024-06-25 S1 / 2024-10-11 S2)
    T2 巨额赎回: 持仓≥10天 + 当日份额流出≥10亿 + pp≥60 → 立即卖
       (2026-01-15 @3.18 / 2026-05-08 @3.075, 2025年小幅赎回不触发)
"""

import math

SH50_CODE = "510050"

BUY_PP_MAX = 40
PANIC_DROP = -5.0
PANIC_PP_MAX = 30
EXTREME_PP = 10
EXTREME_CHG = -2.0
BIG_BUY_YI = 10.0     # 单日申购≥此值豁免距高点要求(国家队长枪)

CLUSTER_ACCUM = 2
CLUSTER_WINDOW = 10
HIGH_LOOKBACK = 30      # 用30日高点判下跌末期(60日窗口会把8月急跌误判为末期)
DROP_EARLY_DAYS = 12
BOUNCE_CHG = 2.0
BOUNCE_VR = 1.2
BOUNCE_PP_MAX = 45

TRAIL_PCT = 0.05       # 持仓期最高收盘回落5%止盈
REDEEM_YI = -10.0      # 单日赎回≥10亿触发快速卖出
REDEEM_PP_MIN = 60     # 巨额赎回卖出需价格仍在高位区

MIN_HOLD = 10
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1)
               if rows[j].get("trade_direction") == "ACCUMULATE")


def _days_since_60d_high(rows: list[dict], idx: int) -> int:
    lo = max(0, idx - HIGH_LOOKBACK + 1)
    high_close = max((rows[j].get("close_price") or 0) for j in range(lo, idx + 1))
    for j in range(idx, lo - 1, -1):
        if (rows[j].get("close_price") or 0) == high_close:
            return idx - j
    return HIGH_LOOKBACK


def run_sh50_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": SH50_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    waiting_reversal = False
    wait_low = None
    peak_close = 0.0   # 持仓期最高收盘

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        sd = row.get("shares_delta_yi")

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- 买入 ----
        if position == 0 and cooldown >= COOLDOWN:
            is_accum = td == "ACCUMULATE"
            accum_count = _count_accum(rows, i)
            days_high = _days_since_60d_high(rows, i)
            money_ok = sd is None or sd > 0

            # P1: 单日恐慌 (非集群中, 左侧)
            if (is_accum and chg <= PANIC_DROP
                    and pp is not None and pp <= PANIC_PP_MAX
                    and accum_count < CLUSTER_ACCUM and money_ok):
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}+份额{sd:.1f}亿"

            # P2: 低位吸筹 (下跌末期 或 国家队大额申购豁免)
            elif (is_accum and pp is not None and pp <= BUY_PP_MAX
                  and accum_count < CLUSTER_ACCUM and money_ok
                  and (days_high >= DROP_EARLY_DAYS
                       or (sd is not None and sd >= BIG_BUY_YI))):
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+距高点{days_high}天"

            # 极低位: 放量恐慌日的极端低位
            elif (pp is not None and pp <= EXTREME_PP and chg <= EXTREME_CHG
                  and days_high >= DROP_EARLY_DAYS
                  and accum_count < CLUSTER_ACCUM and money_ok):
                action = "BUY"
                reason = f"极低位: pp{pp:.0f}+跌{chg:.1f}%"

            # P3: 暴跌集群 → 等待右侧确认
            elif accum_count >= CLUSTER_ACCUM:
                waiting_reversal = True
                wait_low = min((rows[j].get("close_price") or 0)
                               for j in range(max(0, i - CLUSTER_WINDOW + 1), i + 1))

        # ---- P3 右侧确认 ----
        if position == 0 and waiting_reversal and wait_low is not None:
            if close < wait_low:
                waiting_reversal = False
                wait_low = None
            else:
                accum_count = _count_accum(rows, i)
                cluster_ended = accum_count < CLUSTER_ACCUM or td != "ACCUMULATE"
                prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
                pp_ok = pp is not None and pp <= BOUNCE_PP_MAX
                money_ok = sd is None or sd > 0

                strong_bounce = (chg >= BOUNCE_CHG and vr >= BOUNCE_VR
                                 and pp_ok and money_ok)
                two_day_up = (cluster_ended and chg > 0 and prev_chg > 0
                              and vr > 1.0 and pp_ok and money_ok)

                if strong_bounce or two_day_up:
                    action = "BUY"
                    reason = (f"右侧反弹: 涨{chg:.1f}%+vr{vr:.1f}+份额{sd:.1f}亿"
                              if strong_bounce else
                              f"右侧连涨: 2天+放量+份额{sd:.1f}亿")
                    waiting_reversal = False
                    wait_low = None
                elif pp is not None and pp > 55:
                    waiting_reversal = False  # 价格回升太多, 重置
                    wait_low = None

        # ---- 卖出 ----
        if position == 1:
            hold_days += 1
            peak_close = max(peak_close, close)

            # T2: 巨额赎回日快速离场 (份额大幅流出+价格仍在高位区)
            if (hold_days >= MIN_HOLD
                    and sd is not None and sd <= REDEEM_YI
                    and pp is not None and pp >= REDEEM_PP_MIN):
                reason = (f"巨额赎回: {sd:.1f}亿+pp{pp:.0f}")
                action = "SELL"

            # T1: 持仓期最高收盘回落5%止盈
            elif (hold_days >= MIN_HOLD
                    and peak_close > 0
                    and close < peak_close * (1 - TRAIL_PCT)):
                reason = (f"止盈: 高点{peak_close:.3f}回落至{close:.3f}")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            waiting_reversal = False
            wait_low = None
            peak_close = close
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": reason})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            peak_close = 0.0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": SH50_CODE, "trades": trades, "metrics": metrics,
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
