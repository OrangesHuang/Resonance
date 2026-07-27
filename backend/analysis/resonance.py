from analysis.sentiment import percentile_series
from config import (
    ETFS, POSITION_LOW, POSITION_HIGH,
    SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS,
    SENTIMENT_ZONE_P_HIGH, SENTIMENT_ZONE_P_LOW,
    SHARE_PROB_RED, SHARE_PROB_GREEN, RESONANCE_VERDICT_N,
    COMPOSITE_PROB_RED, COMPOSITE_PROB_GREEN,
)

RED, GREEN, GRAY = "red", "green", "gray"

INDICATORS = [
    {"key": "price_position", "name": "价格位置", "group": "etf"},
    {"key": "share_flow", "name": "份额流向", "group": "etf"},
    {"key": "composite_signal", "name": "吸筹/出货", "group": "etf"},
    {"key": "turnover", "name": "成交额热度", "group": "market"},
    {"key": "margin", "name": "融资杠杆", "group": "market"},
]

DIRECTION_LABEL = {"DISTRIBUTE": "出货", "ACCUMULATE": "吸筹", "NEUTRAL": "中性"}


def _position_state(v):
    if v is None:
        return GRAY
    if v >= POSITION_HIGH:
        return RED
    if v <= POSITION_LOW:
        return GREEN
    return GRAY


def _share_state(v):
    if v is None:
        return GRAY
    if v <= SHARE_PROB_RED:
        return RED
    if v >= SHARE_PROB_GREEN:
        return GREEN
    return GRAY


def _direction_state(v):
    if v == "DISTRIBUTE":
        return RED
    if v == "ACCUMULATE":
        return GREEN
    return GRAY


def _composite_state(v):
    if v is None:
        return GRAY
    if v <= COMPOSITE_PROB_RED:
        return RED
    if v >= COMPOSITE_PROB_GREEN:
        return GREEN
    return GRAY


def _pct_state(p):
    if p is None:
        return GRAY
    if p >= SENTIMENT_ZONE_P_HIGH:
        return RED
    if p <= SENTIMENT_ZONE_P_LOW:
        return GREEN
    return GRAY


def eval_day(etf_row: dict, turn_p, margin_p) -> dict:
    return {
        "price_position": _position_state(etf_row.get("price_position")),
        "share_flow": _share_state(etf_row.get("share_prob")),
        "composite_signal": _composite_state(etf_row.get("composite_prob")),
        "turnover": _pct_state(turn_p),
        "margin": _pct_state(margin_p),
    }


def verdict_of(red: int, green: int) -> str:
    if red >= RESONANCE_VERDICT_N:
        return "危险共振"
    if green >= RESONANCE_VERDICT_N:
        return "机会共振"
    return "中性"


def fmt_position(v):
    return f"{v:.1f}%" if v is not None else "-"


def fmt_share(v):
    return f"{v:.0f}" if v is not None else "-"


def fmt_pct(p):
    return f"{p:.0f}%分位" if p is not None else "-"


def _current_indicators(etf_row: dict, turn_p, margin_p, states: dict) -> list:
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
    out = []
    for ind in INDICATORS:
        value, display, note = detail[ind["key"]]
        out.append({**ind, "state": states[ind["key"]],
                    "value": value, "display": display, "note": note})
    return out


def turnover_value(row: dict):
    v = row.get("ma5_yi")
    if v is None:
        v = row.get("total_amount_yi")
    return v


def compute_resonance(code: str, etf_rows: list, turnover_rows: list,
                      margin_rows: list, window: int = SENTIMENT_ZONE_WINDOW,
                      min_pts: int = SENTIMENT_ZONE_MIN_PTS) -> dict:
    etf_by_date = {r["date"]: r for r in etf_rows}
    t_pct = percentile_series(
        [r.get("date") for r in turnover_rows],
        [turnover_value(r) for r in turnover_rows], window, min_pts)
    m_pct = percentile_series(
        [r.get("date") for r in margin_rows],
        [r.get("fin_balance_yi") for r in margin_rows], window, min_pts)

    history = []
    for d in sorted(etf_by_date):
        if d not in t_pct and d not in m_pct:
            continue
        tp = t_pct.get(d, {}).get("percentile")
        mp = m_pct.get(d, {}).get("percentile")
        states = eval_day(etf_by_date[d], tp, mp)
        red = sum(1 for s in states.values() if s == RED)
        green = sum(1 for s in states.values() if s == GREEN)
        history.append({"date": d, "red": red, "green": green, "states": states})

    name = ETFS.get(code, {}).get("name", code)
    total = len(INDICATORS)
    if not history:
        return {"code": code, "name": name, "date": None, "indicators": [],
                "red_count": 0, "green_count": 0, "gray_count": total,
                "total": total, "verdict": "中性", "history": []}

    last = history[-1]
    d = last["date"]
    tp = t_pct.get(d, {}).get("percentile")
    mp = m_pct.get(d, {}).get("percentile")
    return {
        "code": code, "name": name, "date": d,
        "indicators": _current_indicators(etf_by_date[d], tp, mp, last["states"]),
        "red_count": last["red"], "green_count": last["green"],
        "gray_count": total - last["red"] - last["green"],
        "total": total,
        "verdict": verdict_of(last["red"], last["green"]),
        "history": history,
    }
