"""数据管理 API:数据源状态 + 后台任务调度/查询。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from functools import partial

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from base.config import (
    DEFAULT_ETF_SEED_DAYS,
    DEFAULT_SHARES_BACKFILL_DAYS,
    JOB_DAYS_MAX,
    JOB_LIST_LIMIT,
    SENTIMENT_BACKFILL_DAYS,
)
from base.scheduler.job_manager import job_manager, run_job
from base.scheduler.job_registry import JOB_DEFS, JOB_FNS
from base.scheduler.scheduled_defs import SCHEDULED_DEFS
from base.scheduler.tasks import scheduler
from base.store.calendar_repo import get_calendar_count, get_last_sync, get_range, get_trade_days
from base.store.daily_repo import get_distinct_dates, get_stats
from base.store.sentiment_repo import (
    get_margin_count,
    get_margin_series,
    get_turnover_count,
    get_turnover_series,
)
from base.store.settings_repo import get_setting, set_setting

router = APIRouter(prefix="/api/data", tags=["data"])


class StartJobRequest(BaseModel):
    task: str
    params: dict = {}


class SettingsUpdate(BaseModel):
    data_slot_start: str | None = None


def _series_range(rows: list[dict]) -> list:
    if not rows:
        return [None, None]
    return [rows[0].get("date"), rows[-1].get("date")]


def _slot_stats() -> dict:
    """数据槽位汇总: 交易日历为填充槽, 槽位区间 = [数据起始设置, 最新数据日]。

    控制"数据起始日期"设置即可控制系统应有数据的"总量"(槽位 = 起始日至今的
    交易日), 缺口 = 槽位中实际缺失的交易日。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    stats = get_stats()
    lo_data = stats["date_range"][0]
    hi_data = stats["date_range"][1] or today
    slot_start = get_setting("data_slot_start") or lo_data or today
    expected = get_trade_days(slot_start, hi_data)
    actual = set(get_distinct_dates())
    missing = [d for d in expected if d not in actual]
    runs: list[list[str]] = []
    cur: list[str] = []
    for d in expected:
        if d in actual:
            if cur:
                runs.append(cur)
                cur = []
        else:
            cur.append(d)
    if cur:
        runs.append(cur)
    return {
        "slot_start": slot_start,
        "slot_total": len(expected),
        "covered_days": len(expected) - len(missing),
        "missing_days": len(missing),
        "missing_ranges": [[r[0], r[-1]] for r in runs],
    }


def _etf_daily_gaps() -> tuple[list[list[str]], int]:
    """以交易日历为填充槽: 数据区间内"应该有数据"却缺失的交易日区间与天数。

    区间拉取被接口单次上限截断(如 2021~2023 中间段)、任务中断、单日失败
    都会留下缺口 — 日历明确定义哪天应有数据, 缺口可被扫描/展示/一键补全。
    """
    stats = get_stats()
    lo, hi = stats["date_range"]
    if not lo or not hi:
        return [], 0
    actual = set(get_distinct_dates())
    runs: list[list[str]] = []
    cur: list[str] = []
    for d in get_trade_days(lo, hi):
        if d in actual:
            if cur:
                runs.append(cur)
                cur = []
        else:
            cur.append(d)
    if cur:
        runs.append(cur)
    return [[r[0], r[-1]] for r in runs], sum(len(r) for r in runs)


