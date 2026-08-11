"""中证500 (510500) 优化策略 v2。

核心认知:
  中证500是中盘趋势型资产，波动适中，常有集群式吸筹/出货。
  
历史教训:
  1. 量比阈值过高: 2026-03-23 pp=21.8+跌3.91%+vr=1.33，
     因 vr<1.5 未触发 ACCUMULATE，错过买点。
     → 降低量能阈值至 1.25
  2. 过度依赖 ACCUMULATE: 有些低位恐慌日量比不够高但确实是底部
     → 增加恐慌买入路径（pp≤25 + 跌幅≥3%）
  3. 集群检测有效: 2026-07 集群后等右侧确认，避免假反弹
     → 保留集群逻辑

算法:
  买入(4路径):
    P1a 极端恐慌: pp≤25 + 跌≥5% → 左侧买 (不要求下跌成熟度)
    P1b 普通恐慌: pp≤25 + 跌≥3% + 距60日高点≥20天 → 左侧买
        (下跌成熟度判定: ≥20天=衰竭性恐慌安全, <20天=崩溃初期危险)
    P2 极端恐慌+ACCUMULATE: pp≤35 + 跌≥5% + ACCUMULATE → 左侧买
    P3 低位孤立吸筹: ACCUMULATE + pp≤35 + 非集群 + 距高点≥15天
    P4 暴跌集群右侧: 10天≥3个ACCUMULATE → 等反弹确认
       反弹需: 涨≥2%+vr≥1.2+份额净流入, 跌破前低则作废
  卖出(2规则):
    S1 冲顶观察: DISTRIBUTE+pp≥95 → 3日观察期
       放量上涨=换手(假顶), 缩量走弱确认=卖
    S2 集群出货: DISTRIBUTE累计≥阈值+pp≥85+vr≥1.5+份额流出 → 卖
"""

import math

ZZ500_CODE = "510500"

# 买入参数
BUY_PP_MAX = 35           # 买入最高价格位置
PANIC_DROP = -3.0         # 恐慌买入跌幅阈值
PANIC_PP_MAX = 25         # 恐慌买入最高价格位置
EXTREME_DROP = -5.0       # 极端恐慌跌幅
CLUSTER_ACCUM = 3         # 集群ACCUMULATE数量
CLUSTER_WINDOW = 10       # 集群检测窗口
HIGH_LOOKBACK = 60        # 60日高点回看
DROP_EARLY_DAYS = 15      # 下跌末期判定天数
PANIC_MATURITY_DAYS = 20  # 普通恐慌买入所需最小下跌成熟度(距60日高点天数)
VOLUME_ACTIVE_RATIO = 1.25  # 放量判定阈值(从1.5降低)

# 卖出参数
SELL_PP_EXTREME = 95      # 冲顶观察价格位置
SELL_PP_MIN = 85          # 出货确认最低价格位置
SELL_VR_MIN = 1.5         # 出货确认最低量比
S1_WATCH_DAYS = 3         # 冲顶观察天数
S1_WATCH_VR = 1.2         # 观察期放量上涨量比
S1_WATCH_CHG = 1.0        # 观察期放量上涨涨幅
BOUNCE_CHG = 2.0          # 右侧反弹涨幅
BOUNCE_VR = 1.2           # 右侧反弹量比
BOUNCE_PP_MAX = 45        # 右侧反弹最高价格位置

# 持仓参数
MIN_HOLD = 5              # 最小持仓天数
COOLDOWN = 3              # 交易冷却期
VOL_LOOKBACK = 20         # 成交量回看
TRADE_START = "2024-10-08"


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    """最近 window 天内的 ACCUMULATE 数量。"""
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1)
               if rows[j].get("trade_direction") == "ACCUMULATE")


def _days_since_60d_high(rows: list[dict], idx: int) -> int:
    """距 60 日最高收盘价的天数。"""
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


def _is_accumulate(row: dict) -> bool:
    """判定是否为吸筹日（使用降低的量能阈值）。"""
    pp = row.get("price_position")
    vr = row.get("volume_ratio") or 0
    if pp is None:
        return False
    # 低位 + 放量(阈值降低到1.25)
    return vr >= VOLUME_ACTIVE_RATIO and pp <= 40


