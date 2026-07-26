"""回填历史 ETF 份额数据(薄壳,逻辑在 scheduler/data_jobs.py)"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import DEFAULT_SHARES_BACKFILL_DAYS
from store.database import init_db
from scheduler.data_jobs import job_backfill_shares


def _print_progress(current: int, total: int, message: str) -> None:
    print(f"  [{current}/{total}] {message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="backfill historical ETF shares")
    parser.add_argument("--days", type=int, default=DEFAULT_SHARES_BACKFILL_DAYS,
                        help="recent trading days")
    parser.add_argument("--force", action="store_true", help="rewrite complete dates")
    args = parser.parse_args()
    init_db()
    result = job_backfill_shares(_print_progress, args.days, args.force)
    print(f"[BACKFILL] done: {result}")
