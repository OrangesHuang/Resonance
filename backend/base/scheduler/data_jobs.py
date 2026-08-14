"""数据管理任务:可导入、带进度上报的拉取/回填函数。

被 scheduler/job_registry.py 注册为后台任务,同时被 scripts/ 薄壳脚本复用,
保证任务与脚本共用同一条代码路径(开源独立重建的关键)。

情绪/最新数据任务见 sentiment_jobs.py。
"""

from __future__ import annotations

import time
from datetime import datetime

from base.config import (
    BACKFILL_SLEEP_SEC,
    DEFAULT_ETF_SEED_DAYS,
    DEFAULT_SHARES_BACKFILL_DAYS,
    ETFS,
    FETCH_SLEEP_SEC,
    SEED_MIN_BARS,
    SHARE_WINDOW,
    SHARES_FAIL_PAUSE_AFTER,
    SHARES_FAIL_PAUSE_SEC,
)
from base.fetch.calendar import fetch_trade_dates
from base.fetch.kline import fetch_index_kline, fetch_kline
from base.fetch.shares import fetch_shares_for_date
from base.scheduler.job_manager import ProgressFn
from base.store.calendar_repo import (
    get_calendar_count,
    get_last_trading_day,
    get_range,
    get_trade_days,
    reload_cache,
    upsert_trade_dates,
)
from base.store.daily_repo import (
    get_by_date,
    get_latest_date_for,
    get_missing_share_dates,
    get_trading_dates,
    update_share_data,
    upsert_daily,
)
from resonance.analysis.composite import analyze_single_etf
from resonance.analysis.factors import calc_share_probability_dual


def job_sync_calendar(progress: ProgressFn) -> dict:
    progress(0, 1, "同步交易日历…")
    dates = fetch_trade_dates()
    if dates:
        upsert_trade_dates(dates)
        reload_cache()
    progress(1, 1, f"{len(dates)} 个交易日")
    return {"count": get_calendar_count(), "range": get_range()}


def _seed_one_etf(code: str, idx_kline: list[dict], days: int, end: str | None = None) -> int:
    kline = fetch_kline(code, limit=days)
    if len(kline) < SEED_MIN_BARS:
        return 0
    count = 0
    for i in range(SEED_MIN_BARS - 1, len(kline)):
        result = analyze_single_etf(
            kline=kline[: i + 1],
            idx_kline=idx_kline[: i + 1],
            shares_delta_pct=None,
            target_idx=i,
        )
        if result:
            if end and result["date"] > end:
                continue
            upsert_daily(result["date"], code, result)
            count += 1
    return count


def _trading_days_between(start: str, end: str) -> int:
    """估算 [start, end] 区间交易日数(优先交易日历,缺省按自然日 1.5 倍估算)。"""
    days = get_trade_days(start, end)
    if days:
        return len(days)
    delta = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days
    return max(1, int(delta * 1.5) + 1)


def job_backfill_etf_daily(
    progress: ProgressFn,
    days: int = DEFAULT_ETF_SEED_DAYS,
    start_date: str | None = None,
    end_date: str | None = None,
    force: bool = False,
) -> dict:
    if start_date:
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        days = _trading_days_between(start_date, end) + SEED_MIN_BARS
    else:
        end = None
    target = end or get_last_trading_day(datetime.now().strftime("%Y-%m-%d"))
    progress(0, len(ETFS), "拉取指数K线…")
    idx_kline = fetch_index_kline(limit=days)
    if not idx_kline:
        raise RuntimeError("无法拉取指数K线,终止回填")
    codes = list(ETFS.items())
    total_records = 0
    skipped = 0
    for i, (code, info) in enumerate(codes, 1):
        # 缓存判断: 已覆盖目标日则跳过远端拉取(force 强制重拉)
        latest = get_latest_date_for(code)
        if not force and latest and latest >= target:
            skipped += 1
            progress(i, len(codes), f"{code} {info['name']} 已是最新({latest})")
            continue
        progress(i, len(codes), f"{code} {info['name']}")
        total_records += _seed_one_etf(code, idx_kline, days, end)
        time.sleep(FETCH_SLEEP_SEC)
    progress(len(codes), len(codes), f"完成 {total_records} 行 (跳过 {skipped} 只)")
    return {"etfs": len(codes), "records": total_records, "skipped": skipped, "days": days}


def _load_prev_shares(date: str, prev_shares: dict, prev_window: dict[str, list[float]]) -> None:
    for r in get_by_date(date):
        if r.get("shares_yi") is not None:
            prev_shares[r["code"]] = r["shares_yi"]
            hist = prev_window.setdefault(r["code"], [])
            hist.append(r["shares_yi"])
            if len(hist) > SHARE_WINDOW:
                hist.pop(0)


