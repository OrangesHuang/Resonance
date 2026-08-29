from __future__ import annotations

from datetime import datetime, timedelta

from base.config import CACHE_BUFFER_DAYS, CACHE_END_SENTINEL
from base.store.database import get_connection

_trade_dates: set[str] | None = None


def get_last_trading_day(date: str) -> str:
    """date 及之前最后一个交易日(日历缺失时按周末回退)。"""
    days = get_trade_days(None, date)
    if days:
        return days[-1]
    d = datetime.strptime(date, "%Y-%m-%d")
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def get_safe_cache_end(date: str, buffer_days: int = CACHE_BUFFER_DAYS) -> str:
    """前端缓存安全截止日: 最新已收盘交易日往前 buffer_days 个交易日。

    最近 buffer_days 个交易日数据可能被修正(T+1 份额/复权/数据源), 不进
    前端缓存、每次从接口热拉; 更早历史不可变可安全缓存。增量接口
    since 参数即此值。交易日不足 buffer_days 时返回哨兵(增量起点=全量)。
    """
    settled = get_last_trading_day(date)
    days = get_trade_days(None, settled)
    if not days:
        return CACHE_END_SENTINEL
    if len(days) <= buffer_days:
        return CACHE_END_SENTINEL
    return days[-buffer_days - 1]


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


def get_trade_days(start: str | None = None, end: str | None = None) -> list[str]:
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


def get_range() -> list[str | None]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MIN(date) AS lo, MAX(date) AS hi FROM trade_calendar").fetchone()
        return [row["lo"], row["hi"]]
    finally:
        conn.close()


def get_last_sync() -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(created_at) AS t FROM trade_calendar").fetchone()
        return row["t"] if row else None
    finally:
        conn.close()


def get_coverage(start: str | None = None, end: str | None = None) -> dict[str, int]:
    """交易日历覆盖属性: {date: 0-4} — 四源(etf_daily/份额/成交额/融资)已覆盖数。
    交易日历即数据槽位台账, 覆盖属性由 scheduler/calendar_slots.py 刷新。"""
    conn = get_connection()
    try:
        sql = "SELECT date, etf_daily_ok, shares_ok, turnover_ok, margin_ok FROM trade_calendar"
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
        rows = conn.execute(sql, params).fetchall()
        return {
            r["date"]: int(r["etf_daily_ok"]) + int(r["shares_ok"]) + int(r["turnover_ok"]) + int(r["margin_ok"])
            for r in rows
        }
    finally:
        conn.close()


def update_coverage(rows: list[tuple[int, int, int, int, str]]) -> None:
    """批量更新覆盖属性: rows = [(etf_daily_ok, shares_ok, turnover_ok, margin_ok, date)]。"""
    conn = get_connection()
    try:
        conn.executemany(
            "UPDATE trade_calendar SET etf_daily_ok=?, shares_ok=?, turnover_ok=?, margin_ok=? WHERE date=?",
            rows,
        )
        conn.commit()
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
