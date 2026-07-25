from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from config import (
    ETFS, VOLUME_MA_WINDOW, TRADING_MINUTES,
    MARKET_OPEN_HOUR, MARKET_OPEN_MIN,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN,
    LUNCH_START_HOUR, LUNCH_START_MIN,
    LUNCH_END_HOUR, LUNCH_END_MIN,
)
from fetch.realtime import RealtimeQuote
from analysis.factors import (
    calc_volume_probability,
    calc_direction_probability,
    calc_share_probability,
    classify_signal,
    calc_price_position_from_price,
    classify_trade_direction,
)
from analysis.composite import calc_composite_probability


@dataclass
class IntradaySignal:
    code: str
    name: str
    idx_name: str
    price: float
    change_pct: float
    volume_hand: float
    volume_ratio: float
    vol_prob: float
    dir_prob: float
    share_prob: Optional[float]
    composite_prob: float
    signal_level: str
    premium_pct: Optional[float]
    price_position: Optional[float]
    trade_direction: str
    timestamp: str


def _elapsed_trading_minutes(now: datetime) -> float:
    open_t = time(MARKET_OPEN_HOUR, MARKET_OPEN_MIN)
    close_t = time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN)
    lunch_start = time(LUNCH_START_HOUR, LUNCH_START_MIN)
    lunch_end = time(LUNCH_END_HOUR, LUNCH_END_MIN)

    current = now.time()
    if current <= open_t:
        return 0.0
    if current >= close_t:
        return float(TRADING_MINUTES)

    if current <= lunch_start:
        return (current.hour * 60 + current.minute) - (open_t.hour * 60 + open_t.minute)
    elif current <= lunch_end:
        return 120.0
    else:
        afternoon = (current.hour * 60 + current.minute) - (lunch_end.hour * 60 + lunch_end.minute)
        return 120.0 + afternoon


def _volume_correction_factor(elapsed: float) -> float:
    # U型量能分布: 开盘30min占20%, 尾盘15min占15%, 中间195min占65%
    if elapsed <= 0:
        return 0.001
    if elapsed <= 30:
        return 0.20 * (elapsed / 30)
    elif elapsed <= 225:
        return 0.20 + 0.65 * ((elapsed - 30) / 195)
    else:
        return 0.85 + 0.15 * ((elapsed - 225) / 15)


def calc_intraday_signal(
    quote: RealtimeQuote,
    idx_quote: Optional[RealtimeQuote],
    kline_history: list[dict],
    latest_share_delta_pct: Optional[float],
    now: datetime,
) -> Optional[IntradaySignal]:
    elapsed = _elapsed_trading_minutes(now)
    if elapsed < 5:
        return None

    if len(kline_history) < VOLUME_MA_WINDOW:
        return None

    ma20 = sum(k["volume"] for k in kline_history[-VOLUME_MA_WINDOW:]) / VOLUME_MA_WINDOW
    if ma20 <= 0:
        return None

    correction = _volume_correction_factor(elapsed)
    expected_volume = ma20 * correction
    # quote.volume_hand 单位是手, kline volume 单位也是手(万手需确认)
    intraday_vr = quote.volume_hand / expected_volume if expected_volume > 0 else 1.0
    vp = calc_volume_probability(intraday_vr)

    chg = quote.change_pct
    idx_chg = idx_quote.change_pct if idx_quote else 0.0

    t5_etf = 0.0
    t5_idx = 0.0
    if len(kline_history) >= 5:
        recent5 = kline_history[-5:]
        if recent5[0]["close"] > 0:
            t5_etf = (recent5[-1]["close"] - recent5[0]["close"]) / recent5[0]["close"] * 100

    dp = calc_direction_probability(
        chg=chg, t5_etf=t5_etf, t5_idx=t5_idx,
        volume_ratio=intraday_vr, idx_chg=idx_chg,
    )

    sp = calc_share_probability(latest_share_delta_pct)
    cp = calc_composite_probability(vp, dp, sp)
    signal_level = classify_signal(cp)

    price_position = calc_price_position_from_price(quote.price, kline_history)
    trade_direction = classify_trade_direction(price_position, intraday_vr)

    premium_pct = None
    if idx_quote and quote.prev_close > 0:
        estimated_nav = quote.prev_close * (1 + idx_chg / 100)
        if estimated_nav > 0:
            premium_pct = round((quote.price - estimated_nav) / estimated_nav * 100, 3)

    info = ETFS.get(quote.code, {})
    return IntradaySignal(
        code=quote.code,
        name=info.get("name", quote.name),
        idx_name=info.get("idx", ""),
        price=quote.price,
        change_pct=round(chg, 2),
        volume_hand=quote.volume_hand,
        volume_ratio=round(intraday_vr, 3),
        vol_prob=round(vp, 1),
        dir_prob=round(dp, 1),
        share_prob=round(sp, 1) if sp is not None else None,
        composite_prob=cp,
        signal_level=signal_level,
        premium_pct=premium_pct,
        price_position=price_position,
        trade_direction=trade_direction,
        timestamp=now.strftime("%Y-%m-%dT%H:%M:%S"),
    )
