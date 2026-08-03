from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    ETFS, REALTIME_INTERVAL_SEC, REFRESH_MIN_INTERVAL_SEC,
    SENTIMENT_BACKFILL_DAYS, SENTIMENT_FETCH_HOUR, SENTIMENT_FETCH_MIN,
    CALENDAR_SYNC_HOUR, CALENDAR_SYNC_MIN, CALENDAR_SYNC_DOW,
)
from fetch.kline import fetch_kline, fetch_index_kline
from fetch.realtime import fetch_realtime_quotes
from fetch.shares import calc_share_delta
from fetch.sentiment import fetch_market_turnover, fetch_margin_series
from fetch.calendar import fetch_trade_dates
from fetch.breadth import fetch_market_breadth
from analysis.intraday import calc_intraday_signal, IntradaySignal
from analysis.composite import analyze_single_etf
from analysis.factors import calc_share_probability
from store.database import init_db
from store.daily_repo import upsert_daily, update_share_data, get_shares_by_date, shares_complete_for
from store.realtime_repo import insert_snapshots, cleanup_old_snapshots
from store.sentiment_repo import (
    upsert_turnover, upsert_margin, get_turnover_count, get_margin_count,
    get_turnover_series,
)
from store.calendar_repo import (
    upsert_trade_dates, get_calendar_count, get_range, get_last_trading_day, reload_cache,
)
from store.breadth_repo import upsert_breadth, get_latest_breadth_date
from scheduler.time_guard import is_trading_time, trading_day_guard

_kline_cache: dict[str, list[dict]] = {}
_idx_kline_cache: list[dict] = []
_share_delta_cache: dict[str, dict] = {}
_latest_signals: list[dict] = []
_last_update: Optional[str] = None
_last_manual_refresh: Optional[datetime] = None

scheduler = AsyncIOScheduler()


def get_latest_signals() -> list[dict]:
    return _latest_signals


def get_last_update() -> Optional[str]:
    return _last_update


def _load_kline_from_db(code: str, limit: int = 60) -> list[dict]:
    """从本地数据库加载K线缓存，避免每次启动调腾讯API被封禁。"""
    from store.daily_repo import get_by_code
    rows = get_by_code(code)
    if not rows:
        return []
    # get_by_code 返回 date DESC，取最近 limit 条后反转为升序
    recent = rows[:limit][::-1]
    result = []
    for r in recent:
        close = r.get("close_price") or 0.0
        result.append({
            "date": r["date"],
            "open": close,
            "close": close,
            "high": close,
            "low": close,
            "volume": r.get("volume") or 0.0,
        })
    return result


def task_preload_kline() -> None:
    global _kline_cache, _idx_kline_cache
    print("[SCHEDULER] loading kline from local db...")
    _idx_kline_cache = []  # 指数K线仅daily_analysis使用，preload时跳过
    for code in ETFS:
        data = _load_kline_from_db(code)
        if data:
            _kline_cache[code] = data
    print(f"[SCHEDULER] loaded kline for {len(_kline_cache)} ETFs from local db")


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


def task_intraday_update() -> dict:
    """每15分钟将盘中信号写入 etf_daily，供K线图展示当日数据。"""
    global _latest_signals, _last_update
    now = datetime.now()
    if not is_trading_time(now):
        return {"status": "not_trading"}
    if not _latest_signals:
        return {"status": "no_signals"}

    today = now.strftime("%Y-%m-%d")
    count = 0
    for sig in _latest_signals:
        data = {
            "close": sig.get("price"),
            "change_pct": sig.get("change_pct"),
            "volume": sig.get("volume_hand"),
            "volume_ratio": sig.get("volume_ratio"),
            "vol_prob": sig.get("vol_prob"),
            "dir_prob": sig.get("dir_prob"),
            "share_prob": sig.get("share_prob"),
            "composite_prob": sig.get("composite_prob"),
            "signal_level": sig.get("signal_level"),
            "price_position": sig.get("price_position"),
            "trade_direction": sig.get("trade_direction"),
        }
        upsert_daily(today, sig["code"], data)
        count += 1

    print(f"[SCHEDULER] intraday update: {count} ETFs → {today}")
    return {"status": "ok", "date": today, "count": count}


def task_daily_analysis() -> dict:
    global _kline_cache, _idx_kline_cache
    print("[SCHEDULER] running daily analysis...")
    _idx_kline_cache = fetch_index_kline()

    count = 0
    latest_date: Optional[str] = None
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
            upsert_daily(result["date"], code, result)
            count += 1
            latest_date = result["date"]

    print(f"[SCHEDULER] daily analysis complete: {count} ETFs ({latest_date})")
    return {"count": count, "date": latest_date}


def task_manual_refresh() -> dict:
    """手动刷新限速: 距上次刷新过近直接返回, 不触网(防被封)。"""
    global _last_manual_refresh
    now = datetime.now()
    if _last_manual_refresh and (now - _last_manual_refresh).total_seconds() < REFRESH_MIN_INTERVAL_SEC:
        return {"status": "skipped",
                "reason": f"距上次刷新不足 {REFRESH_MIN_INTERVAL_SEC}s, 已跳过"}
    _last_manual_refresh = now
    task_fetch_shares()
    return task_daily_analysis()


