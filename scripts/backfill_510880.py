# mypy: ignore-errors
"""上证红利ETF (510880) 回填: 腾讯K线 2007 上市起 + 上证红利指数(000015)对齐。

510880 不在系统 ETF 清单(ETFS), 数据库无数据; 为对比 515080(中证红利)
一次性回填。份额未拉(全 None, 份额规则降级); 量价/分位指标照常计算。
幂等: upsert 按日覆盖, 重复运行安全。
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, "backend")

from base.fetch.kline import fetch_kline
from base.store.daily_repo import get_by_code, upsert_daily
from resonance.analysis.composite import analyze_single_etf
from resonance.analysis.factors import (
    calc_price_position,
    calc_volume_probability,
    classify_trade_direction,
)

CODE = "510880"
INDEX = "000015"
START = "2007-01-01"


def _relaxed_analyze(kline: list[dict], idx_kline: list[dict], target_idx: int) -> dict | None:
    """预热段(<20 bar)放宽版: 只产出版本能用的量价指标。"""
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
    td = classify_trade_direction(pp, volume_ratio)
    return {
        "close_price": round(target["close"], 4),
        "change_pct": round(chg, 3),
        "volume": int(target["volume"]),
        "volume_ma20": round(ma20, 2),
        "volume_ratio": round(volume_ratio, 3),
        "vol_prob": round(vp, 1),
        "dir_prob": None,
        "idx_chg": round(idx_chg, 3),
        "price_position": round(pp, 1) if pp is not None else None,
        "trade_direction": td,
        "open_price": round(target["open"], 4),
        "high_price": round(target["high"], 4),
        "low_price": round(target["low"], 4),
    }


def main() -> None:
    end = datetime.now().strftime("%Y-%m-%d")
    bars = fetch_kline(CODE, start_date=START, end_date=end)
    idx = fetch_kline(INDEX, start_date=START, end_date=end)
    if not bars:
        print("[510880] K线为空")
        return
    print(f"[510880] K线 {len(bars)} 根 / 指数 {len(idx) if idx else 0} 根")
    idx_map = {b["date"]: b for b in idx or []}
    bars = [b for b in bars if b["date"] in idx_map]
    idx_aligned = [idx_map[b["date"]] for b in bars]

    n = 0
    for target_idx, bar in enumerate(bars):
        d = bar["date"]
        if target_idx >= 19:
            result = analyze_single_etf(bars, idx_aligned, None, target_idx)
        else:
            result = _relaxed_analyze(bars, idx_aligned, target_idx)
        if result is None:
            continue
        upsert_daily(d, CODE, result)
        n += 1
    print(f"[510880] 指标写入 {n} 行")

    # 幂等校验
    rows = get_by_code(CODE, START, end)
    print(f"[510880] 库内 {len(rows)} 行, 范围 {rows[0]['date']}~{rows[-1]['date']}")

    # 同步对比标的: 515080 若有缺口补跑(不强制)


if __name__ == "__main__":
    main()
