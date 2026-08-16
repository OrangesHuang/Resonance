"""中证1000 (512100) 策略辅助函数与底部/顶部形态判定(纯函数, 无 I/O)。

拆自 zz.py: 窗口统计与形态判定纯函数, 主循环调用后组装 action/reason。
判定函数只做计算, 不修改任何状态。
"""

from __future__ import annotations

from base.analysis.strategy.zz_params import (
    BEAR_MA250_SLOPE,
    EXTREME_CHG,
    EXTREME_VR,
    HOT_BREAK_DAYS,
    HOT_PP_MIN,
    HOT_TP_MIN,
    PANIC_CHG_MIN,
    PANIC_PP_MAX,
    QUIET_DD_MIN,
    QUIET_MARGIN_MAX,
    QUIET_PP_MAX,
    QUIET_TRAIL_PCT,
    RAPID_CHG_MIN,
    RAPID_DD20_MIN,
    RAPID_PP_MAX,
    TRAIL_PCT,
    WATCH_BREAK_DAYS,
    WATCH_PP_EXIT,
)


def _count_crash_accum(rows: list[dict], idx: int, window: int = 10) -> int:
    """统计最近 window 天内的 ACCUMULATE 数量 (判断暴跌集群)。"""
    count = 0
    for j in range(max(0, idx - window + 1), idx + 1):
        if rows[j].get("trade_direction") == "ACCUMULATE":
            count += 1
    return count


def _dd_from_high(closes: list[float], idx: int, window: int = 250) -> float:
    """当前收盘距 window 日最高收盘的回撤百分比(负数=回撤)。"""
    lo = max(0, idx + 1 - window)
    hi = max(closes[lo : idx + 1])
    return (closes[idx] / hi - 1) * 100 if hi > 0 else 0.0


def _recent_accum(rows: list[dict], idx: int, window: int) -> bool:
    """近 window 日内是否出现过 ACCUMULATE 信号(缩量深底要求无, 防重叠)。"""
    for j in range(max(0, idx - window), idx):
        if rows[j].get("trade_direction") == "ACCUMULATE":
            return True
    return False


def _ma250_slope(closes: list[float], idx: int) -> float:
    """ma250 20日斜率(%/20日): 正=牛市(政策牛/上行), 负=熊市。"""
    if idx < 249:
        return 0.0
    cur = sum(closes[idx - 249 : idx + 1]) / 250
    prev = sum(closes[idx - 269 : idx - 19]) / 250
    return (cur / prev - 1) * 100 if prev > 0 else 0.0


def is_panic_bottom(chg: float, pp: float | None) -> bool:
    """单日史诗级恐慌底: 跌停日量比失真, 不限 td/vr(Phase 0)。"""
    return chg <= -PANIC_CHG_MIN and pp is not None and pp <= PANIC_PP_MAX


def is_rapid_end(chg: float, pp: float | None, dd20: float, has_recent_accum: bool) -> bool:
    """急跌末端企稳(Phase 1.6): 非放量集群的加速赶底+缩量企稳。"""
    return (
        chg <= -RAPID_CHG_MIN
        and pp is not None
        and pp <= RAPID_PP_MAX
        and dd20 <= -RAPID_DD20_MIN
        and not has_recent_accum
    )


def is_quiet_deep(pp: float | None, mp: float | None, dd250: float, has_recent_accum: bool) -> bool:
    """缩量深底(Phase 1.5): 阴跌尽头的杠杆出清+地量磨底。"""
    return (
        pp is not None
        and pp <= QUIET_PP_MAX
        and mp is not None
        and mp <= QUIET_MARGIN_MAX
        and dd250 <= -QUIET_DD_MIN
        and not has_recent_accum
    )


def is_hot_top(pp: float | None, tp: float | None, closes: list[float], i: int, slope: float) -> bool:
    """熊市热度顶: 弱反弹顶波段卖出, 仅熊市(ma250下行)生效。"""
    if slope >= BEAR_MA250_SLOPE:
        return False
    low5 = min(closes[max(0, i - HOT_BREAK_DAYS) : i]) if i >= HOT_BREAK_DAYS else 0.0
    return (
        pp is not None
        and pp >= HOT_PP_MIN
        and tp is not None
        and tp >= HOT_TP_MIN
        and closes[i] < low5
        and i >= HOT_BREAK_DAYS
    )


