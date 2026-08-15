"""交易日历数据槽位台账刷新: 以交易日历为填充槽, 标注每天四个数据源的覆盖状态。

交易日历定义"哪天应该有数据"(槽位); 本任务把各数据表的实际覆盖回写到
trade_calendar 的 etf_daily_ok/shares_ok/turnover_ok/margin_ok 四列,
成为"应有 vs 实际"的权威台账。数据管理页可一键刷新, 交易日历页按覆盖着色。
"""

from __future__ import annotations

from base.scheduler.job_manager import ProgressFn
from base.store.calendar_repo import get_trade_days, update_coverage
from base.store.daily_repo import get_distinct_dates, get_missing_share_dates
from base.store.sentiment_repo import get_margin_series, get_turnover_series


def job_refresh_calendar_slots(progress: ProgressFn) -> dict:
    """扫描各数据源 → 批量更新日历覆盖属性(幂等, 可随时重跑)。"""
    etf_dates = set(get_distinct_dates())
    missing_share = set(get_missing_share_dates())
    turnover_dates = {r["date"] for r in get_turnover_series()}
    margin_dates = {r["date"] for r in get_margin_series()}
    days = get_trade_days()
    rows: list[tuple[int, int, int, int, str]] = []
    etf_covered = 0
    for d in days:
        etf_ok = 1 if d in etf_dates else 0
        shares_ok = 1 if (etf_ok and d not in missing_share) else 0
        turn_ok = 1 if d in turnover_dates else 0
        margin_ok = 1 if d in margin_dates else 0
        if etf_ok:
            etf_covered += 1
        rows.append((etf_ok, shares_ok, turn_ok, margin_ok, d))
    update_coverage(rows)
    progress(1, 1, f"槽位台账刷新完成: {len(days)} 天, {etf_covered} 天有 ETF 数据")
    return {"days": len(days), "etf_covered": etf_covered}
