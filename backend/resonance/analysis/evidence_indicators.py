"""逐指标判定证据构建(纯函数): 价格位置/份额流向/吸筹出货/成交额/融资。

每个指标返回 {method, formula, thresholds, reason, value, inputs} 结构,
供证据面板展示"为什么亮这盏灯"。聚合入口见 evidence.py。
"""

from __future__ import annotations

from base.config import (
    COMPOSITE_PROB_GREEN,
    COMPOSITE_PROB_RED,
    POSITION_HIGH,
    POSITION_LOW,
    POSITION_WINDOW,
    SENTIMENT_ZONE_P_HIGH,
    SENTIMENT_ZONE_P_LOW,
    SHARE_HIGH_FLIP_PP,
    SHARE_LOW_FLIP_PP,
    SHARE_PROB_GREEN,
    SHARE_PROB_RED,
)
from resonance.analysis.composite import format_composite_formula
from resonance.analysis.core import GREEN, RED, fmt_position


def _position_reason(pp, state):
    if pp is None:
        return "无价格位置数据 → 灰灯"
    if state == RED:
        return f"{pp:.1f}% ≥ {POSITION_HIGH:.0f}% → 高位 → 红灯"
    if state == GREEN:
        return f"{pp:.1f}% ≤ {POSITION_LOW:.0f}% → 低位 → 绿灯"
    return f"{POSITION_LOW:.0f}% < {pp:.1f}% < {POSITION_HIGH:.0f}% → 中位 → 灰灯"


def evidence_position(etf_row, state):
    pp = etf_row.get("price_position")
    close = etf_row.get("close_price")
    return {
        "method": (
            f"价格位置 = (当日收盘 − {POSITION_WINDOW}日最低) / "
            f"({POSITION_WINDOW}日最高 − {POSITION_WINDOW}日最低) × 100，"
            f"高低点取自K线数据源"
        ),
        "formula": f"price_position = {fmt_position(pp)}（收盘价 {close}）",
        "thresholds": (f"≥{POSITION_HIGH:.0f} 判高位(红灯)；≤{POSITION_LOW:.0f} 判低位(绿灯)；其间为中性(灰灯)"),
        "reason": _position_reason(pp, state),
        "value": pp,
        "inputs": {"close_price": close, "price_position": pp, "window": POSITION_WINDOW},
    }


def _share_reason(sp, state, pp=None):
    if state == RED:
        if pp is not None and pp >= SHARE_HIGH_FLIP_PP and sp >= SHARE_PROB_GREEN:
            return f"{sp:.0f} ≥ {SHARE_PROB_GREEN:.0f} 且 pp{pp:.0f} ≥ {SHARE_HIGH_FLIP_PP:.0f} → 高位申购=诱多陷阱 → 转出货灯"
        return f"{sp:.0f} ≤ {SHARE_PROB_RED:.0f} → 净赎回 → 红灯"
    if state == GREEN:
        if pp is not None and pp <= SHARE_LOW_FLIP_PP and sp <= SHARE_PROB_RED:
            return f"{sp:.0f} ≤ {SHARE_PROB_RED:.0f} 且 pp{pp:.0f} ≤ {SHARE_LOW_FLIP_PP:.0f} → 低位流出=诱空/恐慌盘 → 转吸筹灯"
        return f"{sp:.0f} ≥ {SHARE_PROB_GREEN:.0f} → 净申购 → 绿灯"
    return f"{SHARE_PROB_RED:.0f} < {sp:.0f} < {SHARE_PROB_GREEN:.0f} → 中性 → 灰灯"


def evidence_share(etf_row, state):
    sp = etf_row.get("share_prob")
    inputs = {
        "shares_delta_pct": etf_row.get("shares_delta_pct"),
        "shares_yi": etf_row.get("shares_yi"),
        "shares_delta_yi": etf_row.get("shares_delta_yi"),
        "share_prob": sp,
    }
    method = "份额流向：由 ETF 当日份额变动率(%)经分段线性映射为份额概率(0-100)，概率越高代表净申购越强"
    thresholds = f"≤{SHARE_PROB_RED:.0f} 判净赎回(红灯)；≥{SHARE_PROB_GREEN:.0f} 判净申购(绿灯)；其间为中性(灰灯)"
    if sp is None:
        return {
            "method": method,
            "formula": "share_prob = 无（当日无份额数据）",
            "thresholds": thresholds,
            "reason": "当日无份额数据 → 无法判定 → 灰灯",
            "value": None,
            "inputs": inputs,
            "data_note": (
                "份额数据仅在实时采集日（每个交易日收盘后）写入，历史种子数据不含份额因子，因此该指标历史多为灰灯。"
            ),
        }
    sdp = etf_row.get("shares_delta_pct")
    return {
        "method": method,
        "formula": f"份额变动率 {sdp}% → share_prob = {sp:.0f}",
        "thresholds": thresholds,
        "reason": _share_reason(sp, state, etf_row.get("price_position")),
        "value": sp,
        "inputs": inputs,
    }


