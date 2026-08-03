from typing import Optional

from store.database import get_connection
from config import ETFS


def upsert_daily(date: str, code: str, data: dict) -> None:
    info = ETFS.get(code, {})
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO etf_daily (date, code, name, idx_name, close_price, change_pct,
                volume, volume_ma20, volume_ratio, shares_yi, shares_delta_yi,
                shares_delta_pct, vol_prob, dir_prob, share_prob, composite_prob,
                idx_chg, signal_level, price_position, trade_direction, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(date, code) DO UPDATE SET
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
                share_prob=excluded.share_prob,
                composite_prob=excluded.composite_prob,
                idx_chg=excluded.idx_chg,
                signal_level=excluded.signal_level,
                price_position=excluded.price_position,
                trade_direction=excluded.trade_direction,
                updated_at=datetime('now','localtime')
        """, (
            date, code, info.get("name", ""), info.get("idx", ""),
            data.get("close"), data.get("change_pct"),
            data.get("volume"), data.get("volume_ma20"), data.get("volume_ratio"),
            data.get("shares_yi"), data.get("shares_delta_yi"), data.get("shares_delta_pct"),
            data.get("vol_prob"), data.get("dir_prob"), data.get("share_prob"),
            data.get("composite_prob"), data.get("idx_chg"), data.get("signal_level"),
            data.get("price_position"), data.get("trade_direction"),
        ))
        conn.commit()
    finally:
        conn.close()


def update_share_data(date: str, code: str, shares_yi: float,
                      delta_yi: Optional[float], delta_pct: Optional[float],
                      share_prob: Optional[float]) -> None:
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE etf_daily
            SET shares_yi=?, shares_delta_yi=?, shares_delta_pct=?, share_prob=?,
                updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
        """, (shares_yi, delta_yi, delta_pct, share_prob, date, code))
        conn.commit()
    finally:
        conn.close()


def get_latest_date_for(code: str) -> Optional[str]:
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


def get_trading_dates(start: Optional[str] = None, end: Optional[str] = None) -> list[str]:
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
        rows = conn.execute(
            "SELECT * FROM etf_daily WHERE date = ? ORDER BY code", (date,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_by_code(code: str, start: Optional[str] = None, end: Optional[str] = None) -> list[dict]:
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


def get_latest_date() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MAX(date) as d FROM etf_daily WHERE composite_prob IS NOT NULL"
        ).fetchone()
        return row["d"] if row else None
    finally:
        conn.close()


def get_latest_with_shares(code: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM etf_daily WHERE code = ? AND shares_yi IS NOT NULL ORDER BY date DESC LIMIT 1",
            (code,)
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
        with_shares = conn.execute(
            "SELECT COUNT(*) as c FROM etf_daily WHERE shares_yi IS NOT NULL"
        ).fetchone()["c"]
        return {
            "total_records": total,
            "trading_days": dates,
            "date_range": [min_d, max_d],
            "records_with_shares": with_shares,
        }
    finally:
        conn.close()
