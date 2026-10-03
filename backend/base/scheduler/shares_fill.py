"""份额逐日写入的底层核心(被 shares_jobs 的「区间回填」与「缺失补全」共用)。

职责: 给定日期/目标标的, 拉取当日全市场份额 → 计算 delta 与份额概率 →
写入 etf_daily; 以及失败日的轮末重试。上市前过滤与单标的模式见各函数注释。
"""

from __future__ import annotations

import time

from base.config import (
    BACKFILL_SLEEP_SEC,
    ETFS,
    SHARE_WINDOW,
    SHARES_FAIL_PAUSE_SEC,
    SHARES_RETRY_PASSES,
)
from base.fetch.shares import fetch_shares_for_date
from base.scheduler.job_manager import ProgressFn
from base.store.daily_repo import get_by_date, update_share_data
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
    date: str,
    force: bool,
    prev_shares: dict,
    prev_window: dict[str, list[float]],
    first_share: dict[str, str],
    codes: list[str] | None = None,
) -> tuple[int, int]:
    """写单日份额。返回 (写入行数, 目标标的数)。

    目标数为 0 表示该日无需补(不算失败); 目标数 >0 而写入 0 行 = 远端拉取失败。
    codes 显式指定时只补这些标的, 且跳过"上市前"过滤(调用方已把区间收窄到
    该标的存在区间; 新标的尚无 first_share, 走该过滤会永远补不进第一笔)。
    """
    targets = [r["code"] for r in get_by_date(date)] if force else _missing_share_etfs(date)
    if codes is not None:
        allow = set(codes)
        targets = [c for c in targets if c in allow]
    else:
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
    codes: list[str] | None = None,
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
            wrote, n_targets = _write_date(date, force, prev_shares, prev_window, first_share, codes)
            if wrote == 0 and n_targets > 0:
                pending.append(date)
            else:
                written += wrote
                ok_days += 1
            time.sleep(BACKFILL_SLEEP_SEC)
        still = pending
    return written, ok_days, still
