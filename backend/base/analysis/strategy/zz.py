"""中证1000 (512100) 右侧量价记忆策略。[正式版 — 2026-08-16 由 Beta 升级 +288.8% vs 旧版 +190.8%; 2026-08-17 延伸至 2019 起全历史链式 +643.3%]

核心认知: 暴跌集群特征明显(连续5-9个ACCUMULATE密集出现), 左侧抄底会在
集群中段入场继续承压5-10%, 需等集群结束+反弹确认后右侧入场。

历史教训(每条规则至少一个案例):
  2026-07-27 买入日份额基准被抬高致"巨量流出"误卖 — 份额基准改用买入前
  60日最低份额(吸筹周期起点); 2026-08-12 震仓(-6亿)后价格创新高 —
  回撤过半需叠加价格破位确认(收盘跌破近5日最低)
  2020-02-03 疫情底单日-10.4%跌停量比失真(vr0.85)方向漏判 — 恐慌底不限
  td/vr; 2020-03-23 全球股灾底缩量急跌td全NEUTRAL — 急跌末端企稳路径
  2019-02-18 春季主升加速赶顶卖飞+15% — 加速赶顶立即卖仅熊市(ma250下行)
  2023-04-25 阴跌陷阱/2023-09-22 — 验证期第10日一次性检查: 涨幅达标(牛市
  0%/熊市3%)或份额>=5%锁定, 否则立即认错; 2020-03-23 第10日+5.1%锁定

算法: 恐慌底(跌>=7%+pp<=20) → 暴跌集群右侧确认 → 缩量深底(pp<=12+回撤
>=25%+融资<=30分位) → 急跌末端(跌>=4.5%+pp<=30+20日跌>=12%) → 单日恐慌
/低位吸筹/极冷吸筹/反弹确认; 卖出: DISTRIBUTE集群(加速赶顶仅熊市立即卖,
否则顶部观察) + 巨量流出 + 热度顶 + 缩量深底尾随 + 底部失败守卫。
  2019 起全历史: 2019-06 +19.4% / 2020-03 +36.0% / 2020-09 +8.8% /
  2022-04 +28.9% / 2022-10 +16.1% / 2024-06 +26.1% / 2025-04 +33.1% /
  2026-03 +17.6%
"""

from __future__ import annotations

import math

from base.analysis.strategy.metrics import calc_round_metrics
from base.analysis.strategy.zz_helpers import (
    _count_crash_accum,
    _dd_from_high,
    _ma250_slope,
    _recent_accum,
    extreme_bear_only,
    is_hot_top,
    is_panic_bottom,
    is_quiet_deep,
    is_quiet_trail,
    is_rapid_end,
    massive_outflow_confirmed,
    phase2_reversal,
    watch_break,
)
from base.analysis.strategy.zz_params import *

ZZ_CODE = "512100"