def _missing_share_etfs(date: str) -> list[str]:
    """该日期在库中缺份额数据或缺 delta 的 ETF (仅考虑当日已有 K 线行的 ETF)。

    缺 delta 也算缺失: 后补份额时 prev 可能未入库导致 delta 留空
    (如 159352 2026-08-10 shares_yi 有值但 sd None, 需重算)。
    """
    rows = {r["code"]: r for r in get_by_date(date)}
    return [c for c, r in rows.items() if r.get("shares_yi") is None or r.get("shares_delta_yi") is None]


def _write_shares_date(
    date: str, prev_shares: dict, codes: list[str], prev_window: dict[str, list[float]] | None = None
) -> int:
    shares = fetch_shares_for_date(date)
    if not shares:
        return 0
    n = 0
    for code in codes:
        shares_yi = shares.get(code)
        if shares_yi is None:
            continue
        delta_yi = None
        delta_pct = None
        prev = prev_shares.get(code)
        if prev is not None and prev > 0:
            delta_yi = round(shares_yi - prev, 4)
            delta_pct = round(delta_yi / prev * 100, 3)
        # 双基准取强: 当日vs昨日 与 当日vs前N日均值(持续吸筹放大, 如12月底+3.8亿)
        hist = prev_window.get(code, []) if prev_window else []
        sp = calc_share_probability_dual(delta_pct, shares_yi, hist, SHARE_WINDOW)
        update_share_data(date, code, shares_yi, delta_yi, delta_pct, sp)
        prev_shares[code] = shares_yi
        if prev_window is not None:
            hist = prev_window.setdefault(code, [])
            hist.append(shares_yi)
            if len(hist) > SHARE_WINDOW:
                hist.pop(0)
        n += 1
    return n


def job_backfill_shares(
    progress: ProgressFn,
    days: int = DEFAULT_SHARES_BACKFILL_DAYS,
    force: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    if start_date:
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        dates = get_trading_dates(start_date, end)
    else:
        dates = get_trading_dates()[-days:]
    if not dates:
        raise RuntimeError("etf_daily 无交易日,请先回填ETF日度数据")
    prev_shares: dict = {}
    prev_window: dict[str, list[float]] = {}
    written = 0
    fetched_dates = 0
    fail_streak = 0
    for i, date in enumerate(dates, 1):
        missing = _missing_share_etfs(date)
        if not force and not missing:
            _load_prev_shares(date, prev_shares, prev_window)
            progress(i, len(dates), f"{date} 已完整")
            continue
        targets = [r["code"] for r in get_by_date(date)] if force else missing
        progress(i, len(dates), f"{date} 补 {len(targets)} 只: {','.join(targets[:3])}")
        wrote = _write_shares_date(date, prev_shares, targets, prev_window)
        if wrote == 0:
            # 整日拉取失败 → 可能被限流, 连续失败则暂停给远端喘息
            fail_streak += 1
            if fail_streak >= SHARES_FAIL_PAUSE_AFTER:
                progress(i, len(dates), f"{date} 连续失败 {fail_streak} 天, 暂停 {SHARES_FAIL_PAUSE_SEC}s")
                time.sleep(SHARES_FAIL_PAUSE_SEC)
        else:
            fail_streak = 0
            fetched_dates += 1
            written += wrote
        time.sleep(BACKFILL_SLEEP_SEC)
    progress(len(dates), len(dates), f"完成 {written} 行 ({fetched_dates} 天)")
    return {"dates": len(dates), "written": written, "fetched_dates": fetched_dates, "days": days}


def job_backfill_missing_shares(progress: ProgressFn) -> dict:
    """补全全历史缺失份额: 自动扫描缺失交易日, 仅拉取缺失 ETF, 不覆盖已有数据。

    缺失成因: 远端单日拉取失败(限流/网络)、份额 T+1 发布当日拉空、
    早期回填未覆盖。无需日期参数, 自动定位缺失日期从最早开始补。
    """
    dates = get_missing_share_dates()
    if not dates:
        progress(1, 1, "份额无缺失")
        return {"dates": 0, "written": 0, "fetched_dates": 0}
    prev_shares: dict = {}
    prev_window: dict[str, list[float]] = {}
    written = 0
    fetched_dates = 0
    fail_streak = 0
    for i, date in enumerate(dates, 1):
        _load_prev_shares(date, prev_shares, prev_window)
        targets = _missing_share_etfs(date)
        progress(i, len(dates), f"{date} 补 {len(targets)} 只: {','.join(targets[:3])}")
        wrote = _write_shares_date(date, prev_shares, targets, prev_window)
        if wrote == 0:
            fail_streak += 1
            if fail_streak >= SHARES_FAIL_PAUSE_AFTER:
                progress(i, len(dates), f"{date} 连续失败 {fail_streak} 天, 暂停 {SHARES_FAIL_PAUSE_SEC}s")
                time.sleep(SHARES_FAIL_PAUSE_SEC)
        else:
            fail_streak = 0
            fetched_dates += 1
            written += wrote
        time.sleep(BACKFILL_SLEEP_SEC)
    progress(len(dates), len(dates), f"完成 {written} 行 ({fetched_dates} 天)")
    return {"dates": len(dates), "written": written, "fetched_dates": fetched_dates}
