from datetime import datetime, timedelta

from config import MARGIN_USE_SSE_FALLBACK


_TURNOVER_CACHE: dict[str, list[dict]] = {}
_MARGIN_CACHE: dict[str, list[dict]] = {}


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


def fetch_market_turnover(start_date: str, end_date: str) -> list[dict]:
    key = f"{start_date}_{end_date}"
    if key in _TURNOVER_CACHE:
        return _TURNOVER_CACHE[key]

    rows = []
    try:
        cur = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        while cur <= end:
            if cur.weekday() < 5:
                d8 = cur.strftime("%Y%m%d")
                sh = _sse_turnover_yi(d8)
                sz = _szse_turnover_yi(d8)
                if sh is not None or sz is not None:
                    sh_yi = sh or 0.0
                    sz_yi = sz or 0.0
                    rows.append({
                        "date": cur.strftime("%Y-%m-%d"),
                        "sh_amount_yi": sh_yi,
                        "sz_amount_yi": sz_yi,
                        "total_amount_yi": round(sh_yi + sz_yi, 2),
                    })
            cur += timedelta(days=1)
        _TURNOVER_CACHE[key] = rows
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
    key = "sse" if MARGIN_USE_SSE_FALLBACK else "combined"
    if key in _MARGIN_CACHE:
        return _MARGIN_CACHE[key]

    try:
        if MARGIN_USE_SSE_FALLBACK:
            rows = _fetch_margin_sse(start_date, end_date)
        else:
            rows = _fetch_margin_combined()
            rows = [r for r in rows if start_date <= r["date"] <= end_date]
        _MARGIN_CACHE[key] = rows
        return rows
    except Exception as e:
        print(f"[FETCH] margin series failed: {e}")
        return []
