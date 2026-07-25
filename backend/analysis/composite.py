from typing import Optional

from config import (
    WEIGHT_VOLUME, WEIGHT_DIRECTION, WEIGHT_SHARES,
    WEIGHT_VOLUME_DEGRADED, WEIGHT_DIRECTION_DEGRADED,
    VOLUME_MA_WINDOW,
)
from analysis.factors import (
    calc_volume_probability,
    calc_direction_probability,
    calc_share_probability,
    classify_signal,
    calc_price_position,
    classify_trade_direction,
)


def calc_composite_probability(
    vp: float, dp: float, sp: Optional[float]
) -> float:
    if sp is not None:
        return round(vp * WEIGHT_VOLUME + dp * WEIGHT_DIRECTION + sp * WEIGHT_SHARES, 1)
    return round(vp * WEIGHT_VOLUME_DEGRADED + dp * WEIGHT_DIRECTION_DEGRADED, 1)


def _calc_t5_return(kline: list[dict], end_idx: int) -> Optional[float]:
    if end_idx < 5:
        return None
    recent = kline[end_idx - 4: end_idx + 1]
    if len(recent) < 5 or recent[0]["close"] == 0:
        return None
    return (recent[-1]["close"] - recent[0]["close"]) / recent[0]["close"] * 100


def analyze_single_etf(
    kline: list[dict],
    idx_kline: list[dict],
    shares_delta_pct: Optional[float],
    target_idx: Optional[int] = None,
) -> Optional[dict]:
    if len(kline) < VOLUME_MA_WINDOW:
        return None

    if target_idx is None:
        target_idx = len(kline) - 1

    target = kline[target_idx]
    window = kline[max(0, target_idx - VOLUME_MA_WINDOW + 1): target_idx + 1]
    ma20 = sum(k["volume"] for k in window) / len(window)
    if ma20 == 0:
        return None

    volume_ratio = target["volume"] / ma20
    vp = calc_volume_probability(volume_ratio)

    chg = (target["close"] - target["open"]) / target["open"] * 100 if target["open"] else 0
    t5_etf = _calc_t5_return(kline, target_idx)
    t5_idx = _calc_t5_return(idx_kline, min(target_idx, len(idx_kline) - 1))

    idx_chg = 0.0
    if idx_kline and target_idx < len(idx_kline):
        idx_bar = idx_kline[target_idx]
        if idx_bar["open"]:
            idx_chg = (idx_bar["close"] - idx_bar["open"]) / idx_bar["open"] * 100

    dp = calc_direction_probability(
        chg=chg,
        t5_etf=t5_etf or 0,
        t5_idx=t5_idx or 0,
        volume_ratio=volume_ratio,
        idx_chg=idx_chg,
    )

    sp = calc_share_probability(shares_delta_pct)
    cp = calc_composite_probability(vp, dp, sp)
    signal_level = classify_signal(cp)

    price_position = calc_price_position(kline, target_idx)
    trade_direction = classify_trade_direction(price_position, volume_ratio)

    prev_close = kline[target_idx - 1]["close"] if target_idx > 0 else target["open"]
    change_pct = (target["close"] - prev_close) / prev_close * 100 if prev_close else 0

    return {
        "date": target["date"],
        "close": target["close"],
        "change_pct": round(change_pct, 2),
        "volume": target["volume"],
        "volume_ma20": round(ma20, 2),
        "volume_ratio": round(volume_ratio, 3),
        "vol_prob": round(vp, 1),
        "dir_prob": round(dp, 1),
        "share_prob": round(sp, 1) if sp is not None else None,
        "composite_prob": cp,
        "signal_level": signal_level,
        "idx_chg": round(idx_chg, 2),
        "price_position": price_position,
        "trade_direction": trade_direction,
    }
