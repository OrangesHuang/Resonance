from fastapi import APIRouter, Query

from config import ETFS
from fetch.kline import fetch_kline
from store.daily_repo import get_by_code
from store.realtime_repo import get_today_snapshots
from scheduler.tasks import task_manual_refresh

router = APIRouter(prefix="/api/etf", tags=["etf"])


@router.post("/refresh")
def etf_refresh():
    result = task_manual_refresh()
    return {
        "status": "ok",
        "count": result["count"],
        "date": result["date"],
    }


@router.get("/list")
def etf_list():
    return [
        {"code": code, "name": info["name"], "idx": info["idx"]}
        for code, info in ETFS.items()
    ]


@router.get("/{code}/history")
def etf_history(code: str, days: int = Query(default=640, ge=1, le=640)):
    if code not in ETFS:
        return {"error": f"unknown ETF code: {code}"}

    kline = fetch_kline(code, limit=days)
    daily_records = get_by_code(code)

    return {
        "code": code,
        "name": ETFS[code]["name"],
        "idx": ETFS[code]["idx"],
        "kline": kline,
        "daily_signals": daily_records[:days],
    }


@router.get("/{code}/intraday")
def etf_intraday(code: str, date: str = Query(default=None)):
    if code not in ETFS:
        return {"error": f"unknown ETF code: {code}"}

    snapshots = get_today_snapshots(code=code, date_str=date)
    return {
        "code": code,
        "name": ETFS[code]["name"],
        "snapshots": snapshots,
    }
