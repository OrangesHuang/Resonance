"""单只 ETF 的初始化/增量回填(五阶段编排, 供动态添加后的首次拉取)。

阶段与权重: K线 55 → 份额 25 → 折算修正 8 → 综合概率重算 12 → 日历槽位刷新。
全部复用现成积木(不改各阶段算法):
  - _seed_one_etf          单标的K线逐日入库(etf_daily_jobs)
  - job_backfill_shares    codes=[code] 显式标的模式(绕过上市前过滤)
  - job_fix_share_splits   codes=[code] 折算修正
  - job_recalc_composite   codes=[code] 把份额层折进 composite_prob
份额阶段区间收窄到该 code 在 etf_daily 的首/末行日期, 避免对其未上市日期空拉。
"""

from __future__ import annotations

import math
from datetime import datetime

from base.config import DEFAULT_CHUNK_DAYS, DEFAULT_ETF_SEED_DAYS, SEED_MIN_BARS
from base.fetch.kline import fetch_index_kline
from base.scheduler.calendar_slots import job_refresh_calendar_slots
from base.scheduler.etf_daily_jobs import _seed_one_etf, _trading_days_between, _warmup_start
from base.scheduler.job_manager import ProgressFn
from base.scheduler.recalc import job_recalc_composite
from base.scheduler.share_adjust_jobs import job_fix_share_splits
from base.scheduler.shares_jobs import job_backfill_shares
from base.store.daily_repo import get_by_code

_TOTAL = 100
_W_KLINE, _W_SHARES, _W_SPLIT, _W_RECALC = 55, 25, 8, 12


def _stage(progress: ProgressFn, base: int, span: int) -> ProgressFn:
    """把子任务进度按比例映射到总进度的 [base, base+span] 区间。"""

    def cb(current: int, total: int, message: str) -> None:
        frac = current / total if total else 0.0
        progress(base + round(frac * span), _TOTAL, message)

    return cb


def job_backfill_etf(
    progress: ProgressFn,
    code: str = "",
    days: int = DEFAULT_ETF_SEED_DAYS,
    start_date: str | None = None,
    end_date: str | None = None,
    force: bool = False,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
) -> dict:
    """按标的初始化回填: K线 → 份额 → 折算修正 → 综合概率重算 → 刷新槽位。

    days 仅在不传 start_date 时作回看窗口(与全量回填一致); start_date 时
    自动前推 SEED_MIN_BARS 根 K线做滚动窗口暖机。
    """
    if not code:
        raise ValueError("缺少 code 参数")
    end: str | None = end_date
    if start_date:
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        fetch_start = _warmup_start(start_date)
        expected_days = _trading_days_between(fetch_start, end) + SEED_MIN_BARS
    else:
        fetch_start = None
        expected_days = days

    progress(0, _TOTAL, "拉取指数K线…")
    idx_kline = fetch_index_kline(limit=expected_days, start_date=fetch_start, end_date=end)
    if not idx_kline:
        raise RuntimeError("无法拉取指数K线,终止回填")

    progress(0, _TOTAL, f"{code} 拉取日K…")
    est_chunks = max(1, math.ceil((expected_days - SEED_MIN_BARS + 1) / chunk_days))
    etf_rows, _ = _seed_one_etf(
        code,
        idx_kline,
        days=expected_days,
        end=end,
        start_date=start_date,
        fetch_start=fetch_start,
        force=force,
        chunk_days=chunk_days,
        progress=_stage(progress, 0, _W_KLINE),
        chunk_base=0,
        chunk_total=est_chunks,
    )

    rows = get_by_code(code)  # DESC
    if not rows:
        progress(_TOTAL, _TOTAL, f"{code} 无可用K线(上市不足{SEED_MIN_BARS}根或接口失败), 跳过后续阶段")
        return {"code": code, "etf_rows": 0, "shares_written": 0, "split_fixed": 0, "recalc_updated": 0}

    dates = [r["date"] for r in rows]
    seed_start = start_date if start_date and start_date > min(dates) else min(dates)
    seed_end = end or max(dates)

    shares_res = job_backfill_shares(
        _stage(progress, _W_KLINE, _W_SHARES),
        start_date=seed_start,
        end_date=seed_end,
        force=force,
        chunk_days=chunk_days,
        codes=[code],
    )
    splits_res = job_fix_share_splits(_stage(progress, _W_KLINE + _W_SHARES, _W_SPLIT), codes=[code])
    recalc_res = job_recalc_composite(_stage(progress, _W_KLINE + _W_SHARES + _W_SPLIT, _W_RECALC), codes=[code])
    job_refresh_calendar_slots(_stage(progress, _TOTAL - 1, 1))

    progress(
        _TOTAL,
        _TOTAL,
        f"{code} 完成: 日度 {etf_rows} 行 · 份额 {shares_res['written']} 行 · "
        f"折算 {len(splits_res['fixed'])} 起 · 重算 {recalc_res['updated']} 行",
    )
    return {
        "code": code,
        "etf_rows": etf_rows,
        "shares_written": shares_res["written"],
        "split_fixed": len(splits_res["fixed"]),
        "recalc_updated": recalc_res["updated"],
        "range": [seed_start, seed_end],
    }
