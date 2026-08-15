from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from base.scheduler.daily_tasks import task_sync_calendar
from base.store.calendar_repo import get_coverage, get_last_sync, get_range, get_trade_days
from base.store.settings_repo import get_setting

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/days")
def calendar_days(year: int | None = Query(default=None)):
    if year is None:
        year = datetime.now().year
    days = get_trade_days(f"{year}-01-01", f"{year}-12-31")
    return {
        "year": year,
        "days": days,
        "total": len(days),
        "range": get_range(),
        "updated_at": get_last_sync(),
        "today": datetime.now().strftime("%Y-%m-%d"),
        # 数据槽位台账: {date: 0-4}(etf_daily/份额/成交额/融资 覆盖数) + 槽位起始
        "coverage": get_coverage(f"{year}-01-01", f"{year}-12-31"),
        "slot_start": get_setting("data_slot_start"),
    }


@router.post("/refresh")
def calendar_refresh():
    result = task_sync_calendar()
    return {
        "status": "ok",
        "count": result["count"],
        "range": result["range"],
    }
