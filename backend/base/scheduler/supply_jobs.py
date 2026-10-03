"""一级退出/供给数据刷新任务(可导入、带进度上报)。

解禁(近90天+未来210天) + 股东减持(近约400天) + 新股发行, 写入三张表。
减持为全量拉取(约 2 分钟), 只挂周更, 不放在请求路径上。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from base.fetch.supply import fetch_ipo_events, fetch_reduction_events, fetch_unlock_events
from base.scheduler.job_manager import ProgressFn
from base.store.supply_repo import set_meta, upsert_ipos, upsert_reductions, upsert_unlocks

UNLOCK_PAST_DAYS = 90
UNLOCK_FUTURE_DAYS = 210
REDUCTION_LOOKBACK_DAYS = 400


def job_refresh_supply(progress: ProgressFn) -> dict:
    today = datetime.now().date()
    progress(0, 3, "拉取限售解禁(近90天 + 未来210天)…")
    unlocks = fetch_unlock_events(
        (today - timedelta(days=UNLOCK_PAST_DAYS)).isoformat(),
        (today + timedelta(days=UNLOCK_FUTURE_DAYS)).isoformat(),
    )
    n_unlock = upsert_unlocks(unlocks)

    progress(1, 3, "拉取股东减持明细(全量, 约2分钟)…")
    reductions = fetch_reduction_events((today - timedelta(days=REDUCTION_LOOKBACK_DAYS)).isoformat())
    n_reduce = upsert_reductions(reductions)

    progress(2, 3, "拉取新股发行一览…")
    ipos = fetch_ipo_events()
    n_ipo = upsert_ipos(ipos)

    set_meta("supply_updated", today.isoformat())
    progress(3, 3, f"完成: 解禁{n_unlock} · 减持{n_reduce} · 新股{n_ipo}")
    return {"unlock": n_unlock, "reduction": n_reduce, "ipo": n_ipo}


def task_refresh_supply() -> None:
    """定时任务包装(无进度回调, 打印日志)。"""
    job_refresh_supply(lambda c, t, m: print(f"[SUPPLY] {c}/{t} {m}"))
