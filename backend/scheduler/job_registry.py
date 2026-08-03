"""任务注册表:任务名 → 元信息(label/exclusive/defaults) 与执行函数映射。"""
from __future__ import annotations

from config import (
    DEFAULT_ETF_SEED_DAYS, DEFAULT_SHARES_BACKFILL_DAYS, SENTIMENT_BACKFILL_DAYS,
)
from scheduler.data_jobs import (
    job_sync_calendar, job_backfill_etf_daily, job_backfill_shares,
    job_fetch_sentiment, job_fetch_etf_latest,
)
from scheduler.rebuild import job_rebuild_all

JOB_DEFS: dict[str, dict] = {
    "sync_calendar": {
        "label": "同步交易日历", "exclusive": False, "defaults": {},
    },
    "backfill_etf_daily": {
        "label": "回填ETF日度数据", "exclusive": False,
        "defaults": {"days": DEFAULT_ETF_SEED_DAYS, "force": False,
                     "start_date": None, "end_date": None},
    },
    "backfill_shares": {
        "label": "回填份额数据", "exclusive": False,
        "defaults": {"days": DEFAULT_SHARES_BACKFILL_DAYS, "force": False,
                     "start_date": None, "end_date": None},
    },
    "fetch_sentiment": {
        "label": "拉取市场情绪", "exclusive": False,
        "defaults": {"days": SENTIMENT_BACKFILL_DAYS, "force": False,
                     "start_date": None, "end_date": None},
    },
    "fetch_etf_latest": {
        "label": "刷新最新ETF数据", "exclusive": False, "defaults": {},
    },
    "rebuild_all": {
        "label": "一键重建全部数据", "exclusive": True,
        "defaults": {
            "etf_days": DEFAULT_ETF_SEED_DAYS,
            "shares_days": DEFAULT_SHARES_BACKFILL_DAYS,
            "sentiment_days": SENTIMENT_BACKFILL_DAYS,
            "force": False,
            "start_date": None, "end_date": None,
        },
    },
}

JOB_FNS = {
    "sync_calendar": job_sync_calendar,
    "backfill_etf_daily": job_backfill_etf_daily,
    "backfill_shares": job_backfill_shares,
    "fetch_sentiment": job_fetch_sentiment,
    "fetch_etf_latest": job_fetch_etf_latest,
    "rebuild_all": job_rebuild_all,
}
