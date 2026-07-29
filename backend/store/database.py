import sqlite3
from pathlib import Path

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS etf_daily (
                date            TEXT NOT NULL,
                code            TEXT NOT NULL,
                name            TEXT,
                idx_name        TEXT,
                close_price     REAL,
                change_pct      REAL,
                volume          REAL,
                volume_ma20     REAL,
                volume_ratio    REAL,
                shares_yi       REAL,
                shares_delta_yi REAL,
                shares_delta_pct REAL,
                vol_prob        REAL,
                dir_prob        REAL,
                share_prob      REAL,
                composite_prob  REAL,
                idx_chg         REAL,
                signal_level    TEXT,
                price_position  REAL,
                trade_direction TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                updated_at      TEXT DEFAULT (datetime('now','localtime')),
                PRIMARY KEY (date, code)
            );

            CREATE INDEX IF NOT EXISTS idx_daily_code ON etf_daily(code);
            CREATE INDEX IF NOT EXISTS idx_daily_date ON etf_daily(date);

            CREATE TABLE IF NOT EXISTS etf_realtime (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                code            TEXT NOT NULL,
                price           REAL,
                change_pct      REAL,
                volume_hand     REAL,
                volume_ratio    REAL,
                vol_prob        REAL,
                dir_prob        REAL,
                share_prob      REAL,
                composite_prob  REAL,
                signal_level    TEXT,
                premium_pct     REAL,
                price_position  REAL,
                trade_direction TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_rt_code_ts ON etf_realtime(code, timestamp);
            CREATE INDEX IF NOT EXISTS idx_rt_ts ON etf_realtime(timestamp);

            CREATE TABLE IF NOT EXISTS market_turnover (
                date            TEXT PRIMARY KEY,
                sh_amount_yi    REAL,
                sz_amount_yi    REAL,
                total_amount_yi REAL,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                updated_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS margin_trading (
                date            TEXT PRIMARY KEY,
                fin_balance_yi  REAL,
                loan_balance_yi REAL,
                fin_buy_yi      REAL,
                source          TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                updated_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS trade_calendar (
                date        TEXT PRIMARY KEY,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS market_breadth (
                date            TEXT PRIMARY KEY,
                sh_advance      INTEGER,
                sh_decline      INTEGER,
                sz_advance      INTEGER,
                sz_decline      INTEGER,
                total_advance   INTEGER,
                total_decline   INTEGER,
                advance_pct     REAL,
                limit_ups       INTEGER,
                limit_downs     INTEGER,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                updated_at      TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        _migrate_add_direction_columns(conn)
        _migrate_drop_etf_kline(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_add_direction_columns(conn: sqlite3.Connection) -> None:
    for table in ("etf_daily", "etf_realtime"):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "price_position" not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN price_position REAL")
        if "trade_direction" not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN trade_direction TEXT")


def _migrate_drop_etf_kline(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS etf_kline")
