"""一级退出监测页面接口。"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from base.store.supply_repo import get_ipos, get_meta, get_reductions, get_unlocks
from supply.analysis.overview import REDUCTION_DAYS, build_overview

router = APIRouter(prefix="/api/supply", tags=["supply"])


@router.get("/overview")
def supply_overview(weeks: int = Query(8, ge=1, le=26)) -> dict:
    today = datetime.now().date()
    today_s = today.isoformat()
    reductions = get_reductions(
        (today - timedelta(days=REDUCTION_DAYS * 2)).isoformat(),
        today_s,
    )
    return build_overview(
        unlocks=get_unlocks(),
        reductions=reductions,
        ipos=get_ipos(),
        today=today_s,
        updated=get_meta("supply_updated"),
        weeks=weeks,
    )
