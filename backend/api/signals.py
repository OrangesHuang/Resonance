from datetime import datetime
from fastapi import APIRouter

from config import ETFS
from scheduler.tasks import get_latest_signals, get_last_update, is_trading_time
from store.daily_repo import get_by_date, get_latest_date

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/today")
def signals_today():
    now = datetime.now()
    trading = is_trading_time(now)

    if trading:
        signals = get_latest_signals()
        if signals:
            return {
                "date": now.strftime("%Y-%m-%d"),
                "mode": "intraday",
                "updated_at": get_last_update(),
                "etfs": signals,
            }

    today = now.strftime("%Y-%m-%d")
    daily = get_by_date(today)
    if daily and any(r.get("composite_prob") is not None for r in daily):
        return {
            "date": today,
            "mode": "daily",
            "updated_at": None,
            "etfs": daily,
        }

    latest = get_latest_date()
    if latest:
        daily = get_by_date(latest)
        return {
            "date": latest,
            "mode": "daily",
            "updated_at": None,
            "etfs": daily,
        }

    return {"date": today, "mode": "none", "updated_at": None, "etfs": []}


@router.get("/{date}")
def signals_by_date(date: str):
    daily = get_by_date(date)
    return {
        "date": date,
        "mode": "daily",
        "updated_at": None,
        "etfs": daily,
    }
