from analysis.sentiment import pct_rank_parts
from analysis.resonance import (
    INDICATORS, RED, GREEN,
    eval_day, verdict_of, fmt_position, fmt_share, fmt_pct, turnover_value,
)
from config import (
    ETFS, POSITION_WINDOW, POSITION_LOW, POSITION_HIGH,
    VOLUME_MA_WINDOW, VOLUME_ACTIVE_RATIO,
    SHARE_PROB_RED, SHARE_PROB_GREEN,
    COMPOSITE_PROB_RED, COMPOSITE_PROB_GREEN,
    SENTIMENT_MA_WINDOW, SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS,
    SENTIMENT_ZONE_P_HIGH, SENTIMENT_ZONE_P_LOW,
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
    w = [x for x in values[max(0, idx - window + 1):idx + 1] if x is not None]
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


def _position_reason(pp, state):
    if pp is None:
        return "无价格位置数据 → 灰灯"
    if state == RED:
        return f"{pp:.1f}% ≥ {POSITION_HIGH:.0f}% → 高位 → 红灯"
    if state == GREEN:
        return f"{pp:.1f}% ≤ {POSITION_LOW:.0f}% → 低位 → 绿灯"
    return f"{POSITION_LOW:.0f}% < {pp:.1f}% < {POSITION_HIGH:.0f}% → 中位 → 灰灯"


def _evidence_position(etf_row, state):
    pp = etf_row.get("price_position")
    close = etf_row.get("close_price")
    return {
        "method": (f"价格位置 = (当日收盘 − {POSITION_WINDOW}日最低) / "
                   f"({POSITION_WINDOW}日最高 − {POSITION_WINDOW}日最低) × 100，"
                   f"高低点取自K线数据源"),
        "formula": f"price_position = {fmt_position(pp)}（收盘价 {close}）",
        "thresholds": (f"≥{POSITION_HIGH:.0f} 判高位(红灯)；"
                       f"≤{POSITION_LOW:.0f} 判低位(绿灯)；其间为中性(灰灯)"),
        "reason": _position_reason(pp, state),
        "value": pp,
        "inputs": {"close_price": close, "price_position": pp,
                   "window": POSITION_WINDOW},
    }


def _share_reason(sp, state):
    if state == RED:
        return f"{sp:.0f} ≤ {SHARE_PROB_RED:.0f} → 净赎回 → 红灯"
    if state == GREEN:
        return f"{sp:.0f} ≥ {SHARE_PROB_GREEN:.0f} → 净申购 → 绿灯"
    return f"{SHARE_PROB_RED:.0f} < {sp:.0f} < {SHARE_PROB_GREEN:.0f} → 中性 → 灰灯"


def _evidence_share(etf_row, state):
    sp = etf_row.get("share_prob")
    inputs = {
        "shares_delta_pct": etf_row.get("shares_delta_pct"),
        "shares_yi": etf_row.get("shares_yi"),
        "shares_delta_yi": etf_row.get("shares_delta_yi"),
        "share_prob": sp,
    }
    method = ("份额流向：由 ETF 当日份额变动率(%)经分段线性映射为份额概率(0-100)，"
              "概率越高代表净申购越强")
    thresholds = (f"≤{SHARE_PROB_RED:.0f} 判净赎回(红灯)；"
                  f"≥{SHARE_PROB_GREEN:.0f} 判净申购(绿灯)；其间为中性(灰灯)")
    if sp is None:
        return {
            "method": method,
            "formula": "share_prob = 无（当日无份额数据）",
            "thresholds": thresholds,
            "reason": "当日无份额数据 → 无法判定 → 灰灯",
            "value": None,
            "inputs": inputs,
            "data_note": ("份额数据仅在实时采集日（每个交易日收盘后）写入，"
                          "历史种子数据不含份额因子，因此该指标历史多为灰灯。"),
        }
    sdp = etf_row.get("shares_delta_pct")
    return {
        "method": method,
        "formula": f"份额变动率 {sdp}% → share_prob = {sp:.0f}",
        "thresholds": thresholds,
        "reason": _share_reason(sp, state),
        "value": sp,
        "inputs": inputs,
    }


def _evidence_composite(etf_row, state):
    cp = etf_row.get("composite_prob")
    vp = etf_row.get("vol_prob")
    dp = etf_row.get("dir_prob")
    sp = etf_row.get("share_prob")
    method = ("吸筹/出货：综合概率由量比概率(50%)、方向概率(20%)、份额概率(30%)加权合成，"
              "反映 ETF 整体吸筹/出货强度")
    thresholds = (f"≤{COMPOSITE_PROB_RED:.0f} 判出货(红灯)；"
                  f"≥{COMPOSITE_PROB_GREEN:.0f} 判吸筹(绿灯)；其间为中性(灰灯)")
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
        "formula": f"vol_prob×0.5 + dir_prob×0.2 + share_prob×0.3 = {cp}",
        "thresholds": thresholds,
        "reason": reason,
        "value": cp,
        "inputs": {"vol_prob": vp, "dir_prob": dp, "share_prob": sp, "composite_prob": cp},
    }


