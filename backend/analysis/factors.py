from typing import Optional

from config import (
    SIGNAL_HIGH, SIGNAL_MID,
    POSITION_WINDOW, POSITION_LOW, POSITION_HIGH, VOLUME_ACTIVE_RATIO,
)


def calc_volume_probability(volume_ratio: float) -> float:
    r = volume_ratio
    if r < 0.5:
        return max(0.0, r / 0.5 * 5)
    elif r < 1.0:
        return 5 + (r - 0.5) / 0.5 * 12
    elif r < 1.3:
        return 17 + (r - 1.0) / 0.3 * 18
    elif r < 1.5:
        return 35 + (r - 1.3) / 0.2 * 20
    elif r < 2.0:
        return 55 + (r - 1.5) / 0.5 * 25
    elif r < 3.0:
        return 80 + (r - 2.0) / 1.0 * 15
    elif r < 5.0:
        return 95 + (r - 3.0) / 2.0 * 3
    else:
        return min(100.0, 98 + (r - 5.0) / 5.0 * 2)


RALLY_DISCOUNTS = [(2.0, 0.60), (1.5, 0.70), (1.0, 0.80), (0.5, 0.90)]


def _rally_discount(idx_chg: float) -> float:
    for threshold, discount in RALLY_DISCOUNTS:
        if idx_chg > threshold:
            return discount
    return 1.0


def calc_direction_probability(
    chg: float,
    t5_etf: float,
    t5_idx: float,
    volume_ratio: float,
    idx_chg: float,
) -> float:
    # f1: 逆市护盘检测 (40%)
    if chg > 0.3 and t5_idx < -1:
        f1 = 95.0
    elif chg > 0 and idx_chg < -0.5:
        f1 = 85.0
    elif chg > 0 and idx_chg > 0.5:
        f1 = 35.0
    elif chg < -1 and idx_chg < -1:
        f1 = 10.0
    else:
        f1 = 45.0

    # f2: ETF vs 指数超额收益 (30%)
    gap = t5_etf - t5_idx
    if gap > 3:
        f2 = 95.0
    elif gap > 2:
        f2 = 85.0
    elif gap > 1.2:
        f2 = 75.0
    elif gap > 0.6:
        f2 = 60.0
    elif gap > -0.6:
        f2 = 40.0
    else:
        f2 = 15.0

    # f3: 指数近期趋势 (20%)
    if t5_idx < -4:
        f3 = 95.0
    elif t5_idx < -2:
        f3 = 80.0
    elif t5_idx < 0:
        f3 = 55.0
    elif t5_idx < 3:
        f3 = 30.0
    else:
        f3 = 10.0

    # f4: 基线 (10%)
    f4 = 35.0

    raw = f1 * 0.4 + f2 * 0.3 + f3 * 0.2 + f4 * 0.1
    return round(raw * _rally_discount(idx_chg), 1)


def calc_share_probability(share_delta_pct: Optional[float]) -> Optional[float]:
    if share_delta_pct is None:
        return None
    x = share_delta_pct
    if x > 10:
        return 95.0
    elif x > 5:
        return 80 + (x - 5) / 5 * 15
    elif x > 3:
        return 65 + (x - 3) / 2 * 15
    elif x > 1:
        return 45 + (x - 1) / 2 * 20
    elif x > 0:
        return 30 + x / 1 * 15
    elif x > -1:
        return 15 + (x + 1) / 1 * 15
    elif x > -5:
        return 5 + (x + 5) / 4 * 10
    else:
        return max(0.0, 5 + (x + 5) / 5 * 5)


def calc_share_probability_sigmoid(
    share_delta_pct: Optional[float],
    k: float = 0.5,
    midpoint: float = 1.5,
) -> Optional[float]:
    """平滑 sigmoid 映射份额变动率 → 概率 (0-100)。

    替代分段线性映射，消除边界不连续性。
    参数校准使曲线与原分段函数近似:
      k=0.5, midpoint=1.5
      delta=0  → ~32 (原 30)
      delta=1  → ~44 (原 45)
      delta=3  → ~68 (原 65-80)
      delta=5  → ~85 (原 80-95)
      delta=-1 → ~18 (原 15-30)
    """
    if share_delta_pct is None:
        return None
    import math
    return round(100.0 / (1.0 + math.exp(-k * (share_delta_pct - midpoint))), 1)


def classify_signal(composite_prob: float) -> str:
    if composite_prob >= SIGNAL_HIGH:
        return "HIGH"
    elif composite_prob >= SIGNAL_MID:
        return "MID"
    return "LOW"


def calc_price_position(
    kline: list[dict], target_idx: int, window: int = POSITION_WINDOW
) -> Optional[float]:
    start = max(0, target_idx - window + 1)
    recent = kline[start: target_idx + 1]
    if not recent:
        return None
    hi = max(k["high"] for k in recent)
    lo = min(k["low"] for k in recent)
    if hi <= lo:
        return 50.0
    close = kline[target_idx]["close"]
    return round((close - lo) / (hi - lo) * 100, 1)


def calc_price_position_from_price(
    price: float, kline: list[dict], window: int = POSITION_WINDOW
) -> Optional[float]:
    recent = kline[-window:]
    if not recent:
        return None
    hi = max(k["high"] for k in recent)
    lo = min(k["low"] for k in recent)
    if hi <= lo:
        return 50.0
    pos = (price - lo) / (hi - lo) * 100
    return round(max(0.0, min(100.0, pos)), 1)


def classify_trade_direction(
    price_position: Optional[float], volume_ratio: Optional[float]
) -> str:
    if price_position is None or volume_ratio is None:
        return "NEUTRAL"
    if volume_ratio < VOLUME_ACTIVE_RATIO:
        return "NEUTRAL"
    if price_position <= POSITION_LOW:
        return "ACCUMULATE"
    if price_position >= POSITION_HIGH:
        return "DISTRIBUTE"
    return "NEUTRAL"
