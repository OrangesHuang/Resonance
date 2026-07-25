from datetime import datetime
from fastapi import APIRouter

from fetch.realtime import fetch_realtime_quotes
from scheduler.tasks import get_latest_signals, get_last_update, is_trading_time
from config import ETFS

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.get("/quotes")
def realtime_quotes():
    quotes = fetch_realtime_quotes()
    result = []
    for code, q in quotes.items():
        result.append({
            "code": q.code,
            "name": q.name,
            "price": q.price,
            "prev_close": q.prev_close,
            "open": q.open,
            "high": q.high,
            "low": q.low,
            "volume_hand": q.volume_hand,
            "amount_wan": q.amount_wan,
            "change_pct": q.change_pct,
            "timestamp": q.timestamp,
        })
    return {"quotes": result, "fetched_at": datetime.now().isoformat()}


@router.get("/status")
def realtime_status():
    now = datetime.now()
    return {
        "is_trading": is_trading_time(now),
        "last_update": get_last_update(),
        "server_time": now.isoformat(),
        "monitored_etfs": len(ETFS),
        "has_signals": len(get_latest_signals()) > 0,
    }