def _pct_reason(label, p, state):
    if p is None:
        return f"无{label}分位数据 → 灰灯"
    if state == RED:
        return f"{label} {p}%分位 ≥ {SENTIMENT_ZONE_P_HIGH:.0f} → 过热 → 红灯"
    if state == GREEN:
        return f"{label} {p}%分位 ≤ {SENTIMENT_ZONE_P_LOW:.0f} → 冷清 → 绿灯"
    return (f"{SENTIMENT_ZONE_P_LOW:.0f} < {label} {p}%分位 "
            f"< {SENTIMENT_ZONE_P_HIGH:.0f} → 中性 → 灰灯")


def _evidence_pct(label, method, det, state):
    thresholds = (f"≥{SENTIMENT_ZONE_P_HIGH:.0f} 判过热(红灯)；"
                  f"≤{SENTIMENT_ZONE_P_LOW:.0f} 判冷清(绿灯)；其间为中性(灰灯)")
    if det is None:
        return {
            "method": method,
            "formula": "当日无分位数据（样本不足或非交易日）",
            "thresholds": thresholds,
            "reason": _pct_reason(label, None, state),
            "value": None,
            "inputs": {},
        }
    p = det["percentile"]
    return {
        "method": method,
        "formula": (f"({det['below']} + 0.5×{det['equal']}) / {det['count']} "
                    f"× 100 = {p}%分位"),
        "thresholds": thresholds,
        "reason": _pct_reason(label, p, state),
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
        "window_stats": {"count": det["count"], "below": det["below"],
                         "equal": det["equal"], "min": det["min"], "max": det["max"]},
    }


def _turnover_detail(turnover_rows, date, window, min_pts):
    return percentile_detail(
        [r.get("date") for r in turnover_rows],
        [turnover_value(r) for r in turnover_rows], window, min_pts, date)


def _margin_detail(margin_rows, date, window, min_pts):
    return percentile_detail(
        [r.get("date") for r in margin_rows],
        [r.get("fin_balance_yi") for r in margin_rows], window, min_pts, date)


def build_day_indicators(etf_row, turnover_rows, margin_rows, date,
                         window=SENTIMENT_ZONE_WINDOW,
                         min_pts=SENTIMENT_ZONE_MIN_PTS):
    tp = _turnover_detail(turnover_rows, date, window, min_pts)
    mp = _margin_detail(margin_rows, date, window, min_pts)
    turn_p = tp["percentile"] if tp else None
    margin_p = mp["percentile"] if mp else None
    states = eval_day(etf_row, turn_p, margin_p)

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
    turn_method = (f"成交额热度：两市成交额经 {SENTIMENT_MA_WINDOW} 日均线(MA5)平滑"
                   f"（数据不足时回退原始值），在滚动 {window} 个交易日窗口内计算分位。"
                   "分位 = (低于当日的天数 + 0.5×相等的天数) / 样本数 × 100")
    margin_method = (f"融资杠杆：融资余额在滚动 {window} 个交易日窗口内计算分位。"
                     "分位 = (低于当日的天数 + 0.5×相等的天数) / 样本数 × 100")
    evidences = {
        "price_position": _evidence_position(etf_row, states["price_position"]),
        "share_flow": _evidence_share(etf_row, states["share_flow"]),
        "composite_signal": _evidence_composite(etf_row, states["composite_signal"]),
        "turnover": _evidence_pct("成交额", turn_method, tp, states["turnover"]),
        "margin": _evidence_pct("融资余额", margin_method, mp, states["margin"]),
    }
    out = []
    for ind in INDICATORS:
        value, display, note = detail[ind["key"]]
        out.append({**ind, "state": states[ind["key"]], "value": value,
                    "display": display, "note": note, "evidence": evidences[ind["key"]]})
    return out


def compute_day_detail(code, etf_rows, turnover_rows, margin_rows, date,
                       window=SENTIMENT_ZONE_WINDOW,
                       min_pts=SENTIMENT_ZONE_MIN_PTS):
    etf_by_date = {r["date"]: r for r in etf_rows}
    etf_row = etf_by_date.get(date)
    if etf_row is None:
        return None
    indicators = build_day_indicators(etf_row, turnover_rows, margin_rows,
                                      date, window, min_pts)
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
