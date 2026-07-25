from datetime import datetime, time
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    ETFS, REALTIME_INTERVAL_SEC,
    MARKET_OPEN_HOUR, MARKET_OPEN_MIN,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN,
)
from fetch.kline import fetch_kline, fetch_index_kline
from fetch.realtime import fetch_realtime_quotes
from fetch.shares import calc_share_delta
from analysis.intraday import calc_intraday_signal, IntradaySignal
from analysis.composite import analyze_single_etf
from store.database import init_db
from store.daily_repo import upsert_daily
from store.realtime_repo import insert_snapshots, cleanup_old_snapshots

_kline_cache: dict[str, list[dict]] = {}
_idx_kline_cache: list[dict] = []
_share_delta_cache: dict[str, dict] = {}
_latest_signals: list[dict] = []
_last_update: Optional[str] = None

scheduler = AsyncIOScheduler()


def get_latest_signals() -> list[dict]:
    return _latest_signals


def get_last_update() -> Optional[str]:
    return _last_update


def is_trading_time(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning = time(MARKET_OPEN_HOUR, MARKET_OPEN_MIN) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN)
    return morning or afternoon


def task_preload_kline() -> None:
    global _kline_cache, _idx_kline_cache
    print("[SCHEDULER] preloading kline data...")
    _idx_kline_cache = fetch_index_kline()
    for code in ETFS:
        data = fetch_kline(code)
        if data:
            _kline_cache[code] = data
    print(f"[SCHEDULER] loaded kline for {len(_kline_cache)} ETFs")


def task_realtime_poll() -> None:
    global _latest_signals, _last_update
    now = datetime.now()
    if not is_trading_time(now):
        return

    quotes = fetch_realtime_quotes()
    if not quotes:
        return

    idx_quote = quotes.get("000300")
    signals = []

    for code in ETFS:
        quote = quotes.get(code)
        if not quote:
            continue
        kline = _kline_cache.get(code, [])
        share_info = _share_delta_cache.get(code, {})
        share_delta_pct = share_info.get("delta_pct")

        signal = calc_intraday_signal(
            quote=quote,
            idx_quote=idx_quote,
            kline_history=kline,
            latest_share_delta_pct=share_delta_pct,
            now=now,
        )
        if signal:
            signals.append({
                "timestamp": signal.timestamp,
                "code": signal.code,
                "name": signal.name,
                "idx_name": signal.idx_name,
                "price": signal.price,
                "change_pct": signal.change_pct,
                "volume_hand": signal.volume_hand,
                "volume_ratio": signal.volume_ratio,
                "vol_prob": signal.vol_prob,
                "dir_prob": signal.dir_prob,
                "share_prob": signal.share_prob,
                "composite_prob": signal.composite_prob,
                "signal_level": signal.signal_level,
                "premium_pct": signal.premium_pct,
                "price_position": signal.price_position,
                "trade_direction": signal.trade_direction,
            })

    if signals:
        _latest_signals = signals
        _last_update = now.strftime("%Y-%m-%dT%H:%M:%S")
        insert_snapshots(signals)


def task_daily_analysis() -> None:
    global _kline_cache, _idx_kline_cache
    print("[SCHEDULER] running daily analysis...")
    _idx_kline_cache = fetch_index_kline()
    today = datetime.now().strftime("%Y-%m-%d")

    for code in ETFS:
        kline = fetch_kline(code)
        if kline:
            _kline_cache[code] = kline

        share_info = _share_delta_cache.get(code, {})
        result = analyze_single_etf(
            kline=kline,
            idx_kline=_idx_kline_cache,
            shares_delta_pct=share_info.get("delta_pct"),
        )
        if result:
            result["shares_yi"] = share_info.get("shares_yi")
            result["shares_delta_yi"] = share_info.get("delta_yi")
            result["shares_delta_pct"] = share_info.get("delta_pct")
            upsert_daily(today, code, result)

    print("[SCHEDULER] daily analysis complete")


def task_fetch_shares() -> None:
    global _share_delta_cache
    print("[SCHEDULER] fetching share data...")
    today = datetime.now().strftime("%Y-%m-%d")
    deltas = calc_share_delta(today)
    if deltas:
        _share_delta_cache = deltas
        for code, info in deltas.items():
            upsert_daily(today, code, {
                "shares_yi": info.get("shares_yi"),
                "shares_delta_yi": info.get("delta_yi"),
                "shares_delta_pct": info.get("delta_pct"),
            })
        print(f"[SCHEDULER] shares updated for {len(deltas)} ETFs")
    else:
        print("[SCHEDULER] no share data available (non-trading day?)")


def task_cleanup() -> None:
    deleted = cleanup_old_snapshots(keep_days=7)
    if deleted:
        print(f"[SCHEDULER] cleaned {deleted} old realtime records")


def start_scheduler() -> None:
    init_db()
    task_preload_kline()
    task_fetch_shares()

    scheduler.add_job(
        task_realtime_poll,
        IntervalTrigger(seconds=REALTIME_INTERVAL_SEC),
        id="realtime_poll",
        replace_existing=True,
    )
    scheduler.add_job(
        task_preload_kline,
        CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),
        id="preload_kline",
        replace_existing=True,
    )
    scheduler.add_job(
        task_daily_analysis,
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="daily_analysis",
        replace_existing=True,
    )
    scheduler.add_job(
        task_fetch_shares,
        CronTrigger(hour=19, minute=30, day_of_week="mon-fri"),
        id="fetch_shares",
        replace_existing=True,
    )
    scheduler.add_job(
        task_cleanup,
        CronTrigger(hour=2, minute=0),
        id="cleanup",
        replace_existing=True,
    )
    scheduler.start()
    print("[SCHEDULER] started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[SCHEDULER] stopped")