def evidence_composite(etf_row, state):
    cp = etf_row.get("composite_prob")
    vp = etf_row.get("vol_prob")
    dp = etf_row.get("dir_prob")
    sp = etf_row.get("share_prob")
    pp = etf_row.get("price_position")
    method = (
        "吸筹/出货：方向概率定基调(逆市护盘/超额收益/指数趋势)，"
        "量能概率调节偏离置信度(缩量压回中性、放量保持偏离)，"
        "价格位置×量能交互(低位放量=吸筹证据、高位放量=出货证据)，"
        "份额概率验证(与基调一致加分、矛盾减分)，综合反映 ETF 吸筹/出货强度"
    )
    thresholds = f"≤{COMPOSITE_PROB_RED:.0f} 判出货(红灯)；≥{COMPOSITE_PROB_GREEN:.0f} 判吸筹(绿灯)；其间为中性(灰灯)"
    if cp is None:
        reason = "无综合概率数据 → 灰灯"
    elif state == RED:
        reason = f"综合概率 {cp:.1f} ≤ {COMPOSITE_PROB_RED:.0f} → 出货信号 → 红灯"
    elif state == GREEN:
        reason = f"综合概率 {cp:.1f} ≥ {COMPOSITE_PROB_GREEN:.0f} → 吸筹信号 → 绿灯"
    else:
        reason = f"综合概率 {cp:.1f} 处于 {COMPOSITE_PROB_RED:.0f}~{COMPOSITE_PROB_GREEN:.0f} 之间 → 中性 → 灰灯"
    return {
        "method": method,
        "formula": format_composite_formula(vp, dp, sp, pp, cp),
        "thresholds": thresholds,
        "reason": reason,
        "value": cp,
        "inputs": {"vol_prob": vp, "dir_prob": dp, "share_prob": sp, "price_position": pp, "composite_prob": cp},
    }


def _pct_reason(label, p, state, invert=False):
    if p is None:
        return f"无{label}分位数据 → 灰灯"
    if state == RED:
        if invert:
            return f"{label} {p}%分位 ≤ {SENTIMENT_ZONE_P_LOW:.0f} → 避险资金流出/冷清 → 红灯"
        return f"{label} {p}%分位 ≥ {SENTIMENT_ZONE_P_HIGH:.0f} → 过热 → 红灯"
    if state == GREEN:
        if invert:
            return f"{label} {p}%分位 ≥ {SENTIMENT_ZONE_P_HIGH:.0f} → 避险资金涌入 → 绿灯"
        return f"{label} {p}%分位 ≤ {SENTIMENT_ZONE_P_LOW:.0f} → 冷清 → 绿灯"
    return f"{SENTIMENT_ZONE_P_LOW:.0f} < {label} {p}%分位 < {SENTIMENT_ZONE_P_HIGH:.0f} → 中性 → 灰灯"


def evidence_pct(label, method, det, state, invert=False):
    if invert:
        thresholds = (
            f"防御资产反转: ≥{SENTIMENT_ZONE_P_HIGH:.0f} 判避险流入(绿灯)；"
            f"≤{SENTIMENT_ZONE_P_LOW:.0f} 判避险流出(红灯)；其间为中性(灰灯)"
        )
    else:
        thresholds = (
            f"≥{SENTIMENT_ZONE_P_HIGH:.0f} 判过热(红灯)；≤{SENTIMENT_ZONE_P_LOW:.0f} 判冷清(绿灯)；其间为中性(灰灯)"
        )
    if det is None:
        return {
            "method": method,
            "formula": "当日无分位数据（样本不足或非交易日）",
            "thresholds": thresholds,
            "reason": _pct_reason(label, None, state, invert),
            "value": None,
            "inputs": {},
        }
    p = det["percentile"]
    return {
        "method": method,
        "formula": (f"({det['below']} + 0.5×{det['equal']}) / {det['count']} × 100 = {p}%分位"),
        "thresholds": thresholds,
        "reason": _pct_reason(label, p, state, invert),
        "value": p,
        "inputs": {
            "当日值(亿元)": det["value"],
            "窗口样本数": det["count"],
            "低于当日": det["below"],
            "等于当日": det["equal"],
            "窗口最小": det["min"],
            "窗口最大": det["max"],
        },
        "window": det["window"],
        "window_stats": {
            "count": det["count"],
            "below": det["below"],
            "equal": det["equal"],
            "min": det["min"],
            "max": det["max"],
        },
    }