def run_zz500_strategy_v2(rows: list[dict]) -> dict:
    """中证500优化策略。"""
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
    s1_watch = 0

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        sd = row.get("shares_delta_yi")
        cp = row.get("composite_prob") or 0

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # 重新判定 ACCUMULATE（使用降低的量能阈值）
        is_accum = _is_accumulate(row)
        # 始终计算集群中的ACCUMULATE数量（用于恐慌买入的集群检查）
        accum_count = sum(1 for j in range(max(0, i - CLUSTER_WINDOW + 1), i + 1)
                         if rows[j].get("trade_direction") == "ACCUMULATE")

        # ---- 买入 ----
        if position == 0 and cooldown >= COOLDOWN:
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_panic = pp is not None and pp <= PANIC_PP_MAX
            days_high = _days_since_60d_high(rows, i)

            # P1a: 极端恐慌 (跌≥5%, 不在集群中)
            if pp_panic and chg <= EXTREME_DROP and accum_count < CLUSTER_ACCUM:
                action = "BUY"
                reason = f"极端恐慌: 跌{chg:.1f}%+pp{pp:.0f}"

            # P1b: 普通恐慌 (跌≥3% + pp≤25 + 下跌已成熟)
            elif (pp_panic and chg <= PANIC_DROP 
                  and days_high >= PANIC_MATURITY_DAYS
                  and accum_count < CLUSTER_ACCUM):
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}+距高点{days_high}天"

            # P2: 极端恐慌 (pp≤35 + 跌≥5% + ACCUMULATE)
            elif is_accum and chg <= EXTREME_DROP and pp_low:
                action = "BUY"
                reason = f"极端恐慌: 跌{chg:.1f}%+pp{pp:.0f}+ACCUMULATE"

            # P3: 低位孤立吸筹 (ACCUMULATE + pp≤35 + 非集群 + 距高点≥15天)
            elif (is_accum and pp_low and accum_count < CLUSTER_ACCUM
                  and days_high >= DROP_EARLY_DAYS):
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+距高点{days_high}天"

            # P4: 暴跌集群 → 等待右侧确认
            elif accum_count >= CLUSTER_ACCUM:
                waiting_reversal = True
                wait_low = min((rows[j].get("close_price") or 0)
                               for j in range(max(0, i - CLUSTER_WINDOW + 1), i + 1))

        # ---- P4 右侧确认 ----
        if position == 0 and waiting_reversal and wait_low is not None:
            if close < wait_low:
                waiting_reversal = False
                wait_low = None
            else:
                cluster_ended = accum_count < CLUSTER_ACCUM or not is_accum
                prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
                pp_ok = pp is not None and pp <= BOUNCE_PP_MAX
                money_ok = sd is not None and sd > 0

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
                    waiting_reversal = False
                    wait_low = None

        # ---- 卖出 ----
        if position == 1:
            hold_days += 1
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_ok = vr >= SELL_VR_MIN

            # S1 冲顶观察
            if s1_watch > 0:
                s1_watch -= 1
                if vr >= S1_WATCH_VR and chg >= S1_WATCH_CHG:
                    reason = f"冲顶观察: 放量上涨(vr{vr:.1f}) → 换手"
                    s1_watch = 0
                    dist_count = 0
                elif s1_watch == 0:
                    reason = f"冲顶出货: pp{pp:.0f}+vr{vr:.1f}(缩量确认)"
                    action = "SELL"

            if s1_watch == 0 and action is None and (is_dist and pp is not None
                    and pp >= SELL_PP_EXTREME and not _recent_dist(rows, i)):
                s1_watch = S1_WATCH_DAYS

            # S2 集群确认
            if s1_watch == 0 and action is None and is_dist and pp_high and vr_ok:
                dist_count += 1
                if (hold_days >= MIN_HOLD and dist_count >= sell_threshold
                        and sd is not None and sd < 0):
                    reason = (f"出货确认({dist_count}/{sell_threshold})"
                              f"+pp{pp:.0f}+份额{sd:.1f}亿流出")
                    action = "SELL"

        # ---- 执行交易 ----
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
    """计算策略指标。"""
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
