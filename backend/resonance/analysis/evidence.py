"""共振日级证据聚合: 逐指标判定依据构建 + 单日详情组装(纯函数)。

单个指标的 evidence 结构构建见 evidence_indicators.py;
本模块负责分位明细计算与 5 指标证据聚合为页面可展示结构。
"""

from __future__ import annotations

from base.analysis.sentiment.core import pct_rank_parts, turnover_value
from base.config import (
    DEFENSIVE_ETFS,
    ETFS,
    SENTIMENT_MA_WINDOW,
    SENTIMENT_ZONE_MIN_PTS,
    SENTIMENT_ZONE_WINDOW,
)
from resonance.analysis.core import GREEN, INDICATORS, RED, eval_day, fmt_pct, fmt_position, fmt_share, verdict_of
from resonance.analysis.evidence_indicators import (
    evidence_composite,
    evidence_pct,
    evidence_position,
    evidence_share,
)


def percentile_detail(dates, values, window, min_pts, target_date):
    idx = None
    for i, d in enumerate(dates):
        if d == target_date:
            idx = i
            break
    if idx is None:
        return None
    cur = values[idx]
    if cur is None:
        return None
    w = [x for x in values[max(0, idx - window + 1) : idx + 1] if x is not None]
    if len(w) < min_pts:
        return None
    parts = pct_rank_parts(w, cur)
    return {
        "percentile": parts["percentile"],
        "value": cur,
        "window": w,
        "count": parts["count"],
        "below": parts["below"],
        "equal": parts["equal"],
        "min": min(w),
        "max": max(w),
    }


def _turnover_detail(turnover_rows, date, window, min_pts):
    return percentile_detail(
        [r.get("date") for r in turnover_rows], [turnover_value(r) for r in turnover_rows], window, min_pts, date
    )


def _margin_detail(margin_rows, date, window, min_pts):
    return percentile_detail(
        [r.get("date") for r in margin_rows], [r.get("fin_balance_yi") for r in margin_rows], window, min_pts, date
    )


def build_day_indicators(
    etf_row, turnover_rows, margin_rows, date, window=SENTIMENT_ZONE_WINDOW, min_pts=SENTIMENT_ZONE_MIN_PTS
):
    tp = _turnover_detail(turnover_rows, date, window, min_pts)
    mp = _margin_detail(margin_rows, date, window, min_pts)
    turn_p = tp["percentile"] if tp else None
    margin_p = mp["percentile"] if mp else None
    code = etf_row.get("code")
    states = eval_day(etf_row, turn_p, margin_p, code)
    invert = code in DEFENSIVE_ETFS if code else False

    pp = etf_row.get("price_position")
    sp = etf_row.get("share_prob")
    cp = etf_row.get("composite_prob")
    detail = {
        "price_position": (pp, fmt_position(pp), "60日区间位置"),
        "share_flow": (sp, fmt_share(sp), "份额变动概率"),
        "composite_signal": (cp, fmt_share(cp), "综合吸筹/出货概率"),
        "turnover": (turn_p, fmt_pct(turn_p), "两市成交额分位"),
        "margin": (margin_p, fmt_pct(margin_p), "融资余额分位"),
    }
    turn_method = (
        f"成交额热度：两市成交额经 {SENTIMENT_MA_WINDOW} 日均线(MA5)平滑"
        f"（数据不足时回退原始值），在滚动 {window} 个交易日窗口内计算分位。"
        "分位 = (低于当日的天数 + 0.5×相等的天数) / 样本数 × 100"
    )
    margin_method = (
        f"融资杠杆：融资余额在滚动 {window} 个交易日窗口内计算分位。"
        "分位 = (低于当日的天数 + 0.5×相等的天数) / 样本数 × 100"
    )
    evidences = {
        "price_position": evidence_position(etf_row, states["price_position"]),
        "share_flow": evidence_share(etf_row, states["share_flow"]),
        "composite_signal": evidence_composite(etf_row, states["composite_signal"]),
        "turnover": evidence_pct("成交额", turn_method, tp, states["turnover"], invert),
        "margin": evidence_pct("融资余额", margin_method, mp, states["margin"], invert),
    }
    out = []
    for ind in INDICATORS:
        value, display, note = detail[ind["key"]]
        out.append(
            {
                **ind,
                "state": states[ind["key"]],
                "value": value,
                "display": display,
                "note": note,
                "evidence": evidences[ind["key"]],
            }
        )
    return out


def compute_day_detail(
    code, etf_rows, turnover_rows, margin_rows, date, window=SENTIMENT_ZONE_WINDOW, min_pts=SENTIMENT_ZONE_MIN_PTS
):
    etf_by_date = {r["date"]: r for r in etf_rows}
    etf_row = etf_by_date.get(date)
    if etf_row is None:
        return None
    indicators = build_day_indicators(etf_row, turnover_rows, margin_rows, date, window, min_pts)
    red = sum(1 for i in indicators if i["state"] == RED)
    green = sum(1 for i in indicators if i["state"] == GREEN)
    total = len(INDICATORS)
    return {
        "code": code,
        "name": ETFS.get(code, {}).get("name", code),
        "date": date,
        "indicators": indicators,
        "red_count": red,
        "green_count": green,
        "gray_count": total - red - green,
        "total": total,
        "verdict": verdict_of(red, green),
    }
