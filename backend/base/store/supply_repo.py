"""一级退出监测(解禁/减持/IPO)的 SQLite 读写。参数化查询, 幂等 upsert。"""

from __future__ import annotations

from base.store.database import get_connection


def upsert_unlocks(rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO unlock_events
                (date, code, name, unlock_type, shares, market_value, ratio_pct, pre20_chg, post20_chg)
            VALUES (:date, :code, :name, :unlock_type, :shares, :market_value, :ratio_pct, :pre20_chg, :post20_chg)
            ON CONFLICT(date, code) DO UPDATE SET
                name=excluded.name, unlock_type=excluded.unlock_type, shares=excluded.shares,
                market_value=excluded.market_value, ratio_pct=excluded.ratio_pct,
                pre20_chg=excluded.pre20_chg, post20_chg=excluded.post20_chg
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def upsert_reductions(rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = get_connection()
    try:
        cur = conn.executemany(
            """
            INSERT OR IGNORE INTO reduction_events
                (date, code, name, holder, role, shares_delta, price, amount, ratio_pct, reason)
            VALUES (:date, :code, :name, :holder, :role, :shares_delta, :price, :amount, :ratio_pct, :reason)
            """,
            rows,
        )
        conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    finally:
        conn.close()


def upsert_ipos(rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO ipo_events
                (code, name, board, exchange, issue_date, list_date, price, total_shares, pe)
            VALUES (:code, :name, :board, :exchange, :issue_date, :list_date, :price, :total_shares, :pe)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name, board=excluded.board, exchange=excluded.exchange,
                issue_date=excluded.issue_date, list_date=excluded.list_date,
                price=excluded.price, total_shares=excluded.total_shares, pe=excluded.pe
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_unlocks(start: str | None = None, end: str | None = None) -> list[dict]:
    sql = "SELECT * FROM unlock_events WHERE 1=1"
    args: list = []
    if start:
        sql += " AND date>=?"
        args.append(start)
    if end:
        sql += " AND date<=?"
        args.append(end)
    sql += " ORDER BY date, market_value DESC"
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def get_reductions(start: str | None = None, end: str | None = None) -> list[dict]:
    sql = "SELECT * FROM reduction_events WHERE 1=1"
    args: list = []
    if start:
        sql += " AND date>=?"
        args.append(start)
    if end:
        sql += " AND date<=?"
        args.append(end)
    sql += " ORDER BY date DESC, amount ASC"
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def get_ipos(start: str | None = None, end: str | None = None) -> list[dict]:
    sql = "SELECT * FROM ipo_events WHERE issue_date IS NOT NULL"
    args: list = []
    if start:
        sql += " AND issue_date>=?"
        args.append(start)
    if end:
        sql += " AND issue_date<=?"
        args.append(end)
    sql += " ORDER BY issue_date DESC"
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def set_meta(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO supply_meta (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')
            """,
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_meta(key: str) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM supply_meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()
