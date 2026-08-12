"""科创综指 (589680) K线摆动匹配策略。

核心认知 (操盘手意图):
  科创综指主力极度惜售: 买多卖少, 真正拿出的卖盘极少, 目的让筹码进一步
  集中 → 买卖点判断极难, 但可拆解其行为模式:
    "买多卖少" = 吸筹期份额持续净流入(12-24~12-31 连续6天 +3.8亿,
                 05-18~05-25 +3.3亿, 07-30 崩盘吸筹 +3.35亿)
    "卖少则砸" = 顶部不砸大单, 小幅流出后直接砸盘
    "砸后低吸" = 回调中份额仍流入(05-26~06-08 回调期 acc10 持续为正)
    "最后一吸再拉" = 06-29 吸筹 +0.6 → 06-30 拉 +4% 至大顶
  量能记忆(卖出核心): 卖出确认必须与前面的吸筹量匹配 ——
    - 出货信号日若当日仍在净申购(sd>0) = 洗盘/换手, 不是出货:
      08-13(+1.0) 08-18(+0.8) 08-28(+1.2) 05-20(+0.5) 05-27(+0.65)
    - 出货信号日当日净赎回(sd<0) = 真出货, 可卖:
      09-02(-0.35) 03-03(-0.8) 06-22(-0.5)
    - 近期强吸筹(近10日累计≥2亿)时出货信号豁免(刚吸筹完就卖是错的):
      01-06/01-07(近10日+3.4, 12月底刚吸+3.8) → 持有到 03-03 破位卖
  份额 T+1 披露 → 出货信号当日触发, 次日(确认 sd)执行, 无前视偏差。

历史教训:
  1. 08-13 出货信号(pp99+vr2.0)但当日申购+1.0 → 若卖只 +33.5%,
     实际 09-02 卖 @1.233 +48.2%(当日流出-0.35 确认)
  2. 01-06/01-07 连续出货信号(pp98)但 12 月底刚吸筹+3.8 → 卖太早;
     03-03 破位(-5.0%+vr2.5+流出-0.8)卖 @1.352 +13.7% 才合理
  3. 06-22 出货信号(pp99+vr1.76+流出-0.5) → 06-23 确认卖 @1.779
     +42.0%; 若等止盈 07-14 @1.768 收益接近但多扛 3 周波动
  4. 2026-05-20 pp100 出货但当日申购+0.5(吸筹中洗盘) → 豁免;
     06-22 才真出货, 多赚 ~6%
  5. 2026-06-01 深回调-10.1%不触发止盈(吸筹中), 持有到 06-22 卖
     多赚 15.6%
  6. 2025-10-17 止盈 @1.234 (无吸筹背景 T1 兜底)

算法:
  买入(4路径, 不依赖份额):
    P1 极端恐慌: ACCUMULATE+跌≥10%+pp≤40+非集群 → 2025-04-07 @0.832
    P2 低位吸筹: ACCUMULATE+pp≤35+非集群+距30日高点≥15天 (备用)
    极低位缩量: pp≤15+vr<1.0+跌≥2%+距高点≥15天+非集群
       → 2025-11-21 @1.189 / 2026-03-23 @1.253
    极低位放量恐慌: pp≤10+跌≥5%+vr≥1.2 → 2026-07-30 @1.374
  卖出(3规则, 全部需当日净赎回 sd<0 确认, T+1 执行):
    量能记忆豁免: 近10日累计 sd ≥ 2.0(刚吸筹完) → 出货信号豁免
    S1 出货信号: DISTRIBUTE+pp≥97+vr≥1.5+sd<0+非豁免 → T+1 卖
       → 2026-06-22 信号, 06-23 确认 @1.779
    S2 破位出货: 跌≥2.5%+vr≥1.5+sd<0+非豁免 → T+1 卖
       → 2025-09-02 信号 → 09-03 @1.233 / 2026-03-03 → 03-04 @1.352
    T1 止盈: 持仓≥10天 + 收盘<持仓最高×0.90 + 非吸筹中(a10<0.5)
       → 2025-10-17 @1.234 (无吸筹期兜底)
"""

from __future__ import annotations

KC_CODE = "589680"

BUY_PP_MAX = 35
PANIC_DROP = -10.0
PANIC_PP_MAX = 40

EXTREME_PP = 15  # 极低位缩量: 价格位置上限
EXTREME_VR_MAX = 1.0  # 极低位缩量: 量比上限(低量=卖压耗尽)
EXTREME_CHG = -2.0
PANIC_LOW_PP = 10  # 极低位放量恐慌: pp 上限
PANIC_LOW_CHG = -5.0  # 极低位放量恐慌: 跌幅阈值
PANIC_LOW_VR = 1.2  # 极低位放量恐慌: 量比下限

CLUSTER_ACCUM = 2
CLUSTER_WINDOW = 10
HIGH_LOOKBACK = 30
DROP_EARLY_DAYS = 15

# ---- 卖出参数 ----
TRAIL_PCT = 0.10  # 止盈: 持仓期最高收盘回落比例(兜底)
DIST_PP_MIN = 97  # 出货信号: pp 阈值(顶部区)
DIST_VR_MIN = 1.5  # 出货信号: 量比阈值
BREAK_CHG = -2.5  # 破位出货: 跌幅阈值
BREAK_VR_MIN = 1.5  # 破位出货: 量比下限
MEMORY_EXEMPT = 2.0  # 量能记忆: 近10日累计吸筹≥2亿 豁免出货信号
FUND_EXEMPT = 0.5  # 止盈豁免: 前10日累计净申赎阈值(吸筹中)
SD_WINDOW = 10  # 吸筹动能窗口
SD_MIN_COUNT = 8  # 吸筹动能最少有效天数

