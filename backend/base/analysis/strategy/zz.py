"""中证1000 (512100) 右侧量价记忆策略。

核心认知:
  中证1000 暴跌集群特征明显 — 连续5-9个ACCUMULATE密集出现
  左侧抄底会在集群中段入场, 继续承压5-10%
  需要等待集群结束+反弹确认后右侧入场

历史教训:
  2026-07-27 买入后 8/10 触发"巨量流出"卖出, 但 7/1-8/4 累计吸筹
  92.4亿仅回撤45.7% — 右侧确认买入使"买入日份额"基准被抬高,
  修正为以"买入前60日最低份额"(吸筹周期起点)为基准
  (2025-02-17 那轮份额跌破吸筹起点, 卖出仍正确, 不受影响)
  2026-08-12 再次触发巨量流出卖出(-6亿), 但 8/5-8/12 累计流出50亿后
  价格仍创反弹新高(3.04→3.16), 属震仓而非资金撤退 — 修正为: 份额
  跌破吸筹起点(净流入归零)无条件卖(2025-02-17 验证), 回撤过半但未
  跌破起点需叠加价格破位确认(收盘跌破近5日最低)

算法:
  Phase 1 — 暴跌集群检测: 10天内≥3个ACCUMULATE → 进入等待
  Phase 2 — 右侧确认: 集群结束后连续2天涨+放量 → 买入
  Phase 3 — 单日恐慌: 跌≥5%+ACCUMULATE → 直接左侧买入(单日极端)
  Phase 4 — 卖出: DISTRIBUTE集群确认 + 量价记忆 + 买入验证期(10日内未脱离
  成本区即认错, 防阴跌陷阱) + 底部失败守卫(连续浮亏离场)
  2021 起全历史(TRADE_START=2021-01-01): 2022-04-29 底 +22.2% / 2024-06-26
  +26.1% / 2025-04-07 +33.1% 均由现有份额/顶部卖出捕获; 验证期+守卫补
  2023-04-25 式阴跌深套的缺口(份额无巨量流出时价格缓慢下跌的轮次)。
"""

from __future__ import annotations

import math

from base.analysis.strategy.metrics import calc_round_metrics

ZZ_CODE = "512100"

SELL_PP_MIN = 75
SELL_VR_MIN = 1.3

# 顶部观察(延迟卖出): 出货确认达标后不立即卖, 等破位
EXTREME_CHG = 3.0  # 确认日涨幅≥此值 → 加速赶顶(924式)立即卖
EXTREME_VR = 4.0  # 确认日量比≥此值 → 立即卖
TRAIL_PCT = 0.04  # 从观察期最高收盘回落幅度触发
WATCH_BREAK_DAYS = 5  # 跌破N日最低收盘触发
WATCH_PP_EXIT = 60  # 观察期 pp 跌破此值立即卖

