"""键值设置存储(数据槽位起始日期等用户可调配置)。"""

from __future__ import annotations

from base.store.database import get_connection


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, datetime('now','localtime'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now','localtime')
            """,
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
