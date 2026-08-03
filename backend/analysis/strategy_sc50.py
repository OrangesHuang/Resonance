"""双创50 (159780) K线摆动匹配策略。

核心认知:
  双创50主力惜售且用高换手快进快出隐藏吸筹痕迹, 全历史只做了三轮:
    R1 924前: 2024-08-30买@0.425 → 10-09卖@0.607 (+42.8%)
    R2 关税底: 2025-04-07买@0.485 → 10-14卖@0.845 (+74.2%)
    R3 2026-04: 2026-04-08买@0.947 → 07-03卖@1.316 (+39.0%)
  量价规律(经全历史验证):
    惜售 = 下跌缩量: 2026-01~03 阴跌40天 vr 全在0.3~0.8, 卖盘枯竭
    隐藏 = 高换手: 顶部区 vr 1.5~2.4 反复快进快出
    启动 = 藏不住: 全历史 vr≥2且涨≥4%且pp≤75 的放量启动日只有2天
            (2024-09-24 / 2026-04-08), 全部是真启动 → P4 路径
  历史教训:
  1. 2026-07-28 ACCUMULATE (pp7.4) 创新低阴跌中段买入@1.096,
     之后继续跌到 08-03 @1.041(-5%) → P2 要求当日不创新低
  2. 2026-07-17 @1.118 无任何信号(NEUTRAL) → 不买(错过允许)
  3. 924 连续涨停(09-30/10-08 均+20%)无法预测 → 止盈吃10-09回撤
  4. 2025-09-01 顶 0.847 → 09-04 深回调-9% 骗出5%止盈 → 放宽到10%

算法:
  买入(4路径, 均不依赖份额):
    P1 单日恐慌: 跌≥9%+ACCUMULATE+pp≤20+非集群 → 2025-04-07 @0.485
    P2 低位吸筹: ACCUMULATE+pp≤40+距30日高点≥15天+当日不创新低
       → 2024-08-30 @0.425 (2026-07-28 创新低被拦)
    P4 放量启动: 量比≥2+涨≥4%+pp≤75+近20日内出现过pp≤15极低位
       → 2024-09-24 / 2026-04-08 @0.947 (缩量见底后的首次放量启动)
    P3 集群右侧: 10天≥3个ACCUMULATE → 等反弹确认(备用)
  卖出(1规则):
    T1 止盈: 持仓≥10天 + 收盘 < 持仓期最高收盘×0.90 → 卖
       (2024-10-09 @0.607 / 2025-10-14 @0.845 / 2026-07-03 @1.316)
"""

import math

SC50_CODE = "159780"

BUY_PP_MAX = 40
PANIC_DROP = -9.0
PANIC_PP_MAX = 20

CLUSTER_ACCUM = 3
CLUSTER_WINDOW = 10
HIGH_LOOKBACK = 30
DROP_EARLY_DAYS = 15
BOUNCE_CHG = 2.0
BOUNCE_VR = 1.2
BOUNCE_PP_MAX = 45

# 放量启动路径: 缩量见底后首次放量+大涨(惜售→启动的量价特征)
BOOST_VR = 2.0        # 启动日量比≥2倍
BOOST_CHG = 4.0       # 启动日涨幅≥4%
BOOST_PP_MAX = 75     # 启动日价格位置上限
BOOST_LOOKBACK = 20   # 回看窗口: 近期须出现过极低位
BOOST_PP_LOW = 15     # 极低位阈值(证明已缩量见底)

TRAIL_PCT = 0.10       # 持仓期最高收盘回落10%止盈(5%会被09-01顶后回调骗出)

MIN_HOLD = 10
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-08-01"


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


def _new_low(rows: list[dict], idx: int, window: int = 20) -> bool:
    """当日收盘创近 window 日新低 (阴跌中段信号)。"""
    close = rows[idx].get("close_price") or 0
    return close < min((rows[j].get("close_price") or 0)
                       for j in range(max(0, idx - window), idx))


def _recent_low_pp(rows: list[dict], idx: int) -> bool:
    """近 BOOST_LOOKBACK 日内(不含当日)出现过极低位(已缩量见底)。"""
    lo = max(0, idx - BOOST_LOOKBACK)
    return any((rows[j].get("price_position") or 99) <= BOOST_PP_LOW
               for j in range(lo, idx))


def run_sc50_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": SC50_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    waiting_reversal = False
    wait_low = None
    peak_close = 0.0

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
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
            accum_count = _count_accum(rows, i)
            days_high = _days_since_30d_high(rows, i)

            # P1: 单日恐慌 (非集群中, 左侧)
            if (is_accum and chg <= PANIC_DROP
                    and pp is not None and pp <= PANIC_PP_MAX
                    and accum_count < CLUSTER_ACCUM):
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}"

            # P2: 低位吸筹 (下跌末期 + 当日不创新低)
            elif (is_accum and pp is not None and pp <= BUY_PP_MAX
                  and accum_count < CLUSTER_ACCUM
                  and days_high >= DROP_EARLY_DAYS
                  and not _new_low(rows, i)):
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+距高点{days_high}天"

            # P4: 缩量见底后的首次放量启动 (2026-04-08 / 2024-09-24 类)
            elif (vr >= BOOST_VR and chg >= BOOST_CHG
                  and pp is not None and pp <= BOOST_PP_MAX
                  and _recent_low_pp(rows, i)):
                action = "BUY"
                reason = f"放量启动: 涨{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"

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

                strong_bounce = (chg >= BOUNCE_CHG and vr >= BOUNCE_VR
                                 and pp_ok)
                two_day_up = (cluster_ended and chg > 0 and prev_chg > 0
                              and vr > 1.0 and pp_ok)

                if strong_bounce or two_day_up:
                    action = "BUY"
                    reason = (f"右侧反弹: 涨{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"
                              if strong_bounce else
                              f"右侧连涨: 2天+放量+pp{pp:.0f}")
                    waiting_reversal = False
                    wait_low = None
                elif pp is not None and pp > 55:
                    waiting_reversal = False  # 价格回升太多, 重置
                    wait_low = None

        # ---- 卖出: 止盈 ----
        if position == 1:
            hold_days += 1
            peak_close = max(peak_close, close)
            if (hold_days >= MIN_HOLD
                    and close < peak_close * (1 - TRAIL_PCT)):
                reason = f"止盈: 高点{peak_close:.3f}回落至{close:.3f}"
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
    return {"code": SC50_CODE, "trades": trades, "metrics": metrics,
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