def is_quiet_trail(close: float, quiet_peak: float, hold_days: int, min_hold: int = 5) -> bool:
    """缩量深底尾随止盈: 高点回撤即离场(防阴跌年深套)。"""
    return hold_days >= min_hold and close <= quiet_peak * (1 - QUIET_TRAIL_PCT / 100)


def extreme_bear_only(chg: float, vr: float, slope: float) -> bool:
    """加速赶顶立即卖仅熊市(ma250下行)生效; 牛市转顶部观察等破位。"""
    return (chg >= EXTREME_CHG or vr >= EXTREME_VR) and slope < BEAR_MA250_SLOPE


def phase2_reversal(rows: list[dict], i: int, pp: float | None, td, vr: float, chg: float, waiting: bool):
    """右侧确认判定(Phase 2): 集群结束后连涨2天/强反弹买入, 回升过多重置。

    返回 (action, reason, waiting_updated); action None 表示无信号。
    """
    if not waiting:
        return None, "", waiting
    crash_count = _count_crash_accum(rows, i, 10)
    no_recent_accum = td != "ACCUMULATE" and rows[i - 1].get("trade_direction") != "ACCUMULATE" if i > 0 else True
    cluster_ended = crash_count < 2 or no_recent_accum
    pp_ok = pp is not None and pp <= 35
    prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
    two_day_up = cluster_ended and chg > 0 and prev_chg > 0 and vr > 1.0 and pp_ok
    strong_bounce = cluster_ended and chg > 2 and vr > 1.0 and pp_ok
    if two_day_up:
        return "BUY", f"右侧确认: 连涨2天+放量 pp{pp:.0f}", False
    if strong_bounce:
        return "BUY", f"强反弹: 涨{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}", False
    if pp is not None and pp > 50:
        return None, "", False  # 价格回升太多, 重置
    return None, "", waiting


def massive_outflow_confirmed(
    rows: list[dict],
    i: int,
    sd_yi: float,
    cur_shares: float | None,
    base_shares: float | None,
    peak_shares: float | None,
    dist_count: int,
    close: float,
) -> bool:
    """巨量流出卖出确认: 资金撤退过半 + 破位/跌破吸筹起点 双确认。

    不在 DISTRIBUTE 集群中且近 3 日无大额流入; 回撤过半但未跌破吸筹起点
    需叠加价格破位(防震仓误卖, 案例 2026-08-12)。
    """
    in_dist_cluster = dist_count >= 1
    recent_big_inflow = any((rows[j].get("shares_delta_yi") or 0) >= 5 for j in range(max(0, i - 3), i))
    peak_inflow = peak_shares - base_shares if peak_shares is not None and base_shares is not None else 0.0
    low_n = (
        min((rows[j].get("close_price") or 0.0) for j in range(max(0, i - WATCH_BREAK_DAYS), i))
        if i >= WATCH_BREAK_DAYS
        else 0.0
    )
    price_break = close < low_n
    outflow_confirmed = price_break or (cur_shares is not None and base_shares is not None and cur_shares < base_shares)
    return (
        not in_dist_cluster
        and not recent_big_inflow
        and sd_yi <= -5
        and peak_inflow > 0
        and cur_shares is not None
        and base_shares is not None
        and (cur_shares - base_shares) < peak_inflow * 0.5
        and outflow_confirmed
    )


def watch_break(rows: list[dict], i: int, close: float, watch_peak: float, pp: float | None) -> bool:
    """顶部观察破位判定: 破近5日低 / 从观察峰值回撤 / pp 跌破退出线。"""
    low_n = min((rows[j].get("close_price") or 0.0) for j in range(max(0, i - WATCH_BREAK_DAYS), i))
    return close < low_n or close < watch_peak * (1 - TRAIL_PCT) or (pp is not None and pp < WATCH_PP_EXIT)
