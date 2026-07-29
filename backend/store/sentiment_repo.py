from typing import Optional

from store.database import get_connection


def upsert_turnover(rows: list[dict]) -> None:
    if not rows:
        return
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT INTO market_turnover (date, sh_amount_yi, sz_amount_yi, total_amount_yi)
            VALUES (:date, :sh_amount_yi, :sz_amount_yi, :total_amount_yi)
            ON CONFLICT(date) DO UPDATE SET
                sh_amount_yi    = excluded.sh_amount_yi,
                sz_amount_yi    = excluded.sz_amount_yi,
                total_amount_yi = excluded.total_amount_yi,
                updated_at      = datetime('now','localtime')
        """, rows)
        conn.commit()
    finally:
        conn.close()


def upsert_margin(rows: list[dict]) -> None:
    if not rows:
        return
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT INTO margin_trading (date, fin_balance_yi, loan_balance_yi, fin_buy_yi, source)
            VALUES (:date, :fin_balance_yi, :loan_balance_yi, :fin_buy_yi, :source)
            ON CONFLICT(date) DO UPDATE SET
                fin_balance_yi  = excluded.fin_balance_yi,
                loan_balance_yi = excluded.loan_balance_yi,
                fin_buy_yi      = excluded.fin_buy_yi,
                source          = excluded.source,
                updated_at      = datetime('now','localtime')
        """, rows)
        conn.commit()
    finally:
        conn.close()


def get_turnover_series(limit: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    try:
        sql = "SELECT date, sh_amount_yi, sz_amount_yi, total_amount_yi FROM market_turnover ORDER BY date ASC"
        if limit:
            sql = (
                "SELECT date, sh_amount_yi, sz_amount_yi, total_amount_yi FROM ("
                "SELECT * FROM market_turnover ORDER BY date DESC LIMIT ?) ORDER BY date ASC"
            )
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_margin_series(limit: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    try:
        if limit:
            sql = (
                "SELECT date, fin_balance_yi, loan_balance_yi, fin_buy_yi, source FROM ("
                "SELECT * FROM margin_trading ORDER BY date DESC LIMIT ?) ORDER BY date ASC"
            )
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            sql = "SELECT date, fin_balance_yi, loan_balance_yi, fin_buy_yi, source FROM margin_trading ORDER BY date ASC"
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_turnover_latest_date() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) FROM market_turnover").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_margin_latest_date() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) FROM margin_trading").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_turnover_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM market_turnover").fetchone()[0]
    finally:
        conn.close()


def get_margin_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM margin_trading").fetchone()[0]
    finally:
        conn.close()
