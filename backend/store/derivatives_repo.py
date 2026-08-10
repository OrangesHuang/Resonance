"""衍生品数据访问层: 期权PCR + 股指期货基差。"""

from typing import Optional
from store.database import get_connection


def upsert_pcr(rows: list[dict]) -> None:
    if not rows:
        return
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT INTO option_pcr
                (date, underlying_code, underlying_name, pcr,
                 call_volume, put_volume, call_oi, put_oi)
            VALUES (:date, :underlying_code, :underlying_name, :pcr,
                    :call_volume, :put_volume, :call_oi, :put_oi)
            ON CONFLICT(date, underlying_code) DO UPDATE SET
                underlying_name = excluded.underlying_name,
                pcr             = excluded.pcr,
                call_volume     = excluded.call_volume,
                put_volume      = excluded.put_volume,
                call_oi         = excluded.call_oi,
                put_oi          = excluded.put_oi
        """, rows)
        conn.commit()
    finally:
        conn.close()


def upsert_basis(rows: list[dict]) -> None:
    if not rows:
        return
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT INTO futures_basis
                (date, futures_code, futures_name, fut_close, spot_close,
                 basis, basis_pct, volume, hold)
            VALUES (:date, :futures_code, :futures_name, :fut_close, :spot_close,
                    :basis, :basis_pct, :volume, :hold)
            ON CONFLICT(date, futures_code) DO UPDATE SET
                futures_name = excluded.futures_name,
                fut_close    = excluded.fut_close,
                spot_close   = excluded.spot_close,
                basis        = excluded.basis,
                basis_pct    = excluded.basis_pct,
                volume       = excluded.volume,
                hold         = excluded.hold
        """, rows)
        conn.commit()
    finally:
        conn.close()


def get_pcr_series(limit: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    try:
        sql = ("SELECT * FROM option_pcr ORDER BY date ASC, underlying_code ASC")
        if limit:
            sql = (
                "SELECT * FROM (SELECT * FROM option_pcr "
                "ORDER BY date DESC LIMIT ?) ORDER BY date ASC, underlying_code ASC"
            )
            rows = conn.execute(sql, (limit * 4,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_basis_series(limit: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM futures_basis ORDER BY date ASC, futures_code ASC"
        if limit:
            sql = (
                "SELECT * FROM (SELECT * FROM futures_basis "
                "ORDER BY date DESC LIMIT ?) ORDER BY date ASC, futures_code ASC"
            )
            rows = conn.execute(sql, (limit * 3,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pcr_latest_date() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) FROM option_pcr").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_basis_latest_date() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) FROM futures_basis").fetchone()
        return row[0] if row else None
    finally:
        conn.close()
