from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from base.config import ETFS
from base.scheduler.daily_tasks import task_manual_refresh
from base.store.calendar_repo import get_safe_cache_end
from base.store.daily_repo import get_by_code
from base.store.realtime_repo import get_today_snapshots

router = APIRouter(prefix="/api/etf", tags=["etf"])


@router.post("/refresh")
def etf_refresh():
    result = task_manual_refresh()
    if result.get("status") == "skipped":
        return result
    return {
        "status": "ok",
        "count": result["count"],
        "date": result["date"],
    }


@router.get("/list")
def etf_list():
    return [{"code": code, "name": info["name"], "idx": info["idx"]} for code, info in ETFS.items()]


@router.get("/{code}/history")
def etf_history(
    code: str,
    days: int = Query(default=640, ge=1, le=3200),
    since: str | None = Query(default=None, description="增量起点(不含此日): 前端缓存末尾日期"),
):
    if code not in ETFS:
        return {"error": f"unknown ETF code: {code}"}

    daily_records = get_by_code(code)
    # ma250 必须基于全量计算, 增量请求只过滤输出, 不截断计算窗口
    kline = _build_kline_from_db(daily_records, days)
    if since:
        kline = [k for k in kline if k["date"] > since]
        daily_records = [r for r in daily_records[:days] if r["date"] > since]

    return {
        "code": code,
        "name": ETFS[code]["name"],
        "idx": ETFS[code]["idx"],
        "kline": kline,
        "daily_signals": daily_records[:days],
        "safe_end": get_safe_cache_end(datetime.now().strftime("%Y-%m-%d")),
    }


def _build_kline_from_db(records: list[dict], limit: int) -> list[dict]:
    """从 etf_daily 表构建 K 线数据，不调外部 API。

    优先用真实 OHLC(open/high/low 已入库的), 否则退回重构。
    附 ma250 序列(实时计算, 不持久化 — 派生数据入库会带来口径漂移风险,
    任何历史回填/修复都会使其后全部 ma250 失效)。
    """
    recent = records[:limit][::-1]  # DESC → ASC
    result = []
    closes_all = [r.get("close_price") or 0 for r in recent]
    for i, r in enumerate(recent):
        close = r.get("close_price")
        if close is None or close == 0:
            continue
        op = r.get("open_price")
        hi = r.get("high_price")
        lo = r.get("low_price")
        if op is None or hi is None or lo is None:
            # 无真实OHLC: 从收盘价和涨跌幅反推
            chg = r.get("change_pct")
            if chg is not None and chg != 0:
                op = round(close / (1 + chg / 100), 3)
            else:
                op = close
            hi = round(max(op, close), 3)
            lo = round(min(op, close), 3)
        # ma250: 前250日收盘均值(实时计算)
        ma250 = None
        if i >= 249:
            ma250 = round(sum(closes_all[i - 249 : i + 1]) / 250, 4)
        result.append(
            {
                "date": r["date"],
                "open": op,
                "close": close,
                "high": hi,
                "low": lo,
                "volume": r.get("volume") or 0,
                "ma250": ma250,
            }
        )
    return result


@router.get("/{code}/intraday")
def etf_intraday(code: str, date: str = Query(default=None)):
    if code not in ETFS:
        return {"error": f"unknown ETF code: {code}"}

    snapshots = get_today_snapshots(code=code, date_str=date)
    return {
        "code": code,
        "name": ETFS[code]["name"],
        "snapshots": snapshots,
    }