def task_fetch_shares() -> None:
    global _share_delta_cache
    print("[SCHEDULER] fetching share data...")
    target = get_last_trading_day(datetime.now().strftime("%Y-%m-%d"))
    if shares_complete_for(target):
        _share_delta_cache = {code: {"date": target, **info}
                              for code, info in get_shares_by_date(target).items()}
        print(f"[SCHEDULER] shares already fresh for {target}, skipped network")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    deltas = calc_share_delta(today)
    if deltas:
        _share_delta_cache = deltas
        for code, info in deltas.items():
            update_share_data(
                info["date"], code,
                info.get("shares_yi"), info.get("delta_yi"), info.get("delta_pct"),
                calc_share_probability(info.get("delta_pct")),
            )
        print(f"[SCHEDULER] shares updated for {len(deltas)} ETFs")
    else:
        print("[SCHEDULER] no share data available (non-trading day?)")


def task_cleanup() -> None:
    deleted = cleanup_old_snapshots(keep_days=7)
    if deleted:
        print(f"[SCHEDULER] cleaned {deleted} old realtime records")


def task_fetch_sentiment(backfill: bool = False) -> dict:
    now = datetime.now()
    if backfill:
        cal_days = int(SENTIMENT_BACKFILL_DAYS * 1.5)
    else:
        cal_days = 10
    start = (now - timedelta(days=cal_days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    print(f"[SCHEDULER] fetching sentiment ({start} ~ {end}, backfill={backfill})...")

    # 缓存判断: 已入库日期跳过远端逐日拉取
    skip_dates = set(r["date"] for r in get_turnover_series()) if not backfill else set()
    # 边拉边写: 每拉到一天立即入库
    turnover = fetch_market_turnover(start, end, skip_dates=skip_dates,
                                     on_row=lambda row: upsert_turnover([row]))
    if turnover:
        print(f"[SCHEDULER] turnover upserted: {len(turnover)} days")

    margin = fetch_margin_series(start, end)
    if margin:
        upsert_margin(margin)
        print(f"[SCHEDULER] margin upserted: {len(margin)} days")

    if not turnover and not margin:
        print("[SCHEDULER] no sentiment data fetched")

    return {"turnover": len(turnover), "margin": len(margin), "start": start, "end": end}


def task_sync_calendar() -> dict:
    print("[SCHEDULER] syncing trade calendar...")
    dates = fetch_trade_dates()
    if dates:
        upsert_trade_dates(dates)
        reload_cache()
        print(f"[SCHEDULER] trade calendar synced: {len(dates)} days")
    else:
        print("[SCHEDULER] no trade calendar data fetched")
    return {"count": get_calendar_count(), "range": get_range()}


def task_fetch_breadth() -> dict:
    """采集当日涨跌家数 (收盘后运行)。"""
    print("[SCHEDULER] fetching market breadth...")
    row = fetch_market_breadth()
    if row:
        upsert_breadth(row)
        print(f"[SCHEDULER] breadth upserted: {row['date']}")
        return {"date": row["date"], "advance_pct": row.get("advance_pct")}
    print("[SCHEDULER] breadth fetch returned empty")
    return {}


def start_scheduler() -> None:
    init_db()
    reload_cache()
    if get_calendar_count() == 0:
        task_sync_calendar()

    task_preload_kline()
    task_fetch_shares()

    # 盘中启动时立即拉取当日数据
    from scheduler.time_guard import is_trading_time
    if is_trading_time(datetime.now()):
        print("[SCHEDULER] trading hours detected, fetching today's data...")
        try:
            task_realtime_poll()
            task_intraday_update()
        except Exception as e:
            print(f"[SCHEDULER] initial fetch failed (non-critical): {e}")

    if get_turnover_count() == 0 or get_margin_count() == 0:
        task_fetch_sentiment(backfill=True)

    scheduler.add_job(
        task_realtime_poll,
        IntervalTrigger(seconds=REALTIME_INTERVAL_SEC),
        id="realtime_poll",
        replace_existing=True,
    )
    scheduler.add_job(
        trading_day_guard(task_intraday_update),
        IntervalTrigger(minutes=15),
        id="intraday_update",
        replace_existing=True,
    )
    scheduler.add_job(
        trading_day_guard(task_preload_kline),
        CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),
        id="preload_kline",
        replace_existing=True,
    )
    scheduler.add_job(
        trading_day_guard(task_daily_analysis),
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="daily_analysis",
        replace_existing=True,
    )
    scheduler.add_job(
        trading_day_guard(task_fetch_shares),
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
    scheduler.add_job(
        trading_day_guard(task_fetch_sentiment),
        CronTrigger(hour=SENTIMENT_FETCH_HOUR, minute=SENTIMENT_FETCH_MIN, day_of_week="mon-fri"),
        id="fetch_sentiment",
        replace_existing=True,
    )
    scheduler.add_job(
        trading_day_guard(task_fetch_breadth),
        CronTrigger(hour=16, minute=30, day_of_week="mon-fri"),
        id="fetch_breadth",
        replace_existing=True,
    )
    scheduler.add_job(
        task_sync_calendar,
        CronTrigger(day_of_week=CALENDAR_SYNC_DOW, hour=CALENDAR_SYNC_HOUR, minute=CALENDAR_SYNC_MIN),
        id="sync_calendar",
        replace_existing=True,
    )
    scheduler.start()
    print("[SCHEDULER] started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[SCHEDULER] stopped")
