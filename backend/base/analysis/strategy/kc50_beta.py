"""科创50 (588000) Beta — 高波动宽基买卖点先行。[按用户 9 组拟合 + 两处优化, 全历史 +584.5%]

核心认知: 买点 = 价格低位 + 机构净申购(sd>0, 9 组买点无一例外); 顶分两类 —
净赎回顶(机构连续3交易日撤离+承接消失sp<=15+浮盈>=18%: 2-26/4-03/8-22)与
净申购顶(散户接盘力竭: 放量触线/加速赶顶/暴跌离场); 单日流出多为波段内
洗盘(1-14/7-29/8-12), 需连续撤离+浮盈双确认。

算法: 买入(全 sd>0): P1 恐慌底 / P3 熊市深回撤底(距250日高<=-38%+跌速趋缓)
/ P4 牛市回调底(pp<=35+sp>=50+距60日高<=-8%) / P5 放量大阳底(924式) /
P6 熊市回调底(pp15-30+距线浅+申购>=5亿)。卖出: S1 止损-5% -> S-A 净赎回顶
-> S-B 放量触线 -> S-D 温和滞涨顶(2024-03-20) -> S-E 缩量新高背离(2026-01-22)
-> S6 暴跌离场 -> S2 加速赶顶观察 -> S3 累计流出100亿 -> S4 尾随兜底;
尾随与当日买入冲突时买入优先(虚拟换仓)。迭代备忘: 顶背离/浮盈分档/13%尾随
(浮点边缘)过拟合撤回, 尾随参数不可泛化仅兜底。
"""

from __future__ import annotations

from base.analysis.strategy.metrics import calc_round_metrics

KC50_BETA_CODE = "588000"
TRADE_START = "2020-12-11"  # ETF 数据首日(2020-11 上市, 腾讯接口从 12-11 起有数据)