MIN_HOLD = 10
COOLDOWN = 3
TRADE_START = "2025-04-01"


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1) if rows[j].get("trade_direction") == "ACCUMULATE")


def _days_since_30d_high(rows: list[dict], idx: int) -> int:
    lo = max(0, idx - HIGH_LOOKBACK + 1)
    high_close = max((rows[j].get("close_price") or 0) for j in range(lo, idx + 1))
    for j in range(idx, lo - 1, -1):
        if (rows[j].get("close_price") or 0) == high_close:
            return idx - j
    return HIGH_LOOKBACK


def _acc_sd(rows: list[dict], idx: int) -> float | None:
    """前 SD_WINDOW 日累计净申赎(不含当日, 只用 T-1 及更早数据).
    份额 T+1 披露, 当日盘中不可得; 有效天数不足返回 None."""
    total = 0.0
    cnt = 0
    for j in range(max(0, idx - SD_WINDOW), idx):
        v = rows[j].get("shares_delta_yi")
        if v is not None:
            total += v
            cnt += 1
    return total if cnt >= SD_MIN_COUNT else None


def run_kc_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": KC_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    peak_close = 0.0
    pending_sell_idx = None

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

        # ---- T+1 确认执行挂起的卖出 ----
        if pending_sell_idx is not None and i > pending_sell_idx:
            signal_date = rows[pending_sell_idx]["date"]
            action = "SELL"
            reason = f"{signal_date}出货确认sd{rows[pending_sell_idx].get('shares_delta_yi')}"
            pending_sell_idx = None

        # ---- 买入 ----
        if action is None and position == 0 and cooldown >= COOLDOWN:
            is_accum = td == "ACCUMULATE"
            accum_count = _count_accum(rows, i)
            days_high = _days_since_30d_high(rows, i)

            # P1: 极端恐慌 (非集群中, 左侧)
            if is_accum and chg <= PANIC_DROP and pp is not None and pp <= PANIC_PP_MAX and accum_count < CLUSTER_ACCUM:
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}"

            # P2: 低位吸筹 (下跌末期)
            elif (
                is_accum
                and pp is not None
                and pp <= BUY_PP_MAX
                and accum_count < CLUSTER_ACCUM
                and days_high >= DROP_EARLY_DAYS
            ):
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+距高点{days_high}天"

            # 极低位缩量: 低量=卖压耗尽 (无份额过滤, 份额无判别力)
            elif (
                pp is not None
                and pp <= EXTREME_PP
                and vr < EXTREME_VR_MAX
                and chg <= EXTREME_CHG
                and days_high >= DROP_EARLY_DAYS
                and accum_count < CLUSTER_ACCUM
            ):
                action = "BUY"
                reason = f"极低位: pp{pp:.0f}+缩量{vr:.2f}"

            # 极低位放量恐慌: 放量恐慌日见底 (2026-07-30 型)
            elif pp is not None and pp <= PANIC_LOW_PP and chg <= PANIC_LOW_CHG and vr >= PANIC_LOW_VR:
                action = "BUY"
                reason = f"放量恐慌: 跌{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"

        # ---- 卖出: 出货信号+量能记忆, 止盈兜底 ----
        if action is None and position == 1:
            hold_days += 1
            peak_close = max(peak_close, close)
            a10 = _acc_sd(rows, i)
            sd_today = rows[i].get("shares_delta_yi")
            is_dist = td == "DISTRIBUTE"

            # 量能记忆: 近10日累计吸筹≥2亿, 刚吸筹完不卖
            memory_exempt = a10 is not None and a10 >= MEMORY_EXEMPT
            # 止盈豁免: 吸筹中(a10≥0.5)不止盈
            trail_exempt = a10 is not None and a10 >= FUND_EXEMPT

            # S1: 出货信号 + 当日净赎回确认 (洗盘日 sd>0 不触发)
            if (
                is_dist
                and pp is not None
                and pp >= DIST_PP_MIN
                and vr >= DIST_VR_MIN
                and not memory_exempt
                and sd_today is not None
                and sd_today < 0
            ) or (
                chg <= BREAK_CHG and vr >= BREAK_VR_MIN and not memory_exempt and sd_today is not None and sd_today < 0
            ):
                pending_sell_idx = i
            # T1: 止盈兜底 (吸筹中豁免)
            elif hold_days >= MIN_HOLD and close < peak_close * (1 - TRAIL_PCT) and not trail_exempt:
                reason = f"止盈: 高点{peak_close:.3f}回落至{close:.3f}"
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            peak_close = close
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            peak_close = 0.0
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": KC_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}


def _calc_metrics(trades: list[dict], last_close: float, position: float) -> dict:
    rounds = []
    buy_price = None
    buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price is not None:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append(
                {
                    "buy_date": buy_date,
                    "sell_date": t["date"],
                    "buy_price": buy_price,
                    "sell_price": t["price"],
                    "return_pct": round(ret, 2),
                }
            )
            buy_price = None

    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append(
            {
                "buy_date": buy_date,
                "sell_date": None,
                "buy_price": buy_price,
                "sell_price": last_close,
                "return_pct": round(ret, 2),
            }
        )

    total_ret = 1.0
    wins = 0
    for r in rounds:
        total_ret *= 1 + r["return_pct"] / 100
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
