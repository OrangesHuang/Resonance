# mypy: ignore-errors
"""沪深300 (510300) 数据回填: 2014-01-01 起(真实 ETF, 无需指数代理)。

510300 于 2012-05-28 上市: 腾讯K线自上市首日起可得, 上交所份额接口
2013-06 起可得, 2014+ 全程真实数据。回填 2013 年作预热年(MA250 窗口),
观察重点 2014 起(14-15 大牛/15 股灾/16 熔断/17 白马牛/18 熊)。
两市成交额与融资余额已由 中证1000 回填脚本延伸(2006/2010 起), 本脚本跳过。
幂等可重入, 份额检查点续传。仅本地运行, 不上生产。
"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "backend")

from base.config import SHARE_WINDOW
from base.fetch.kline import fetch_kline
from base.fetch.shares import fetch_shares_sse
from base.store.daily_repo import (
    get_by_code,
    update_direction_signal,
    update_share_data,
    upsert_daily,
)
from resonance.analysis.composite import analyze_single_etf, calc_composite_probability
from resonance.analysis.factors import (
    calc_direction_probability,
    calc_share_probability_dual,
    classify_signal,
)

CODE = "510300"
INDEX = "000300"
KL_START = "2012-05-28"  # 上市首日(预热窗口用)
STORE_START = "2013-01-01"  # 预热年起点(2014 起为观察重点)
END = "2018-12-31"
SHARES_START = "2013-12-30"  # 份额起点(供 2014-01-02 delta 的 prev)
SLEEP_SEC = 0.4
CP_FILE = "/tmp/hs300_shares_checkpoint.json"


def _load_checkpoint() -> tuple[dict[str, dict], float | None, list[float]]:
    import json

    try:
        with open(CP_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data["share_map"], data.get("prev_yi"), data.get("hist", [])
    except (FileNotFoundError, KeyError, ValueError):
        return {}, None, []


def _save_checkpoint(
    share_map: dict[str, dict], prev_yi: float | None, hist: list[float]
) -> None:
    import json

    with open(CP_FILE, "w", encoding="utf-8") as f:
        json.dump({"share_map": share_map, "prev_yi": prev_yi, "hist": hist}, f)


def backfill_shares(dates: list[str]) -> dict[str, dict]:
    """逐日拉上交所份额(2013-12-30 起), 检查点续传。"""
    existing = {
        r["date"]
        for r in get_by_code(CODE, SHARES_START, END)
        if r.get("shares_yi") is not None
    }
    share_map, prev_yi, hist = _load_checkpoint()
    share_map = {d: v for d, v in share_map.items() if d not in existing}
    if share_map:
        prev_dates = sorted(share_map)
        prev_yi = share_map[prev_dates[-1]]["shares_yi"]
        hist = [share_map[d]["shares_yi"] for d in prev_dates[-SHARE_WINDOW:]]
        print(f"[HS300] 检查点续传 {len(share_map)} 日", flush=True)
    for i, d in enumerate(dates):
        if d in existing or d in share_map:
            continue
        yi = fetch_shares_sse(d).get(CODE)
        if yi is None:
            print(f"[HS300] 份额 {d} 无数据")
            continue
        delta_yi = delta_pct = None
        if prev_yi is not None and prev_yi > 0:
            delta_yi = round(yi - prev_yi, 4)
            delta_pct = round(delta_yi / prev_yi * 100, 3)
        sp = calc_share_probability_dual(delta_pct, yi, list(hist), SHARE_WINDOW)
        share_map[d] = {
            "shares_yi": round(yi, 4),
            "delta_yi": delta_yi,
            "delta_pct": delta_pct,
            "sp": sp,
        }
        hist.append(yi)
        if len(hist) > SHARE_WINDOW:
            hist.pop(0)
        prev_yi = yi
        if (i + 1) % 80 == 0:
            print(f"[HS300] 份额 {d} ({i + 1}/{len(dates)})", flush=True)
            _save_checkpoint(share_map, prev_yi, hist)
        time.sleep(SLEEP_SEC)
    _save_checkpoint(share_map, prev_yi, hist)
    print(f"[HS300] 份额拉取完成 {len(share_map)} 日", flush=True)
    return share_map


def backfill_rows(
    bars: list[dict], idx_bars: list[dict], share_map: dict[str, dict]
) -> int:
    """2013-01-01 起逐日分析写入(真实ETF价 + 000300 指数)。"""
    idx_map = {b["date"]: b for b in idx_bars}
    merged = [b for b in bars if b["date"] >= STORE_START and b["date"] in idx_map]
    idx_aligned = [idx_map[b["date"]] for b in merged]
    n = 0
    for target_idx, bar in enumerate(merged):
        sm = share_map.get(bar["date"])
        sdp = sm["delta_pct"] if sm else None
        result = analyze_single_etf(merged, idx_aligned, sdp, target_idx)
        if result is None:
            continue
        upsert_daily(bar["date"], CODE, result)
        if sm and sm.get("shares_yi") is not None:
            update_share_data(
                bar["date"],
                CODE,
                sm["shares_yi"],
                sm["delta_yi"],
                sm["delta_pct"],
                sm["sp"],
            )
        n += 1
        if (target_idx + 1) % 400 == 0:
            print(
                f"[HS300] 指标 {bar['date']} ({target_idx + 1}/{len(merged)})",
                flush=True,
            )
    print(f"[HS300] 指标写入 {n} 行", flush=True)
    return n


def recalc_segment() -> int:
    """镜像 recalc.py: 2013-01-01~2018-12-31 重算 dp/cp/signal。"""
    rows = list(reversed(get_by_code(CODE, STORE_START, END)))
    updated = 0
    for idx, r in enumerate(rows):
        vp = r.get("vol_prob")
        if vp is None:
            continue
        t5_etf = 0.0
        if idx >= 4 and rows[idx - 4].get("close_price"):
            t5_etf = (r["close_price"] / rows[idx - 4]["close_price"] - 1) * 100
        t5_idx = 0.0
        if idx >= 4:
            acc = 1.0
            for j in range(idx - 3, idx + 1):
                acc *= 1 + (rows[j].get("idx_chg") or 0) / 100
            t5_idx = (acc - 1) * 100
        dp = calc_direction_probability(
            r.get("change_pct") or 0,
            t5_etf,
            t5_idx,
            r.get("volume_ratio") or 0,
            r.get("idx_chg") or 0,
            r.get("price_position"),
        )
        cp = calc_composite_probability(
            vp, dp, r.get("share_prob"), r.get("price_position")
        )
        update_direction_signal(r["date"], CODE, round(dp, 1), cp, classify_signal(cp))
        updated += 1
    print(f"[HS300] 重算 {updated} 行", flush=True)
    return updated


def main() -> None:
    bars = fetch_kline(CODE, start_date=KL_START, end_date=END)
    idx_bars = fetch_kline(INDEX, start_date=KL_START, end_date=END)
    print(f"[HS300] K线 {len(bars)} 根 / 指数 {len(idx_bars)} 根", flush=True)
    dates = [b["date"] for b in bars if SHARES_START <= b["date"] <= END]
    share_map = backfill_shares(dates)
    backfill_rows(bars, idx_bars, share_map)
    recalc_segment()


if __name__ == "__main__":
    main()
