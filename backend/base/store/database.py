from __future__ import annotations

import sqlite3

from base.config import DB_PATH


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
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                etf_daily_ok INTEGER NOT NULL DEFAULT 0,
                shares_ok    INTEGER NOT NULL DEFAULT 0,
                turnover_ok  INTEGER NOT NULL DEFAULT 0,
                margin_ok    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS intraday_turnover (
                timestamp   TEXT PRIMARY KEY,
                amount_yi   REAL,
                est_amount_yi REAL,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        _migrate_add_direction_columns(conn)
        _migrate_add_ohlc_columns(conn)
        _migrate_add_calendar_slot_columns(conn)
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


def _migrate_add_ohlc_columns(conn: sqlite3.Connection) -> None:
    """etf_daily 增加真实开高低收列(上影/下影线需要真实 high/low)。"""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(etf_daily)")}
    for col in ("open_price", "high_price", "low_price"):
        if col not in existing:
            conn.execute(f"ALTER TABLE etf_daily ADD COLUMN {col} REAL")


def _migrate_add_calendar_slot_columns(conn: sqlite3.Connection) -> None:
    """trade_calendar 增加数据槽位覆盖属性列(交易日历即填充槽: 每天标注四个
    数据源是否已覆盖, 见 scheduler/calendar_slots.py)。"""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(trade_calendar)")}
    for col in ("etf_daily_ok", "shares_ok", "turnover_ok", "margin_ok"):
        if col not in existing:
            conn.execute(f"ALTER TABLE trade_calendar ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")


def _migrate_drop_etf_kline(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS etf_kline")
