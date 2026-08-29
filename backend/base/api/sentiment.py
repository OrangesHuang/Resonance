from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from base.analysis.sentiment.core import (
    compute_zone,
    enrich_margin,
    enrich_turnover,
    margin_summary,
    turnover_summary,
)
from base.scheduler.daily_tasks import task_fetch_sentiment
from base.store.calendar_repo import get_safe_cache_end
from base.store.sentiment_repo import get_margin_series, get_turnover_series

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


@router.post("/refresh")
def sentiment_refresh():
    result = task_fetch_sentiment(backfill=False)
    return {
        "status": "ok",
        "turnover_days": result["turnover"],
        "margin_days": result["margin"],
        "range": [result["start"], result["end"]],
    }


@router.get("/overview")
def sentiment_overview(since: str | None = None):
    turnover_raw = get_turnover_series()
    margin_raw = get_margin_series()

    # summary/zone/MA 均基于全量计算, 增量请求只过滤输出的历史行
    turnover = enrich_turnover(turnover_raw)
    margin = enrich_margin(margin_raw)
    summary = {
        "turnover": turnover_summary(turnover),
        "margin": margin_summary(margin),
    }
    zone = compute_zone(turnover, margin)

    if since:
        turnover = [r for r in turnover if r["date"] > since]
        margin = [r for r in margin if r["date"] > since]

    updated_at = None
    dates = [r["date"] for r in turnover + margin if r.get("date")]
    if dates:
        updated_at = max(dates)

    return {
        "turnover": turnover,
        "margin": margin,
        "summary": summary,
        "zone": zone,
        "updated_at": updated_at,
        "safe_end": get_safe_cache_end(datetime.now().strftime("%Y-%m-%d")),
    }
