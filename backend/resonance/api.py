from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from base.analysis.sentiment.core import enrich_turnover, percentile_series, turnover_value
from base.config import (
    DEFAULT_RESONANCE_CODE,
    ETFS,
    SENTIMENT_ZONE_MIN_PTS,
    SENTIMENT_ZONE_WINDOW,
)
from base.store.calendar_repo import get_safe_cache_end
from base.store.daily_repo import get_by_code
from base.store.sentiment_repo import get_margin_series, get_turnover_series
from resonance.analysis.core import compute_resonance
from resonance.analysis.evidence import compute_day_detail

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
def resonance_overview(code: str = DEFAULT_RESONANCE_CODE, since: str | None = None):
    etf_rows, turnover, margin = _load_series(code)
    # indicators/五灯为当前状态(全量计算), 增量只过滤 history 历史行
    result = compute_resonance(code, etf_rows, turnover, margin)
    if since:
        result["history"] = [h for h in result["history"] if h["date"] > since]
    result["safe_end"] = get_safe_cache_end(datetime.now().strftime("%Y-%m-%d"))
    return result


@router.get("/day")
def resonance_day(code: str = DEFAULT_RESONANCE_CODE, date: str = ""):
    if not date:
        raise HTTPException(status_code=400, detail="缺少 date 参数")
    etf_rows, turnover, margin = _load_series(code)
    detail = compute_day_detail(code, etf_rows, turnover, margin, date)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"{code} 在 {date} 无共振数据")
    return detail


@router.get("/trades/versions")
def resonance_trades_versions():
    """返回 {code: has_beta} 供前端控制 Beta 切换按钮显隐。"""
    from base.analysis.strategy.router import list_strategy_versions

    return list_strategy_versions()


@router.get("/trades")
def resonance_trades(code: str = DEFAULT_RESONANCE_CODE, version: str = "stable"):
    """页面「共振买卖点」— 按 ETF 代码分派各专属策略(与组合回测共用统一入口)。

    version: stable(正式版) / beta(调试版), 仅沪深300 双版本, 其余 ETF 相同。
    """
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    if version not in ("stable", "beta", "band"):
        version = "stable"

    from base.analysis.strategy.a500 import A500_CODE
    from base.analysis.strategy.kc50 import KC50_CODE
    from base.analysis.strategy.router import compute_trades

    etf_rows = list(reversed(get_by_code(code)))
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    t_pct = percentile_series(
        [r.get("date") for r in turnover],
        [turnover_value(r) for r in turnover],
        SENTIMENT_ZONE_WINDOW,
        SENTIMENT_ZONE_MIN_PTS,
    )
    m_pct = percentile_series(
        [r.get("date") for r in margin],
        [r.get("fin_balance_yi") for r in margin],
        SENTIMENT_ZONE_WINDOW,
        SENTIMENT_ZONE_MIN_PTS,
    )

    hs300_rows = None
    kc_idx_rows = None
    if code == A500_CODE:
        hs300_rows = list(reversed(get_by_code("510300")))
    elif code == KC50_CODE:
        kc_idx_rows = list(reversed(get_by_code("589680")))

    result = compute_trades(
        code, etf_rows, t_pct=t_pct, m_pct=m_pct, hs300_rows=hs300_rows, kc_idx_rows=kc_idx_rows, version=version
    )
    return {
        "code": code,
        "trades": result["trades"],
        "regimes": result.get("regimes"),
        "version": version,
    }
