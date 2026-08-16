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
  -> S3 顶部大流出(单次>=30亿 或 2次>=15亿) -> S4 尾随 12%
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
OUTFLOW_SUM_MIN = 60.0  # S3 累计流出(亿)确认卖: 持仓期 DISTRIBUTE 日流出累计>=
# 60亿才卖(2025-07-31 -15.9 + 08-14 -30.5 = 46亿洗盘不卖, 08-22 累计85亿卖@1.323;
# 2026-04-30 -29.3 + 05-06 -16.7 = 46亿不卖, 洗盘后 5 月继续涨)
OUTFLOW_SD_MIN = 15.0  # S3 一般大流出(亿), 2 次确认才卖(洗盘 vs 真顶)
TRAIL_PCT = 12.0  # S4 尾随(熊市): 2022-08 顶 -13.6% 才确认
TRAIL_BULL_PCT = 18.0  # S4 尾随(牛市放宽): 2026-06 洗盘 -14% 不卖(6-30 新高 2.344),
# 2026-07 顶 -22.9% 才确认卖 1.807(保住 6 月 V 反转)
TRAIL_MIN_HOLD = 3  # 尾随最短持有


def _ma(closes: list[float], window: int, idx: int) -> float | None:
    if idx < window - 1:
        return None
    return sum(closes[idx - window + 1 : idx + 1]) / window


def _dd_from_high(closes: list[float], idx: int, window: int = 250) -> float:
    lo = max(0, idx + 1 - window)
    hi = max(closes[lo : idx + 1])
    return (closes[idx] / hi - 1) * 100 if hi > 0 else 0.0


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
        dd250 = _dd_from_high(closes, i, 250)

        action = None
        reason = ""

        if position == 1:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            ret_pct = (close / buy_price - 1) * 100 if buy_price else 0.0
            # S1 硬止损
            if ret_pct <= -STOP_LOSS_PCT:
                action, reason = "SELL", f"接刀止损(收盘{ret_pct:.1f}%)"
            # S2 加速赶顶: 观察模式(924 两天+20%, 中间不卖, 峰值回落 3% 确认)
            elif chg >= EXTREME_CHG or vr >= EXTREME_VR:
                watch_extreme = True
                watch_peak = max(watch_peak, close)
            elif watch_extreme:
                watch_peak = max(watch_peak, close)
                if close <= watch_peak * (1 - EXTREME_BREAK_PCT / 100):
                    action, reason = "SELL", f"加速赶顶回落确认: 峰{watch_peak:.3f}+收盘{close:.3f}"
            # S3 顶部大流出: 持仓期累计流出 >=60亿 确认(洗盘累计不够不卖)
            elif td == "DISTRIBUTE" and sd_yi <= -OUTFLOW_SD_MIN:
                outflow_sum += -sd_yi
                if outflow_sum >= OUTFLOW_SUM_MIN:
                    action, reason = "SELL", f"顶部大流出: 累计{outflow_sum:.0f}亿+pp{pp:.0f}"
            # S4 尾随(牛市放宽: 洗盘不卖)
            elif hold_days >= TRAIL_MIN_HOLD:
                trail_pct = TRAIL_BULL_PCT if bull else TRAIL_PCT
                if close <= high_since_buy * (1 - trail_pct / 100):
                    action, reason = "SELL", f"尾随止盈(回撤{trail_pct:.0f}%)"
            if action == "SELL":
                position = 0.0
                watch_extreme = False
                trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})
                action, reason = None, ""

        if position == 0:
            if not warmup_done:
                continue  # 牛熊斜率数据预热不足, 不交易
            # P1 恐慌底
            if chg <= -PANIC_CHG_MIN and pp is not None and pp <= PANIC_PP_MAX:
                action, reason = "BUY", f"恐慌底: 跌{chg:.1f}%+pp{pp:.0f}"
            # P3 熊市深回撤底(跌速趋缓才接)
            elif (
                not bull
                and dd250 <= -BEAR_DD_MIN
                and ma60_slope is not None
                and ma60_slope >= BEAR_MA60_SLOPE_MIN
                and pp is not None
                and pp <= BEAR_PP_MAX
                and sp is not None
                and sp >= BEAR_SP_MIN
            ):
                action, reason = "BUY", f"熊市深回撤底: 距高{dd250:.0f}%+pp{pp:.0f}+sp{sp:.0f}"
            # P4 牛市回调底(恐慌日让位 P1)
            elif (
                bull
                and pp is not None
                and pp <= BULL_PP_MAX
                and sp is not None
                and sp >= BULL_SP_MIN
                and chg <= -BULL_CHG_MIN
                and chg > -BULL_CHG_MAX
            ):
                action, reason = "BUY", f"牛市回调底: 跌{chg:.1f}%+pp{pp:.0f}+sp{sp:.0f}"
            # P5 放量大阳底(924 式政策底)
            elif (
                not bull
                and vr >= SNAP_VR_MIN
                and sp is not None
                and sp >= SNAP_SP_MIN
                and chg >= SNAP_CHG_MIN
                and td == "ACCUMULATE"
            ):
                action, reason = "BUY", f"放量大阳底: 涨{chg:.1f}%+vr{vr:.1f}+sp{sp:.0f}"

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
