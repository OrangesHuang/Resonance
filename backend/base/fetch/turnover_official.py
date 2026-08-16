"""两市成交额逐日官方源兜底(上交所/深交所官网 via akshare)。

SSE 官方接口对 2021 返回空列表(akshare stock_sse_deal_daily 报
Length mismatch), 2022 起稳定; 作为东财/雪球批量源的最后一层兜底,
逐日边拉边写, 单日失败静默跳过(下次重跑自动补)。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta

from base.config import TURNOVER_FETCH_SLEEP_SEC


def _sse_turnover_yi(d8: str):
    try:
        import akshare as ak

        df = ak.stock_sse_deal_daily(date=d8)
        row = df[df["单日情况"] == "成交金额"]
        if row.empty:
            return None
        return round(float(row["股票"].iloc[0]), 2)
    except Exception:
        return None


def _szse_turnover_yi(d8: str):
    try:
        import akshare as ak

        df = ak.stock_szse_summary(date=d8)
        row = df[df["证券类别"] == "股票"]
        if row.empty:
            return None
        return round(float(row["成交金额"].iloc[0]) / 1e8, 2)
    except Exception:
        return None


def _weekday_dates(start_date: str, end_date: str) -> list[datetime]:
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    out: list[datetime] = []
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def _turnover_row(cur: datetime) -> dict | None:
    d8 = cur.strftime("%Y%m%d")
    sh = _sse_turnover_yi(d8)
    sz = _szse_turnover_yi(d8)
    if not sh or not sz:
        return None
    return {
        "date": cur.strftime("%Y-%m-%d"),
        "sh_amount_yi": sh,
        "sz_amount_yi": sz,
        "total_amount_yi": round(sh + sz, 2),
    }


def fetch_market_turnover(
    start_date: str,
    end_date: str,
    on_progress: Callable[[int, int, str], None] | None = None,
    skip_dates: set[str] | None = None,
    on_row: Callable[[dict], None] | None = None,
) -> list[dict]:
    """逐日拉取成交额; on_row 每次拉到一天立即回调(便于边拉边写库)。"""
    days = _weekday_dates(start_date, end_date)
    skip_dates = skip_dates or set()
    rows = []
    try:
        for i, cur in enumerate(days, 1):
            ds = cur.strftime("%Y-%m-%d")
            if on_progress:
                on_progress(i, len(days), ds)
            if ds in skip_dates:
                continue
            row = _turnover_row(cur)
            if row:
                rows.append(row)
                if on_row:
                    on_row(row)
            time.sleep(TURNOVER_FETCH_SLEEP_SEC)
        return rows
    except Exception as e:
        print(f"[FETCH] market turnover failed: {e}")
        return rows
