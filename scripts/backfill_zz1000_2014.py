# mypy: ignore-errors
"""中证1000 (512100) 数据延伸回填: 2014-10-17(指数发布日) 起。

512100 腾讯K线仅到 2016-11-04, 更早用中证1000指数(000852, 同接口 2014-10-17
起)按上市首日收盘比缩放为价格代理(分红未计, 误差<2%); 份额上交所接口
2016-11 起可得; 两市成交额与融资余额(akshare 合计)2012 起可得。代理期
shares 全 None, 份额规则降级。幂等可重入, 检查点续传。--skip-shares 可跳份额。
"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "backend")

from base.config import SHARE_WINDOW
from base.fetch.kline import fetch_kline
from base.fetch.sentiment import fetch_margin_series, fetch_turnover_range
from base.fetch.shares import fetch_shares_sse
from base.store.daily_repo import (
    get_by_code,
    update_direction_signal,
    update_share_data,
    upsert_daily,
)
from base.store.sentiment_repo import upsert_margin, upsert_turnover
from resonance.analysis.composite import analyze_single_etf, calc_composite_probability
from resonance.analysis.factors import (
    calc_direction_probability,
    calc_price_position,
    calc_share_probability,
    calc_share_probability_dual,
    calc_volume_probability,
    classify_signal,
    classify_trade_direction,
)

CODE = "512100"
INDEX = "000852"
PROXY_START = "2014-10-17"  # 中证1000 指数发布日
ETF_START = "2016-11-04"  # 腾讯 512100 首日
END = "2018-12-31"
SLEEP_SEC = 0.4  # 份额逐日限速


def _chg(prev_close: float | None, close: float, open_: float) -> float:
    base = prev_close if prev_close is not None else open_
    return (close - base) / base * 100 if base else 0.0


def _relaxed_analyze(
    kline: list[dict], idx_kline: list[dict], sdp: float | None, target_idx: int
) -> dict | None:
    """analyze_single_etf 的 2-bar 放宽版: 预热段也产出指标(生产版要求 20-bar)。"""
    if len(kline) < 2:
        return None
    target = kline[target_idx]
    window = kline[max(0, target_idx - 19) : target_idx + 1]
    ma20 = sum(k["volume"] for k in window) / len(window)
    if ma20 <= 0:
        return None
    volume_ratio = target["volume"] / ma20
    vp = calc_volume_probability(volume_ratio)
    chg = (
        (target["close"] - target["open"]) / target["open"] * 100
        if target["open"]
        else 0.0
    )

    ib = idx_kline[target_idx] if idx_kline and target_idx < len(idx_kline) else None
    idx_chg = (
        (ib["close"] - ib["open"]) / ib["open"] * 100 if ib and ib["open"] else 0.0
    )
    pp = calc_price_position(kline, target_idx)
    t5e = (
        0.0
        if target_idx < 4 or not kline[target_idx - 4]["close"]
        else (target["close"] / kline[target_idx - 4]["close"] - 1) * 100
    )
    t5i = 0.0
    if ib and target_idx >= 4 and idx_kline[target_idx - 4]["close"]:
        t5i = (ib["close"] / idx_kline[target_idx - 4]["close"] - 1) * 100
    dp = calc_direction_probability(chg, t5e, t5i, volume_ratio, idx_chg, pp)
    td = classify_trade_direction(pp, volume_ratio)
    sp = calc_share_probability(sdp)
    prev_close = kline[target_idx - 1]["close"] if target_idx > 0 else None
    cp = calc_composite_probability(vp, dp, sp, pp)
    return {
        "date": target["date"],
        "open": target["open"],
        "close": target["close"],
        "high": target["high"],
        "low": target["low"],
        "change_pct": round(_chg(prev_close, target["close"], target["open"]), 2),
        "volume": target["volume"],
        "volume_ma20": round(ma20, 2),
        "volume_ratio": round(volume_ratio, 3),
        "vol_prob": round(vp, 1),
        "dir_prob": round(dp, 1),
        "share_prob": round(sp, 1) if sp is not None else None,
        "composite_prob": cp,
        "signal_level": classify_signal(cp),
        "idx_chg": round(idx_chg, 2),
        "price_position": pp,
        "trade_direction": td,
    }


def fetch_klines() -> tuple[list[dict], list[dict]]:
    """返回 (合并后ETF价序列, 指数序列), 代理段按 C 缩放。"""
    idx = fetch_kline(INDEX, start_date=PROXY_START, end_date=END)
    etf = fetch_kline(CODE, start_date=ETF_START, end_date=END)
    idx_map = {b["date"]: b for b in idx}
    etf_map = {b["date"]: b for b in etf}
    seam = min(etf_map)
    c = etf_map[seam]["close"] / idx_map[seam]["close"]
    print(f"[ZZ1000] 指数 {len(idx)} 根 / ETF {len(etf)} 根, C={c:.8f}", flush=True)
    merged: list[dict] = []
    for d in sorted(idx_map):
        if d >= seam:
            bar = etf_map.get(d)
            if bar is None:
                continue
        else:
            b = idx_map[d]
            bar = {
                k: (v * c if k in ("open", "close", "high", "low") else v)
                for k, v in b.items()
            }
        merged.append(bar)
    return merged, idx


def _load_shares_checkpoint() -> tuple[dict[str, dict], float | None, list[float]]:
    import json

    try:
        with open("/tmp/zz1000_shares_checkpoint.json", encoding="utf-8") as f:
            data = json.load(f)
        return data["share_map"], data.get("prev_yi"), data.get("hist", [])
    except (FileNotFoundError, KeyError, ValueError):
        return {}, None, []


def _save_shares_checkpoint(
    share_map: dict[str, dict], prev_yi: float | None, hist: list[float]
) -> None:
    import json

    with open("/tmp/zz1000_shares_checkpoint.json", "w", encoding="utf-8") as f:
        json.dump({"share_map": share_map, "prev_yi": prev_yi, "hist": hist}, f)


def backfill_shares(merged: list[dict]) -> dict[str, dict]:
    """2016-11-04 起逐日拉上交所份额, 检查点续传, 返回 {date: share dict}。"""
    dates = [b["date"] for b in merged if b["date"] >= ETF_START]
    existing = {
        r["date"]
        for r in get_by_code(CODE, ETF_START, END)
        if r.get("shares_yi") is not None
    }
    share_map, prev_yi, hist = _load_shares_checkpoint()
    share_map = {d: v for d, v in share_map.items() if d not in existing}
    if share_map:
        prev_dates = sorted(share_map)
        prev_yi = share_map[prev_dates[-1]]["shares_yi"]
        hist = [share_map[d]["shares_yi"] for d in prev_dates[-SHARE_WINDOW:]]
        print(f"[ZZ1000] 检查点续传 {len(share_map)} 日", flush=True)
    for i, d in enumerate(dates):
        if d in existing or d in share_map:
            continue
        yi = fetch_shares_sse(d).get(CODE)
        if yi is None:
            print(f"[ZZ1000] 份额 {d} 无数据")
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
        if (i + 1) % 60 == 0:
            print(f"[ZZ1000] 份额 {d} ({i + 1}/{len(dates)})", flush=True)
            _save_shares_checkpoint(share_map, prev_yi, hist)
        time.sleep(SLEEP_SEC)
    _save_shares_checkpoint(share_map, prev_yi, hist)
    print(f"[ZZ1000] 份额拉取完成 {len(share_map)} 日")
    return share_map


def backfill_sentiment() -> None:
    """两市成交额(按年分块) + 融资余额(合计, 一次全量)回填。"""
    chunks: list[tuple[str, str]] = [
        ("2014-10-17", "2014-12-31"),
        ("2015-01-01", "2015-12-31"),
        ("2016-01-01", "2016-12-31"),
        ("2017-01-01", "2017-12-31"),
        ("2018-01-01", "2018-12-31"),
    ]
    n_t = 0
    for s, e in chunks:
        rows = fetch_turnover_range(s, e)
        upsert_turnover(rows)
        n_t += len(rows)
        print(f"[ZZ1000] 成交额 {s}~{e}: {len(rows)} 行")
        time.sleep(1)
    margin = [
        r
        for r in fetch_margin_series(PROXY_START, END)
        if PROXY_START <= r["date"] <= END
    ]
    upsert_margin(margin)
    print(f"[ZZ1000] 成交额 {n_t} 行 / 融资 {len(margin)} 行 入库")


def backfill_rows(
    merged: list[dict], idx: list[dict], share_map: dict[str, dict]
) -> int:
    """逐日分析指标并写入 etf_daily(预热段用放宽版, 之后用生产版)。"""
    idx_map = {b["date"]: b for b in idx}
    merged = [b for b in merged if b["date"] in idx_map]
    idx_aligned = [idx_map[b["date"]] for b in merged]
    n = 0
    for target_idx, bar in enumerate(merged):
        d = bar["date"]
        sm = share_map.get(d)
        sdp = sm["delta_pct"] if sm else None
        result = (
            analyze_single_etf(merged, idx_aligned, sdp, target_idx)
            if target_idx >= 19
            else _relaxed_analyze(merged, idx_aligned, sdp, target_idx)
        )
        if result is None:
            continue
        upsert_daily(d, CODE, result)
        if sm and sm.get("shares_yi") is not None:
            update_share_data(
                d, CODE, sm["shares_yi"], sm["delta_yi"], sm["delta_pct"], sm["sp"]
            )
        n += 1
    print(f"[ZZ1000] 指标写入 {n} 行")
    return n


def recalc_extended() -> int:
    """镜像 recalc.py: 对 2014-10-17~2018-12-31 重算 dp/cp/signal(份额双基准后对齐)。"""
    rows = list(reversed(get_by_code(CODE, PROXY_START, END)))
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
        level = classify_signal(cp)
        update_direction_signal(r["date"], CODE, round(dp, 1), cp, level)
        updated += 1
    return updated


def main() -> None:
    skip_shares = "--skip-shares" in sys.argv
    merged, idx = fetch_klines()
    backfill_sentiment()
    share_map = {} if skip_shares else backfill_shares(merged)
    backfill_rows(merged, idx, share_map)
    recalc_extended()


if __name__ == "__main__":
    main()
