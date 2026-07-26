"""回填历史 ETF 份额数据（上交所 + 深交所），重算 delta 与 share_prob"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import ETFS
from fetch.shares import fetch_shares_for_date
from analysis.factors import calc_share_probability
from store.database import init_db
from store.daily_repo import get_trading_dates, get_by_date, update_share_data


def _load_prev_shares(date: str, prev_shares: dict) -> None:
    for r in get_by_date(date):
        if r.get("shares_yi") is not None:
            prev_shares[r["code"]] = r["shares_yi"]


def _date_complete(date: str) -> bool:
    rows = {r["code"]: r for r in get_by_date(date)}
    return all(
        rows.get(c, {}).get("shares_yi") is not None
        and rows.get(c, {}).get("share_prob") is not None
        for c in ETFS
    )


def _write_date(date: str, prev_shares: dict) -> int:
    shares = fetch_shares_for_date(date)
    if not shares:
        return 0
    n = 0
    for code, shares_yi in shares.items():
        delta_yi = None
        delta_pct = None
        prev = prev_shares.get(code)
        if prev is not None and prev > 0:
            delta_yi = round(shares_yi - prev, 4)
            delta_pct = round(delta_yi / prev * 100, 3)
        update_share_data(date, code, shares_yi, delta_yi, delta_pct,
                          calc_share_probability(delta_pct))
        prev_shares[code] = shares_yi
        n += 1
    return n


def backfill(days: int, force: bool) -> None:
    init_db()
    dates = get_trading_dates()[-days:]
    if not dates:
        print("[BACKFILL] no trading dates in etf_daily")
        return
    print(f"[BACKFILL] {len(dates)} trading days: {dates[0]} -> {dates[-1]}")

    prev_shares: dict = {}
    written = 0
    for i, date in enumerate(dates, 1):
        if not force and _date_complete(date):
            _load_prev_shares(date, prev_shares)
            print(f"  [{i}/{len(dates)}] {date}: already complete, skipped")
            continue
        n = _write_date(date, prev_shares)
        written += n
        print(f"  [{i}/{len(dates)}] {date}: {n} codes updated")
        time.sleep(0.15)
    print(f"[BACKFILL] done, {written} rows updated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="backfill historical ETF shares")
    parser.add_argument("--days", type=int, default=140, help="recent trading days")
    parser.add_argument("--force", action="store_true", help="rewrite complete dates")
    args = parser.parse_args()
    backfill(args.days, args.force)
