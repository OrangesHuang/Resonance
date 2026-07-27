from fastapi import APIRouter, HTTPException

from config import ETFS, DEFAULT_RESONANCE_CODE, SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
from store.daily_repo import get_by_code
from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import enrich_turnover, percentile_series
from analysis.resonance import compute_resonance, turnover_value
from analysis.resonance_evidence import compute_day_detail

router = APIRouter(prefix="/api/resonance", tags=["resonance"])


def _load_series(code: str):
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    etf_rows = list(reversed(get_by_code(code)))
    etf_rows = [r for r in etf_rows if r.get("composite_prob") is not None]
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    return etf_rows, turnover, margin


@router.get("/overview")
def resonance_overview(code: str = DEFAULT_RESONANCE_CODE):
    etf_rows, turnover, margin = _load_series(code)
    return compute_resonance(code, etf_rows, turnover, margin)


@router.get("/day")
def resonance_day(code: str = DEFAULT_RESONANCE_CODE, date: str = ""):
    if not date:
        raise HTTPException(status_code=400, detail="缺少 date 参数")
    etf_rows, turnover, margin = _load_series(code)
    detail = compute_day_detail(code, etf_rows, turnover, margin, date)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"{code} 在 {date} 无共振数据")
    return detail


@router.get("/trades")
def resonance_trades(code: str = DEFAULT_RESONANCE_CODE):
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    etf_rows = list(reversed(get_by_code(code)))
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()

    t_pct = percentile_series(
        [r.get("date") for r in turnover],
        [turnover_value(r) for r in turnover],
        SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
    m_pct = percentile_series(
        [r.get("date") for r in margin],
        [r.get("fin_balance_yi") for r in margin],
        SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)

    import math
    SELL_PP = 80
    SELL_MP = 90
    MIN_HOLD = 10
    VOL_LOOKBACK = 20
    TRADE_START = "2024-01-02"

    trades = []
    position = 0.0
    hold_days = 0
    sell_threshold = 1
    dist_count = 0

    for i, row in enumerate(etf_rows):
        d = row["date"]
        if d not in t_pct and d not in m_pct:
            continue
        close = row.get("close_price")
        if close is None:
            continue
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        tp = t_pct.get(d, {}).get("percentile")
        mp = m_pct.get(d, {}).get("percentile")

        action = None
        reason = ""

        if position == 0 and d >= TRADE_START:
            pp_green = pp is not None and pp <= 40
            pp_extreme = pp is not None and pp <= 10
            td_green = td == "ACCUMULATE"
            sp_green = sp is not None and sp >= 65
            tp_cold = tp is not None and tp <= 10
            cp_high = cp is not None and cp > 60
            if pp_green and sp_green and td_green:
                action, reason = "BUY", "价格低位+份额净申购+吸筹"
            elif pp_green and td_green and tp_cold:
                action, reason = "BUY", "价格低位+吸筹+成交额极冷"
            elif pp_extreme and td_green and cp_high:
                action, reason = "BUY", "价格极低位+吸筹+概率>60%"

        if position == 1:
            hold_days += 1
            if td == "DISTRIBUTE" and pp is not None and pp >= SELL_PP \
                    and mp is not None and mp >= SELL_MP:
                dist_count += 1

            if hold_days >= MIN_HOLD and td == "DISTRIBUTE" \
                    and dist_count >= sell_threshold:
                reason = (f"出货共振(第{dist_count}/{sell_threshold}次出货确认)"
                          f"+价格{pp:.0f}%+融资{mp:.0f}%分位")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            dist_count = 0
            vol = row.get("volume") or 0
            prev_vols = [etf_rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            tp_cold = tp is not None and tp <= 10
            if tp_cold:
                sell_threshold = 1
            else:
                sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": action, "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            trades.append({"date": d, "action": action, "price": close, "reason": reason})

    return {"code": code, "trades": trades}
