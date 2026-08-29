#!/usr/bin/env python3
"""中证1000 波段策略 CLI —— 直读本地数据库, 输出当前买卖信号与近期交易。

用法:
  python cli/band.py              # 当前信号 + 最近8笔交易
  python cli/band.py --signals    # 只输出今日各规则触发状态
  python cli/band.py --json       # 结构化输出(供外部 Agent)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from store.daily_repo import get_by_code  # noqa: E402
from strategy.band import run_band_strategy, TRADE_START  # noqa: E402
from strategy.band import (  # noqa: E402
    S1_CHG, S1_PP, S2_VR, S2_DD20, S2_MA_SLOPE, BREAK_DAYS, BREAK_MIN_HOLD,
    B1_CHG, B1_PP, B1_SD, B2_DD60_LO, B2_DD60_HI, B2_VR, B2_SD5, B3_SD_DAYS, B3_VR,
)
from strategy.band import _ma, _dd, _ma_slope, _sd_sum  # noqa: E402


def _load():
    rows = list(reversed(get_by_code("512100")))
    return [r for r in rows if r.get("composite_prob") is not None]


def _rule_status(rows) -> dict:
    r = rows[-1]
    closes = [x["close_price"] for x in rows]
    i = len(rows) - 1
    chg, pp, vr = r["change_pct"], r["price_position"], r["volume_ratio"]
    sd = r.get("shares_delta_yi")
    sd5 = _sd_sum(rows, i, 5)
    m250 = _ma(closes, i, 250)
    slope250 = _ma_slope(closes, i, 250)
    dd20, dd60 = _dd(closes, i, 20), _dd(closes, i, 60)
    low5 = min(closes[max(0, i - BREAK_DAYS) : i])
    return {
        "date": r["date"], "close": closes[i], "chg": chg, "pp": pp, "vr": vr,
        "sd": sd, "sd5": sd5, "m250": m250, "ma_slope": slope250,
        "dd20": dd20, "dd60": dd60, "low5": low5,
        "S1_高位涨3%": bool(chg >= S1_CHG and pp is not None and pp >= S1_PP),
        "S2_缩量反弹未修复": bool(vr <= S2_VR and dd20 <= -S2_DD20 and slope250 is not None and slope250 <= S2_MA_SLOPE),
        "S3_破位": bool(close := closes[i]) and close < low5,
        "B1_恐慌承接": bool(chg <= B1_CHG and pp is not None and pp <= B1_PP and (sd or 0) >= B1_SD),
        "B2_中继回踩": bool(
            m250 is not None and slope250 is not None and slope250 > 0 and closes[i] > m250
            and B2_DD60_LO <= dd60 <= B2_DD60_HI and vr <= B2_VR
            and (sd5 if sd5 is not None else 0) >= B2_SD5
        ),
        "B3_右侧确认": bool(
            m250 is not None and closes[i] > m250 and vr >= B3_VR
            and sd5 is not None and sd5 >= B3_SD_DAYS * 1.0
        ),
    }


def _fmt(s: dict) -> str:
    return (
        f"=== 波段信号 {s['date']} (收盘 {s['close']:.3f}) ===\n"
        f"  涨跌 {s['chg']:+.2f}% | pp {s['pp']:.0f} | 量比 {s['vr']:.2f} | 当日申购 {s['sd']} | 近5日 {s['sd5']}\n"
        f"  MA250 {s['m250']:.3f}(斜率 {s['ma_slope'] if s['ma_slope'] is None else f"{s['ma_slope']:+.1f}%"}) | "
        f"前20日回撤 {s['dd20']:.0f}% | 距60日高 {s['dd60']:.0f}% | 近5日低 {s['low5']:.3f}\n"
        + "\n".join(f"  {'✅' if v else '⬜'} {k}" for k, v in s.items() if k not in
            ("date", "close", "chg", "pp", "vr", "sd", "sd5", "m250", "ma_slope", "dd20", "dd60", "low5"))
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", action="store_true", help="只输出规则触发状态")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    args = ap.parse_args()
    rows = _load()
    if args.json:
        res = run_band_strategy(rows)
        print(json.dumps({"signals": _rule_status(rows), "trades": res["trades"][-8:]}, ensure_ascii=False))
        return
    print(_fmt(_rule_status(rows)))
    if args.signals:
        return
    res = run_band_strategy(rows)
    print(f"\n=== 持仓: {'是' if res['holding'] else '否'} | 最近交易 ===")
    for t in res["trades"][-8:]:
        print(f"  {t['date']} {t['action']:4} @{t['price']:.3f}  {t['reason']}")


if __name__ == "__main__":
    main()
