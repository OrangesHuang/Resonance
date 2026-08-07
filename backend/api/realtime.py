from datetime import datetime
from fastapi import APIRouter

from fetch.realtime import fetch_realtime_quotes, fetch_market_turnover_intraday
from scheduler.tasks import get_latest_signals, get_last_update, is_trading_time
from analysis.intraday import estimate_full_day_turnover, calc_turnover_percentile
from store.realtime_repo import (
    get_today_intraday_turnover, get_latest_intraday_turnover,
    insert_intraday_turnover,
)
from store.sentiment_repo import get_turnover_series
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


@router.get("/turnover")
def realtime_turnover():
    """盘中两市成交额: 当日累计序列 + 最新 + 全天预估 + 历史分位。"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    series = get_today_intraday_turnover(today)

    latest = get_latest_intraday_turnover()
    fresh = latest and latest["timestamp"].startswith(today)
    if fresh:
        try:
            fresh = (now - datetime.strptime(latest["timestamp"], "%Y-%m-%d %H:%M:%S")
                     ).total_seconds() < 180
        except ValueError:
            fresh = False
    if not fresh and is_trading_time(now):
        # 定时任务尚未轮询到时兜底拉取一次
        data = fetch_market_turnover_intraday()
        if data:
            est = estimate_full_day_turnover(data["amount_yi"], now)
            latest = {"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                      "amount_yi": data["amount_yi"], "est_amount_yi": est}
            insert_intraday_turnover(latest["timestamp"],
                                     data["amount_yi"], est)
            series = get_today_intraday_turnover(today)

    hist = [r["total_amount_yi"] for r in get_turnover_series()
            if r.get("total_amount_yi")]
    percentile = None
    if latest and latest.get("est_amount_yi") and hist:
        percentile = calc_turnover_percentile(latest["est_amount_yi"], hist)

    return {
        "is_trading": is_trading_time(now),
        "latest": latest,
        "percentile": percentile,
        "hist_days": len(hist),
        "series": series,
        "fetched_at": now.isoformat(),
    }
