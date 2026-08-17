"""科创50 (588000) Beta — 高波动宽基的买卖点先行策略。[2026-08-17 按用户 9 组买卖点重新拟合, 全历史 +405.9%]

核心认知(用户方法论):
  买点 = 价格低位 + 机构净申购(sd>0, 9 组买点无一例外; ETF 份额申赎是
  公募/做市商行为, 散户做不到单日 34 亿); 顶分两类 —
    净赎回顶(机构撤离: 连续3交易日净流出+承接消失sp<=15+浮盈>=18):
      2025-02-26 / 2023-04-03 / 2025-08-22;
    净申购顶(散户狂热接盘, 力竭): 2022-08-05 / 2024-10-10 / 2026-06-30,
      靠放量触线/加速赶顶/暴跌离场。
  单日流出可能是波段内洗盘(2026-01-14 前日+4亿、2025-07-29 前日+8亿、
  2025-08-12 浮盈15.9%), 需连续撤离+浮盈门槛双确认。

算法:
  买入(全部 sd>0): P1 恐慌底(跌>=6%+pp<=20) / P3 熊市深回撤底(距250日高
  <=-38%+跌速趋缓) / P4 牛市回调底(pp<=35+sp>=50+距60日高<=-8%) /
  P5 放量大阳底(924式) / P6 熊市回调底(pp15-30+距线浅+申购>=5亿+跌势衰竭)
  卖出: S1 止损-5% -> S-A 净赎回顶 -> S-B 熊市反弹触线(放量+浮盈>=15) ->
  S6 暴跌离场 -> S2 加速赶顶观察 -> S3 累计流出100亿 -> S4 尾随(熊15/牛18);
  尾随与当日买入信号冲突时买入优先(虚拟换仓不记录)。
  迭代备忘: 顶背离卖(1-14 vs 8-14 同指纹矛盾)、浮盈分档(切碎大波段)、
  13% 尾随(0.971 vs 线 0.970 边缘触发)均过拟合撤回; 尾随参数不可泛化,
  卖出主力是 S-A/S-B/S6/S2, 尾随仅兜底。
"""

from __future__ import annotations

from base.analysis.strategy.metrics import calc_round_metrics

KC50_BETA_CODE = "588000"
TRADE_START = "2020-12-11"  # ETF 数据首日(2020-11 上市, 腾讯接口从 12-11 起有数据)

