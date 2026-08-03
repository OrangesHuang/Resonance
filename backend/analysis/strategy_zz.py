"""中证1000 (512100) 右侧量价记忆策略。

核心认知:
  中证1000 暴跌集群特征明显 — 连续5-9个ACCUMULATE密集出现
  左侧抄底会在集群中段入场, 继续承压5-10%
  需要等待集群结束+反弹确认后右侧入场

算法:
  Phase 1 — 暴跌集群检测: 10天内≥3个ACCUMULATE → 进入等待
  Phase 2 — 右侧确认: 集群结束后连续2天涨+放量 → 买入
  Phase 3 — 单日恐慌: 跌≥5%+ACCUMULATE → 直接左侧买入(单日极端)
  Phase 4 — 卖出: DISTRIBUTE集群确认 + 量价记忆
"""

import math

ZZ_CODE = "512100"

SELL_PP_MIN = 75
SELL_VR_MIN = 1.3

# 顶部观察(延迟卖出): 出货确认达标后不立即卖, 等破位
EXTREME_CHG = 3.0         # 确认日涨幅≥此值 → 加速赶顶(924式)立即卖
EXTREME_VR = 4.0          # 确认日量比≥此值 → 立即卖
TRAIL_PCT = 0.04          # 从观察期最高收盘回落幅度触发
WATCH_BREAK_DAYS = 5      # 跌破N日最低收盘触发
WATCH_PP_EXIT = 60        # 观察期 pp 跌破此值立即卖

MIN_HOLD = 5
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def _count_crash_accum(rows: list[dict], idx: int, window: int = 10) -> int:
    """统计最近 window 天内的 ACCUMULATE 数量 (判断暴跌集群)。"""
    count = 0
    for j in range(max(0, idx - window + 1), idx + 1):
        if rows[j].get("trade_direction") == "ACCUMULATE":
            count += 1
    return count


