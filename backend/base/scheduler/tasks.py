"""定时任务编排层: 任务注册与启动/停止(阻塞任务经 asyncio.to_thread 派发)。

任务实现见 intraday_tasks.py(盘中) / daily_tasks.py(盘后);
共享内存状态见 state.py。api 层从本模块导入任务函数与 scheduler,
保证 import 路径不变。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from base.config import (
    CALENDAR_SYNC_DOW,
    CALENDAR_SYNC_HOUR,
    CALENDAR_SYNC_MIN,
    REALTIME_INTERVAL_SEC,
    SENTIMENT_FETCH_HOUR,
    SENTIMENT_FETCH_MIN,
    SENTIMENT_FETCH_NIGHT_HOUR,
    SENTIMENT_FETCH_NIGHT_MIN,
    TURNOVER_POLL_INTERVAL_SEC,
)
from base.scheduler.daily_tasks import (
    task_cleanup,
    task_daily_analysis,
    task_fetch_sentiment,
    task_fetch_shares,
    task_sync_calendar,
)
from base.scheduler.intraday_tasks import (
    task_intraday_update,
    task_preload_kline,
    task_realtime_poll,
    task_turnover_poll,
)
from base.scheduler.time_guard import is_trading_time, trading_day_guard
from base.store.calendar_repo import get_calendar_count, reload_cache
from base.store.database import init_db
from base.store.sentiment_repo import get_margin_count, get_turnover_count

scheduler = AsyncIOScheduler()


def _to_thread(fn: Callable[..., object]) -> Callable[..., object]:
    """APScheduler 注册包装: 阻塞任务丢线程池, 避免事件循环被网络/DNS 卡死。

    曾因实时轮询同步 urllib 在事件循环上执行, DNS 挂起时整个 API 阻塞
    (日志出现 "Run time of job was missed by ...")。
    """

    async def wrapper(*args, **kwargs) -> object:
        return await asyncio.to_thread(fn, *args, **kwargs)

    return wrapper


def start_scheduler() -> None:
    init_db()
    reload_cache()
    if get_calendar_count() == 0:
        task_sync_calendar()

    task_preload_kline()
    task_fetch_shares()

    # 盘中启动时立即拉取当日数据
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
        _to_thread(task_realtime_poll),
        IntervalTrigger(seconds=REALTIME_INTERVAL_SEC),
        id="realtime_poll",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(trading_day_guard(task_intraday_update)),
        IntervalTrigger(minutes=15),
        id="intraday_update",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(trading_day_guard(task_preload_kline)),
        CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),
        id="preload_kline",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(trading_day_guard(task_daily_analysis)),
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="daily_analysis",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(trading_day_guard(task_fetch_shares)),
        CronTrigger(hour=19, minute=30, day_of_week="mon-fri"),
        id="fetch_shares",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(task_turnover_poll),
        IntervalTrigger(seconds=TURNOVER_POLL_INTERVAL_SEC),
        id="turnover_poll",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(task_cleanup),
        CronTrigger(hour=2, minute=0),
        id="cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(trading_day_guard(task_fetch_sentiment)),
        CronTrigger(hour=SENTIMENT_FETCH_HOUR, minute=SENTIMENT_FETCH_MIN, day_of_week="mon-fri"),
        id="fetch_sentiment",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(trading_day_guard(task_fetch_sentiment)),
        CronTrigger(hour=SENTIMENT_FETCH_NIGHT_HOUR, minute=SENTIMENT_FETCH_NIGHT_MIN, day_of_week="mon-fri"),
        id="fetch_sentiment_night",
        replace_existing=True,
    )
    scheduler.add_job(
        _to_thread(task_sync_calendar),
        CronTrigger(day_of_week=CALENDAR_SYNC_DOW, hour=CALENDAR_SYNC_HOUR, minute=CALENDAR_SYNC_MIN),
        id="sync_calendar",
        replace_existing=True,
    )
    scheduler.start()
    print("[SCHEDULER] started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
