"""市场情绪与最新数据任务(后台任务, 带进度上报)。

job_fetch_sentiment — 成交额 + 融资余额拉取;
job_fetch_etf_latest  — 最新交易日 K 线 + 份额增量刷新。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from base.config import DEFAULT_CHUNK_DAYS, ETFS, SENTIMENT_BACKFILL_DAYS
from base.fetch.kline import fetch_index_kline, fetch_kline
from base.fetch.sentiment import fetch_margin_series, fetch_market_turnover, fetch_turnover_range
from base.fetch.shares import calc_share_delta
from base.scheduler.calendar_slots import job_refresh_calendar_slots
from base.scheduler.job_manager import ProgressFn
from base.store.calendar_repo import get_last_trading_day
from base.store.daily_repo import (
    get_shares_by_date,
    shares_complete_for,
    update_share_data,
    upsert_daily,
)
from base.store.sentiment_repo import (
    get_margin_latest_date,
    get_turnover_latest_date,
    get_turnover_series,
    upsert_margin,
    upsert_turnover,
)
from resonance.analysis.composite import analyze_single_etf
from resonance.analysis.factors import calc_share_probability


def _turnover_chunks(start: str, end: str, chunk_days: int) -> list[tuple[str, str]]:
    """成交额回填按 chunk_days 个自然日切批(东财批量源一次请求一批)。"""
    cur = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    out: list[tuple[str, str]] = []
    while cur <= end_dt:
        nxt = cur + timedelta(days=chunk_days - 1)
        nxt = min(nxt, end_dt)
        out.append((cur.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        cur = nxt + timedelta(days=1)
    return out


def _fetch_turnover_batch(
    start: str,
    end: str,
    progress: ProgressFn,
    total: int,
    chunk_i: int,
    skip_dates: set[str],
    force: bool,
) -> list[dict]:
    """拉取一批成交额: 优先东财区间批量(一次请求全批), 失败回退逐日 akshare。

    东财源含 2021 全历史(SSE 官方 2021 返回空, akshare 逐日不可用),
    故补 2021 时走东财; 2022 后东财失败时逐日回退兜底。
    """
    # 区间整批已在库 → 跳过(force 时强制重拉)
    if not force:
        all_covered = all(d in skip_dates for d in _weekday_dates(start, end))
        if all_covered:
            return []
    rows = fetch_turnover_range(start, end)
    if rows:
        upsert_turnover(rows)
        return rows

    # 回退: 逐日 akshare 边拉边写
    def cb(i: int, t: int, d: str) -> None:
        progress(chunk_i, total, f"成交额 第{chunk_i}/{total}批 {d}")

    fetched = fetch_market_turnover(
        start,
        end,
        on_progress=cb,
        skip_dates=skip_dates if not force else set(),
        on_row=lambda row: upsert_turnover([row]),
    )
    return fetched


def _weekday_dates(start_date: str, end_date: str) -> list[datetime]:
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    out: list[datetime] = []
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def job_fetch_sentiment(
    progress: ProgressFn,
    days: int = SENTIMENT_BACKFILL_DAYS,
    force: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
) -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    end = end_date or today
    end = min(end, today)

    latest_turnover = None if (force or start_date) else get_turnover_latest_date()
    if latest_turnover and latest_turnover >= end:
        progress(1, 1, "成交额已是最新")
        turnover: list[dict] = []
    else:
        if start_date:
            turnover_start = start_date
        elif latest_turnover:
            turnover_start = (datetime.strptime(latest_turnover, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            turnover_start = (now - timedelta(days=int(days * 1.5))).strftime("%Y-%m-%d")

        # 缓存判断: 已入库的日期跳过远端拉取(force 强制重拉)
        skip_dates = {r["date"] for r in get_turnover_series()} if not force else set()
        chunks = _turnover_chunks(turnover_start, end, chunk_days)
        total = len(chunks)
        turnover = []
        for ci, (cs, ce) in enumerate(chunks, 1):
            progress(ci, total, f"成交额 第 {ci}/{total} 批 · {cs}")
            rows = _fetch_turnover_batch(cs, ce, progress, total, ci, skip_dates, force)
            turnover.extend(rows)

    latest_margin = None if (force or start_date) else get_margin_latest_date()
    if latest_margin and latest_margin >= end:
        progress(1, 1, "融资余额已是最新")
        margin = []
    else:
        if start_date:
            margin_start = start_date
        elif latest_margin:
            margin_start = (datetime.strptime(latest_margin, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            margin_start = (now - timedelta(days=int(days * 1.5))).strftime("%Y-%m-%d")
        progress(1, 1, "融资余额拉取中…")
        margin = fetch_margin_series(margin_start, end)
        if margin:
            upsert_margin(margin)

    progress(1, 1, "完成")
    job_refresh_calendar_slots(progress)  # 刷新日历槽位台账(成交额/融资覆盖)
    return {
        "turnover": len(turnover),
        "margin": len(margin),
        "start": start_date or latest_turnover or "full",
        "end": end,
    }


def _refresh_share_cache() -> dict:
    """份额增量缓存: 库中最新交易日已完整则直接读库, 不触网。"""
    target = get_last_trading_day(datetime.now().strftime("%Y-%m-%d"))
    if shares_complete_for(target):
        return {code: {"date": target, **info} for code, info in get_shares_by_date(target).items()}
    today = datetime.now().strftime("%Y-%m-%d")
    deltas = calc_share_delta(today)
    for code, info in deltas.items():
        update_share_data(
            info["date"],
            code,
            info["shares_yi"],
            info.get("delta_yi"),
            info.get("delta_pct"),
            calc_share_probability(info.get("delta_pct")),
        )
    return deltas


def job_fetch_etf_latest(progress: ProgressFn) -> dict:
    progress(0, len(ETFS) + 1, "拉取份额数据…")
    share_cache = _refresh_share_cache()
    idx_kline = fetch_index_kline()
    codes = list(ETFS.items())
    count = 0
    latest_date: str | None = None
    for i, (code, info) in enumerate(codes, 1):
        progress(i, len(codes) + 1, f"{code} {info['name']}")
        kline = fetch_kline(code)
        share_info = share_cache.get(code, {})
        result = analyze_single_etf(
            kline=kline,
            idx_kline=idx_kline,
            shares_delta_pct=share_info.get("delta_pct"),
        )
        if result:
            # 份额日期必须与当日匹配(份额 T+1 发布, 缓存可能是前一日)
            if share_info.get("date") == result["date"]:
                result["shares_yi"] = share_info.get("shares_yi")
                result["shares_delta_yi"] = share_info.get("delta_yi")
                result["shares_delta_pct"] = share_info.get("delta_pct")
            upsert_daily(result["date"], code, result)
            count += 1
            latest_date = result["date"]
    progress(len(codes) + 1, len(codes) + 1, f"完成 {count} 只 ETF")
    return {"count": count, "date": latest_date}
