"""回填历史数据到 etf_monitor.db"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "backend"))

from datetime import datetime, timedelta
from config import ETFS
from fetch.kline import fetch_kline, fetch_index_kline
from analysis.composite import analyze_single_etf
from store.database import init_db
from store.daily_repo import upsert_daily


def seed(days: int = 60):
    init_db()
    print(f"[SEED] fetching index kline ({days} days)...")
    idx_kline = fetch_index_kline(limit=days)
    if not idx_kline:
        print("[SEED] ERROR: cannot fetch index kline")
        return

    for code, info in ETFS.items():
        print(f"[SEED] processing {code} {info['name']}...")
        kline = fetch_kline(code, limit=days)
        if len(kline) < 20:
            print(f"  skipped (only {len(kline)} bars)")
            continue

        count = 0
        for i in range(19, len(kline)):
            result = analyze_single_etf(
                kline=kline[:i + 1],
                idx_kline=idx_kline[:i + 1],
                shares_delta_pct=None,
                target_idx=i,
            )
            if result:
                upsert_daily(result["date"], code, result)
                count += 1
        print(f"  inserted {count} records")

    print("[SEED] done")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    seed(days)