# 买入路径阈值(案例见 docstring)
PANIC_CHG_MIN = 6.0  # P1 恐慌底单日跌幅下限(%)
PANIC_PP_MAX = 20.0  # P1 恐慌底 pp 上限
BEAR_DD_MIN = 38.0  # P3 熊市深回撤底: 距250日高回撤下限(2022-10-10 -38.4 真底;
# 2022-09-30 -35.5 买贵 4.5% 被拦, 等 10-10 更深的底)
BEAR_MA60_SLOPE_MIN = -5.0  # P3 跌速门槛: ma60 20日斜率>=-5%(跌速趋缓才接;
# 2022-04-07/14 斜率-8.5% 加速下跌接刀必死; 2022-10-10 -3.4% 跌势衰竭)
BEAR_PP_MAX = 20.0  # P3 pp 上限(2022-10-12 pp17.8)
BULL_PP_MAX = 35.0  # P4 牛市回调底 pp 上限(2025-11-21 pp29.6 回调底; 2026-03-03 pp36.4 接刀被拦)
BULL_SP_MIN = 50.0  # P4 份额下限(2025-01-06 sp55.7; 2022-01-19 sp38.7 顶后第一波被拦)
BULL_DD60_MIN = 8.0  # P4 距60日高回撤下限(2025-01-06 -9.3%; 2022-01-19 -4.3% 浅回撤被拦)
BULL_CHG_MIN = 3.0  # P4 当日跌幅下限(2025-11-21 -3.2%; 2022 接刀日 -2.8 被拦)
BULL_CHG_MAX = 6.0  # P4 当日跌幅上限(恐慌日让位 P1 等更极端买点: 2026-07-28 -6.6% pp24
# 不买, 07-30 pp3 的 P1 买更低)
SNAP_VR_MIN = 2.0  # P5 放量大阳底量比下限(924 前夜 vr2.09)
SNAP_SP_MIN = 50.0  # P5 份额下限
SNAP_CHG_MIN = 3.0  # P5 当日涨幅下限
# 熊市回调底(2022-12-23 案例: pp23.7 中位回调+距线-15.5%+申购5.3亿, 跌势衰竭)
BEAR_RB_PP_LO = 15.0
BEAR_RB_PP_HI = 30.0
BEAR_RB_DIV_MIN = 18.0  # 距 ma250 浅回撤下限
BEAR_RB_SD_MIN = 5.0  # 申购下限(2022-12-22 5.3亿真回调底; 2023-11-22 2.9亿/
# 2024-05-15 2.5亿/2024-07-09 2.1亿 阴跌年接刀全拦)
BEAR_RB_DD_MIN = 10.0  # 距250日高回撤下限(2022-01-19 顶后第一波 -5% 被拦)
# 卖出
STOP_LOSS_PCT = 5.0  # S1 硬止损(假底快速认错)
EXTREME_CHG = 15.0  # S2 加速赶顶单日涨幅(924: 9-30 +19.95%)
EXTREME_VR = 4.0  # S2 加速赶顶量比(924: 9-30 vr4.8)
EXTREME_BREAK_PCT = 3.0  # S2 观察模式: 峰值回落此幅度确认(924 10-09 从 1.14 回落)
OUTFLOW_SUM_MIN = 100.0  # S3 累计流出(亿)确认卖(2025-08 洗盘85亿不卖, 110亿卖)
OUTFLOW_SD_MIN = 15.0  # S3 一般大流出(亿), 2 次确认才卖(洗盘 vs 真顶)
TRAIL_PCT = 15.0  # S4 尾随(熊市兜底; 12/13/15 三案例打架, 不可泛化)
TRAIL_BULL_PCT = 18.0  # S4 尾随(牛市): 吃大波段, 波段内回调(2026-01~03 -16%、
# 2026-06 -14% 洗盘)持有穿越; 顶部确认(6-30 顶 2.344 后)才离场
OUT_MIN = 10.0  # S-A 净赎回顶: 单日净流出(亿)(2026-04-27 -9.7亿 波段内洗盘被拦,
# 5-6月还涨到2.344; 2025-02-26 -11.9 / 2023-04-04 -13.5 / 2025-08-22 -38.7 真顶)
OUT_SP_MAX = 15.0  # S-A 承接消失(份额概率)
OUT_PP_MIN = 80.0  # S-A 高位
OUT_PROFIT_MIN = 18.0  # S-A 浮盈门槛: 2025-08-12 浮盈15.9%波段内洗盘被拦(8月新高);
# 2025-02-26 19.9% / 2023-04-04 21.8% / 2025-08-22 36.4% 真顶放行
TOUCH_DIV_MIN = -7.0  # S-B 反弹触线: 距 ma250 7% 内(2022-08-05 -6.6 / 11-04 -6.5)
TOUCH_PROFIT_MIN = 15.0  # S-B 浮盈门槛(2023-01-02 月到线浮盈<15% 持有穿越)
TOUCH_CHG_MIN = 2.0  # S-B 放量上攻(2022-06-13 缩量阴跌触线是洗盘不卖)
TOUCH_VR_MIN = 1.3
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
    if sd_yi <= 0:
        return None, ""  # 买点必须是机构净申购日(9 组买点 sd>0 无一例外)
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
            # S-A 净赎回顶(连续3交易日撤离+承接消失+浮盈>=18%):
            # 2025-02-26 / 2023-04-04 / 2025-08-22 真顶; 2025-08-12(浮盈15.9%)、
            # 2026-01-14(浮盈16.9%)波段内洗盘被浮盈门槛拦
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
            # S-B 熊市反弹触线(放量上攻到 ma250 目标位+浮盈可观):
            # 2022-08-05/11-04 卖; 2022-06-13 缩量阴跌触线是洗盘不卖
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
            # S1 硬止损
            if action is None and ret_pct <= -STOP_LOSS_PCT:
                action, reason = "SELL", f"接刀止损(收盘{ret_pct:.1f}%)"
            # S6 牛市暴跌离场: 吃大波段的代价是顶部暴跌才跑(2026-07-02 案例)
            elif bull and chg <= -PANIC_SELL_CHG:
                action, reason = "SELL", f"牛市暴跌离场: 跌{chg:.1f}%"
            # S2 加速赶顶: 观察模式(924 两天+20%, 中间不卖, 峰值回落 3% 确认)
            elif chg >= EXTREME_CHG or vr >= EXTREME_VR:
                watch_extreme = True
                watch_peak = max(watch_peak, close)
            elif watch_extreme:
                watch_peak = max(watch_peak, close)
                if close <= watch_peak * (1 - EXTREME_BREAK_PCT / 100):
                    action, reason = "SELL", f"加速赶顶回落确认: 峰{watch_peak:.3f}+收盘{close:.3f}"
            # S3 顶部大流出: 持仓期累计流出 >=60亿 确认(洗盘累计不够不卖)
            if action is None and td == "DISTRIBUTE" and sd_yi <= -OUTFLOW_SD_MIN:
                outflow_sum += -sd_yi
                if outflow_sum >= OUTFLOW_SUM_MIN:
                    action, reason = "SELL", f"顶部大流出: 累计{outflow_sum:.0f}亿+pp{pp:.0f}"
            # S4 尾随(牛市放宽: 洗盘不卖)
            if action is None and hold_days >= TRAIL_MIN_HOLD:
                trail_pct = TRAIL_BULL_PCT if bull else TRAIL_PCT
                if close <= high_since_buy * (1 - trail_pct / 100):
                    action, reason = "SELL", f"尾随止盈(回撤{trail_pct:.0f}%)"
                    trail_sell = True
            # 尾随让位: 当日同时出现强买入信号(如 2026-03-23 牛市回调底),
            # 说明是洗盘而非趋势破坏 — 继续持有, 不做"同日卖+买"的无意义换仓;
            # 虚拟换仓重置基准(peak/流出/持有天数), 否则旧 peak 的尾随线会卡死
            # 后续持有(3-31 再次触发卖出, 反而更差)
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
