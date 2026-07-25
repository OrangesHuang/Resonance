from typing import Optional

from store.database import get_connection


def insert_snapshots(signals: list[dict]) -> None:
    if not signals:
        return
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT INTO etf_realtime
                (timestamp, code, price, change_pct, volume_hand, volume_ratio,
                 vol_prob, dir_prob, share_prob, composite_prob, signal_level, premium_pct,
                 price_position, trade_direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                s["timestamp"], s["code"], s["price"], s["change_pct"],
                s["volume_hand"], s["volume_ratio"],
                s["vol_prob"], s["dir_prob"], s["share_prob"],
                s["composite_prob"], s["signal_level"], s.get("premium_pct"),
                s.get("price_position"), s.get("trade_direction"),
            )
            for s in signals
        ])
        conn.commit()
    finally:
        conn.close()


def get_today_snapshots(code: Optional[str] = None, date_str: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM etf_realtime WHERE 1=1"
        params: list = []
        if date_str:
            sql += " AND timestamp LIKE ?"
            params.append(f"{date_str}%")
        if code:
            sql += " AND code = ?"
            params.append(code)
        sql += " ORDER BY timestamp ASC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_snapshot() -> list[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(timestamp) as ts FROM etf_realtime").fetchone()
        if not row or not row["ts"]:
            return []
        rows = conn.execute(
            "SELECT * FROM etf_realtime WHERE timestamp = ? ORDER BY code", (row["ts"],)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cleanup_old_snapshots(keep_days: int = 7) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM etf_realtime WHERE timestamp < datetime('now', 'localtime', ?)",
            (f"-{keep_days} days",)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
