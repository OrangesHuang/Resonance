"""数据管理任务:可导入、带进度上报的拉取/回填函数。

被 scheduler/job_registry.py 注册为后台任务,同时被 scripts/ 薄壳脚本复用,
保证任务与脚本共用同一条代码路径(开源独立重建的关键)。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

from config import (
    ETFS, DEFAULT_ETF_SEED_DAYS, DEFAULT_SHARES_BACKFILL_DAYS,
    SEED_MIN_BARS, BACKFILL_SLEEP_SEC, SENTIMENT_BACKFILL_DAYS,
)
from fetch.kline import fetch_kline, fetch_index_kline
from fetch.shares import calc_share_delta, fetch_shares_for_date
from fetch.sentiment import fetch_market_turnover, fetch_margin_series
from fetch.calendar import fetch_trade_dates
from analysis.composite import analyze_single_etf
from analysis.factors import calc_share_probability
from store.daily_repo import (
    upsert_daily, update_share_data, get_trading_dates, get_by_date,
)
from store.sentiment_repo import (
    upsert_turnover, upsert_margin,
    get_turnover_latest_date, get_margin_latest_date,
)
from store.calendar_repo import (
    upsert_trade_dates, get_calendar_count, get_range, reload_cache,
)
from scheduler.job_manager import ProgressFn


def job_sync_calendar(progress: ProgressFn) -> dict:
    progress(0, 1, "同步交易日历…")
    dates = fetch_trade_dates()
    if dates:
        upsert_trade_dates(dates)
        reload_cache()
    progress(1, 1, f"{len(dates)} 个交易日")
    return {"count": get_calendar_count(), "range": get_range()}


def _seed_one_etf(code: str, idx_kline: list[dict], days: int) -> int:
    kline = fetch_kline(code, limit=days)
    if len(kline) < SEED_MIN_BARS:
        return 0
    count = 0
    for i in range(SEED_MIN_BARS - 1, len(kline)):
        result = analyze_single_etf(
            kline=kline[:i + 1],
            idx_kline=idx_kline[:i + 1],
            shares_delta_pct=None,
            target_idx=i,
        )
        if result:
            upsert_daily(result["date"], code, result)
            count += 1
    return count


def job_backfill_etf_daily(progress: ProgressFn, days: int = DEFAULT_ETF_SEED_DAYS) -> dict:
    progress(0, len(ETFS), "拉取指数K线…")
    idx_kline = fetch_index_kline(limit=days)
    if not idx_kline:
        raise RuntimeError("无法拉取指数K线,终止回填")
    codes = list(ETFS.items())
    total_records = 0
    for i, (code, info) in enumerate(codes, 1):
        progress(i, len(codes), f"{code} {info['name']}")
        total_records += _seed_one_etf(code, idx_kline, days)
    progress(len(codes), len(codes), f"完成 {len(codes)} 只 ETF")
    return {"etfs": len(codes), "records": total_records, "days": days}


def _load_prev_shares(date: str, prev_shares: dict) -> None:
    for r in get_by_date(date):
        if r.get("shares_yi") is not None:
            prev_shares[r["code"]] = r["shares_yi"]


def _date_complete(date: str) -> bool:
    rows = {r["code"]: r for r in get_by_date(date)}
    return all(
        rows.get(c, {}).get("shares_yi") is not None
        and rows.get(c, {}).get("share_prob") is not None
        for c in ETFS
    )


def _write_shares_date(date: str, prev_shares: dict) -> int:
    shares = fetch_shares_for_date(date)
    if not shares:
        return 0
    n = 0
    for code, shares_yi in shares.items():
        delta_yi = None
        delta_pct = None
        prev = prev_shares.get(code)
        if prev is not None and prev > 0:
            delta_yi = round(shares_yi - prev, 4)
            delta_pct = round(delta_yi / prev * 100, 3)
        update_share_data(date, code, shares_yi, delta_yi, delta_pct,
                          calc_share_probability(delta_pct))
        prev_shares[code] = shares_yi
        n += 1
    return n


def job_backfill_shares(progress: ProgressFn, days: int = DEFAULT_SHARES_BACKFILL_DAYS,
                        force: bool = False) -> dict:
    dates = get_trading_dates()[-days:]
    if not dates:
        raise RuntimeError("etf_daily 无交易日,请先回填ETF日度数据")
    prev_shares: dict = {}
    written = 0
    for i, date in enumerate(dates, 1):
        progress(i, len(dates), date)
        if not force and _date_complete(date):
            _load_prev_shares(date, prev_shares)
            continue
        written += _write_shares_date(date, prev_shares)
        time.sleep(BACKFILL_SLEEP_SEC)
    progress(len(dates), len(dates), f"完成 {written} 行")
    return {"dates": len(dates), "written": written, "days": days}


def job_fetch_sentiment(progress: ProgressFn, days: int = SENTIMENT_BACKFILL_DAYS, force: bool = False) -> dict:
    now = datetime.now()
    end = now.strftime("%Y-%m-%d")

    latest_turnover = None if force else get_turnover_latest_date()
    if latest_turnover and latest_turnover >= end:
        progress(1, 1, "成交额已是最新")
        turnover = []
    else:
        if latest_turnover:
            start = (datetime.strptime(latest_turnover, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            cal_days = int(days * 1.5)
            start = (now - timedelta(days=cal_days)).strftime("%Y-%m-%d")

        def turnover_cb(i: int, total: int, date: str) -> None:
            progress(i, total + 1, f"成交额 {date}")

        turnover = fetch_market_turnover(start, end, on_progress=turnover_cb)
        if turnover:
            upsert_turnover(turnover)

    latest_margin = None if force else get_margin_latest_date()
    if latest_margin and latest_margin >= end:
        progress(1, 1, "融资余额已是最新")
        margin = []
    else:
        margin_start = (datetime.strptime(latest_margin, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if latest_margin else (now - timedelta(days=int(days * 1.5))).strftime("%Y-%m-%d")
        progress(1, 1, "融资余额拉取中…")
        margin = fetch_margin_series(margin_start, end)
        if margin:
            upsert_margin(margin)

    progress(1, 1, "完成")
    return {"turnover": len(turnover), "margin": len(margin), "start": latest_turnover or "full", "end": end}


def _refresh_share_cache() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    deltas = calc_share_delta(today)
    for code, info in deltas.items():
        update_share_data(
            info["date"], code,
            info.get("shares_yi"), info.get("delta_yi"), info.get("delta_pct"),
            calc_share_probability(info.get("delta_pct")),
        )
    return deltas


def job_fetch_etf_latest(progress: ProgressFn) -> dict:
    progress(0, len(ETFS) + 1, "拉取份额数据…")
    share_cache = _refresh_share_cache()
    idx_kline = fetch_index_kline()
    codes = list(ETFS.items())
    count = 0
    latest_date: Optional[str] = None
    for i, (code, info) in enumerate(codes, 1):
        progress(i, len(codes) + 1, f"{code} {info['name']}")
        kline = fetch_kline(code)
        share_info = share_cache.get(code, {})
        result = analyze_single_etf(
            kline=kline, idx_kline=idx_kline,
            shares_delta_pct=share_info.get("delta_pct"),
        )
        if result:
            result["shares_yi"] = share_info.get("shares_yi")
            result["shares_delta_yi"] = share_info.get("delta_yi")
            result["shares_delta_pct"] = share_info.get("delta_pct")
            upsert_daily(result["date"], code, result)
            count += 1
            latest_date = result["date"]
    progress(len(codes) + 1, len(codes) + 1, f"完成 {count} 只 ETF")
    return {"count": count, "date": latest_date}
