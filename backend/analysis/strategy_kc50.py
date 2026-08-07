"""科创50 (588000) K线摆动匹配策略。

核心认知:
  科创50高波动成长资产, 份额信号极强(单日±10~76亿)但经常"边拉边出":
  08-22 (-38.75亿) 之后还涨 +22%, 04-30 (-29.31亿) 之后还涨 +42%
  → 巨额赎回不是卖出理由, 顶几乎全是 NEUTRAL 无信号
  → 卖出必须用持仓期最高收盘回落止盈
   K线主观买卖点(大波段):
    B1 2024-02-02 雪球底@0.707   → S1 2024-06-21 顶@0.795
    B2 2024-09-24 924反弹@0.699  → S2 2024-10-08 924顶@1.14
    B4 2025-04-07 关税底@0.97    → S4 2025-10-09 顶@1.618
    B5 2025-11-21 深底@1.351     → S6 2026-06-30 大顶@2.344
    B6 2026-07-30 恐慌底@1.669   → 持有
  历史教训:
   1. 2024-08-05 距高点仅10天(急跌初期)买入会继续跌 → 距30日高点≥15天
   2. 2024-06-20 (pp34) 高位吸筹买入@0.791 后跌到 07-04 @0.723(-8.6%)
      → pp≤30 拦掉高位吸筹
   3. 2026-07-17 距高点13天 且 当日+27.78亿申购, 买入后跌到 08-03 @1.64
      (-9.2%) → 距高点门槛15天不放宽, 急跌初期即使大额申购也等右侧
   4. 2026-07-30 (pp3.0, -6.0%, +34.26亿申购) 是10天窗口内第3个ACCUMULATE,
      原集群守卫会拦截 → 极端低位(pp≤15)豁免集群守卫, 全历史仅
      04-07/07-30 两个触发日零误伤 (07-17 pp35.2 仍被拦)
   5. 2025-05-28 5%止盈被浅回调(-5.4%)骗出@1.023, 之后涨到 10-09 @1.618
      → 止盈放宽到8%
   6. 卖在主升浪前(系统性): 09-04/-10.5%、06-01/-12.2% 假回调后都创新高
      → 止盈改为"连续3日未收复才卖": 假回调2-3天内收复不卖
      (2025-10-22 @1.476 +52.2% 吃到10-09主升浪, 06-04 @1.832 +37.9%)
   7. 2026-06-01 深回调触发但 sd +6.48亿(国家队抄底)不计数,
      06-04 确认后卖 @1.832 — 申购豁免+收复确认叠加
   8. 与双创50同源的"缩量见底→放量启动"规律: 科创50的底部启动几乎都带
      ACCUMULATE信号(P1/P2已覆盖), 无需双创式P4放量启动路径

算法:
  买入(2路径, 02-05 类底部由 P2 覆盖):
    P1 单日恐慌: 跌≥6%+ACCUMULATE+pp≤30+sd>0
       + (非集群 或 pp≤15极端低位豁免集群守卫)
       → 2025-04-07 @0.97 / 2026-07-30 @1.669
    P2 低位吸筹: ACCUMULATE+pp≤30+sd>0+距30日高点≥15天
       → 2024-02-02 @0.707 / 2024-09-24 / 2025-11-21 / 2026-03-23
       (2026-07-17 距13天被拦, 2024-06-20 pp34被拦)
  卖出(1规则):
    T1 止盈: 持仓≥10天 + 收盘 < 持仓期最高收盘×0.92
       连续3日未收复才卖(2-3天内收复=假回调不卖)
       + 触发日份额申购≥5亿不计数(国家队抄底)
       (2025-10-22 @1.476 +52.2% / 2026-06-04 @1.832 +37.9%
        / 2024-10-17 @0.926 / 2026-03-06 @1.491)
"""

import math

KC50_CODE = "588000"

BUY_PP_MAX = 30
PANIC_DROP = -6.0
PANIC_PP_MAX = 30
EXTREME_CLUSTER_PP = 15  # 集群守卫豁免: pp≤15 的极端低位允许集群末左侧

CLUSTER_ACCUM = 3
CLUSTER_WINDOW = 10
HIGH_LOOKBACK = 30
DROP_EARLY_DAYS = 15
BOUNCE_CHG = 2.0
BOUNCE_VR = 1.2
BOUNCE_PP_MAX = 45

TRAIL_PCT = 0.08       # 持仓期最高收盘回落8%触发
TRAIL_CONFIRM_DAYS = 3 # 连续3日未收复才卖出(假回调2-3天内会收复)
TRAIL_SD_EXEMPT = 5.0  # 触发日份额申购≥5亿不计数(国家队抄底的假回调)

MIN_HOLD = 10
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1)
               if rows[j].get("trade_direction") == "ACCUMULATE")


def _days_since_30d_high(rows: list[dict], idx: int) -> int:
    lo = max(0, idx - HIGH_LOOKBACK + 1)
    high_close = max((rows[j].get("close_price") or 0) for j in range(lo, idx + 1))
    for j in range(idx, lo - 1, -1):
        if (rows[j].get("close_price") or 0) == high_close:
            return idx - j
    return HIGH_LOOKBACK


def run_kc50_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": KC50_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    waiting_reversal = False
    wait_low = None
    peak_close = 0.0
    breach_days = 0   # 连续未收复天数

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
            days_high = _days_since_30d_high(rows, i)
            money_ok = sd is None or sd > 0

            # P1: 单日恐慌 (非集群中, 左侧; 极端低位 pp≤15 豁免集群守卫)
            if (is_accum and chg <= PANIC_DROP
                    and pp is not None and pp <= PANIC_PP_MAX
                    and (accum_count < CLUSTER_ACCUM
                         or pp <= EXTREME_CLUSTER_PP)
                    and money_ok):
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}+份额{sd:.1f}亿"

            # P2: 低位吸筹 (下跌末期; pp≤30 拦掉高位吸筹如2024-06-20)
            elif (is_accum and pp is not None and pp <= BUY_PP_MAX
                  and accum_count < CLUSTER_ACCUM and money_ok
                  and days_high >= DROP_EARLY_DAYS):
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+距高点{days_high}天"

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

        # ---- 卖出: 止盈(连续N日未收复确认, 巨额申购日不计数) ----
        if position == 1:
            hold_days += 1
            peak_close = max(peak_close, close)
            exempt = sd is not None and sd >= TRAIL_SD_EXEMPT
            if (hold_days >= MIN_HOLD
                    and close < peak_close * (1 - TRAIL_PCT)
                    and not exempt):
                breach_days += 1
                if breach_days >= TRAIL_CONFIRM_DAYS:
                    reason = (f"止盈确认: 高点{peak_close:.3f}回落至{close:.3f}"
                              f"(连续{breach_days}日未收复)")
                    action = "SELL"
            else:
                breach_days = 0  # 收复或申购豁免, 重置计数

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            waiting_reversal = False
            wait_low = None
            peak_close = close
            breach_days = 0
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": reason})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            peak_close = 0.0
            breach_days = 0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": KC50_CODE, "trades": trades, "metrics": metrics,
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
