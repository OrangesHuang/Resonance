"""数据管理任务(可导入、带进度上报): 日历同步在此文件。

ETF 日度回填见 etf_daily_jobs.py(渐进式分批, 支持 2021 等历史日期区间);
份额回填见 shares_jobs.py; 情绪/最新数据任务见 sentiment_jobs.py。
被 job_registry.py 注册为后台任务, 同时被 scripts/ 薄壳脚本复用,
保证任务与脚本共用同一条代码路径(开源独立重建的关键)。
"""

from __future__ import annotations

from base.fetch.calendar import fetch_trade_dates
from base.scheduler.job_manager import ProgressFn
from base.store.calendar_repo import get_calendar_count, get_range, reload_cache, upsert_trade_dates


def job_sync_calendar(progress: ProgressFn) -> dict:
    progress(0, 1, "同步交易日历…")
    dates = fetch_trade_dates()
    if dates:
        upsert_trade_dates(dates)
        reload_cache()
    progress(1, 1, f"{len(dates)} 个交易日")
    return {"count": get_calendar_count(), "range": get_range()}
