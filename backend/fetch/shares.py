import time
from typing import Optional
from datetime import datetime, timedelta

from config import ETFS, AKSHARE_TIMEOUT, MAX_RETRY, SHARES_RETRY, SHARES_RETRY_BACKOFF_SEC


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
        import requests
        url = "https://query.sse.com.cn/commonQuery.do"
        params = {
            "isPagination": "true",
            "pageHelp.pageSize": "10000",
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "1",
            "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
            "STAT_DATE": date_str,
        }
        headers = {
            "Referer": "https://www.sse.com.cn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        r = requests.get(url, params=params, headers=headers, timeout=AKSHARE_TIMEOUT)
        rows = r.json().get("result") or []
        if not rows:
            return {}
        result = {}
        for row in rows:
            code = str(row.get("SEC_CODE", ""))
            vol = row.get("TOT_VOL")
            if code and vol is not None:
                result[code] = float(vol) / 1e4
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
    """拉取某日全部监控 ETF 份额; 整日空结果时重试(限流容错)。"""
    for attempt in range(SHARES_RETRY + 1):
        sse = fetch_shares_sse(date_str)
        szse = fetch_shares_szse(date_str)
        merged = {**sse, **szse}
        result = {code: merged[code] for code in ETFS if code in merged}
        if result:
            return result
        if attempt < SHARES_RETRY:
            wait = SHARES_RETRY_BACKOFF_SEC * (attempt + 1)
            print(f"[FETCH] shares {date_str} 空结果, {wait}s 后重试 ({attempt + 1}/{SHARES_RETRY})")
            time.sleep(wait)
    return {}


def _recent_weekdays(date_str: str, max_lookback: int) -> list[str]:
    """date_str 往前回溯的工作日序列(跳过周末, 含最多 max_lookback+1 天)。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    out: list[str] = []
    cur = dt
    while len(out) <= max_lookback:
        if cur.weekday() < 5:
            out.append(cur.strftime("%Y-%m-%d"))
        cur -= timedelta(days=1)
    return out


def fetch_latest_shares(date_str: str, max_lookback: int = 5) -> dict[str, dict]:
    """返回 {code: {"shares_yi": float, "date": str}} 使用最近可用数据(跳过周末)"""
    for check in _recent_weekdays(date_str, max_lookback):
        shares = fetch_shares_for_date(check)
        if shares:
            return {code: {"shares_yi": v, "date": check} for code, v in shares.items()}
    return {}


def calc_share_delta(date_str: str, max_lookback: int = 7) -> dict[str, dict]:
    """计算份额日变化: {code: {"shares_yi", "delta_yi", "delta_pct", "date"}}"""
    today_shares = None
    today_date = None

    for check in _recent_weekdays(date_str, max_lookback):
        shares = fetch_shares_for_date(check)
        if shares:
            today_shares = shares
            today_date = check
            break

    if not today_shares:
        return {}

    prev_shares = None
    for check in _recent_weekdays(today_date, max_lookback)[1:]:
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
