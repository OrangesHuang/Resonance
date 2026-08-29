"""盘后/日度任务: 收盘分析/份额拉取/情绪抓取/日历同步/清理。

所有触网任务均由 tasks.py 注册时经 asyncio.to_thread 派发,
本模块不直接操作事件循环。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from base.config import ETFS, MANUAL_REFRESH_DAYS, REFRESH_MIN_INTERVAL_SEC, SENTIMENT_BACKFILL_DAYS, SHARE_WINDOW
from base.fetch.calendar import fetch_trade_dates
from base.fetch.kline import fetch_index_kline, fetch_kline
from base.fetch.sentiment import fetch_margin_series, fetch_market_turnover
from base.fetch.shares import calc_share_delta
from base.scheduler import state
from base.scheduler.etf_daily_jobs import job_backfill_etf_daily
from base.scheduler.shares_jobs import job_backfill_shares
from base.store.calendar_repo import (
    get_calendar_count,
    get_last_trading_day,
    get_range,
    reload_cache,
    upsert_trade_dates,
)
from base.store.daily_repo import (
    get_shares_by_date,
    shares_complete_for,
    update_share_data,
    upsert_daily,
)
from base.store.realtime_repo import cleanup_old_snapshots
from base.store.sentiment_repo import get_turnover_series, upsert_margin, upsert_turnover
from resonance.analysis.composite import analyze_single_etf
from resonance.analysis.factors import calc_share_probability_dual


def task_daily_analysis() -> dict:
    print("[SCHEDULER] running daily analysis...")
    state._idx_kline_cache = fetch_index_kline()

    count = 0
    latest_date: str | None = None
    for code in ETFS:
        kline = fetch_kline(code)
        if kline:
            state._kline_cache[code] = kline

        share_info = state._share_delta_cache.get(code, {})
        result = analyze_single_etf(
            kline=kline,
            idx_kline=state._idx_kline_cache,
            shares_delta_pct=share_info.get("delta_pct"),
        )
        if result:
            # 份额必须与当日匹配才附加, 否则留空待份额回填补齐
            # (份额 T+1 发布, 缓存可能是前一交易日的, 不能盖到今日行上)
            if share_info.get("date") == result["date"]:
                result["shares_yi"] = share_info.get("shares_yi")
                result["shares_delta_yi"] = share_info.get("delta_yi")
                result["shares_delta_pct"] = share_info.get("delta_pct")
            upsert_daily(result["date"], code, result)
            count += 1
            latest_date = result["date"]

    print(f"[SCHEDULER] daily analysis complete: {count} ETFs ({latest_date})")
    return {"count": count, "date": latest_date}


def task_fetch_shares() -> dict:
    """拉取份额数据, 返回实际落库的份额日期。

    份额 T+1 发布: 目标日未发布时自动回溯到最近已发布日, 返回的
    shares_date 即实际数据日期; 与 target 不一致说明数据源尚未发布。
    """
    print("[SCHEDULER] fetching share data...")
    target = get_last_trading_day(datetime.now().strftime("%Y-%m-%d"))
    if shares_complete_for(target):
        state._share_delta_cache = {code: {"date": target, **info} for code, info in get_shares_by_date(target).items()}
        print(f"[SCHEDULER] shares already fresh for {target}, skipped network")
        return {"status": "fresh", "shares_date": target}
    today = datetime.now().strftime("%Y-%m-%d")
    deltas = calc_share_delta(today)
    if deltas:
        shares_date = next(iter(deltas.values()))["date"]
        state._share_delta_cache = deltas
        # 双基准取强: 加载各 code 前10日份额序列(持续吸筹放大)
        window_by_code: dict[str, list[float]] = {}
        for code in deltas:
            from base.store.daily_repo import get_by_code

            rows = get_by_code(code)
            hist = [r["shares_yi"] for r in rows if r.get("shares_yi") is not None][:SHARE_WINDOW]
            window_by_code[code] = hist
        for code, info in deltas.items():
            update_share_data(
                info["date"],
                code,
                info["shares_yi"],
                info.get("delta_yi"),
                info.get("delta_pct"),
                calc_share_probability_dual(
                    info.get("delta_pct"), info["shares_yi"], window_by_code.get(code, []), SHARE_WINDOW
                ),
            )
        print(f"[SCHEDULER] shares updated for {len(deltas)} ETFs (date {shares_date})")
        return {"status": "updated", "shares_date": shares_date}
    print(f"[SCHEDULER] shares fetch failed: no data within lookback for {today}")
    return {"status": "empty", "shares_date": None}


def _noop_progress(*args: object, **kwargs: object) -> None:
    """后台任务进度回调占位: 手动刷新同步执行, 无需上报进度。"""


def task_manual_refresh() -> dict:
    """手动刷新: 补齐最近 MANUAL_REFRESH_DAYS 个交易日(而非仅当天)。

    本地错过数天未重启时定时任务欠账 → 手动刷新一次补齐区间缺失日:
    份额 T+1 已发布的历史日可直接拉到, 日度/份额回填均幂等跳过已有
    (先日度后份额: 份额补拉依赖当日行存在)。限速不变, 距上次过近
    直接返回不触网(防被封)。
    """
    now = datetime.now()
    if state._last_manual_refresh and (now - state._last_manual_refresh).total_seconds() < REFRESH_MIN_INTERVAL_SEC:
        return {"status": "skipped", "reason": f"距上次刷新不足 {REFRESH_MIN_INTERVAL_SEC}s, 已跳过"}
    state._last_manual_refresh = now

    # 自然日跨度放大覆盖最近 N 个交易日(多拉无害, 幂等跳过已有)
    start = (now - timedelta(days=int(MANUAL_REFRESH_DAYS * 2.5))).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    daily = job_backfill_etf_daily(_noop_progress, start_date=start, end_date=end)
    shares = job_backfill_shares(_noop_progress, start_date=start, end_date=end)
    try:
        sentiment = task_fetch_sentiment()
    except Exception as e:
        print(f"[SCHEDULER] manual sentiment fetch failed: {e}")
        sentiment = {"status": "error", "error": str(e)}
    return {
        "status": "ok",
        "count": int(daily.get("written", 0)),
        "date": end,
        "shares": {
            "status": "ok" if shares.get("written", 0) or shares.get("fetched_dates", 0) else "empty",
            "shares_date": None,
        },
        "sentiment": sentiment,
    }


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
    skip_dates = {r["date"] for r in get_turnover_series()} if not backfill else set()
    # 边拉边写: 每拉到一天立即入库
    turnover = fetch_market_turnover(start, end, skip_dates=skip_dates, on_row=lambda row: upsert_turnover([row]))
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
