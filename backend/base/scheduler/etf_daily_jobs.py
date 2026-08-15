"""ETF 日度数据回填(可导入、带进度上报): 渐进式分批拉取。

- 腾讯 K线接口单次 limit 上限约 640 根, 补 2021 等更早历史必须走日期区间
  (KLINE_URL_RANGE + fetch_kline(start_date/end_date)), 起点前自动取
  SEED_MIN_BARS 根做滚动窗口暖机;
- 区间完整覆盖才跳过(_range_covered, 后向扩展免强制重拉), 逐日跳过已入库
  日期, 重跑只补缺失段; 每 chunk_days 个交易日一批上报进度("第 N/M 批")。

被 job_registry.py 注册为后台任务, 同时被 scripts/seed_db.py 复用。
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta

from base.config import (
    DEFAULT_CHUNK_DAYS,
    DEFAULT_ETF_SEED_DAYS,
    ETFS,
    FETCH_SLEEP_SEC,
    SEED_MIN_BARS,
)
from base.fetch.kline import fetch_index_kline, fetch_kline
from base.scheduler.calendar_slots import job_refresh_calendar_slots
from base.scheduler.job_manager import ProgressFn
from base.store.calendar_repo import get_last_trading_day, get_trade_days
from base.store.daily_repo import get_by_code, get_latest_date_for, upsert_daily
from resonance.analysis.composite import analyze_single_etf


def _trading_days_between(start: str, end: str) -> int:
    """估算 [start, end] 区间交易日数(优先交易日历,缺省按自然日 1.5 倍估算)。"""
    days = get_trade_days(start, end)
    if days:
        return len(days)
    delta = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days
    return max(1, int(delta * 1.5) + 1)


def _warmup_start(start_date: str, warmup_days: int = SEED_MIN_BARS) -> str:
    """回填起点往前推 warmup_days 个交易日(按自然日 1.5 倍估算)。

    目的: K线滚动窗口(量能 MA20/价格位置 60 日)需要起点之前的K线做暖机,
    否则回填区间最前面的日期窗口不完整、指标失真。
    """
    return (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=int(warmup_days * 1.5) + 5)).strftime("%Y-%m-%d")


def _missing_etf_ranges(code: str) -> list[tuple[str, str]]:
    """该 ETF 在自身数据区间内缺失的交易日区间(以交易日历为"填充槽"定义)。

    返回 [(gap_start, gap_end), ...], 无缺失返回 []。缺口成因: 区间拉取被
    接口单次上限截断、任务中断、单日拉取失败等 — 交易日历能明确"哪天
    应该有数据"这件事, 缺口一目了然。
    """
    rows = get_by_code(code)
    if not rows:
        return []
    dates = {r["date"] for r in rows}
    lo, hi = min(dates), max(dates)
    runs: list[list[str]] = []
    cur: list[str] = []
    for d in get_trade_days(lo, hi):
        if d in dates:
            if cur:
                runs.append(cur)
                cur = []
        else:
            cur.append(d)
    if cur:
        runs.append(cur)
    return [(r[0], r[-1]) for r in runs]


def _range_covered(code: str, start: str, end: str | None) -> bool:
    """请求区间 [start, end] 是否已全部入库(以交易日历为准)。

    后向扩展(如补 2021 历史)用: 原跳过逻辑只检查"最新日期 >= 结束日",
    对往前补的区间会误判为已最新而跳过; 改为区间完整覆盖才跳过,
    缺任意一天都进入回填(配合逐日跳过只补缺失段, 免强制重拉)。
    """
    end = end or datetime.now().strftime("%Y-%m-%d")
    expected = set(get_trade_days(start, end))
    if not expected:
        return False
    existing = {r["date"] for r in get_by_code(code, start, end)}
    return expected.issubset(existing)


def _seed_one_etf(
    code: str,
    idx_kline: list[dict],
    days: int,
    end: str | None = None,
    start_date: str | None = None,
    fetch_start: str | None = None,
    force: bool = False,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
    progress: ProgressFn | None = None,
    chunk_base: int = 0,
    chunk_total: int = 1,
) -> tuple[int, int]:
    """拉取单只 ETF 日K并逐日分析入库(渐进式)。

    - 已入库日期直接跳过(不 force 时): 后向扩展重跑只补缺失段, 成本随补全递减;
    - 每 chunk_days 个交易日上报一次进度("第 N/M 批");
    - 返回 (写入行数, 本 ETF 批次数)。
    """
    kline = fetch_kline(code, limit=days, start_date=fetch_start, end_date=end)
    if len(kline) < SEED_MIN_BARS:
        return 0, 0
    existing: set[str] = set()
    if not force:
        existing = {r["date"] for r in get_by_code(code)}
    count = 0
    span = len(kline) - SEED_MIN_BARS + 1
    chunk_n = max(1, math.ceil(span / chunk_days))
    cur_chunk = -1
    for i in range(SEED_MIN_BARS - 1, len(kline)):
        d = kline[i]["date"]
        if not force:
            if d in existing:
                continue
            if start_date and d < start_date:
                continue
            if end and d > end:
                continue
        result = analyze_single_etf(
            kline=kline[: i + 1],
            idx_kline=idx_kline[: i + 1],
            shares_delta_pct=None,
            target_idx=i,
        )
        if result:
            if end and result["date"] > end:
                continue
            if start_date and result["date"] < start_date:
                continue
            upsert_daily(result["date"], code, result)
            count += 1
        ci = (i - (SEED_MIN_BARS - 1)) // chunk_days
        if progress and ci != cur_chunk:
            cur_chunk = ci
            progress(chunk_base + min(ci, chunk_n - 1), chunk_total, f"{code} 第 {ci + 1}/{chunk_n} 批 · {d}")
    return count, chunk_n


def job_backfill_missing_etf_daily(progress: ProgressFn, chunk_days: int = DEFAULT_CHUNK_DAYS) -> dict:
    """补全全历史缺失 ETF 日度: 以交易日历为填充槽, 扫描各 ETF 自身数据区间
    内的缺失交易日, 对缺口整体范围复用区间回填(逐日跳过只补缺失段)。

    与 backfill_missing_shares 对应, 处理接口截断/任务中断/单日失败遗留的
    缺口; 无需日期参数, 自动定位。
    """
    codes = list(ETFS.items())
    gaps: list[tuple[str, str]] = []
    for i, (code, info) in enumerate(codes, 1):
        rs = _missing_etf_ranges(code)
        if rs:
            gaps.extend(rs)
            progress(i, len(codes), f"{code} {info['name']} 缺失 {len(rs)} 段")
        else:
            progress(i, len(codes), f"{code} 无缺失")
    if not gaps:
        progress(len(codes), len(codes), "ETF日度无缺失")
        return {"gaps": 0, "records": 0}
    lo = min(g[0] for g in gaps)
    hi = max(g[1] for g in gaps)
    progress(len(codes), len(codes), f"回填缺口 {lo} ~ {hi}")
    result = job_backfill_etf_daily(progress, start_date=lo, end_date=hi, chunk_days=chunk_days)
    return {"gaps": len(gaps), "range": [lo, hi], **result}


def job_backfill_etf_daily(
    progress: ProgressFn,
    days: int = DEFAULT_ETF_SEED_DAYS,
    start_date: str | None = None,
    end_date: str | None = None,
    force: bool = False,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
) -> dict:
    """回填 ETF 日度数据(渐进式分批)。

    带 start_date 时按 [start_date, end] 区间拉取(腾讯接口支持日期区间,
    单次 limit 上限约 640 根, 更早历史必须走日期区间), 起点前自动取
    SEED_MIN_BARS 根做滚动窗口暖机; 每 chunk_days 个交易日一批上报进度,
    中断后重跑只补缺失段(区间覆盖 + 逐日跳过), 无需强制重拉。
    """
    if start_date:
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        fetch_start = _warmup_start(start_date)
        expected_days = _trading_days_between(fetch_start, end) + SEED_MIN_BARS
        range_days = _trading_days_between(start_date, end)
    else:
        end = None
        fetch_start = None
        expected_days = days
        range_days = days
    target = end or get_last_trading_day(datetime.now().strftime("%Y-%m-%d"))
    progress(0, len(ETFS), "拉取指数K线…")
    idx_kline = fetch_index_kline(limit=expected_days, start_date=fetch_start, end_date=end)
    if not idx_kline:
        raise RuntimeError("无法拉取指数K线,终止回填")
    codes = list(ETFS.items())
    per_etf_chunks = max(1, math.ceil(range_days / chunk_days))
    total_chunks = per_etf_chunks * len(codes)
    processed_chunks = 0
    total_records = 0
    skipped = 0
    for code, info in codes:
        latest = get_latest_date_for(code)
        # 区间覆盖判断(后向扩展): 请求区间已完整入库才跳过, 不再只看最新日期
        if not force and start_date and _range_covered(code, start_date, end):
            skipped += 1
            processed_chunks += per_etf_chunks
            progress(processed_chunks, total_chunks, f"{code} {info['name']} 区间已完整覆盖")
            continue
        # 无日期参数时保持原逻辑: 最新日期已到目标日则跳过
        if not force and not start_date and latest and latest >= target:
            skipped += 1
            processed_chunks += per_etf_chunks
            progress(processed_chunks, total_chunks, f"{code} {info['name']} 已是最新({latest})")
            continue
        progress(processed_chunks, total_chunks, f"{code} {info['name']}")
        cnt, n_chunks = _seed_one_etf(
            code,
            idx_kline,
            expected_days,
            end,
            start_date,
            fetch_start,
            force,
            chunk_days,
            progress,
            processed_chunks,
            total_chunks,
        )
        processed_chunks += max(n_chunks, 1)
        total_records += cnt
        time.sleep(FETCH_SLEEP_SEC)
    progress(total_chunks, total_chunks, f"完成 {total_records} 行 (跳过 {skipped} 只)")
    # 回填后刷新日历槽位台账(交易日历即填充槽, 保持覆盖属性新鲜)
    job_refresh_calendar_slots(progress)
    return {
        "etfs": len(codes),
        "records": total_records,
        "skipped": skipped,
        "days": expected_days,
        "chunks": total_chunks,
    }
