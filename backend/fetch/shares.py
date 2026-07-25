from typing import Optional
from datetime import datetime, timedelta

from config import ETFS, AKSHARE_TIMEOUT, MAX_RETRY


_SSE_CACHE: dict[str, dict[str, float]] = {}
_SZSE_CACHE: dict[str, dict[str, float]] = {}


def _date_to_ak(d: str) -> str:
    return d.replace("-", "")


def _ak_to_date(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def fetch_shares_sse(date_str: str) -> dict[str, float]:
    key = date_str
    if key in _SSE_CACHE:
        return _SSE_CACHE[key]

    try:
        import akshare as ak
        df = ak.fund_etf_scale_sse(date=_date_to_ak(date_str))
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            code = str(row.get("基金代码", ""))
            shares = row.get("基金份额")
            if code and shares is not None:
                result[code] = float(shares) / 1e8
        _SSE_CACHE[key] = result
        return result
    except Exception as e:
        print(f"[FETCH] SSE shares {date_str} failed: {e}")
        return {}


def fetch_shares_szse(date_str: str) -> dict[str, float]:
    key = date_str
    if key in _SZSE_CACHE:
        return _SZSE_CACHE[key]

    try:
        import akshare as ak
        d8 = _date_to_ak(date_str)
        df = ak.fund_scale_daily_szse(start_date=d8, end_date=d8, symbol="ETF")
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            code = str(row.get("基金代码", ""))
            shares = row.get("基金份额")
            if code and shares is not None:
                result[code] = float(shares) / 1e8
        _SZSE_CACHE[key] = result
        return result
    except Exception as e:
        print(f"[FETCH] SZSE shares {date_str} failed: {e}")
        return {}


def fetch_shares_for_date(date_str: str) -> dict[str, float]:
    sse = fetch_shares_sse(date_str)
    szse = fetch_shares_szse(date_str)
    merged = {**sse, **szse}
    return {code: merged[code] for code in ETFS if code in merged}


def fetch_latest_shares(date_str: str, max_lookback: int = 5) -> dict[str, dict]:
    """返回 {code: {"shares_yi": float, "date": str}} 使用最近可用数据"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    for offset in range(max_lookback + 1):
        check_date = (dt - timedelta(days=offset)).strftime("%Y-%m-%d")
        shares = fetch_shares_for_date(check_date)
        if shares:
            return {code: {"shares_yi": v, "date": check_date} for code, v in shares.items()}
    return {}


def calc_share_delta(date_str: str, max_lookback: int = 7) -> dict[str, dict]:
    """计算份额日变化: {code: {"shares_yi", "delta_yi", "delta_pct", "date"}}"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    today_shares = None
    today_date = None

    for offset in range(max_lookback + 1):
        check = (dt - timedelta(days=offset)).strftime("%Y-%m-%d")
        shares = fetch_shares_for_date(check)
        if shares:
            today_shares = shares
            today_date = check
            break

    if not today_shares:
        return {}

    prev_shares = None
    prev_dt = datetime.strptime(today_date, "%Y-%m-%d")
    for offset in range(1, max_lookback + 1):
        check = (prev_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
        shares = fetch_shares_for_date(check)
        if shares:
            prev_shares = shares
            break

    result = {}
    for code, shares_yi in today_shares.items():
        delta_yi = None
        delta_pct = None
        if prev_shares and code in prev_shares and prev_shares[code] > 0:
            delta_yi = round(shares_yi - prev_shares[code], 4)
            delta_pct = round(delta_yi / prev_shares[code] * 100, 3)
        result[code] = {
            "shares_yi": round(shares_yi, 4),
            "delta_yi": delta_yi,
            "delta_pct": delta_pct,
            "date": today_date,
        }
    return result
