"""回填历史 ETF 日度数据到 etf_monitor.db(薄壳,逻辑在 scheduler/data_jobs.py)"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "backend"))

from config import DEFAULT_ETF_SEED_DAYS
from store.database import init_db
from scheduler.data_jobs import job_backfill_etf_daily


def _print_progress(current: int, total: int, message: str) -> None:
    print(f"  [{current}/{total}] {message}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ETF_SEED_DAYS
    init_db()
    print(f"[SEED] backfilling ETF daily ({days} days)...")
    result = job_backfill_etf_daily(_print_progress, days)
    print(f"[SEED] done: {result}")
