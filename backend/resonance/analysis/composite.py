from __future__ import annotations

from base.config import (
    COMPOSITE_AGREE_REWARD,
    COMPOSITE_CONFLICT_PENALTY,
    COMPOSITE_PP_VOL_MAX,
    COMPOSITE_VOLUME_FLOOR,
    COMPOSITE_VOLUME_SPAN,
    VOLUME_MA_WINDOW,
)
from resonance.analysis.factors import (
    calc_direction_probability,
    calc_price_position,
    calc_share_probability,
    calc_volume_probability,
    classify_signal,
    classify_trade_direction,
)


def calc_composite_probability(
    vp: float,
    dp: float,
    sp: float | None,
    price_position: float | None = None,
) -> float:
    """分层门控模型: 方向为基调, 量能为置信度, 份额+价格为验证层。

    Layer 1: 方向概率作为基调 (dp)
    Layer 2: 量概率调节方向偏离度 — 低量收缩向中性, 高量保持偏离
    Layer 3: 价格位置×量能交互 — 低位放量=吸筹证据, 高位放量=出货证据
    Layer 4: 份额验证 — 价格位置作为可信度放大器(方向不对称)
      流入: 低位放大(便宜价位买入更可信), 过半反转惩罚(高位申购疑似诱多/傻大户接盘),
      且 pp≥95 惩罚加倍(极高位仍大额申购几乎必为诱多, 如 589680 2025-08-28 pp99.7
      申购1.2亿 → 后5日-8.6%; 159780 2024-10-08 pp100 申购11亿 → 后5日-20%)
      流出: 高位放大(高价抛售更可信), 低位衰减(低位赎回未必真出货)
      历史案例: 589680 2026-06-29 pp99.8 流入0.6亿 → 旧式75.1吸筹, 实为见顶(后5日-4.4%);
      反例: 563300 2026-01 连涨期高位流入后继续涨, 反转惩罚会漏掉该类绿灯(可接受: 错过行情被允许)。
    """
    direction_deviation = (dp - 50) / 50
    volume_confidence = vp / 100
    adjusted_deviation = direction_deviation * (COMPOSITE_VOLUME_FLOOR + COMPOSITE_VOLUME_SPAN * volume_confidence)
    signal = 50 + adjusted_deviation * 50

    if price_position is not None:
        pp_deviation = (price_position - 50) / 50
        signal += pp_deviation * volume_confidence * -COMPOSITE_PP_VOL_MAX

    if sp is not None:
        share_deviation = (sp - 50) / 50
        if price_position is not None:
            if share_deviation > 0:
                # 流入证据: 位置反转惩罚 — 低位(pp=0)全奖励, pp=50归零;
                # pp≥50 转惩罚且 pp≥95 惩罚加倍(极高位仍大额申购=诱多/傻大户接盘)
                position_scale = 1.0 - price_position / 50.0
                if price_position >= 95:
                    position_scale *= 2.0
            else:
                position_scale = 0.5 + price_position / 100
        else:
            position_scale = 1.0
        amplified = share_deviation * position_scale
        if amplified > 0:
            signal += amplified * COMPOSITE_AGREE_REWARD
        else:
            signal += amplified * COMPOSITE_CONFLICT_PENALTY

    return round(max(0.0, min(100.0, signal)), 1)


def format_composite_formula(
    vp: float | None,
    dp: float | None,
    sp: float | None,
    price_position: float | None,
    cp: float | None,
) -> str:
    """按 4 层门控逐步展开当日算式, 供证据弹窗展示(缺输入时逐层降级)。"""
    if vp is None or dp is None:
        return f"composite_prob = {cp}（缺量能/方向概率, 无法展开算式）"
    expr = f"50 + ({dp}−50)/50×50×({COMPOSITE_VOLUME_FLOOR:g}+{COMPOSITE_VOLUME_SPAN:g}×{vp}/100)"
    if price_position is not None:
        expr += f" − ({price_position}−50)/50×({vp}/100)×{COMPOSITE_PP_VOL_MAX:g}"
    if sp is not None:
        if price_position is not None:
            if sp > 50:
                scale = 1.0 - price_position / 50.0
                if price_position >= 95:
                    scale *= 2.0
            else:
                scale = 0.5 + price_position / 100
        else:
            scale = 1.0
        reward = COMPOSITE_AGREE_REWARD if (sp - 50) * scale > 0 else COMPOSITE_CONFLICT_PENALTY
        expr += f" + ({sp}−50)/50×{scale:.2f}×{reward:g}"
    return f"{expr} → 截断[0,100] = {cp}"


def _calc_t5_return(kline: list[dict], end_idx: int) -> float | None:
    if end_idx < 5:
        return None
    recent = kline[end_idx - 4 : end_idx + 1]
    if len(recent) < 5 or recent[0]["close"] == 0:
        return None
    return (recent[-1]["close"] - recent[0]["close"]) / recent[0]["close"] * 100


def analyze_single_etf(
    kline: list[dict],
    idx_kline: list[dict],
    shares_delta_pct: float | None,
    target_idx: int | None = None,
) -> dict | None:
    if len(kline) < VOLUME_MA_WINDOW:
        return None

    if target_idx is None:
        target_idx = len(kline) - 1

    target = kline[target_idx]
    window = kline[max(0, target_idx - VOLUME_MA_WINDOW + 1) : target_idx + 1]
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
    price_position = calc_price_position(kline, target_idx)
    trade_direction = classify_trade_direction(price_position, volume_ratio)
    cp = calc_composite_probability(vp, dp, sp, price_position)
    signal_level = classify_signal(cp)

    prev_close = kline[target_idx - 1]["close"] if target_idx > 0 else target["open"]
    change_pct = (target["close"] - prev_close) / prev_close * 100 if prev_close else 0

    return {
        "date": target["date"],
        "open": target["open"],
        "close": target["close"],
        "high": target["high"],
        "low": target["low"],
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
