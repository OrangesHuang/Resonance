"""中证500 (510500) 右侧趋势策略。

核心认知:
  中证500是趋势型慢牛资产, 924以来每次回调15-20%后创新高。
  历史教训:
  1. 买太早: 2026-07-13首日ACCUMULATE就买@8.14, 实际是暴跌集群开端
     7-13~7-20连续4天ACCUMULATE继续跌到7.43(-8.8%), 应等右侧反弹
  2. 卖太早: 2025-12-26首波DISTRIBUTE就卖@7.37, 当天份额仍+3.11亿流入
     真正资金流出在1-15(-8.34亿), 期间价格涨到8.57(+16%)
  3. 卖太早(S1): 2025-08-18 首个DISTRIBUTE就卖@6.537, 实际是慢牛换手
     之后放量上涨(vr1.64/+1.4%)创新高, 10-09 真顶@7.438(+13.8%)
     → S1 触发后进入3日观察: 放量上涨日(涨≥1%+vr≥1.2)判为换手继续持有
       (08-20 换手 → 持有到 08-26 出货确认 @6.837 +34.88%)
       缩量走弱则卖出 (2025-03-14 触发 → 3日缩量 → 03-19 卖@5.891, 正确)
  4. 假反弹: 2026-07-21涨4.93%但份额-0.32亿流出(无资金支持),
     随后7-30跌破7-20前低7.426 → 反弹必须份额净流入+不破前低

算法:
  买入(3路径):
    P1 单日极端恐慌: 跌≥5%+ACCUMULATE+pp≤35+非集群 → 左侧买 (2025-04-07)
    P2 低位孤立吸筹: ACCUMULATE+pp≤35+非集群+距60日高点≥15天 → 左侧买
       (2025-11-21 / 2024-12-31, 下跌末期才左侧)
    P3 暴跌集群右侧: 10天≥3个ACCUMULATE → 等反弹确认
       反弹需: 涨≥2%+vr≥1.2+份额净流入(sd>0), 跌破前低则作废
       (2026-07-31, 避免集群中段入场和假反弹)
  卖出(2规则):
    S1 首个出货冲顶: DISTRIBUTE+pp≥95+近5天无DISTRIBUTE → 3日观察
       观察期内放量上涨日(涨≥1%+vr≥1.2)=换手, 取消卖出并清零出货计数;
       否则缩量走弱确认后卖出 (2025-03-14正确 / 2025-08-18换手)
    S2 集群出货确认: DISTRIBUTE累计≥阈值+当日份额净流出 → 卖
       (需量价记忆+份额流出双确认, 避免机构还在买时卖出)
"""

import math

ZZ500_CODE = "510500"

BUY_PP_MAX = 35
PANIC_DROP = -5.0
CLUSTER_ACCUM = 3
CLUSTER_WINDOW = 10
HIGH_LOOKBACK = 60
DROP_EARLY_DAYS = 15
SELL_PP_EXTREME = 95
SELL_PP_MIN = 85
SELL_VR_MIN = 1.5
# S1 冲顶观察: 触发后3日内出现放量上涨日 → 判定换手(假顶), 取消卖出
S1_WATCH_DAYS = 3
S1_WATCH_VR = 1.2
S1_WATCH_CHG = 1.0
BOUNCE_CHG = 2.0
BOUNCE_VR = 1.2
BOUNCE_PP_MAX = 45
MIN_HOLD = 5
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-10-08"


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    """最近 window 天内的 ACCUMULATE 数量。"""
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1)
               if rows[j].get("trade_direction") == "ACCUMULATE")


def _days_since_60d_high(rows: list[dict], idx: int) -> int:
    """距 60 日最高收盘价的天数 (0=当天创新高)。"""
    lo = max(0, idx - HIGH_LOOKBACK + 1)
    high_close = max((rows[j].get("close_price") or 0) for j in range(lo, idx + 1))
    for j in range(idx, lo - 1, -1):
        if (rows[j].get("close_price") or 0) == high_close:
            return idx - j
    return HIGH_LOOKBACK


def _recent_dist(rows: list[dict], idx: int, window: int = 5) -> bool:
    """近 window 天内是否出现过 DISTRIBUTE。"""
    return any(rows[j].get("trade_direction") == "DISTRIBUTE"
               for j in range(max(0, idx - window), idx))


def run_zz500_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": ZZ500_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    sell_threshold = 1
    dist_count = 0
    waiting_reversal = False
    wait_low = None
    s1_watch = 0   # S1 冲顶观察剩余天数(0=未在观察)

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
            pp_low = pp is not None and pp <= BUY_PP_MAX
            days_high = _days_since_60d_high(rows, i)

            # P1: 单日极端恐慌 (非集群中, 左侧)
            if is_accum and chg <= PANIC_DROP and pp_low and accum_count < CLUSTER_ACCUM:
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}"

            # P2: 低位孤立吸筹 (下跌末期才左侧)
            elif (is_accum and pp_low and accum_count < CLUSTER_ACCUM
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
                # 跌破前低 → 假反弹, 本次集群作废
                waiting_reversal = False
                wait_low = None
            else:
                accum_count = _count_accum(rows, i)
                cluster_ended = accum_count < CLUSTER_ACCUM or td != "ACCUMULATE"
                prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
                pp_ok = pp is not None and pp <= BOUNCE_PP_MAX
                money_ok = sd is not None and sd > 0  # 反弹需份额净流入

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
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_ok = vr >= SELL_VR_MIN

            # S1 冲顶观察: 触发后3日内出现放量上涨日 → 换手(假顶), 取消卖出
            if s1_watch > 0:
                s1_watch -= 1
                if vr >= S1_WATCH_VR and chg >= S1_WATCH_CHG:
                    reason = f"冲顶观察: 放量上涨(vr{vr:.1f}) → 换手, 继续持有"
                    s1_watch = 0
                    dist_count = 0  # 假顶集群作废, 重新计数
                elif s1_watch == 0:
                    reason = f"冲顶出货: pp{pp:.0f}+vr{vr:.1f}(缩量走弱确认)"
                    action = "SELL"

            # S1: 首个出货冲顶 (近5天无DISTRIBUTE + pp≥95) → 进入观察
            if s1_watch == 0 and action is None and (is_dist and pp is not None
                    and pp >= SELL_PP_EXTREME and not _recent_dist(rows, i)):
                s1_watch = S1_WATCH_DAYS

            # S2: 集群确认 + 份额净流出 (双确认)
            if s1_watch == 0 and action is None and is_dist and pp_high and vr_ok:
                dist_count += 1
                if (hold_days >= MIN_HOLD and dist_count >= sell_threshold
                        and sd is not None and sd < 0):
                    reason = (f"出货确认({dist_count}/{sell_threshold})"
                              f"+pp{pp:.0f}+份额{sd:.1f}亿流出")
                    action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            dist_count = 0
            waiting_reversal = False
            s1_watch = 0
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
            s1_watch = 0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": ZZ500_CODE, "trades": trades, "metrics": metrics,
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