# 买入路径阈值(案例见 docstring)
PANIC_CHG_MIN = 6.0  # P1 恐慌底单日跌幅下限(%)
PANIC_PP_MAX = 20.0  # P1 恐慌底 pp 上限
BEAR_DD_MIN = 38.0  # P3 熊市深回撤底: 距250日高回撤下限(2022-10-10 -38.4 真底;
# 2022-09-30 -35.5 买贵 4.5% 被拦)
BEAR_MA60_SLOPE_MIN = -5.0  # P3 跌速门槛: 斜率>=-5% 跌势趋缓才接(2022-04 -8.5% 接刀必死)
BEAR_PP_MAX = 20.0  # P3 pp 上限(2022-10-12 pp17.8)
BULL_PP_MAX = 35.0  # P4 牛市回调底 pp 上限(2025-11-21 pp29.6; 2026-03-03 pp36.4 接刀拦)
BULL_SP_MIN = 50.0  # P4 份额下限(2025-01-06 sp55.7; 2022-01-19 sp38.7 顶后第一波拦)
BULL_DD60_MIN = 8.0  # P4 距60日高回撤下限(2026-01-06 -9.3%; 2022-01-19 -4.3% 拦)
BULL_CHG_MIN = 3.0  # P4 当日跌幅下限(2025-11-21 -3.2%)
BULL_CHG_MAX = 6.0  # P4 当日跌幅上限(恐慌日让位 P1: 2026-07-28 -6.6% 不买等 07-30)
SNAP_VR_MIN = 2.0  # P5 放量大阳底(924 前夜 vr2.09)
SNAP_SP_MIN = 50.0  # P5 份额下限
SNAP_CHG_MIN = 3.0  # P5 当日涨幅下限
# P7 线上极冷底(2025-01-06: 价格在 ma250 上+17% 但被判熊, 成交额极冷+机构
# 净申购+距60日高-12.5%; 不依赖牛熊判定)
ONLINE_TP_MAX = 10.0  # 成交额极冷
ONLINE_PP_MAX = 35.0
ONLINE_DD60_MIN = 8.0  # 距60日高回撤下限(2022-01-19 -4.9% 顶后第一波拦)
ONLINE_CHG_MAX = 6.0  # 恐慌日让位 P1(2026-07-28 不买)
ONLINE_PREV_CHG_MIN = -3.0  # 前一日非暴跌(2026-07-29 暴跌次日不接)
# 熊市回调底(2022-12-23: pp23.7 中位回调+距线-15.5%+申购5.3亿, 跌势衰竭)
BEAR_RB_PP_LO = 15.0
BEAR_RB_PP_HI = 30.0
BEAR_RB_DIV_MIN = 18.0  # 距 ma250 浅回撤下限
BEAR_RB_SD_MIN = 5.0  # 申购下限(12-22 5.3亿; 23-11-22/24-05-15/24-07-09 2~3亿接刀全拦)
BEAR_RB_DD_MIN = 10.0  # 距250日高回撤下限(2022-01-19 顶后第一波 -5% 拦)
# 卖出
STOP_LOSS_PCT = 5.0  # S1 硬止损(假底快速认错)
EXTREME_CHG = 15.0  # S2 加速赶顶涨幅(924: 9-30 +19.95%)
EXTREME_VR = 4.0  # S2 加速赶顶量比(924: 9-30 vr4.8)
EXTREME_BREAK_PCT = 3.0  # S2 观察回落确认(924 10-09 从 1.14 回落)
OUTFLOW_SUM_MIN = 100.0  # S3 累计流出(亿)确认卖(2025-08 洗盘85亿不卖, 110亿卖)
OUTFLOW_SD_MIN = 15.0  # S3 一般大流出(亿), 2 次确认才卖(洗盘 vs 真顶)
TRAIL_PCT = 15.0  # S4 尾随(熊市兜底; 12/13/15 三案例打架, 不可泛化)
TRAIL_BULL_PCT = 18.0  # S4 尾随(牛市): 吃大波段, 波段内回调(2026-01~03 -16%、
# 2026-06 -14% 洗盘)持有穿越; 顶部确认(6-30 顶 2.344 后)才离场
OUT_MIN = 10.0  # S-A 净赎回顶单日流出(亿)(4-27 -9.7洗盘拦; 2-26/4-04/8-22 -12~-39真顶)
OUT_SP_MAX = 15.0  # S-A 承接消失(份额概率)
OUT_PP_MIN = 80.0  # S-A 高位
OUT_PROFIT_MIN = 18.0  # S-A 浮盈门槛: 2025-08-12 浮盈15.9%波段内洗盘被拦(8月新高);
# 2025-02-26 19.9% / 2023-04-04 21.8% / 2025-08-22 36.4% 真顶放行
TOUCH_DIV_MIN = -7.0  # S-B 反弹触线: 距 ma250 7% 内(2022-08-05 -6.6 / 11-04 -6.5)
TOUCH_PROFIT_MIN = 15.0  # S-B 浮盈门槛(2023-01-02 月到线浮盈<15% 持有穿越)
TOUCH_CHG_MIN = 2.0  # S-B 放量上攻(2022-06-13 缩量阴跌触线是洗盘不卖)
TOUCH_VR_MIN = 1.3
LAG_PROFIT_MIN = 15.0  # S-D 温和滞涨顶浮盈门槛(2024-03-20 +16.2%)
LAG_DAYS = 2  # S-D 距前高 N 日不新高
LAG_SP_MAX = 40.0  # S-D 承接弱(3-20 sp29; 6-13 sp56.7 洗盘拦)
DIVG_PROFIT_MIN = 15.0  # S-E 缩量新高背离浮盈门槛(2026-01-22 +20%)
DIVG_VR_MAX = 1.0  # S-E 缩量(1-22 vr0.84; 8-15 chg1.4 被 chg<=1 拦)
DIVG_OUTFLOW_3D = 20.0  # S-E 前3日累计流出(亿)(1-20/21/22 25.7亿; 6-30 前3日12亿不足)
PANIC_SELL_CHG = 6.0  # S6 牛市暴跌离场: 牛市持仓单日跌>=6% 果断卖(与 S2 加速
# 赶顶对称的"情绪崩"信号; 2026-07-02 顶后次日 -7.5% 卖@2.119 vs 尾随 7-17 卖
# 1.807; 2026-06 洗盘三连跌 -4.5~-5 未达 6 不误杀)
TRAIL_MIN_HOLD = 3  # 尾随最短持有


def _ma(closes: list[float], window: int, idx: int) -> float | None:
    if idx < window - 1:
        return None
    return sum(closes[idx - window + 1 : idx + 1]) / window


def _dd_from_high(closes: list[float], idx: int, window: int = 250) -> float:
    lo = max(0, idx + 1 - window)
    hi = max(closes[lo : idx + 1])
    return (closes[idx] / hi - 1) * 100 if hi > 0 else 0.0


