"""科创50 (588000) Beta — 高波动宽基的买卖点先行策略。

核心认知:
  科创50 波动剧烈(单日 ±5-20%, 924 两天 +40%), 2021-08 顶 1.657 至
  2024-02 底 0.709 长熊(-57%)中夹 4 次大反弹(+31.6%/+25%/+14%);
  924 后三段大牛(2024-09 +63% / 2025-04~08 +48% / 2026-03~07 +72%)。
  份额信号极强(日增 ±5~76 亿): 底部散户暴买(sp95), 顶部大额流出(-16~-49亿)。

历史教训:
  2022-01-05 集群假底(pp0-8 sp75-88, 买入后 -31%): 跌势未成熟(ma60 斜率
  +0.3%)接刀, 靠 -5% 硬止损认错, 2022-04-25 真底再买;
  2023-08-28 假底(sp91 sd+21亿, 距250日高仅 -23.9% 浅回撤): 熊市阴跌途中,
  距高门槛 -30% 拦截, 真底 2024-02-05 回撤 -41.5%;
  2024-02-05 真底 sp47 弱承接(买不动了)被拦, 错过后 924 轮抓住(+63%);
  2022-08-05 顶份额仍流入(sd+9亿) 份额流出信号失效, 靠尾随 12% 兜底。

算法(买入路径化):
  牛熊斜率预热不足(ma250+20日)不交易; P1 恐慌底: 单日跌>=6%+pp<=20;
  P3 熊市深回撤底: 距250日高<=-35% + pp<=20 + sp>=60(2022-10-10);
  P4 牛市回调底: ma250上行 + pp<=20 + sp>=75 + 当日跌>=4%(2026-03-23);
  P5 放量大阳底(924式): 熊市 + vr>=2 + sp>=50 + 当日涨>=3%(2024-09-24)
  卖出: S1 硬止损-5% -> S2 加速赶顶观察(924 两天+20%不卖, 峰值回落3%确认)
  -> S6 牛市暴跌离场(单日跌>=6% 果断卖, 2026-07-02 顶后次日卖@2.119) ->
  S7 出货确认(综指移植, 过拟合探针: DIST+pp>=97+vr>=1.5+净赎回 -> 次日卖) ->
  S3 顶部大流出(累计>=100亿) -> S4 尾随(熊市15% 让波段走完; 牛市18% 吃大波段);
  规律挖掘(2026-08-17 过拟合探针结论): 588000 顶部分两类 —
    净赎回顶(2023-04/2025-08, sd<0+DIST): S7 提前确认卖;
    净申购顶(2022-08/2024-10/2026-06-30, sd>0): 靠量价兜底(S2 加速/S6 暴跌/尾随);
  尾随参数 12/13/15 在三个案例上互相打架(8-31 vs 12-21 vs 12-22 边缘触发),
  该参数不可泛化, 后续版本应让 S7/S6 承担卖出、尾随仅兜底。
  尾随与当日买入信号冲突时买入优先(继续持有, 不做同日换仓)；
  迭代备忘: "牛市顶背离卖"(2026-01-14 顶 vs 2025-08-14 主升同指纹矛盾)与
  "浮盈分档尾随"(波段内回调 3-17 卖 3-23 买, 把大波段切碎)均已撤回;
  正确哲学 = 牛市吃大波段(回调持有穿越) + 顶部暴跌日果断离场(S6)。
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
BEAR_SP_MIN = 60.0  # P3 份额下限(2022-10-12 sp69.2; 2024-02-05 sp47 被拦)
BULL_PP_MAX = 35.0  # P4 牛市回调底 pp 上限(2025-11-21 pp29.6 回调底; 2026-03-03 pp36.4 接刀被拦)
BULL_SP_MIN = 75.0  # P4 份额下限
BULL_CHG_MIN = 3.0  # P4 当日跌幅下限(2025-11-21 -3.2%; 2022 接刀日 -2.8 被拦)
BULL_CHG_MAX = 6.0  # P4 当日跌幅上限(恐慌日让位 P1 等更极端买点: 2026-07-28 -6.6% pp24
# 不买, 07-30 pp3 的 P1 买更低)
SNAP_VR_MIN = 2.0  # P5 放量大阳底量比下限(924 前夜 vr2.09)
SNAP_SP_MIN = 50.0  # P5 份额下限
SNAP_CHG_MIN = 3.0  # P5 当日涨幅下限
# 卖出
STOP_LOSS_PCT = 5.0  # S1 硬止损(假底快速认错)
EXTREME_CHG = 15.0  # S2 加速赶顶单日涨幅(924: 9-30 +19.95%)
EXTREME_VR = 4.0  # S2 加速赶顶量比(924: 9-30 vr4.8)
EXTREME_BREAK_PCT = 3.0  # S2 观察模式: 峰值回落此幅度确认(924 10-09 从 1.14 回落)
OUTFLOW_SUM_MIN = 100.0  # S3 累计流出(亿)确认卖: 持仓期 DISTRIBUTE 日流出累计>=
# 100亿才卖(2025-07-31~08-22 累计85亿洗盘不卖, 08-28 累计110亿卖@1.433 顶;
# 2026-04-30 -29.3 + 05-06 -16.7 = 46亿不卖, 洗盘后 5 月继续涨)
OUTFLOW_SD_MIN = 15.0  # S3 一般大流出(亿), 2 次确认才卖(洗盘 vs 真顶)
TRAIL_PCT = 15.0  # S4 尾随(熊市): 放宽让波段走完(2022-12 回调 -12% 持有穿越,
# 2023-03-23 出货确认 -> 03-24 卖@1.104 vs 12% 尾随 12-21 卖@0.981; 13% 在 12-22
# 边缘触发(0.971 vs 线0.970)过拟合弃用; 代价是 2022-08 顶后拖到 9-19 卖 1.021
DIST_PP_MIN = 97.0  # S7 出货确认(综指移植): 顶部区 pp 门槛
DIST_VR_MIN = 1.5  # S7 出货确认: 量比门槛(2026-06-24 vr1.2 缩量顶不误杀)
TRAIL_BULL_PCT = 18.0  # S4 尾随(牛市): 吃大波段, 波段内回调(2026-01~03 -16%、
# 2026-06 -14% 洗盘)持有穿越; 顶部确认(6-30 顶 2.344 后)才离场
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
    if chg <= -PANIC_CHG_MIN and pp is not None and pp <= PANIC_PP_MAX:
        return "BUY", f"恐慌底: 跌{chg:.1f}%+pp{pp:.0f}"
    if (
        not bull
        and dd250 <= -BEAR_DD_MIN
        and ma60_slope is not None
        and ma60_slope >= BEAR_MA60_SLOPE_MIN
        and pp is not None
        and pp <= BEAR_PP_MAX
        and sp is not None
        and sp >= BEAR_SP_MIN
    ):
        return "BUY", f"熊市深回撤底: 距高{dd250:.0f}%+pp{pp:.0f}+sp{sp:.0f}"
    if (
        bull
        and pp is not None
        and pp <= BULL_PP_MAX
        and sp is not None
        and sp >= BULL_SP_MIN
        and chg <= -BULL_CHG_MIN
        and chg > -BULL_CHG_MAX
    ):
        return "BUY", f"牛市回调底: 跌{chg:.1f}%+pp{pp:.0f}+sp{sp:.0f}"
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
    pending_sell: str | None = None  # S7 出货确认信号日(次日卖, 综指 T+1 口径)

    for i, row in enumerate(rows):
        d = row["date"]
        if d < TRADE_START:
            continue
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
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
        dd250 = _dd_from_high(closes, i, 250)

        action = None
        reason = ""

        buy_candidate, buy_reason = _buy_signal(rows, closes, i, bull, dd250, ma60_slope, warmup_done)

        if position == 1:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            ret_pct = (close / buy_price - 1) * 100 if buy_price else 0.0
            trail_sell = False
            # S7 出货确认(综指移植): 昨日 DIST+pp>=97+vr>=1.5+净赎回 -> 今日卖
            # (2023-04-03 信号 -> 04-04 卖 1.172; 2025-08-22 信号 -> 08-25 卖 1.356;
            #  净申购顶 2022-08-05/2024-10-08/2026-06-30 不触发, 靠量价兜底)
            if pending_sell:
                action, reason = "SELL", f"出货确认(信号{pending_sell})"
                pending_sell = None
            if (
                action is None
                and td == "DISTRIBUTE"
                and pp is not None
                and pp >= DIST_PP_MIN
                and vr >= DIST_VR_MIN
                and sd_yi < 0
            ):
                pending_sell = d
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
                pending_sell = None
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
            pending_sell = None
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})

    metrics = calc_round_metrics(trades, closes[-1] if closes else 0.0, position)
    return {"code": KC50_BETA_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}
