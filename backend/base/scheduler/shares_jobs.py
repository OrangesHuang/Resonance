"""ETF 份额数据回填(可导入、带进度上报)。

逐日边拉边写, 已有份额/已完整的日期自动跳过, 中断后重跑续传;
按 chunk_days 交易日一批上报进度, 每批入库后图表即增长。
逐日写入核心见 shares_fill.py(区间回填与缺失补全共用)。
被 job_registry.py 注册为后台任务, 同时被 scripts/backfill_shares.py 复用。
"""

from __future__ import annotations

import math
import time
from datetime import datetime

from base.config import (
    BACKFILL_SLEEP_SEC,
    DEFAULT_CHUNK_DAYS,
    DEFAULT_SHARES_BACKFILL_DAYS,
    SHARES_FAIL_PAUSE_AFTER,
    SHARES_FAIL_PAUSE_SEC,
)
from base.scheduler.calendar_slots import job_refresh_calendar_slots
from base.scheduler.job_manager import ProgressFn
from base.scheduler.shares_fill import (
    _fillable_targets,
    _load_prev_shares,
    _missing_share_etfs,
    _retry_failed_dates,
    _write_shares_date,
)
from base.store.daily_repo import get_by_date, get_first_share_dates, get_missing_share_dates, get_trading_dates
from base.store.settings_repo import get_setting


