"""市场情绪与最新数据任务(后台任务, 带进度上报)。

job_fetch_sentiment — 成交额 + 融资余额拉取;
job_fetch_etf_latest  — 最新交易日 K 线 + 份额增量刷新。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from base.config import ETFS, SENTIMENT_BACKFILL_DAYS
from base.fetch.kline import fetch_index_kline, fetch_kline
from base.fetch.sentiment import fetch_margin_series, fetch_market_turnover
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


def job_fetch_sentiment(
    progress: ProgressFn,
    days: int = SENTIMENT_BACKFILL_DAYS,
    force: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    end = end_date or today
    end = min(end, today)

    latest_turnover = None if (force or start_date) else get_turnover_latest_date()
    if latest_turnover and latest_turnover >= end:
        progress(1, 1, "成交额已是最新")
        turnover = []
    else:
        if start_date:
            turnover_start = start_date
        elif latest_turnover:
            turnover_start = (datetime.strptime(latest_turnover, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            turnover_start = (now - timedelta(days=int(days * 1.5))).strftime("%Y-%m-%d")

        def turnover_cb(i: int, total: int, date: str) -> None:
            progress(i, total + 1, f"成交额 {date}")

        # 缓存判断: 已入库的日期跳过远端逐日拉取(force 强制重拉)
        skip_dates = {r["date"] for r in get_turnover_series()} if not force else set()
        # 边拉边写: 每拉到一天立即入库, 中断也不丢已拉数据
        turnover = fetch_market_turnover(
            turnover_start,
            end,
            on_progress=turnover_cb,
            skip_dates=skip_dates,
            on_row=lambda row: upsert_turnover([row]),
        )

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