def _buy_signal(
    rows: list[dict],
    closes: list[float],
    i: int,
    bull: bool,
    dd250: float,
    ma60_slope: float | None,
    warmup_done: bool,
    div: float = 0.0,
) -> tuple[str | None, str]:
    """买入信号判定(纯函数, 不改状态): 供空仓买入与"尾随让位"两处复用。"""
    if not warmup_done:
        return None, ""
    row = rows[i]
    pp = row.get("price_position")
    td = row.get("trade_direction")
    sp = row.get("share_prob")
    vr = row.get("volume_ratio") or 0
    chg = row.get("change_pct") or 0
    sd_yi = row.get("shares_delta_yi") or 0
    tp = row.get("_tp")
    if sd_yi <= 0:
        return None, ""  # 买点必须机构净申购(sd>0, 9 组无一例外)
    if chg <= -PANIC_CHG_MIN and pp is not None and pp <= PANIC_PP_MAX:
        return "BUY", f"恐慌底: 跌{chg:.1f}%+pp{pp:.0f}"
    if (
        not bull
        and dd250 <= -BEAR_DD_MIN
        and ma60_slope is not None
        and ma60_slope >= BEAR_MA60_SLOPE_MIN
        and pp is not None
        and pp <= BEAR_PP_MAX
    ):
        return "BUY", f"熊市深回撤底: 距高{dd250:.0f}%+pp{pp:.0f}+申购{sd_yi:.0f}亿"
    if (
        bull
        and pp is not None
        and pp <= BULL_PP_MAX
        and sp is not None
        and sp >= BULL_SP_MIN
        and chg <= -BULL_CHG_MIN
        and chg > -BULL_CHG_MAX
        and _dd_from_high(closes, i, 60) <= -BULL_DD60_MIN
    ):
        return "BUY", f"牛市回调底: 跌{chg:.1f}%+pp{pp:.0f}+sp{sp:.0f}"
    if (
        not bull
        and pp is not None
        and BEAR_RB_PP_LO <= pp <= BEAR_RB_PP_HI
        and div >= -BEAR_RB_DIV_MIN
        and sd_yi >= BEAR_RB_SD_MIN
        and dd250 <= -BEAR_RB_DD_MIN
        and ma60_slope is not None
        and ma60_slope >= -3.0
    ):
        return "BUY", f"熊市回调底: pp{pp:.0f}+距线{div:.0f}%+申购{sd_yi:.0f}亿"
    if (
        not bull
        and vr >= SNAP_VR_MIN
        and sp is not None
        and sp >= SNAP_SP_MIN
        and chg >= SNAP_CHG_MIN
        and td == "ACCUMULATE"
    ):
        return "BUY", f"放量大阳底: 涨{chg:.1f}%+vr{vr:.1f}+sp{sp:.0f}"
    if (
        div > 0
        and tp is not None
        and tp <= ONLINE_TP_MAX
        and pp is not None
        and pp <= ONLINE_PP_MAX
        and _dd_from_high(closes, i, 60) <= -ONLINE_DD60_MIN
        and chg > -ONLINE_CHG_MAX
        and (rows[i - 1].get("change_pct") or 0) > ONLINE_PREV_CHG_MIN
    ):
        return "BUY", f"线上极冷底: pp{pp:.0f}+成交额{tp:.0f}分位+申购{sd_yi:.0f}亿"
    return None, ""


