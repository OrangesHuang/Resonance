from fastapi import APIRouter, HTTPException

from config import ETFS, DEFAULT_RESONANCE_CODE
from store.daily_repo import get_by_code
from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import enrich_turnover
from analysis.resonance import compute_resonance
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
