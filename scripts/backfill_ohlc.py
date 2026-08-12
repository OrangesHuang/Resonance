"""回填 etf_daily 真实 OHLC(上影/下影线数据源)。

腾讯 K 线接口含真实 open/high/low, 但历史入库时只存了 close。
本脚本按 ETF 拉取 K 线, 仅更新缺失 OHLC 的行(幂等, 可重复跑)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from base.config import ETFS
from base.store.database import init_db, get_connection
from base.fetch.kline import fetch_kline


def main() -> None:
    init_db()
    conn = get_connection()
    try:
        total = 0
        for code in ETFS:
            kline = fetch_kline(code, limit=640)
            if not kline:
                print(f"[BACKFILL] {code} K线为空, 跳过")
                continue
            updated = 0
            for k in kline:
                cur = conn.execute(
                    "SELECT open_price, high_price, low_price FROM etf_daily "
                    "WHERE date=? AND code=?", (k["date"], code)
                ).fetchone()
                if cur is None:
                    continue
                has_ohlc = all(cur[c] is not None for c in ("open_price", "high_price", "low_price"))
                if has_ohlc:
                    continue  # 已有真实 OHLC, 跳过
                conn.execute(
                    "UPDATE etf_daily SET open_price=?, high_price=?, low_price=?, "
                    "updated_at=datetime('now','localtime') WHERE date=? AND code=?",
                    (k["open"], k["high"], k["low"], k["date"], code))
                updated += 1
            conn.commit()
            print(f"[BACKFILL] {code}: 更新 {updated} 行真实 OHLC")
            total += updated
        print(f"[BACKFILL] 完成, 共更新 {total} 行")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
