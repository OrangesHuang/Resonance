from typing import Optional

_CACHE: Optional[list[str]] = None


def fetch_trade_dates() -> list[str]:
    """返回全部 A 股交易日(YYYY-MM-DD 升序),失败返回空列表。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is None or df.empty or "trade_date" not in df.columns:
            print(f"[FETCH] trade calendar unexpected columns: {list(getattr(df, 'columns', []))}")
            return []
        dates = sorted({str(d)[:10] for d in df["trade_date"]})
        _CACHE = dates
        print(f"[FETCH] trade calendar loaded: {len(dates)} days")
        return dates
    except Exception as e:
        print(f"[FETCH] trade calendar failed: {e}")
        return []
