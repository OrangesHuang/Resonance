"""涨跌家数(市场广度)数据获取 — 来自乐咕乐股。

仅返回当日快照；历史数据通过每日定时采集累积。
"""

from typing import Optional, Callable


def _parse_activity(df) -> Optional[dict]:
    """解析 stock_market_activity_legu() 的返回值。

    返回 {"date": str, "advances": int, "declines": int,
          "advance_pct": float, "limit_ups": int, "limit_downs": int}
    """
    try:
        data = {}
        for _, row in df.iterrows():
            item = str(row.get("item", ""))
            value = row.get("value", "")
            if item == "上涨":
                data["advances"] = int(value)
            elif item == "下跌":
                data["declines"] = int(value)
            elif item == "涨停":
                data["limit_ups"] = int(value)
            elif item == "跌停":
                data["limit_downs"] = int(value)
            elif item == "统计日期":
                data["date"] = str(value)[:10]

        if "advances" not in data or "declines" not in data:
            return None

        total = data["advances"] + data["declines"]
        data["advance_pct"] = round(data["advances"] / total * 100, 2) if total > 0 else 50.0
        data.setdefault("date", "")
        data.setdefault("limit_ups", 0)
        data.setdefault("limit_downs", 0)
        return data
    except Exception:
        return None


def fetch_market_breadth(
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> Optional[dict]:
    """获取当日全市场涨跌家数快照。

    Returns:
        单日广度数据 dict，失败返回 None
    """
    try:
        import akshare as ak
        df = ak.stock_market_activity_legu()
        if df is None or df.empty:
            print("[FETCH] breadth: empty response from stock_market_activity_legu")
            return None
        if on_progress:
            on_progress(1, 1, "breadth")
        return _parse_activity(df)
    except Exception as e:
        print(f"[FETCH] breadth failed: {e}")
        return None