MIN_HOLD = 5
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2021-01-01"  # 放开 2021 起全历史(2021 前无共振数据)
# 底部失败守卫: 持仓连续浮亏超阈值即顺势离场, 不扛逆势深套
# (案例 2023-04-25 买@2.56, 2023 小盘阴跌份额无巨量流出, 份额卖出不触发,
#  一直扛到 2024-05 -16.4%; 而 2022-04-29 真底部 0 天浮亏超 8%)
UNDERWATER_PCT = 8.0
UNDERWATER_DAYS = 15
# 吸筹周期起点窗口: 右侧确认买入常发生在吸筹中后段, 用买入日份额作基准
# 会把已流入份额计入基准, 导致小幅回撤即"净流入回撤过半"过早卖出
# (案例: 2026-07-27 买入, 7/1-8/4 累计吸筹92.4亿仅回撤45.7%却触发卖出)
BASE_LOOKBACK = 60
# 买入验证期: 买入后应快速脱离成本区, 否则尽早认错离场
# (案例 2023-04-25 买入@2.56, 前20日无恐慌日+20日波动0.90%全史最低,
#  买入后20日价格横盘±1%且份额不流入 — 阴跌陷阱; 而 8 个赢家轮全部
#  在第10日价格≥+3.8% 或份额暴涨承接, 唯一价格为负的 2024-06-26
#  份额+7.1% 承接, 最终 +26.1%。验证期第10日检查: 价格<3%且份额<5%即离场)
VERIFY_START_DAY = 10  # 买入后第 N 日开始检查
VERIFY_ESCAPE_PCT = 3.0  # 累计涨幅低于此值视为未脱离成本区
VERIFY_SHARES_PCT = 5.0  # 份额较买入日增长低于此值视为无承接
# 买入量能门槛: 左侧买入(暴跌抄底/低位吸筹/极冷吸筹/反弹确认)当日量比必须
# 高于均值 20%, 防止"地量假信号"误发买入(2023-05-24 vr0.86 等缩量低位吸筹
# 日 20日胜率仅20%均值-1.9%; 而历史 11 个真实买入 vr 全部≥1.02, 左侧类全部
# ≥1.52, 此门槛不改变任何既有轮次, 只堵规则漏洞: 量能要求显式化)
BUY_VOL_MIN = 1.2


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
    entry_price = None  # 买入价(底部失败守卫用)
    underwater_streak = 0  # 连续浮亏超阈值天数
    entry_shares = None  # 买入时份额
    base_shares = None  # 吸筹起点份额(买入前 BASE_LOOKBACK 日最低)
    peak_shares = None  # 持仓期最高份额(用于计算净流入峰值)
    watch_mode = False  # 顶部观察模式(阈值达标后等破位)
    watch_peak = 0.0  # 观察期最高收盘

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
            if is_accum and chg <= -5 and vr >= BUY_VOL_MIN:
                action = "BUY"
                reason = f"暴跌抄底: 跌{chg:.1f}%+pp{pp:.0f}"

            # 暴跌集群: ≥3个ACCUMULATE → 进入等待右侧确认
            elif in_crash_cluster:
                waiting_for_reversal = True

            # 非暴跌集群的普通买入
            elif is_accum and pp is not None and pp <= 25 and vr >= BUY_VOL_MIN:
                if sp is not None and sp >= 50:
                    action = "BUY"
                    reason = f"低位吸筹: pp{pp:.0f}+sp{sp:.0f}"
                elif tp is not None and tp <= 10:
                    action = "BUY"
                    reason = f"极冷吸筹: pp{pp:.0f}+成交额{tp:.0f}分位"

            # 反弹确认 (跌超7% + 当日回升 + 不在暴跌集群中)
            elif (
                is_accum
                and last_sell_price is not None
                and close < last_sell_price * 0.93
                and chg > 0  # 当日企稳回升, 非继续下跌
                and pp is not None
                and pp <= 30
                and crash_count < 2
                and vr >= BUY_VOL_MIN
            ):
                action = "BUY"
                reason = f"反弹确认: 跌超7%后企稳 pp{pp:.0f}"

        # ---- Phase 2: 右侧确认 (暴跌集群结束后) ----
        if position == 0 and waiting_for_reversal:
            crash_count = _count_crash_accum(rows, i, 10)
            # 集群结束: ACCUMULATE密度下降 或 连续2天无ACCUMULATE
            no_recent_accum = (
                td != "ACCUMULATE" and rows[i - 1].get("trade_direction") != "ACCUMULATE" if i > 0 else True
            )
            cluster_ended = crash_count < 2 or no_recent_accum
            pp_ok = pp is not None and pp <= 35

            prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0

            two_day_up = cluster_ended and chg > 0 and prev_chg > 0 and vr > 1.0 and pp_ok
            strong_bounce = cluster_ended and chg > 2 and vr > 1.0 and pp_ok

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

        # ---- 卖出 (份额驱动 + 底部失败守卫) ----
        if position == 1:
            hold_days += 1
            # 底部失败: 连续浮亏超阈值 → 顺势离场(防 2023-04-25 式阴跌深套)
            if entry_price is not None and close < entry_price * (1 - UNDERWATER_PCT / 100):
                underwater_streak += 1
            else:
                underwater_streak = 0
            cur_shares = row.get("shares_yi")

            # 跟踪持仓期最高份额
            if cur_shares is not None:
                if peak_shares is None:
                    peak_shares = cur_shares
                else:
                    peak_shares = max(peak_shares, cur_shares)

            # 买入验证期: 快速脱离成本区检查(在浮亏守卫之前, 尽早认错)
            if VERIFY_START_DAY <= hold_days <= VERIFY_START_DAY + 5:
                ret_pct = (close / entry_price - 1) * 100 if entry_price else 0.0
                cur_shares = row.get("shares_yi")
                shares_gain = (
                    (cur_shares / entry_shares - 1) * 100
                    if cur_shares is not None and entry_shares and entry_shares > 0
                    else 0.0
                )
                if ret_pct < VERIFY_ESCAPE_PCT and shares_gain < VERIFY_SHARES_PCT:
                    action = "SELL"
                    reason = f"买入未验证: 第{hold_days}日累计{ret_pct:+.1f}%+份额{shares_gain:+.1f}%未承接"

            # 卖出条件1: DISTRIBUTE集群中不触发巨量流出 (让集群完整)
            in_dist_cluster = dist_count >= 1
            recent_big_inflow = any((rows[j].get("shares_delta_yi") or 0) >= 5 for j in range(max(0, i - 3), i))
            peak_inflow = peak_shares - base_shares if peak_shares is not None and base_shares is not None else 0.0
            # 价格破位确认: 收盘跌破近5日最低 (防震仓误卖, 案例 2026-08-12)
            low_n = (
                min((rows[j].get("close_price") or 0.0) for j in range(max(0, i - WATCH_BREAK_DAYS), i))
                if i >= WATCH_BREAK_DAYS
                else 0.0
            )
            price_break = close < low_n
            # 跌破吸筹起点(净流入归零)无条件卖(2025-02-17 验证);
            # 仅回撤过半时需价格破位确认(防震仓误卖, 案例 2026-08-12)
            outflow_confirmed = price_break or (cur_shares is not None and cur_shares < base_shares)
            massive_outflow = (
                not in_dist_cluster  # 不在DISTRIBUTE集群中
                and not recent_big_inflow
                and sd_yi <= -5
                and peak_inflow > 0
                and cur_shares is not None
                and base_shares is not None
                and (cur_shares - base_shares) < peak_inflow * 0.5
                and outflow_confirmed  # 资金撤退过半 + 破位/跌破起点 双确认
            )

            # 卖出条件2: DISTRIBUTE + 份额净流出 (经典确认)
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_ok = vr >= SELL_VR_MIN
            if is_dist and pp_high and vr_ok:
                dist_count += 1

            if hold_days >= MIN_HOLD:
                if underwater_streak >= UNDERWATER_DAYS:
                    action = "SELL"
                    reason = f"底部失败: 连续{UNDERWATER_DAYS}日浮亏超{UNDERWATER_PCT}%"
                elif massive_outflow:
                    action = "SELL"
                    reason = f"巨量流出: {sd_yi:.0f}亿+净流入回撤+pp{pp:.0f}"
                elif is_dist and dist_count >= sell_threshold and not watch_mode:
                    # 首次达标: 加速赶顶日(924式)立即卖, 否则进入顶部观察等破位
                    if chg >= EXTREME_CHG or vr >= EXTREME_VR:
                        reason = f"出货确认+加速赶顶({dist_count}/{sell_threshold})+pp{pp:.0f}+vr{vr:.1f}"
                        action = "SELL"
                    else:
                        watch_mode = True
                        watch_peak = close
                elif watch_mode:
                    # 顶部观察: 跟踪最高收盘, 破位即卖
                    watch_peak = max(watch_peak, close)
                    low_n = min((rows[j].get("close_price") or 0) for j in range(max(0, i - WATCH_BREAK_DAYS), i))
                    if close < low_n or close < watch_peak * (1 - TRAIL_PCT) or (pp is not None and pp < WATCH_PP_EXIT):
                        reason = f"顶部破位: 高点{watch_peak:.3f}+收盘{close:.3f}+pp{pp:.0f}"
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
            entry_price = close
            underwater_streak = 0
            peak_shares = entry_shares
            # 吸筹起点 = 买入前 BASE_LOOKBACK 日内最低份额
            # (右侧确认买入时基准不被已流入份额抬高, 避免过早卖出)
            base_shares = min(
                (v for j in range(max(0, i - BASE_LOOKBACK), i) if (v := rows[j].get("shares_yi")) is not None),
                default=None,
            )
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0 for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": "BUY", "price": close, "reason": f"{reason} [阈值{sell_threshold}]"})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            watch_mode = False
            watch_peak = 0.0
            last_sell_price = close
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = calc_round_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": ZZ_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}
