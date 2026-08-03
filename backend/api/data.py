"""数据管理 API:数据源状态 + 后台任务调度/查询。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import (
    DEFAULT_ETF_SEED_DAYS, DEFAULT_SHARES_BACKFILL_DAYS, SENTIMENT_BACKFILL_DAYS,
    JOB_LIST_LIMIT, JOB_DAYS_MAX,
)
from store.daily_repo import get_stats
from store.sentiment_repo import (
    get_turnover_count, get_margin_count, get_turnover_series, get_margin_series,
)
from store.calendar_repo import get_calendar_count, get_range, get_last_sync
from scheduler.tasks import scheduler
from scheduler.job_manager import job_manager, run_job
from scheduler.job_registry import JOB_DEFS, JOB_FNS

router = APIRouter(prefix="/api/data", tags=["data"])


class StartJobRequest(BaseModel):
    task: str
    params: dict = {}


def _series_range(rows: list[dict]) -> list:
    if not rows:
        return [None, None]
    return [rows[0].get("date"), rows[-1].get("date")]


@router.get("/status")
def data_status():
    turnover = get_turnover_series()
    margin = get_margin_series()
    running = [j.to_dict() for j in job_manager.list(JOB_LIST_LIMIT)
               if j.status in ("pending", "running")]
    sched = []
    for j in scheduler.get_jobs():
        nr = j.next_run_time
        sched.append({"id": j.id, "next_run": nr.isoformat() if nr else None})
    return {
        "sources": {
            "etf_daily": get_stats(),
            "turnover": {"count": get_turnover_count(), "range": _series_range(turnover)},
            "margin": {"count": get_margin_count(), "range": _series_range(margin)},
            "calendar": {"count": get_calendar_count(), "range": get_range(),
                         "last_sync": get_last_sync()},
        },
        "jobs": [{"task": k, "label": v["label"], "defaults": v["defaults"]}
                 for k, v in JOB_DEFS.items()],
        "running": running,
        "scheduler": sched,
        "defaults": {"etf_days": DEFAULT_ETF_SEED_DAYS,
                     "shares_days": DEFAULT_SHARES_BACKFILL_DAYS,
                     "sentiment_days": SENTIMENT_BACKFILL_DAYS},
    }


def _merge_params(defaults: dict, incoming: dict) -> dict:
    merged = dict(defaults)
    for k, v in incoming.items():
        if k in merged:
            merged[k] = v
    return merged


def _validate_params(params: dict) -> Optional[str]:
    for k, v in params.items():
        if k.endswith("days"):
            if not isinstance(v, int) or isinstance(v, bool) or not (1 <= v <= JOB_DAYS_MAX):
                return f"参数 {k} 必须为 1~{JOB_DAYS_MAX} 的整数"
        elif k in ("start_date", "end_date") and v is not None:
            if not isinstance(v, str):
                return f"参数 {k} 必须为 YYYY-MM-DD 字符串"
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                return f"参数 {k} 格式必须为 YYYY-MM-DD"
    start, end = params.get("start_date"), params.get("end_date")
    today = datetime.now().strftime("%Y-%m-%d")
    if start and start > today:
        return "开始日期不能晚于今天"
    if start and end and start > end:
        return "开始日期不能晚于结束日期"
    return None


@router.post("/jobs", status_code=202)
async def start_job(req: StartJobRequest):
    if req.task not in JOB_DEFS:
        raise HTTPException(status_code=404, detail=f"unknown task: {req.task}")
    defn = JOB_DEFS[req.task]
    params = _merge_params(defn["defaults"], req.params)
    err = _validate_params(params)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if not job_manager.can_start(req.task, defn["exclusive"]):
        raise HTTPException(status_code=409, detail="任务正在运行,请稍后再试")
    job_id = job_manager.submit(req.task, params, defn["exclusive"])
    asyncio.create_task(run_job(job_id, partial(JOB_FNS[req.task], **params)))
    return {"job_id": job_id}


@router.get("/jobs")
def list_jobs(limit: int = Query(default=JOB_LIST_LIMIT, ge=1, le=100)):
    return [j.to_dict() for j in job_manager.list(limit)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()
