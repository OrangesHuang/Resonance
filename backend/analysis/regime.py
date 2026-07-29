"""市场状态检测 — 纯函数，无 I/O。

判断当前处于牛市/熊市/震荡，输出连续状态分数 ∈ [-1, 1]，
作为贝叶斯推断的先验输入。
"""

from config import REGIME_MA_PERIOD, REGIME_EMA_SMOOTH


def detect_regime(
    closes: list[float],
    ma_period: int = REGIME_MA_PERIOD,
    ema_smooth: int = REGIME_EMA_SMOOTH,
) -> float:
    """检测最近一个交易日的市场状态。

    Args:
        closes: 按时间升序排列的收盘价序列
        ma_period: 长期均线周期，默认 200
        ema_smooth: EMA 平滑窗口，默认 20

    Returns:
        状态分数 ∈ [-1, 1]: +1=强牛, -1=强熊, 0=完全中性
    """
    n = len(closes)
    if n < ma_period:
        return 0.0

    # 计算每日价格偏离 MA200 的比例
    deviations = []
    for i in range(ma_period - 1, n):
        ma = sum(closes[i - ma_period + 1:i + 1]) / ma_period
        if ma > 0:
            deviations.append(closes[i] / ma - 1.0)

    if not deviations:
        return 0.0

    # EMA 平滑偏离序列
    alpha = 2.0 / (ema_smooth + 1.0)
    ema = deviations[0]
    for d in deviations[1:]:
        ema = alpha * d + (1.0 - alpha) * ema

    # 归一化到 [-1, 1]：偏离 ±15% 对应 ±1
    return round(max(-1.0, min(1.0, ema / 0.15)), 4)


def regime_label(score: float) -> str:
    """将连续状态分数转为标签。"""
    if score > 0.3:
        return "bull"
    if score < -0.3:
        return "bear"
    return "range"


def regime_prior(score: float) -> tuple[float, float, float]:
    """根据市场状态返回 P(吸筹), P(出货), P(中性) 先验概率。

    牛市 → 吸筹先验高；熊市 → 出货先验高。
    """
    from config import PRIOR_BULL, PRIOR_BEAR, PRIOR_RANGE

    label = regime_label(score)
    if label == "bull":
        p_accum, p_dist = PRIOR_BULL
    elif label == "bear":
        p_accum, p_dist = PRIOR_BEAR
    else:
        p_accum, p_dist = PRIOR_RANGE

    p_neutral = round(1.0 - p_accum - p_dist, 4)
    return p_accum, p_dist, p_neutral