def job_backfill_shares(
    progress: ProgressFn,
    days: int = DEFAULT_SHARES_BACKFILL_DAYS,
    force: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
    codes: list[str] | None = None,
) -> dict:
    """回填份额数据(逐日边拉边写, 按 chunk_days 交易日一批上报进度)。

    末尾对"整日拉取失败"的日期做轮末重试(SHARES_RETRY_PASSES), 避免一次限流
    抖动留下永久缺口。codes 显式指定时只补这些标的(单标的回填用), 跳过
    "上市前"过滤并把补全目标收窄到该集合。
    """
    if start_date:
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        dates = get_trading_dates(start_date, end)
    else:
        dates = get_trading_dates()[-days:]
    if not dates:
        raise RuntimeError("etf_daily 无交易日,请先回填ETF日度数据")
    code_filter = set(codes) if codes else None
    first_share = get_first_share_dates()
    prev_shares: dict = {}
    prev_window: dict[str, list[float]] = {}
    written = 0
    fetched_dates = 0
    fail_streak = 0
    failed: list[str] = []
    total_chunks = max(1, math.ceil(len(dates) / chunk_days))
    for i, date in enumerate(dates, 1):
        chunk_idx = min((i - 1) // chunk_days + 1, total_chunks)
        missing = _missing_share_etfs(date)
        if code_filter is not None:
            missing = [c for c in missing if c in code_filter]
        if not force and not missing:
            _load_prev_shares(date, prev_shares, prev_window)
            progress(chunk_idx, total_chunks, f"{date} 已完整 (第 {chunk_idx}/{total_chunks} 批)")
            continue
        if force:
            targets = [r["code"] for r in get_by_date(date)]
            if code_filter is not None:
                targets = [c for c in targets if c in code_filter]
        elif code_filter is not None:
            targets = missing  # 显式指定标的: 不做上市前过滤(调用方已收窄区间)
        else:
            targets = _fillable_targets(date, missing, first_share)
        if not targets:
            _load_prev_shares(date, prev_shares, prev_window)
            progress(chunk_idx, total_chunks, f"{date} 无份额数据(上市前), 跳过")
            continue
        progress(chunk_idx, total_chunks, f"{date} 补 {len(targets)} 只 (第 {chunk_idx}/{total_chunks} 批)")
        wrote = _write_shares_date(date, prev_shares, targets, prev_window)
        if wrote == 0:
            # 整日拉取失败 → 可能被限流, 连续失败则暂停给远端喘息
            failed.append(date)
            fail_streak += 1
            if fail_streak >= SHARES_FAIL_PAUSE_AFTER:
                progress(chunk_idx, total_chunks, f"{date} 连续失败 {fail_streak} 天, 暂停 {SHARES_FAIL_PAUSE_SEC}s")
                time.sleep(SHARES_FAIL_PAUSE_SEC)
        else:
            fail_streak = 0
            fetched_dates += 1
            written += wrote
        time.sleep(BACKFILL_SLEEP_SEC)
    retry_written, retry_days, still = _retry_failed_dates(
        progress, failed, force, prev_shares, prev_window, first_share, total_chunks, total_chunks, codes
    )
    written += retry_written
    fetched_dates += retry_days
    if still:
        progress(total_chunks, total_chunks, f"仍有 {len(still)} 天失败: {','.join(still[:5])}")
        print(f"[SCHEDULER] shares 仍失败 {len(still)} 天: {still}")
    progress(total_chunks, total_chunks, f"完成 {written} 行 ({fetched_dates} 天)")
    job_refresh_calendar_slots(progress)  # 刷新日历槽位台账(份额覆盖)
    return {
        "dates": len(dates),
        "written": written,
        "fetched_dates": fetched_dates,
        "days": days,
        "retried": len(failed),
        "still_failed": len(still),
    }


def job_backfill_missing_shares(
    progress: ProgressFn, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """补全缺失份额: 扫描缺失交易日, 仅拉取缺失 ETF, 不覆盖已有数据。

    缺失成因: 远端单日拉取失败(限流/网络)、份额 T+1 发布当日拉空、早期回填未覆盖。

    - 支持 [start_date, end_date] 收窄; 不传则用数据槽位起点之后的全区间。
    - **剔除上市前日期**: 只补"该标的已有份额最早日期"之后的日子。曾是严重陷阱 ——
      无约束时从 2005-01-17 起扫 5258 个缺失日, 其中大量是 512100 等标的尚未
      成立的日子, 远端必然返回空, 每 3 次失败暂停 60s, 几小时跑不完。
    - 末尾轮末重试失败日, 避免一次抖动留下永久缺口。
    """
    start = start_date or get_setting("data_slot_start") or None
    dates = get_missing_share_dates(start, end_date)
    if not dates:
        progress(1, 1, "份额无缺失")
        return {"dates": 0, "written": 0, "fetched_dates": 0, "skipped_pre_listing": 0, "still_failed": 0}
    first_share = get_first_share_dates()
    prev_shares: dict = {}
    prev_window: dict[str, list[float]] = {}
    written = 0
    fetched_dates = 0
    fail_streak = 0
    skipped = 0
    failed: list[str] = []
    for i, date in enumerate(dates, 1):
        _load_prev_shares(date, prev_shares, prev_window)
        targets = _fillable_targets(date, _missing_share_etfs(date), first_share)
        if not targets:
            skipped += 1
            progress(i, len(dates), f"{date} 无标的可补(上市前/无基准), 跳过")
            continue
        progress(i, len(dates), f"{date} 补 {len(targets)} 只: {','.join(targets[:3])}")
        wrote = _write_shares_date(date, prev_shares, targets, prev_window)
        if wrote == 0:
            failed.append(date)
            fail_streak += 1
            if fail_streak >= SHARES_FAIL_PAUSE_AFTER:
                progress(i, len(dates), f"{date} 连续失败 {fail_streak} 天, 暂停 {SHARES_FAIL_PAUSE_SEC}s")
                time.sleep(SHARES_FAIL_PAUSE_SEC)
        else:
            fail_streak = 0
            fetched_dates += 1
            written += wrote
        time.sleep(BACKFILL_SLEEP_SEC)
    retry_written, retry_days, still = _retry_failed_dates(
        progress, failed, False, prev_shares, prev_window, first_share, len(dates), len(dates)
    )
    written += retry_written
    fetched_dates += retry_days
    if still:
        progress(len(dates), len(dates), f"仍有 {len(still)} 天失败: {','.join(still[:5])}")
        print(f"[SCHEDULER] missing shares 仍失败 {len(still)} 天: {still}")
    progress(len(dates), len(dates), f"完成 {written} 行 ({fetched_dates} 天), 跳过 {skipped} 天")
    job_refresh_calendar_slots(progress)
    return {
        "dates": len(dates),
        "written": written,
        "fetched_dates": fetched_dates,
        "skipped_pre_listing": skipped,
        "retried": len(failed),
        "still_failed": len(still),
    }
