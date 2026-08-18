# mypy: ignore-errors
"""中证1000 (512100) 数据再延伸: 2005-01-04(中证1000 基日翌日) 起。

源: 中证指数官网 csindex.com.cn 官方回溯点位(index-perf 接口, 一次拉全
2005-01-04~2014-10-16), 按上市首日收盘比 C 缩放接续 2014-10-17 起的
腾讯数据(scripts/backfill_zz1000_2014.py 已回填段)。2005 年为预热年份
(MA250 窗口), 观察重点 2006 起(06-07 大牛/08 崩盘/09 反弹/10-14 慢熊)。
份额: 2016-11 前无 ETF, 全 None; 成交额 2006 起(雪球/东财); 融资余额
2010-03-31(两融试点)~2012-09-26 用上交所源(source=sse), 与合计源有口径
接缝(仅影响 2011-2013 的融资分位, 已在 docstring 记录)。
幂等可重入。仅本地运行, 不上生产。--skip-shares 参数为兼容保留(本段无份额)。
"""

from __future__ import annotations

import sys
import time

import requests

sys.path.insert(0, "backend")

from base.fetch.kline import fetch_kline
from base.fetch.sentiment import fetch_turnover_range
from base.store.daily_repo import get_by_code, update_direction_signal, upsert_daily
from base.store.sentiment_repo import upsert_margin, upsert_turnover
from resonance.analysis.composite import analyze_single_etf, calc_composite_probability
from resonance.analysis.factors import (
    calc_direction_probability,
    calc_price_position,
    calc_share_probability,
    calc_volume_probability,
    classify_signal,
    classify_trade_direction,
)

CODE = "512100"
INDEX = "000852"
CS_START = "2005-01-04"  # 中证1000 基日(2004-12-31=1000)后首个交易日
CS_END = "2014-10-16"  # 腾讯 000852 首日(2014-10-17)前一天, 无缝接续
CS_URL = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
CS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.csindex.com.cn/",
}
MARGIN_START = "2010-03-31"  # 两融试点首日
MARGIN_END = "2012-09-26"  # akshare 合计源起点(2012-09-27)前一天


def _chg(prev_close: float | None, close: float, open_: float) -> float:
    base = prev_close if prev_close is not None else open_
    return (close - base) / base * 100 if base else 0.0


def _relaxed_analyze(
    kline: list[dict], idx_kline: list[dict], target_idx: int
) -> dict | None:
    """analyze_single_etf 的 2-bar 放宽版: 2005-01 预热段也产出指标。"""
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

    def t5(bars: list[dict], j: int) -> float:
        if j < 4:
            return 0.0
        base = bars[j - 4]["close"]
        return (bars[j]["close"] / base - 1) * 100 if base else 0.0

    ib = idx_kline[target_idx] if idx_kline and target_idx < len(idx_kline) else None
    idx_chg = (
        (ib["close"] - ib["open"]) / ib["open"] * 100 if ib and ib["open"] else 0.0
    )
    pp = calc_price_position(kline, target_idx)
    dp = calc_direction_probability(
        chg, t5(kline, target_idx), t5(idx_kline, target_idx), volume_ratio, idx_chg, pp
    )
    td = classify_trade_direction(pp, volume_ratio)
    sp = calc_share_probability(None)
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
        "share_prob": None,
        "composite_prob": cp,
        "signal_level": classify_signal(cp),
        "idx_chg": round(idx_chg, 2),
        "price_position": pp,
        "trade_direction": td,
    }


