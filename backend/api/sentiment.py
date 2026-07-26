from fastapi import APIRouter

from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import (
    enrich_turnover, enrich_margin, turnover_summary, margin_summary, compute_zone,
)
from scheduler.tasks import task_fetch_sentiment

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
def sentiment_overview():
    turnover_raw = get_turnover_series()
    margin_raw = get_margin_series()

    turnover = enrich_turnover(turnover_raw)
    margin = enrich_margin(margin_raw)

    updated_at = None
    dates = [r.get("date") for r in turnover + margin if r.get("date")]
    if dates:
        updated_at = max(dates)

    return {
        "turnover": turnover,
        "margin": margin,
        "summary": {
            "turnover": turnover_summary(turnover),
            "margin": margin_summary(margin),
        },
        "zone": compute_zone(turnover, margin),
        "updated_at": updated_at,
    }