def run_zz_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": ZZ_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    sell_threshold = 1
    dist_count = 0
    waiting_for_reversal = False
    last_sell_price = None
    entry_shares = None      # 买入时份额
    peak_net_inflow = 0.0    # 累计净流入峰值
    watch_mode = False       # 顶部观察模式(阈值达标后等破位)
    watch_peak = 0.0         # 观察期最高收盘

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
        sd_yi = row.get("shares_delta_yi") or 0

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- Phase 1: 暴跌集群检测 ----
        if position == 0 and not waiting_for_reversal:
            is_accum = td == "ACCUMULATE"
            crash_count = _count_crash_accum(rows, i, 10)
            in_crash_cluster = crash_count >= 2

            # 单日极端暴跌: 跌≥5%+ACCUMULATE → 直接左侧买入
            if is_accum and chg <= -5:
                action = "BUY"
                reason = f"暴跌抄底: 跌{chg:.1f}%+pp{pp:.0f}"

            # 暴跌集群: ≥3个ACCUMULATE → 进入等待右侧确认
            elif in_crash_cluster:
                waiting_for_reversal = True

            # 非暴跌集群的普通买入
            elif is_accum and pp is not None and pp <= 25:
                if sp is not None and sp >= 50:
                    action = "BUY"
                    reason = f"低位吸筹: pp{pp:.0f}+sp{sp:.0f}"
                elif tp is not None and tp <= 10:
                    action = "BUY"
                    reason = f"极冷吸筹: pp{pp:.0f}+成交额{tp:.0f}分位"

            # 反弹确认 (跌超7% + 当日回升 + 不在暴跌集群中)
            elif (is_accum and last_sell_price is not None
                  and close < last_sell_price * 0.93
                  and chg > 0                      # 当日企稳回升, 非继续下跌
                  and pp is not None and pp <= 30
                  and crash_count < 2):
                action = "BUY"
                reason = f"反弹确认: 跌超7%后企稳 pp{pp:.0f}"

        # ---- Phase 2: 右侧确认 (暴跌集群结束后) ----
        if position == 0 and waiting_for_reversal:
            crash_count = _count_crash_accum(rows, i, 10)
            # 集群结束: ACCUMULATE密度下降 或 连续2天无ACCUMULATE
            no_recent_accum = (td != "ACCUMULATE"
                               and rows[i-1].get("trade_direction") != "ACCUMULATE" if i > 0 else True)
            cluster_ended = crash_count < 2 or no_recent_accum
            pp_ok = pp is not None and pp <= 35

            prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
            prev_vr = rows[i - 1].get("volume_ratio") or 0 if i > 0 else 0

            two_day_up = (cluster_ended and chg > 0 and prev_chg > 0
                          and vr > 1.0 and pp_ok)
            strong_bounce = (cluster_ended and chg > 2 and vr > 1.0 and pp_ok)

            if two_day_up:
                action = "BUY"
                reason = f"右侧确认: 连涨2天+放量 pp{pp:.0f}"
                waiting_for_reversal = False
            elif strong_bounce:
                action = "BUY"
                reason = f"强反弹: 涨{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"
                waiting_for_reversal = False
            elif pp is not None and pp > 50:
                waiting_for_reversal = False  # 价格回升太多, 重置

        # ---- 卖出 (份额驱动) ----
        if position == 1:
            hold_days += 1
            cur_shares = row.get("shares_yi")

            # 跟踪累计净流入
            if cur_shares is not None and entry_shares is not None:
                net_flow = cur_shares - entry_shares
                peak_net_inflow = max(peak_net_inflow, net_flow)

            # 卖出条件1: DISTRIBUTE集群中不触发巨量流出 (让集群完整)
            in_dist_cluster = dist_count >= 1
            recent_big_inflow = any(
                (rows[j].get("shares_delta_yi") or 0) >= 5
                for j in range(max(0, i - 3), i)
            )
            massive_outflow = (not in_dist_cluster  # 不在DISTRIBUTE集群中
                               and not recent_big_inflow
                               and sd_yi <= -5
                               and peak_net_inflow > 0
                               and cur_shares is not None
                               and entry_shares is not None
                               and (cur_shares - entry_shares) < peak_net_inflow * 0.5)

            # 卖出条件2: DISTRIBUTE + 份额净流出 (经典确认)
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_ok = vr >= SELL_VR_MIN
            if is_dist and pp_high and vr_ok:
                dist_count += 1

            if hold_days >= MIN_HOLD:
                if massive_outflow:
                    action = "SELL"
                    reason = (f"巨量流出: {sd_yi:.0f}亿+净流入回撤"
                              f"+pp{pp:.0f}")
                elif is_dist and dist_count >= sell_threshold and not watch_mode:
                    # 首次达标: 加速赶顶日(924式)立即卖, 否则进入顶部观察等破位
                    if chg >= EXTREME_CHG or vr >= EXTREME_VR:
                        reason = (f"出货确认+加速赶顶({dist_count}/{sell_threshold})"
                                  f"+pp{pp:.0f}+vr{vr:.1f}")
                        action = "SELL"
                    else:
                        watch_mode = True
                        watch_peak = close
                elif watch_mode:
                    # 顶部观察: 跟踪最高收盘, 破位即卖
                    watch_peak = max(watch_peak, close)
                    low_n = min((rows[j].get("close_price") or 0)
                                for j in range(max(0, i - WATCH_BREAK_DAYS), i))
                    if (close < low_n
                            or close < watch_peak * (1 - TRAIL_PCT)
                            or (pp is not None and pp < WATCH_PP_EXIT)):
                        reason = (f"顶部破位: 高点{watch_peak:.3f}"
                                  f"+收盘{close:.3f}+pp{pp:.0f}")
                        action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            dist_count = 0
            waiting_for_reversal = False
            watch_mode = False
            watch_peak = 0.0
            entry_shares = row.get("shares_yi")
            peak_net_inflow = 0.0
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
            watch_mode = False
            watch_peak = 0.0
            last_sell_price = close
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": ZZ_CODE, "trades": trades, "metrics": metrics,
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
