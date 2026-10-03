"""ETF 监控清单(动态管理)的 SQLite 读写。

etfs 表是真源; config.ETFS 仅为运行时镜像 —— load_into_config() 原地
clear/update(绝不重新绑定), 所有 `from base.config import ETFS` 的模块
(定时任务/实时行情/份额过滤/策略版本列举/接口校验)自动感知增删。

存储分层约束: base/fetch 不允许 import base/store, 所以镜像必须留在
config.py(叶子层), 这是刻意选择。
"""

from __future__ import annotations

from base.config import ETFS
from base.store.database import get_connection


def seed_from_config() -> int:
    """把 config.ETFS 存量配置导入 etfs 表(INSERT OR IGNORE, 仅补缺不覆盖)。

    首次启动时把硬编码清单播种进库; 之后库即真源, 配置只作缺省兜底。
    """
    rows = [(code, info["name"], info["idx"], info["market"]) for code, info in ETFS.items()]
    if not rows:
        return 0
    conn = get_connection()
    try:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO etfs (code, name, idx, market) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    finally:
        conn.close()


def list_all() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT code, name, idx, market, created_at FROM etfs ORDER BY created_at, code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get(code: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT code, name, idx, market, created_at FROM etfs WHERE code=?", (code,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def insert_etf(code: str, name: str, idx: str, market: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO etfs (code, name, idx, market) VALUES (?, ?, ?, ?)",
            (code, name, idx, market),
        )
        conn.commit()
    finally:
        conn.close()


def delete_etf(code: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM etfs WHERE code=?", (code,))
        conn.commit()
    finally:
        conn.close()


def purge_code_data(code: str) -> dict:
    """硬删除该标的的全部行情/份额/实时快照行(不可恢复)。

    交易日历等市场级表不含 code 维度, 不在此清理; 调用方需刷新日历槽位。
    """
    conn = get_connection()
    try:
        daily_rows = conn.execute("DELETE FROM etf_daily WHERE code=?", (code,)).rowcount
        realtime_rows = conn.execute("DELETE FROM etf_realtime WHERE code=?", (code,)).rowcount
        conn.commit()
        return {"daily_rows": daily_rows, "realtime_rows": realtime_rows}
    finally:
        conn.close()


def load_into_config() -> int:
    """把 etfs 表刷进 config.ETFS 运行时镜像(原地更新, 绝不重新绑定)。"""
    rows = list_all()
    ETFS.clear()
    ETFS.update({r["code"]: {"name": r["name"], "idx": r["idx"], "market": r["market"]} for r in rows})
    return len(rows)


def etf_coverage() -> dict[str, dict]:
    """每只标的的数据覆盖: 日度区间/行数/份额末日/折算标记数 + 实时快照行数。

    只返回库中有行的 code(含已移除标的的遗留行, 调用方按在册清单过滤)。
    """
    conn = get_connection()
    try:
        daily_rows = conn.execute(
            """
            SELECT code,
                   MIN(date) AS first_date,
                   MAX(date) AS last_date,
                   COUNT(*) AS daily_rows,
                   MAX(CASE WHEN shares_yi IS NOT NULL THEN date END) AS shares_last_date,
                   SUM(CASE WHEN share_adjust IS NOT NULL THEN 1 ELSE 0 END) AS adjust_events
              FROM etf_daily GROUP BY code
            """
        ).fetchall()
        out = {r["code"]: dict(r) for r in daily_rows}
        for item in out.values():
            item["realtime_rows"] = 0
            item["realtime_last"] = None
        for r in conn.execute(
            "SELECT code, COUNT(*) AS n, MAX(timestamp) AS ts FROM etf_realtime GROUP BY code"
        ).fetchall():
            item = out.setdefault(
                r["code"],
                {
                    "code": r["code"],
                    "first_date": None,
                    "last_date": None,
                    "daily_rows": 0,
                    "shares_last_date": None,
                    "adjust_events": 0,
                    "realtime_rows": 0,
                    "realtime_last": None,
                },
            )
            item["realtime_rows"] = r["n"]
            item["realtime_last"] = r["ts"]
        return out
    finally:
        conn.close()
