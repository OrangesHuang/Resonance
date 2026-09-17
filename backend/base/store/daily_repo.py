from __future__ import annotations

from base.config import ETFS
from base.store.database import get_connection


def upsert_daily(date: str, code: str, data: dict) -> None:
    info = ETFS.get(code, {})
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO etf_daily (date, code, name, idx_name, open_price, high_price,
                low_price, close_price, change_pct,
                volume, volume_ma20, volume_ratio, shares_yi, shares_delta_yi,
                shares_delta_pct, vol_prob, dir_prob, share_prob, composite_prob,
                idx_chg, signal_level, price_position, trade_direction, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(date, code) DO UPDATE SET
                open_price=COALESCE(excluded.open_price, etf_daily.open_price),
                high_price=COALESCE(excluded.high_price, etf_daily.high_price),
                low_price=COALESCE(excluded.low_price, etf_daily.low_price),
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
                composite_prob=excluded.composite_prob,
                idx_chg=excluded.idx_chg,
                signal_level=excluded.signal_level,
                price_position=excluded.price_position,
                trade_direction=excluded.trade_direction,
                updated_at=datetime('now','localtime')
        """,
            (
                date,
                code,
                info.get("name", ""),
                info.get("idx", ""),
                data.get("open"),
                data.get("high"),
                data.get("low"),
                data.get("close"),
                data.get("change_pct"),
                data.get("volume"),
                data.get("volume_ma20"),
                data.get("volume_ratio"),
                data.get("shares_yi"),
                data.get("shares_delta_yi"),
                data.get("shares_delta_pct"),
                data.get("vol_prob"),
                data.get("dir_prob"),
                data.get("share_prob"),
                data.get("composite_prob"),
                data.get("idx_chg"),
                data.get("signal_level"),
                data.get("price_position"),
                data.get("trade_direction"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_share_data(
    date: str, code: str, shares_yi: float, delta_yi: float | None, delta_pct: float | None, share_prob: float | None
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE etf_daily
            SET shares_yi=?, shares_delta_yi=?, shares_delta_pct=?, share_prob=?,
                updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
        """,
            (shares_yi, delta_yi, delta_pct, share_prob, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def update_share_adjust(
    date: str,
    code: str,
    delta_yi: float | None,
    delta_pct: float | None,
    share_prob: float | None,
    adjust_ratio: float,
) -> None:
    """修正折算日的份额字段: 写入扣除折算后的真实净申赎 + 折算比例标记。

    只动份额相关列(不含 shares_yi —— 份额总数是交易所真实值)与 share_adjust
    标记, 不触碰价格/成交/方向等其它字段。
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE etf_daily
            SET shares_delta_yi=?, shares_delta_pct=?, share_prob=?, share_adjust=?,
                updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
        """,
            (delta_yi, delta_pct, share_prob, adjust_ratio, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def update_share_prob(date: str, code: str, share_prob: float | None) -> None:
    """只更新 share_prob 一列(折算后重算尾随日概率用, 不改折算标记)。"""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE etf_daily SET share_prob=?, updated_at=datetime('now','localtime') WHERE date=? AND code=?",
            (share_prob, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def clear_share_adjust(date: str, code: str) -> None:
    """清除折算标记(复核后确认非折算时的自愈路径)。"""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE etf_daily SET share_adjust=NULL, updated_at=datetime('now','localtime') "
            "WHERE date=? AND code=? AND share_adjust IS NOT NULL",
            (date, code),
        )
        conn.commit()
    finally:
        conn.close()


def update_composite_signal(date: str, code: str, composite_prob: float, signal_level: str) -> None:
    """重算对齐: 只更新综合概率与信号等级两列, 不动其他字段。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE etf_daily
            SET composite_prob=?, signal_level=?, updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
            """,
            (composite_prob, signal_level, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def update_direction_signal(date: str, code: str, dir_prob: float, composite_prob: float, signal_level: str) -> None:
    """重算对齐(方向概率修正后): 更新方向概率+综合概率+信号等级三列。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE etf_daily
            SET dir_prob=?, composite_prob=?, signal_level=?,
                updated_at=datetime('now','localtime')
            WHERE date=? AND code=?
            """,
            (dir_prob, composite_prob, signal_level, date, code),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_date_for(code: str) -> str | None:
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


def get_missing_share_dates(start: str | None = None, end: str | None = None) -> list[str]:
    """份额缺失的交易日(升序): 当日有 K 线记录但至少一只 ETF 缺份额字段。

    可按 [start, end] 收窄 —— 补全任务支持区间, 避免动辄从 2005 年全量扫描。
    """
    conn = get_connection()
    try:
        sql = "SELECT date, COUNT(*) AS total, COUNT(shares_yi) AS with_shares FROM etf_daily"
        conds: list[str] = []
        params: list = []
        if start:
            conds.append("date >= ?")
            params.append(start)
        if end:
            conds.append("date <= ?")
            params.append(end)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " GROUP BY date HAVING with_shares < total ORDER BY date"
        rows = conn.execute(sql, params).fetchall()
        return [r["date"] for r in rows]
    finally:
        conn.close()


def get_first_share_dates() -> dict[str, str]:
    """各标的**已有份额的最早日期**(完全没有份额的标的不在返回中)。

    用途: 剔除"ETF 尚未成立"的日期。曾因此踩坑 —— 补全任务从 2005-01-17 起
    扫 512100 等标的上市前的日期, 远端必然返回空, 每 3 次失败暂停 60s,
    5258 个日期几小时都跑不完。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT code, MIN(date) AS d FROM etf_daily WHERE shares_yi IS NOT NULL GROUP BY code"
        ).fetchall()
        return {r["code"]: r["d"] for r in rows}
    finally:
        conn.close()


def count_fillable_missing_shares(codes: list[str] | None = None, start: str | None = None) -> int:
    """可被「补全缺失份额」真正补上的缺失记录数(单条 SQL, 供状态页展示)。

    口径与任务一致:
      - 缺 shares_yi 或缺 delta;
      - 日期不早于该标的已有份额的最早日期(剔除上市前, 否则会把 512100 上市前
        的 2876 天算成缺口);
      - 只统计 codes(默认全部; 调用方传在册标的, 以免把已移除标的的历史空洞
        算进来 —— 库里的 510880/159919/510310/510330 就是这种遗留行);
      - 可传 start 与任务的范围(数据槽位起点)对齐;
      - 排除**结构性缺失**: 各标的"首个有份额的日子"没有前一日可比, delta
        必然为空, 不算可补缺口。
    """
    conn = get_connection()
    try:
        sql = """
            SELECT COUNT(*) AS c FROM etf_daily d
            JOIN (SELECT code, MIN(date) AS f FROM etf_daily
                  WHERE shares_yi IS NOT NULL GROUP BY code) s ON s.code = d.code
            WHERE (d.shares_yi IS NULL OR d.shares_delta_yi IS NULL)
              AND d.date >= s.f
              AND NOT (d.shares_yi IS NOT NULL AND d.shares_delta_yi IS NULL AND d.date = s.f)
        """
        params: list = []
        if start:
            sql += " AND d.date >= ?"
            params.append(start)
        if codes:
            placeholders = ",".join(["?"] * len(codes))
            sql += f" AND d.code IN ({placeholders})"
            params.extend(codes)
        row = conn.execute(sql, params).fetchone()
        return int(row["c"])
    finally:
        conn.close()


def get_trading_dates(start: str | None = None, end: str | None = None) -> list[str]:
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
        rows = conn.execute("SELECT * FROM etf_daily WHERE date = ? ORDER BY code", (date,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_by_code(code: str, start: str | None = None, end: str | None = None) -> list[dict]:
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


def get_distinct_dates() -> list[str]:
    """etf_daily 中出现过的全部交易日(升序), 供缺口扫描与交易日历比对。"""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT DISTINCT date FROM etf_daily ORDER BY date").fetchall()
        return [r["date"] for r in rows]
    finally:
        conn.close()


def get_latest_date() -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(date) as d FROM etf_daily WHERE composite_prob IS NOT NULL").fetchone()
        return row["d"] if row else None
    finally:
        conn.close()


def get_latest_with_shares(code: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM etf_daily WHERE code = ? AND shares_yi IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)
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
        with_shares = conn.execute("SELECT COUNT(*) as c FROM etf_daily WHERE shares_yi IS NOT NULL").fetchone()["c"]
        return {
            "total_records": total,
            "trading_days": dates,
            "date_range": [min_d, max_d],
            "records_with_shares": with_shares,
        }
    finally:
        conn.close()