def fetch_csindex() -> list[dict]:
    """中证指数官网回溯点位(分 4 段拉, 每段一次请求)。"""
    out: list[dict] = []
    chunks = [
        ("20050104", "20071231"),
        ("20080101", "20101231"),
        ("20110101", "20131231"),
        ("20140101", "20141016"),
    ]
    for s, e in chunks:
        r = requests.get(
            CS_URL,
            params={"indexCode": INDEX, "startDate": s, "endDate": e},
            headers=CS_HEADERS,
            timeout=30,
        )
        rows = (r.json() or {}).get("data") or []
        for row in rows:
            td = row["tradeDate"]
            out.append(
                {
                    "date": f"{td[:4]}-{td[4:6]}-{td[6:]}",
                    "open": float(row["open"]),
                    "close": float(row["close"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "volume": float(row.get("tradingVol") or 0),
                }
            )
        print(f"[ZZ06] csindex {s}~{e}: {len(rows)} 行", flush=True)
        time.sleep(1)
    return out


def fetch_proxy_bars() -> list[dict]:
    """官网回溯 × C 缩放 → 价格代理K线(2005-01-04~2014-10-16)。"""
    bars = fetch_csindex()
    if not bars:
        return []
    seam_etf = fetch_kline(CODE, start_date="2016-11-04", end_date="2016-11-04")
    seam_idx = fetch_kline(INDEX, start_date="2016-11-04", end_date="2016-11-04")
    c = seam_etf[0]["close"] / seam_idx[0]["close"]
    print(f"[ZZ06] 缩放系数 C={c:.8f}", flush=True)
    for b in bars:
        for k in ("open", "close", "high", "low"):
            b[k] = round(b[k] * c, 6)
    return bars


def backfill_sentiment() -> None:
    """成交额 2006-2014(按年分块) + 上交所融资 2010-03~2012-09。"""
    chunks = [
        ("2006-01-01", "2007-12-31"),
        ("2008-01-01", "2009-12-31"),
        ("2010-01-01", "2011-12-31"),
        ("2012-01-01", "2014-10-16"),
    ]
    n_t = 0
    for s, e in chunks:
        rows = fetch_turnover_range(s, e)
        upsert_turnover(rows)
        n_t += len(rows)
        print(f"[ZZ06] 成交额 {s}~{e}: {len(rows)} 行", flush=True)
        time.sleep(1)
    import akshare as ak

    df = ak.stock_margin_sse(
        start_date=MARGIN_START.replace("-", ""), end_date=MARGIN_END.replace("-", "")
    )
    margin = []
    if df is not None and not df.empty and "融资余额" in df.columns:
        for _, row in df.iterrows():
            date = str(row["信用交易日期"])[:10]
            try:
                fin = round(float(row.get("融资余额") or 0), 4)
                loan = round(float(row.get("融券余量金额") or 0), 4)
                buy = round(float(row.get("融资买入额") or 0), 4)
            except (TypeError, ValueError):
                continue
            margin.append(
                {
                    "date": date,
                    "fin_balance_yi": fin,
                    "loan_balance_yi": loan,
                    "fin_buy_yi": buy,
                    "source": "sse",
                }
            )
    upsert_margin(sorted(margin, key=lambda r: r["date"]))
    print(f"[ZZ06] 成交额 {n_t} 行 / 融资 {len(margin)} 行 入库", flush=True)


def backfill_rows(bars: list[dict]) -> int:
    """逐日分析并写入 etf_daily(2005-01-04~2014-10-16)。"""
    n = 0
    for target_idx, bar in enumerate(bars):
        if target_idx >= 19:
            result = analyze_single_etf(bars, bars, None, target_idx)
        else:
            result = _relaxed_analyze(bars, bars, target_idx)
        if result is None:
            continue
        upsert_daily(bar["date"], CODE, result)
        n += 1
        if (target_idx + 1) % 400 == 0:
            print(
                f"[ZZ06] 指标 {bar['date']} ({target_idx + 1}/{len(bars)})", flush=True
            )
    print(f"[ZZ06] 指标写入 {n} 行", flush=True)
    return n


def recalc_segment() -> int:
    """镜像 recalc.py: 对 2005-01-04~2014-10-16 重算 dp/cp/signal。"""
    rows = list(reversed(get_by_code(CODE, CS_START, CS_END)))
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
    print(f"[ZZ06] 重算 {updated} 行", flush=True)
    return updated


def main() -> None:
    bars = fetch_proxy_bars()
    if not bars:
        print("[ZZ06] 官网数据为空, 终止")
        return
    backfill_sentiment()
    backfill_rows(bars)
    recalc_segment()


if __name__ == "__main__":
    main()