def run_zz_strategy(rows: list[dict], trade_start: str | None = None) -> dict:
    """trade_start: 覆盖 TRADE_START(zz_beta 延伸验证用), None 走常量。"""
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
    quiet_buy = False  # 缩量深底买入(30日验证期+尾随止盈)
    quiet_peak = 0.0  # 缩量深底持仓期最高收盘(尾随止盈用)
    verify_locked = False  # 验证期已达标锁定(不再复查)

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

        if d < (trade_start or TRADE_START):
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- Phase 0: 单日史诗级恐慌底(不受集群等待限制) ----
        if position == 0 and is_panic_bottom(chg, pp):
            action = "BUY"
            reason = f"恐慌底: 单日跌{chg:.1f}%+pp{pp:.0f}"

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

        # ---- Phase 1.5: 缩量深底 (阴跌尽头的杠杆出清形态) ----
        # 仅放量路径未触发时启用(2024-02-01 td=ACCUMULATE 走低位吸筹, 不被覆盖)
        if action is None and position == 0 and not waiting_for_reversal:
            mp = row.get("_mp")
            dd250 = _dd_from_high(closes, i, 250)
            if is_quiet_deep(pp, mp, dd250, _recent_accum(rows, i, QUIET_NO_ACCUM_DAYS)):
                action = "BUY"
                reason = f"缩量深底: pp{pp:.0f}+融资{mp:.0f}分位+回撤{dd250:.0f}%"

        # ---- Phase 1.6: 急跌末端企稳(非集群缩量赶底) ----
        if action is None and position == 0 and not waiting_for_reversal:
            dd20 = _dd_from_high(closes, i, 20)
            if is_rapid_end(chg, pp, dd20, _recent_accum(rows, i, QUIET_NO_ACCUM_DAYS)):
                action = "BUY"
                reason = f"急跌末端: 跌{chg:.1f}%+pp{pp:.0f}+20日{dd20:.0f}%"

        # ---- Phase 2: 右侧确认 (暴跌集群结束后) ----
        if position == 0 and waiting_for_reversal:
            act2, rsn2, waiting_for_reversal = phase2_reversal(rows, i, pp, td, vr, chg, waiting_for_reversal)
            if act2:
                action = act2
                reason = rsn2

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
            # 缩量深底磨底慢: 30日验证(QUIET), 放量底10日验证(普通)
            verify_lo = QUIET_VERIFY_START if quiet_buy else VERIFY_START_DAY  # 一次性检查日
            if hold_days == verify_lo and not verify_locked:
                ret_pct = (close / entry_price - 1) * 100 if entry_price else 0.0
                cur_shares = row.get("shares_yi")
                shares_gain = (
                    (cur_shares / entry_shares - 1) * 100
                    if cur_shares is not None and entry_shares and entry_shares > 0
                    else 0.0
                )
                # 熊市反弹多陷阱: 验证门槛更高(2023-06-26 +1.6% 阴跌陷阱 vs
                # 2020-03-23 +5.1% V反转), 牛市/数据不足宽松(2026-03/2019-06)
                ret_min = VERIFY_BEAR_ESCAPE_PCT if _ma250_slope(closes, i) < BEAR_MA250_SLOPE else VERIFY_ESCAPE_PCT
                if ret_pct >= ret_min or shares_gain >= VERIFY_SHARES_PCT:
                    verify_locked = True
                else:
                    action = "SELL"
                    reason = f"买入未验证: 第{hold_days}日累计{ret_pct:+.1f}%+份额{shares_gain:+.1f}%未承接"

            # 熊市热度顶止盈: 弱反弹顶波段卖出(924 前熊市; 牛市热度顶是常态不卖)
            # 案例: 2023-02-16 熊市顶 pp99+成交额热, 卖+16.1% vs 缩量深底尾随+6.1%;
            # 牛市 2025-07-31 同样热度顶但 ma250 上行, 屏蔽避免卖飞 +33.1% 主升
            # 缩量深底(quiet)也适用: 优先级高于 quiet 尾随(先看是否热度顶)
            if action is None and hold_days > HOT_BREAK_DAYS:
                slope = _ma250_slope(closes, i)
                if is_hot_top(pp, row.get("_tp"), closes, i, slope):
                    action = "SELL"
                    reason = f"熊市热度顶: pp{pp:.0f}+成交额{row.get('_tp'):.0f}分位破5日低"

            # 缩量深底尾随止盈: 高点回撤即离场(防阴跌年深套, 案例 2022-10-10)
            if quiet_buy:
                quiet_peak = max(quiet_peak, close)
                if is_quiet_trail(close, quiet_peak, hold_days, MIN_HOLD):
                    action = "SELL"
                    reason = f"缩量深底尾随: 峰{quiet_peak:.3f}+收盘{close:.3f}回撤10%"

            # 卖出条件1: 巨量流出(资金撤退过半 + 破位/跌破吸筹起点双确认,
            # 不在DISTRIBUTE集群中且近3日无大额流入; 防震仓误卖案例 2026-08-12)
            massive_outflow = massive_outflow_confirmed(
                rows, i, sd_yi, cur_shares, base_shares, peak_shares, dist_count, close
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
                    # 首次达标: 加速赶顶日仅熊市(ma250下行)立即卖, 否则进顶部观察等破位
                    # (924 熊末脉冲 2024-10-08 ma250下行 保留立即卖; 牛市主升的加速
                    #  赶顶不是顶: 2019-02-18 春季行情卖飞+15%, 2020-07-06 科技牛卖飞+8%,
                    #  转观察后等破位多拿; ma250 数据不足按非熊处理)
                    if extreme_bear_only(chg, vr, _ma250_slope(closes, i)):
                        reason = f"出货确认+加速赶顶({dist_count}/{sell_threshold})+pp{pp:.0f}+vr{vr:.1f}"
                        action = "SELL"
                    else:
                        watch_mode = True
                        watch_peak = close
                elif watch_mode:
                    # 顶部观察: 跟踪最高收盘, 破位即卖
                    watch_peak = max(watch_peak, close)
                    if watch_break(rows, i, close, watch_peak, pp):
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
            quiet_buy = reason.startswith("缩量深底")  # 30日验证期+尾随仅缩量深底用
            quiet_peak = close if quiet_buy else 0.0
            entry_price = close
            underwater_streak = 0
            verify_locked = False
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
            quiet_buy = False
            quiet_peak = 0.0
            last_sell_price = close
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = calc_round_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": ZZ_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}
