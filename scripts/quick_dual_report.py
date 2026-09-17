"""双标的共振与买卖点速览(临时分析脚本)。

读取本地库, 输出 515880(通信设备) 与 588000(科创50) 的:
- 最新交易日行情: 收盘/涨跌/量比/价格位置/成交额
- 五灯共振明细与综合概率
- 专属策略(正式版/Beta)最新买卖点与持仓状态
- 关键均线与区间统计
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from resonance.analysis.core import INDICATORS, compute_resonance  # noqa: E402
from base.analysis.sentiment.core import enrich_turnover  # noqa: E402
from base.analysis.strategy.router import compute_trades  # noqa: E402
from base.config import ETFS  # noqa: E402
from base.store.daily_repo import get_by_code  # noqa: E402
from base.store.sentiment_repo import get_margin_series, get_turnover_series  # noqa: E402

TARGETS = ["515880", "588000"]

STATE_ICON = {"red": "红", "green": "绿", "gray": "灰"}


def _asc(code: str) -> list[dict]:
    return list(reversed(get_by_code(code)))


def _ma(rows: list[dict], n: int) -> float | None:
    closes = [float(r["close_price"]) for r in rows[-n:] if r.get("close_price") is not None]
    return sum(closes) / len(closes) if len(closes) == n else None


def _pct_change(rows: list[dict], n: int) -> float | None:
    cs = [float(r["close_price"]) for r in rows if r.get("close_price") is not None]
    if len(cs) <= n:
        return None
    return (cs[-1] / cs[-1 - n] - 1) * 100


def _range(rows: list[dict], n: int) -> tuple[float, float]:
    seg = [float(r["close_price"]) for r in rows[-n:] if r.get("close_price") is not None]
    return min(seg), max(seg)


def report(
    code: str,
    rows: list[dict],
    turnover: list[dict],
    margin: list[dict],
    kc_idx_rows: list[dict] | None = None,
) -> None:
    name = ETFS[code]["name"]
    idx = ETFS[code]["idx"]
    print("=" * 68)
    print(f"{name} ({code})  标的指数: {idx}")
    print("=" * 68)

    last = rows[-1]
    close = float(last["close_price"])
    print(f"数据截至 {last['date']}  收盘 {close:.3f}")

    for label, n in (("近5日", 5), ("近20日", 20), ("近60日", 60)):
        chg = _pct_change(rows, n)
        if chg is not None:
            print(f"  {label}涨跌: {chg:+.2f}%")
    for n in (5, 10, 20, 60):
        ma = _ma(rows, n)
        if ma:
            pos = "上方" if close > ma else "下方"
            print(f"  MA{n:<3} {ma:8.3f}   收盘在其{pos} ({(close / ma - 1) * 100:+.2f}%)")
    lo, hi = _range(rows, 60)
    print(f"  60日区间 {lo:.3f} ~ {hi:.3f}  当前位置 {(close - lo) / (hi - lo) * 100:.1f}%")
    print(f"  量比 {last.get('volume_ratio')}  价格位置 {last.get('position_pct')}  综合概率 {last.get('composite_prob')}")
    if last.get("shares_delta_yi") is not None:
        print(f"  份额变动 {last['shares_delta_yi']:+.4f} 亿")

    r = compute_resonance(code, rows, turnover, margin)
    print(f"\n  【共振判定】{r['verdict']}  红{r['red_count']}/绿{r['green_count']}/灰{r['gray_count']}")
    for ind in r["indicators"]:
        print(f"    [{STATE_ICON.get(ind['state'], '?')}] {ind['name']}: {ind['display']}  ({ind['note']})")

    versions = ["stable"]
    if code == "588000":
        versions.append("beta")
    for version in versions:
        try:
            res = compute_trades(code, rows, kc_idx_rows=kc_idx_rows, version=version)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  【{version}】生成失败: {exc}")
            continue
        trades = res.get("trades", [])
        print(f"\n  【策略 {version}】买卖点 {len(trades)} 笔")
        for t in trades[-6:]:
            print(f"    {t['date']}  {t['action']:<10} {t['price']:.3f}  {t.get('reason', '')[:60]}")
        print(f"    持仓状态: {res.get('holding')}")
        print(f"    指标: {res.get('metrics')}")
    print()


def main() -> None:
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    kc_idx = _asc("589680")
    for code in TARGETS:
        report(code, _asc(code), turnover, margin, kc_idx)


if __name__ == "__main__":
    main()
