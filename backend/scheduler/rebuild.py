"""一键重建全量数据的有序流水线。

阶段顺序承重:交易日历 → ETF日度 → 份额(依赖 etf_daily 交易日) → 市场情绪。
子任务进度按阶段权重映射到总百分比(0-100)。
"""
from __future__ import annotations

from typing import Optional

from config import (
    DEFAULT_ETF_SEED_DAYS, DEFAULT_SHARES_BACKFILL_DAYS, SENTIMENT_BACKFILL_DAYS,
)
from scheduler.job_manager import ProgressFn
from scheduler.data_jobs import (
    job_sync_calendar, job_backfill_etf_daily, job_backfill_shares, job_fetch_sentiment,
)

_W_CALENDAR = 5
_W_ETF = 45
_W_SHARES = 30
_W_SENTIMENT = 20


def _scaled(progress: ProgressFn, start: int, weight: int) -> ProgressFn:
    def cb(current: int, total: int, message: str) -> None:
        frac = (current / total) if total else 0.0
        progress(start + int(frac * weight), 100, message)
    return cb


def job_rebuild_all(progress: ProgressFn,
                    etf_days: int = DEFAULT_ETF_SEED_DAYS,
                    shares_days: int = DEFAULT_SHARES_BACKFILL_DAYS,
                    sentiment_days: int = SENTIMENT_BACKFILL_DAYS,
                    force: bool = False,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> dict:
    progress(0, 100, "阶段1/4 交易日历")
    calendar = job_sync_calendar(_scaled(progress, 0, _W_CALENDAR))

    progress(_W_CALENDAR, 100, "阶段2/4 ETF日度数据")
    etf = job_backfill_etf_daily(_scaled(progress, _W_CALENDAR, _W_ETF),
                                 etf_days, start_date, end_date, force)

    shares_start = _W_CALENDAR + _W_ETF
    progress(shares_start, 100, "阶段3/4 份额数据")
    shares = job_backfill_shares(_scaled(progress, shares_start, _W_SHARES),
                                 shares_days, force, start_date, end_date)

    sentiment_start = shares_start + _W_SHARES
    progress(sentiment_start, 100, "阶段4/4 市场情绪")
    sentiment = job_fetch_sentiment(_scaled(progress, sentiment_start, _W_SENTIMENT),
                                    sentiment_days, False, start_date, end_date)

    progress(100, 100, "重建完成")
    return {"calendar": calendar, "etf_daily": etf, "shares": shares, "sentiment": sentiment}