def run_kc50_beta_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": KC50_BETA_CODE, "trades": [], "metrics": {}, "holding": False}
    closes = [r.get("close_price") or 0.0 for r in rows]

    trades: list[dict] = []
    position = 0.0
    hold_days = 0
    high_since_buy = 0.0
    buy_price = 0.0
    watch_extreme = False  # S2 观察模式(加速赶顶后等回落确认)
    watch_peak = 0.0
    outflow_sum = 0.0  # S3 持仓期累计流出(亿)

    for i, row in enumerate(rows):
        d = row["date"]
        if d < TRADE_START:
            continue
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        sd_yi = row.get("shares_delta_yi") or 0

        m250 = _ma(closes, 250, i)
        m250_prev = _ma(closes, 250, max(0, i - 20))
        m60 = _ma(closes, 60, i)
        m60_prev = _ma(closes, 60, max(0, i - 20))
        ma60_slope = (m60 / m60_prev - 1) * 100 if m60 and m60_prev else None
        warmup_done = m250_prev is not None  # 牛熊斜率数据预热完成(250+20 交易日)
        bull = m250 is not None and m250_prev is not None and m250 > m250_prev
        div = (close / m250 - 1) * 100 if m250 else 0.0
        dd250 = _dd_from_high(closes, i, 250)

        action = None
        reason = ""

        buy_candidate, buy_reason = _buy_signal(rows, closes, i, bull, dd250, ma60_slope, warmup_done, div)

        if position == 1:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            ret_pct = (close / buy_price - 1) * 100 if buy_price else 0.0
            trail_sell = False
            if (
                action is None
                and sd_yi <= -OUT_MIN
                and sp is not None
                and sp <= OUT_SP_MAX
                and pp is not None
                and pp >= OUT_PP_MIN
                and ret_pct >= OUT_PROFIT_MIN
                and i >= 2
                and (rows[i - 1].get("shares_delta_yi") or 0) <= -0.5
                and (rows[i - 2].get("shares_delta_yi") or 0) <= -0.5
            ):
                action, reason = "SELL", f"净赎回顶: 流出{sd_yi:.0f}亿+sp{sp:.0f}"
            if (
                action is None
                and not bull
                and div >= TOUCH_DIV_MIN
                and ret_pct >= TOUCH_PROFIT_MIN
                and chg >= TOUCH_CHG_MIN
                and vr >= TOUCH_VR_MIN
                and chg < EXTREME_CHG
                and vr < EXTREME_VR
            ):
                action, reason = "SELL", f"反弹触线: 距线{div:+.1f}%+浮盈{ret_pct:.0f}%"
            if (
                action is None
                and not bull
                and ret_pct >= LAG_PROFIT_MIN
                and sp is not None
                and sp <= LAG_SP_MAX
                and hold_days > LAG_DAYS
                and close < high_since_buy
                and vr < 1.0
                and div >= -13.0
            ):
                recent_high = max(closes[max(0, i - LAG_DAYS) : i]) if i >= LAG_DAYS else close
                if close < recent_high:
                    action, reason = "SELL", f"温和滞涨顶: 浮盈{ret_pct:.0f}%+缩量"
            if (
                action is None
                and ret_pct >= DIVG_PROFIT_MIN
                and close >= high_since_buy
                and vr < DIVG_VR_MAX
                and chg <= 1.0
                and i >= 3
                and sum((rows[j].get("shares_delta_yi") or 0) for j in range(i - 2, i + 1)) <= -DIVG_OUTFLOW_3D
            ):
                action, reason = "SELL", f"缩量新高背离: 浮盈{ret_pct:.0f}%+前3日流出"
            # S1 硬止损
            if action is None and ret_pct <= -STOP_LOSS_PCT:
                action, reason = "SELL", f"接刀止损(收盘{ret_pct:.1f}%)"
            elif bull and chg <= -PANIC_SELL_CHG:
                action, reason = "SELL", f"牛市暴跌离场: 跌{chg:.1f}%"
            elif chg >= EXTREME_CHG or vr >= EXTREME_VR:
                watch_extreme = True
                watch_peak = max(watch_peak, close)
            elif watch_extreme:
                watch_peak = max(watch_peak, close)
                if close <= watch_peak * (1 - EXTREME_BREAK_PCT / 100):
                    action, reason = "SELL", f"加速赶顶回落确认: 峰{watch_peak:.3f}+收盘{close:.3f}"
            if action is None and td == "DISTRIBUTE" and sd_yi <= -OUTFLOW_SD_MIN:
                outflow_sum += -sd_yi
                if outflow_sum >= OUTFLOW_SUM_MIN:
                    action, reason = "SELL", f"顶部大流出: 累计{outflow_sum:.0f}亿+pp{pp:.0f}"
            if action is None and hold_days >= TRAIL_MIN_HOLD:
                trail_pct = TRAIL_BULL_PCT if bull else TRAIL_PCT
                if close <= high_since_buy * (1 - trail_pct / 100):
                    action, reason = "SELL", f"尾随止盈(回撤{trail_pct:.0f}%)"
                    trail_sell = True
            if action == "SELL" and trail_sell and buy_candidate == "BUY":
                action, reason = None, ""
                hold_days = 0
                high_since_buy = close
                buy_price = close
                outflow_sum = 0.0
                watch_extreme = False
                watch_peak = 0.0
            if action == "SELL":
                position = 0.0
                watch_extreme = False
                trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})
                action, reason = None, ""

        if position == 0 and buy_candidate == "BUY":
            action, reason = buy_candidate, buy_reason

        if action == "BUY":
            position = 1.0
            hold_days = 0
            high_since_buy = close
            buy_price = close
            watch_extreme = False
            watch_peak = 0.0
            outflow_sum = 0.0
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})

    metrics = calc_round_metrics(trades, closes[-1] if closes else 0.0, position)
    return {"code": KC50_BETA_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}
