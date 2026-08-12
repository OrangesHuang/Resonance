from __future__ import annotations

from base.config import ETFS
from base.store.database import get_connection


def upsert_daily(date: str, code: str, data: dict) -> None:
    info = ETFS.get(code, {})
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO etf_daily (date, code, name, idx_name, open_price, high_price,
                low_price, close_price, change_pct,
                volume, volume_ma20, volume_ratio, shares_yi, shares_delta_yi,
                shares_delta_pct, vol_prob, dir_prob, share_prob, composite_prob,
                idx_chg, signal_level, price_position, trade_direction, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(date, code) DO UPDATE SET
                open_price=COALESCE(excluded.open_price, etf_daily.open_price),
                high_price=COALESCE(excluded.high_price, etf_daily.high_price),
                low_price=COALESCE(excluded.low_price, etf_daily.low_price),
                close_price=excluded.close_price,
                change_pct=excluded.change_pct,
                volume=excluded.volume,
                volume_ma20=excluded.volume_ma20,
                volume_ratio=excluded.volume_ratio,
                shares_yi=COALESCE(excluded.shares_yi, etf_daily.shares_yi),
                shares_delta_yi=COALESCE(excluded.shares_delta_yi, etf_daily.shares_delta_yi),
                shares_delta_pct=COALESCE(excluded.shares_delta_pct, etf_daily.shares_delta_pct),
                share_prob=COALESCE(excluded.share_prob, etf_daily.share_prob),
                vol_prob=excluded.vol_prob,
                dir_prob=excluded.dir_prob,
                composite_prob=excluded.composite_prob,
                idx_chg=excluded.idx_chg,
                signal_level=excluded.signal_level,
                price_position=excluded.price_position,
                trade_direction=excluded.trade_direction,
                updated_at=datetime('now','localtime')
        """,
            (
                date,
                code,
                info.get("name", ""),
                info.get("idx", ""),
                data.get("open"),
                data.get("high"),
                data.get("low"),
                data.get("close"),
                data.get("change_pct"),
                data.get("volume"),
                data.get("volume_ma20"),
                data.get("volume_ratio"),
                data.get("shares_yi"),
                data.get("shares_delta_yi"),
                data.get("shares_delta_pct"),
                data.get("vol_prob"),
                data.get("dir_prob"),
                data.get("share_prob"),
                data.get("composite_prob"),
                data.get("idx_chg"),
                data.get("signal_level"),
                data.get("price_position"),
                data.get("trade_direction"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_share_data(
    date: str, code: str, shares_yi: float, delta_yi: float | None, delta_pct: float | None, share_prob: float | None
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE etf_daily
            SET shares_yi=?, shares_delta_yi=?, shares_delta_pct=?, share_prob=?,
                updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
        """,
            (shares_yi, delta_yi, delta_pct, share_prob, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def update_composite_signal(date: str, code: str, composite_prob: float, signal_level: str) -> None:
    """重算对齐: 只更新综合概率与信号等级两列, 不动其他字段。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE etf_daily
            SET composite_prob=?, signal_level=?, updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
            """,
            (composite_prob, signal_level, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_date_for(code: str) -> str | None:
    """单只 ETF 在库中的最新日期 (无数据返回 None)。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MAX(date) AS d FROM etf_daily WHERE code=? AND close_price IS NOT NULL",
            (code,),
        ).fetchone()
        return row["d"] if row else None
    finally:
        conn.close()


def get_shares_by_date(date: str) -> dict[str, dict]:
    """某交易日各 ETF 的份额数据: {code: {shares_yi, delta_yi, delta_pct}}。"""
    result: dict[str, dict] = {}
    for r in get_by_date(date):
        if r.get("shares_yi") is None:
            continue
        result[r["code"]] = {
            "shares_yi": r["shares_yi"],
            "delta_yi": r.get("shares_delta_yi"),
            "delta_pct": r.get("shares_delta_pct"),
        }
    return result


def shares_complete_for(date: str) -> bool:
    """某交易日全部监控 ETF 是否都已有份额数据 (避免重复拉取份额接口)。"""
    rows = get_shares_by_date(date)
    return all(c in rows for c in ETFS)


def get_missing_share_dates() -> list[str]:
    """份额缺失的交易日(升序): 当日有 K 线记录但至少一只 ETF 缺 shares_yi。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT date, COUNT(*) AS total, COUNT(shares_yi) AS with_shares "
            "FROM etf_daily GROUP BY date HAVING with_shares < total ORDER BY date"
        ).fetchall()
        return [r["date"] for r in rows]
    finally:
        conn.close()


def get_trading_dates(start: str | None = None, end: str | None = None) -> list[str]:
    conn = get_connection()
    try:
        sql = "SELECT DISTINCT date FROM etf_daily WHERE composite_prob IS NOT NULL"
        params: list = []
        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        sql += " ORDER BY date"
        return [r["date"] for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_by_date(date: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM etf_daily WHERE date = ? ORDER BY code", (date,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_by_code(code: str, start: str | None = None, end: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM etf_daily WHERE code = ?"
        params: list = [code]
        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        sql += " ORDER BY date DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_date() -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) as d FROM etf_daily WHERE composite_prob IS NOT NULL").fetchone()
        return row["d"] if row else None
    finally:
        conn.close()


def get_latest_with_shares(code: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM etf_daily WHERE code = ? AND shares_yi IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_stats() -> dict:
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) as c FROM etf_daily").fetchone()["c"]
        dates = conn.execute("SELECT COUNT(DISTINCT date) as c FROM etf_daily").fetchone()["c"]
        min_d = conn.execute("SELECT MIN(date) as d FROM etf_daily").fetchone()["d"]
        max_d = conn.execute("SELECT MAX(date) as d FROM etf_daily").fetchone()["d"]
        with_shares = conn.execute("SELECT COUNT(*) as c FROM etf_daily WHERE shares_yi IS NOT NULL").fetchone()["c"]
        return {
            "total_records": total,
            "trading_days": dates,
            "date_range": [min_d, max_d],
            "records_with_shares": with_shares,
        }
    finally:
        conn.close()
