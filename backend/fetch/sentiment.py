import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from config import MARGIN_USE_SSE_FALLBACK, TURNOVER_FETCH_SLEEP_SEC


def _date_to_ak(d: str) -> str:
    return d.replace("-", "")


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


def _turnover_row(cur: datetime) -> Optional[dict]:
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


def fetch_market_turnover(start_date: str, end_date: str,
                          on_progress: Optional[Callable[[int, int, str], None]] = None,
                          skip_dates: Optional[set[str]] = None,
                          on_row: Optional[Callable[[dict], None]] = None) -> list[dict]:
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


def _to_float(v) -> float:
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return 0.0


def _fetch_margin_combined() -> list[dict]:
    import akshare as ak
    df = ak.stock_margin_account_info()
    if df is None or df.empty or "融资余额" not in df.columns:
        print(f"[FETCH] margin combined unexpected columns: {list(getattr(df, 'columns', []))}")
        return []
    rows = []
    for _, row in df.iterrows():
        date = str(row["日期"])[:10]
        rows.append({
            "date": date,
            "fin_balance_yi": _to_float(row.get("融资余额")),
            "loan_balance_yi": _to_float(row.get("融券余额")),
            "fin_buy_yi": _to_float(row.get("融资买入额")),
            "source": "combined",
        })
    return sorted(rows, key=lambda r: r["date"])


def _fetch_margin_sse(start_date: str, end_date: str) -> list[dict]:
    import akshare as ak
    df = ak.stock_margin_sse(
        start_date=_date_to_ak(start_date),
        end_date=_date_to_ak(end_date),
    )
    if df is None or df.empty or "融资余额" not in df.columns:
        print(f"[FETCH] margin sse unexpected columns: {list(getattr(df, 'columns', []))}")
        return []
    rows = []
    for _, row in df.iterrows():
        date = str(row["信用交易日期"])[:10]
        rows.append({
            "date": date,
            "fin_balance_yi": _to_float(row.get("融资余额")),
            "loan_balance_yi": _to_float(row.get("融券余量金额")),
            "fin_buy_yi": _to_float(row.get("融资买入额")),
            "source": "sse",
        })
    return sorted(rows, key=lambda r: r["date"])


def fetch_margin_series(start_date: str, end_date: str) -> list[dict]:
    try:
        if MARGIN_USE_SSE_FALLBACK:
            rows = _fetch_margin_sse(start_date, end_date)
        else:
            rows = _fetch_margin_combined()
            rows = [r for r in rows if start_date <= r["date"] <= end_date]
        return rows
    except Exception as e:
        print(f"[FETCH] margin series failed: {e}")
        return []
