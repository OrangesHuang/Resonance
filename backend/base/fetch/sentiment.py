from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta

import requests

from base.config import (
    EM_FETCH_RETRIES,
    EM_FETCH_RETRY_SLEEP,
    EM_FETCH_TIMEOUT,
    EM_INDEX_SH_SECID,
    EM_INDEX_SZ_SECID,
    EM_KLINE_URL,
    EM_UT,
    MARGIN_USE_SSE_FALLBACK,
    TURNOVER_FETCH_SLEEP_SEC,
    XQ_FETCH_TIMEOUT,
    XQ_HQ_URL,
    XQ_INDEX_SH,
    XQ_INDEX_SZ,
    XQ_KLINE_URL,
)


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


def _em_index_kline(secid: str, start_date: str, end_date: str) -> dict[str, float]:
    """东财指数日线成交额(元→亿): 一次请求返回区间内全部交易日。

    返回 {date: amount_yi}。指数口径: 上证综指/深证综指成交额与交易所
    官方"全市场成交金额"误差 <0.4% (2022-03-01 对照: 上交所 4125.6 vs
    4139.9 亿; 深交所 5565.0 vs 5576.2 亿), 且 2021 全年完整可得 —
    SSE 官方接口对 2021 返回空列表(akshare stock_sse_deal_daily 报
    Length mismatch), 这是补 2021 两市成交额的关键源之一。
    """
    params = {
        "secid": secid,
        "klt": "101",  # 日线
        "fqt": "0",
        "beg": _date_to_ak(start_date),
        "end": _date_to_ak(end_date),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": EM_UT,
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
    data = None
    for attempt in range(EM_FETCH_RETRIES):
        try:
            r = requests.get(EM_KLINE_URL, params=params, headers=headers, timeout=EM_FETCH_TIMEOUT)
            data = r.json().get("data") or {}
            if data.get("klines"):
                break
        except Exception as e:
            print(f"[FETCH] em index {secid} attempt{attempt + 1} failed: {e}")
            time.sleep(EM_FETCH_RETRY_SLEEP * (attempt + 1))
    out: dict[str, float] = {}
    for line in (data or {}).get("klines") or []:
        parts = line.split(",")
        # kline 格式: 日期,开,收,高,低,量,额(元),振幅,涨跌幅,涨跌额,换手
        if len(parts) > 6:
            out[parts[0]] = round(float(parts[6]) / 1e8, 2)
    return out


def _em_batch(start_date: str, end_date: str) -> list[dict]:
    """东财两市成交额区间(一次请求全批)。"""
    sh = _em_index_kline(EM_INDEX_SH_SECID, start_date, end_date)
    sz = _em_index_kline(EM_INDEX_SZ_SECID, start_date, end_date)
    if not sh or not sz:
        return []
    out: list[dict] = []
    for d in sorted(set(sh) & set(sz)):
        sh_v, sz_v = sh[d], sz[d]
        out.append(
            {
                "date": d,
                "sh_amount_yi": sh_v,
                "sz_amount_yi": sz_v,
                "total_amount_yi": round(sh_v + sz_v, 2),
            }
        )
    return out


_xq_session: requests.Session | None = None


def _xq_klines(symbol: str, end_date: str, count: int = 600) -> dict[str, float]:
    """雪球指数日K成交额(元→亿): 从 end_date 往前翻 count 条。

    雪球 kline 的 begin 是"往前数"的时间戳: 传区间末时间戳, 返回其
    之前的交易日(含 amount 成交额列)。与东财交叉验证一致(2021-03-01
    上证 4024.77 亿两源完全相同)。
    """
    global _xq_session
    if _xq_session is None:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
        )
        s.get(XQ_HQ_URL, timeout=XQ_FETCH_TIMEOUT)  # 拿 xq_a_token cookie
        _xq_session = s
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
    params = {
        "symbol": symbol,
        "begin": str(end_ts),
        "period": "day",
        "type": "before",
        "count": str(-count),
        "indicator": "kline",
    }
    try:
        j = _xq_session.get(XQ_KLINE_URL, params=params, timeout=XQ_FETCH_TIMEOUT).json()
    except Exception as e:
        print(f"[FETCH] xq kline failed: {e}")
        return {}
    data = j.get("data") or {}
    cols = data.get("column") or []
    if "amount" not in cols:
        return {}
    ai = cols.index("amount")
    out: dict[str, float] = {}
    for it in data.get("item") or []:
        d = datetime.fromtimestamp(it[0] / 1000).astimezone().strftime("%Y-%m-%d")
        if it[ai]:
            out[d] = round(float(it[ai]) / 1e8, 2)
    return out


def _xq_turnover_range(start_date: str, end_date: str) -> list[dict]:
    """雪球两市成交额区间(一次请求约 600 条, 覆盖 chunk 区间)。"""
    sh = _xq_klines(XQ_INDEX_SH, end_date)
    sz = _xq_klines(XQ_INDEX_SZ, end_date)
    if not sh or not sz:
        return []
    out: list[dict] = []
    for d in sorted(set(sh) & set(sz)):
        if not (start_date <= d <= end_date):
            continue
        sh_v, sz_v = sh[d], sz[d]
        out.append(
            {
                "date": d,
                "sh_amount_yi": sh_v,
                "sz_amount_yi": sz_v,
                "total_amount_yi": round(sh_v + sz_v, 2),
            }
        )
    return out


def fetch_turnover_range(start_date: str, end_date: str) -> list[dict]:
    """两市成交额区间批量拉取: 东财优先, 雪球回退(2021 起全历史)。

    上交所=上证综指成交额, 深交所=深证综指成交额; 两指数都有的日期才
    入库。东财接口偶发限流(push2his 连接失败), 雪球带 cookie 独立源,
    两源交叉验证一致, 保证补 2021 稳定可用。
    """
    rows = _em_batch(start_date, end_date)
    if rows:
        return rows
    try:
        return _xq_turnover_range(start_date, end_date)
    except Exception as e:
        print(f"[FETCH] xq turnover range failed: {e}")
        return []


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
        rows.append(
            {
                "date": date,
                "fin_balance_yi": _to_float(row.get("融资余额")),
                "loan_balance_yi": _to_float(row.get("融券余额")),
                "fin_buy_yi": _to_float(row.get("融资买入额")),
                "source": "combined",
            }
        )
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
        rows.append(
            {
                "date": date,
                "fin_balance_yi": _to_float(row.get("融资余额")),
                "loan_balance_yi": _to_float(row.get("融券余量金额")),
                "fin_buy_yi": _to_float(row.get("融资买入额")),
                "source": "sse",
            }
        )
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
