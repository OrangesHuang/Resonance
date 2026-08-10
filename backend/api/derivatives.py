"""衍生品数据API: 期权PCR + 股指期货基差 + 三维背离信号。"""
from fastapi import APIRouter, BackgroundTasks

from store.derivatives_repo import (
    get_pcr_series, get_basis_series,
    get_pcr_latest_date, get_basis_latest_date,
)
from store.daily_repo import get_by_code
from analysis.derivatives_divergence import compute_divergence, FUTURES_PROXY
from scheduler.tasks import task_fetch_derivatives

router = APIRouter(prefix="/api/derivatives", tags=["derivatives"])


@router.get("/overview")
def derivatives_overview():
    pcr = get_pcr_series()
    basis = get_basis_series()

    dates = set()
    for r in pcr:
        dates.add(r["date"])
    for r in basis:
        dates.add(r["date"])

    return {
        "pcr": pcr,
        "basis": basis,
        "pcr_latest_date": get_pcr_latest_date(),
        "basis_latest_date": get_basis_latest_date(),
        "trading_days": len(dates),
    }


@router.get("/divergence")
def derivatives_divergence(code: str = "588000"):
    fut = FUTURES_PROXY.get(code)
    if not fut:
        return {"code": code, "signals": []}
    kl = get_by_code(code)
    pcr = [r for r in get_pcr_series() if r["underlying_code"] == code]
    basis = [r for r in get_basis_series() if r["futures_code"] == fut]
    return {"code": code, "signals": compute_divergence(kl, pcr, basis)}


@router.post("/refresh")
def derivatives_refresh(bg: BackgroundTasks):
    backfill = get_pcr_latest_date() is None
    bg.add_task(task_fetch_derivatives, backfill=backfill)
    return {"status": "ok", "message": "后台拉取中，请稍后刷新页面"}

