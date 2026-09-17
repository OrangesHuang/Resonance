"""ETF 份额数据回填(可导入、带进度上报)。

逐日边拉边写, 已有份额/已完整的日期自动跳过, 中断后重跑续传;
按 chunk_days 交易日一批上报进度, 每批入库后图表即增长。
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
    ETFS,
    SHARE_WINDOW,
    SHARES_FAIL_PAUSE_AFTER,
    SHARES_FAIL_PAUSE_SEC,
    SHARES_RETRY_PASSES,
)
from base.fetch.shares import fetch_shares_for_date
from base.scheduler.calendar_slots import job_refresh_calendar_slots
from base.scheduler.job_manager import ProgressFn
from base.store.daily_repo import (
    get_by_date,
    get_first_share_dates,
    get_missing_share_dates,
    get_trading_dates,
    update_share_data,
)
from base.store.settings_repo import get_setting
from resonance.analysis.factors import calc_share_probability_dual


def _load_prev_shares(date: str, prev_shares: dict, prev_window: dict[str, list[float]]) -> None:
    for r in get_by_date(date):
        if r.get("shares_yi") is not None:
            prev_shares[r["code"]] = r["shares_yi"]
            hist = prev_window.setdefault(r["code"], [])
            hist.append(r["shares_yi"])
            if len(hist) > SHARE_WINDOW:
                hist.pop(0)


def _missing_share_etfs(date: str) -> list[str]:
    """该日期在库中缺份额数据或缺 delta 的**当前在册** ETF。

    - 缺 delta 也算缺失: 后补份额时 prev 可能未入库导致 delta 留空
      (如 159352 2026-08-10 shares_yi 有值但 sd None, 需重算)。
    - 只看 ETFS 在册标的: 库里保留着已移除标的的历史行(510880/159919/510310/
      510330 等), 追它们的份额毫无意义, 还会让补全任务反复失败。
    """
    rows = {r["code"]: r for r in get_by_date(date)}
    return [
        c for c, r in rows.items() if c in ETFS and (r.get("shares_yi") is None or r.get("shares_delta_yi") is None)
    ]


def _write_shares_date(
    date: str, prev_shares: dict, codes: list[str], prev_window: dict[str, list[float]] | None = None
) -> int:
    shares = fetch_shares_for_date(date)
    if not shares:
        return 0
    n = 0
    for code in codes:
        shares_yi = shares.get(code)
        if shares_yi is None:
            continue
        delta_yi = None
        delta_pct = None
        prev = prev_shares.get(code)
        if prev is not None and prev > 0:
            delta_yi = round(shares_yi - prev, 4)
            delta_pct = round(delta_yi / prev * 100, 3)
        # 双基准取强: 当日vs昨日 与 当日vs前N日均值(持续吸筹放大, 如12月底+3.8亿)
        hist = prev_window.get(code, []) if prev_window else []
        sp = calc_share_probability_dual(delta_pct, shares_yi, hist, SHARE_WINDOW)
        update_share_data(date, code, shares_yi, delta_yi, delta_pct, sp)
        prev_shares[code] = shares_yi
        if prev_window is not None:
            hist = prev_window.setdefault(code, [])
            hist.append(shares_yi)
            if len(hist) > SHARE_WINDOW:
                hist.pop(0)
        n += 1
    return n


def _fillable_targets(date: str, targets: list[str], first_share: dict[str, str]) -> list[str]:
    """剔除"ETF 尚未成立"的日期上的标的。

    判据: 该标的已有份额的最早日期(无任何份额的标的视为"需先做区间回填",
    不参与自动补全 —— 否则会像 512100 那样在上市前的日期上反复失败)。
    """
    out = []
    for code in targets:
        first = first_share.get(code)
        if first and date >= first:
            out.append(code)
    return out


def _write_date(
    date: str, force: bool, prev_shares: dict, prev_window: dict[str, list[float]], first_share: dict[str, str]
) -> tuple[int, int]:
    """写单日份额。返回 (写入行数, 目标标的数)。

    目标数为 0 表示该日无需补(不算失败); 目标数 >0 而写入 0 行 = 远端拉取失败。
    """
    targets = [r["code"] for r in get_by_date(date)] if force else _missing_share_etfs(date)
    targets = _fillable_targets(date, targets, first_share)
    if not targets:
        return 0, 0
    return _write_shares_date(date, prev_shares, targets, prev_window), len(targets)


def _retry_failed_dates(
    progress: ProgressFn,
    failed: list[str],
    force: bool,
    prev_shares: dict,
    prev_window: dict[str, list[float]],
    first_share: dict[str, str],
    progress_base: int,
    progress_total: int,
) -> tuple[int, int, list[str]]:
    """轮末重试"整日拉取失败"的日期(错开时间, 规避持续限流留下的永久缺口)。

    即时重试(SHARES_RETRY)只覆盖秒级抖动; 588200 的 2025-09-26~10-20 共 11 天
    就是三次即时重试全失败后被永久跳过的。返回 (写入行数, 成功天数, 仍失败日期)。
    """
    written = 0
    ok_days = 0
    still = list(failed)
    for p in range(SHARES_RETRY_PASSES):
        if not still:
            break
        progress(progress_base, progress_total, f"重试 {len(still)} 个失败日 (第 {p + 1}/{SHARES_RETRY_PASSES} 轮)")
        time.sleep(SHARES_FAIL_PAUSE_SEC)  # 先给远端喘息, 再重试
        pending: list[str] = []
        for date in still:
            _load_prev_shares(date, prev_shares, prev_window)
            wrote, n_targets = _write_date(date, force, prev_shares, prev_window, first_share)
            if wrote == 0 and n_targets > 0:
                pending.append(date)
            else:
                written += wrote
                ok_days += 1
            time.sleep(BACKFILL_SLEEP_SEC)
        still = pending
    return written, ok_days, still


def job_backfill_shares(
    progress: ProgressFn,
    days: int = DEFAULT_SHARES_BACKFILL_DAYS,
    force: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
) -> dict:
    """回填份额数据(逐日边拉边写, 按 chunk_days 交易日一批上报进度)。

    末尾对"整日拉取失败"的日期做轮末重试(SHARES_RETRY_PASSES), 避免一次限流
    抖动留下永久缺口。
    """
    if start_date:
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        dates = get_trading_dates(start_date, end)
    else:
        dates = get_trading_dates()[-days:]
    if not dates:
        raise RuntimeError("etf_daily 无交易日,请先回填ETF日度数据")
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
        if not force and not missing:
            _load_prev_shares(date, prev_shares, prev_window)
            progress(chunk_idx, total_chunks, f"{date} 已完整 (第 {chunk_idx}/{total_chunks} 批)")
            continue
        targets = _fillable_targets(date, missing, first_share) if not force else [r["code"] for r in get_by_date(date)]
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
        progress, failed, force, prev_shares, prev_window, first_share, total_chunks, total_chunks
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
