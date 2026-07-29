"""市场广度数据访问层。"""

from typing import Optional
from store.database import get_connection


def upsert_breadth(row: dict) -> None:
    """插入或更新单日广度数据。"""
    if not row or not row.get("date"):
        return
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO market_breadth
                (date, sh_advance, sh_decline, sz_advance, sz_decline,
                 total_advance, total_decline, advance_pct,
                 limit_ups, limit_downs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                sh_advance=excluded.sh_advance,
                sh_decline=excluded.sh_decline,
                sz_advance=excluded.sz_advance,
                sz_decline=excluded.sz_decline,
                total_advance=excluded.total_advance,
                total_decline=excluded.total_decline,
                advance_pct=excluded.advance_pct,
                limit_ups=excluded.limit_ups,
                limit_downs=excluded.limit_downs,
                updated_at=datetime('now','localtime')
        """, (
            row["date"],
            row.get("sh_advance"), row.get("sh_decline"),
            row.get("sz_advance"), row.get("sz_decline"),
            row.get("advances"), row.get("declines"),
            row.get("advance_pct"),
            row.get("limit_ups"), row.get("limit_downs"),
        ))
        conn.commit()
    finally:
        conn.close()


def get_breadth_series(limit: Optional[int] = None) -> list[dict]:
    """获取广度时间序列 (升序)。"""
    conn = get_connection()
    try:
        if limit:
            sql = (
                "SELECT * FROM (SELECT * FROM market_breadth "
                "ORDER BY date DESC LIMIT ?) ORDER BY date ASC"
            )
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM market_breadth ORDER BY date ASC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_breadth_date() -> Optional[str]:
    """获取最新广度数据日期。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) FROM market_breadth").fetchone()
        return row[0] if row else None
    finally:
        conn.close()