@router.get("/status")
def data_status():
    turnover = get_turnover_series()
    margin = get_margin_series()
    running = [j.to_dict() for j in job_manager.list(JOB_LIST_LIMIT) if j.status in ("pending", "running")]
    sched = []
    for j in scheduler.get_jobs():
        nr = j.next_run_time
        sched.append({"id": j.id, "next_run": nr.isoformat() if nr else None})
    slots = _slot_stats()
    return {
        "sources": {
            "etf_daily": {
                **get_stats(),
                "missing_days": slots["missing_days"],
                "missing_ranges": slots["missing_ranges"],
            },
            "turnover": {"count": get_turnover_count(), "range": _series_range(turnover)},
            "margin": {"count": get_margin_count(), "range": _series_range(margin)},
            "calendar": {"count": get_calendar_count(), "range": get_range(), "last_sync": get_last_sync()},
        },
        "slots": slots,
        "jobs": [
            {"task": k, "label": v["label"], "defaults": v["defaults"], "data_flow": v.get("data_flow", [])}
            for k, v in JOB_DEFS.items()
        ],
        "running": running,
        "scheduler": sched,
        "defaults": {
            "etf_days": DEFAULT_ETF_SEED_DAYS,
            "shares_days": DEFAULT_SHARES_BACKFILL_DAYS,
            "sentiment_days": SENTIMENT_BACKFILL_DAYS,
        },
    }


def _merge_params(defaults: dict, incoming: dict) -> dict:
    merged = dict(defaults)
    for k, v in incoming.items():
        if k in merged:
            merged[k] = v
    return merged


def _validate_params(params: dict) -> str | None:
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


@router.get("/settings")
def read_settings():
    """数据槽位设置: data_slot_start 定义"从哪天起应该有数据"(控制数据总量)。"""
    return {"data_slot_start": get_setting("data_slot_start")}


@router.put("/settings")
def write_settings(body: SettingsUpdate):
    value = (body.data_slot_start or "").strip()
    if value:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="data_slot_start 格式必须为 YYYY-MM-DD")
    set_setting("data_slot_start", value)
    return {"data_slot_start": get_setting("data_slot_start")}


@router.get("/jobs")
def list_jobs(limit: int = Query(default=JOB_LIST_LIMIT, ge=1, le=100)):
    return [j.to_dict() for j in job_manager.list(limit)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()


def _prev_fire_time(trigger: object, now: datetime) -> datetime | None:
    """反推上次计划触发时间(本版本 APScheduler trigger 无 get_previous_fire_time)。

    谓词 P(x) = "(x, now) 内存在触发":P(now) 恒假,往前指数扩窗直到 P(lo) 为真,
    再在 [lo, hi] 分钟级二分找最晚触发点。
    """
    get_next = getattr(trigger, "get_next_fire_time", None)
    if get_next is None:
        return None
    best: datetime | None = None
    hi = now
    step = timedelta(hours=1)
    lo = now - step
    for _ in range(40):
        cand = get_next(lo, now)
        if cand is not None and cand < now:
            best = cand
            break
        hi = lo
        step *= 2
        lo = now - step
    else:
        return None
    grain = timedelta(minutes=1)
    while hi - lo > grain:
        mid = lo + (hi - lo) / 2
        cand = get_next(mid, now)
        if cand is not None and cand < now:
            lo = mid
            best = cand
        else:
            hi = mid
    cand = get_next(lo, now)
    if cand is not None and cand < now:
        return cand
    return best


@router.get("/scheduled")
def list_scheduled_tasks() -> list[dict]:
    """定时任务全景:注册表元信息 + 运行中的上次/下次运行时间(供前端倒计时与进度条)。"""
    now = datetime.now().astimezone()
    next_runs: dict[str, str | None] = {}
    prev_runs: dict[str, str | None] = {}
    for j in scheduler.get_jobs():
        nr = j.next_run_time
        next_runs[j.id] = nr.isoformat() if nr else None
        pr: datetime | None = None
        if nr:
            interval = getattr(j.trigger, "interval", None)
            if interval is not None:
                pr = nr - interval  # IntervalTrigger 直接反推一个周期
            else:
                pr = _prev_fire_time(j.trigger, now)
        prev_runs[j.id] = pr.isoformat() if pr else None
    return [
        {"id": tid, **defn, "next_run": next_runs.get(tid), "prev_run": prev_runs.get(tid)}
        for tid, defn in SCHEDULED_DEFS.items()
    ]
