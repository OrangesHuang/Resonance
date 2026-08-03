from datetime import datetime, timedelta
from typing import Optional

from store.database import get_connection

_trade_dates: Optional[set[str]] = None


def get_last_trading_day(date: str) -> str:
    """date 及之前最后一个交易日(日历缺失时按周末回退)。"""
    days = get_trade_days(None, date)
    if days:
        return days[-1]
    d = datetime.strptime(date, "%Y-%m-%d")
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def upsert_trade_dates(dates: list[str]) -> None:
    if not dates:
        return
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT INTO trade_calendar(date) VALUES(?) ON CONFLICT(date) DO NOTHING",
            [(d,) for d in dates],
        )
        conn.commit()
    finally:
        conn.close()


def get_calendar_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM trade_calendar").fetchone()["c"]
    finally:
        conn.close()


def get_trade_days(start: Optional[str] = None, end: Optional[str] = None) -> list[str]:
    conn = get_connection()
    try:
        sql = "SELECT date FROM trade_calendar"
        clauses: list[str] = []
        params: list[str] = []
        if start:
            clauses.append("date >= ?")
            params.append(start)
        if end:
            clauses.append("date <= ?")
            params.append(end)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY date ASC"
        rows = conn.execute(sql, params).fetchall()
        return [r["date"] for r in rows]
    finally:
        conn.close()


def get_range() -> list[Optional[str]]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MIN(date) AS lo, MAX(date) AS hi FROM trade_calendar").fetchone()
        return [row["lo"], row["hi"]]
    finally:
        conn.close()


def get_last_sync() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(created_at) AS t FROM trade_calendar").fetchone()
        return row["t"] if row else None
    finally:
        conn.close()


def reload_cache() -> None:
    global _trade_dates
    conn = get_connection()
    try:
        rows = conn.execute("SELECT date FROM trade_calendar").fetchall()
        _trade_dates = {r["date"] for r in rows}
    finally:
        conn.close()


def is_trading_day(date: str) -> bool:
    days = _trade_dates
    if days is None:
        reload_cache()
        days = _trade_dates
    if not days:
        return datetime.strptime(date, "%Y-%m-%d").weekday() < 5
    return date in days
