from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from base.scheduler.daily_tasks import task_sync_calendar
from base.store.calendar_repo import get_coverage, get_last_sync, get_range, get_trade_days
from base.store.daily_repo import get_distinct_dates
from base.store.settings_repo import get_setting

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _slot_summary() -> dict:
    """数据槽位汇总(跨年): 槽位 = [数据起始设置, 今天] 的交易日, 缺口 = 槽位 − 实际。
    供交易日历页展示总量/覆盖/缺失。"""
    today = datetime.now().strftime("%Y-%m-%d")
    distinct = get_distinct_dates()
    lo_data = distinct[0] if distinct else today
    slot_start = get_setting("data_slot_start") or lo_data
    expected = [d for d in get_trade_days() if slot_start <= d <= today]
    actual = set(distinct)
    missing = [d for d in expected if d not in actual]
    runs: list[list[str]] = []
    cur: list[str] = []
    for d in expected:
        if d in actual:
            if cur:
                runs.append(cur)
                cur = []
        else:
            cur.append(d)
    if cur:
        runs.append(cur)
    return {
        "slot_start": slot_start,
        "slot_total": len(expected),
        "covered_days": len(expected) - len(missing),
        "missing_days": len(missing),
        "missing_ranges": [[r[0], r[-1]] for r in runs],
    }


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
        # 数据槽位台账: {date: 0-4}(etf_daily/份额/成交额/融资 覆盖数) + 槽位起始 + 跨年汇总
        "coverage": get_coverage(f"{year}-01-01", f"{year}-12-31"),
        "slot_start": get_setting("data_slot_start"),
        "slot_stats": _slot_summary(),
    }


@router.post("/refresh")
def calendar_refresh():
    result = task_sync_calendar()
    return {
        "status": "ok",
        "count": result["count"],
        "range": result["range"],
    }
