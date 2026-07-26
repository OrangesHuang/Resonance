from config import (
    SENTIMENT_MA_WINDOW, VOLUME_UP_RATIO, VOLUME_DOWN_RATIO,
    SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS,
    SENTIMENT_ZONE_P_HIGH, SENTIMENT_ZONE_P_LOW,
)


def enrich_turnover(rows: list[dict], window: int = SENTIMENT_MA_WINDOW) -> list[dict]:
    out = []
    totals = [r.get("total_amount_yi") for r in rows]
    for i, r in enumerate(rows):
        item = dict(r)
        ma = None
        ratio = None
        if i + 1 >= window:
            segment = totals[i + 1 - window:i + 1]
            if all(v is not None for v in segment):
                ma = round(sum(segment) / window, 2)
                cur = totals[i]
                if ma and cur is not None:
                    ratio = round(cur / ma, 4)
        item["ma5_yi"] = ma
        item["vol_ratio"] = ratio
        out.append(item)
    return out


def enrich_margin(rows: list[dict]) -> list[dict]:
    out = []
    prev = None
    for r in rows:
        item = dict(r)
        cur = r.get("fin_balance_yi")
        if prev is not None and cur is not None:
            item["net_fin_buy_yi"] = round(cur - prev, 4)
        else:
            item["net_fin_buy_yi"] = None
        prev = cur
        out.append(item)
    return out


def _volume_state(ratio) -> str:
    if ratio is None:
        return "持平"
    if ratio >= VOLUME_UP_RATIO:
        return "放量"
    if ratio <= VOLUME_DOWN_RATIO:
        return "缩量"
    return "持平"


def turnover_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"latest_date": None, "latest_yi": None, "ma5_yi": None,
                "vol_ratio": None, "volume_state": None}
    last = rows[-1]
    return {
        "latest_date": last.get("date"),
        "latest_yi": last.get("total_amount_yi"),
        "ma5_yi": last.get("ma5_yi"),
        "vol_ratio": last.get("vol_ratio"),
        "volume_state": _volume_state(last.get("vol_ratio")),
    }


def margin_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"latest_date": None, "fin_balance_yi": None,
                "net_fin_buy_yi": None, "prev_fin_balance_yi": None}
    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else {}
    return {
        "latest_date": last.get("date"),
        "fin_balance_yi": last.get("fin_balance_yi"),
        "net_fin_buy_yi": last.get("net_fin_buy_yi"),
        "prev_fin_balance_yi": prev.get("fin_balance_yi"),
    }


_ZONE_LABEL = {"danger": "危险区", "neutral": "中性区", "safe": "安全区"}
_LEVEL_SCORE = {"high": 1, "mid": 0, "low": -1}


def pct_rank_parts(window: list, cur: float) -> dict:
    below = sum(1 for v in window if v < cur)
    equal = sum(1 for v in window if v == cur)
    count = len(window)
    percentile = round((below + 0.5 * equal) / count * 100, 1)
    return {"percentile": percentile, "below": below, "equal": equal, "count": count}


def _pct_rank(window: list, cur: float) -> float:
    return pct_rank_parts(window, cur)["percentile"]


def _level(p: float) -> str:
    if p >= SENTIMENT_ZONE_P_HIGH:
        return "high"
    if p <= SENTIMENT_ZONE_P_LOW:
        return "low"
    return "mid"


def percentile_series(dates: list, values: list, window: int, min_pts: int) -> dict:
    out = {}
    for i, (d, v) in enumerate(zip(dates, values)):
        if v is None:
            continue
        w = [x for x in values[max(0, i - window + 1):i + 1] if x is not None]
        if len(w) < min_pts:
            continue
        p = _pct_rank(w, v)
        out[d] = {"percentile": p, "level": _level(p)}
    return out


def _zone_of(score: int) -> str:
    if score >= 1:
        return "danger"
    if score <= -1:
        return "safe"
    return "neutral"


def compute_zone(turnover_rows: list[dict], margin_rows: list[dict],
                 window: int = SENTIMENT_ZONE_WINDOW,
                 min_pts: int = SENTIMENT_ZONE_MIN_PTS) -> dict:
    t_dates, t_vals = [], []
    for r in turnover_rows:
        d = r.get("date")
        v = r.get("ma5_yi")
        if v is None:
            v = r.get("total_amount_yi")
        if d and v is not None:
            t_dates.append(d)
            t_vals.append(v)

    m_dates = [r.get("date") for r in margin_rows]
    m_vals = [r.get("fin_balance_yi") for r in margin_rows]

    t_pct = percentile_series(t_dates, t_vals, window, min_pts)
    m_pct = percentile_series(m_dates, m_vals, window, min_pts)

    history = []
    for d in sorted(set(t_pct) & set(m_pct)):
        score = _LEVEL_SCORE[t_pct[d]["level"]] + _LEVEL_SCORE[m_pct[d]["level"]]
        zone = _zone_of(score)
        history.append({"date": d, "zone": zone, "label": _ZONE_LABEL[zone], "score": score})

    current = None
    if history:
        last = history[-1]
        current = {
            "date": last["date"],
            "zone": last["zone"],
            "label": last["label"],
            "score": last["score"],
            "window": window,
            "turnover": t_pct[last["date"]],
            "margin": m_pct[last["date"]],
        }
    return {"current": current, "history": history}
