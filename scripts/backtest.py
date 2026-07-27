"""共振策略回测 CLI（薄壳，逻辑在 analysis/strategy.py）"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "backend"))

import argparse
import json
from typing import Optional

from config import STRATEGY_CODE
from store.database import init_db
from store.daily_repo import get_by_code
from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import enrich_turnover
from analysis.resonance import compute_resonance
from analysis.strategy import run_backtest


def _load_data(code: str, start: Optional[str], end: Optional[str]):
    etf_rows = get_by_code(code, start, end)
    etf_rows.sort(key=lambda r: r["date"])

    turnover_raw = get_turnover_series()
    margin_raw = get_margin_series()
    turnover = enrich_turnover(turnover_raw)

    result = compute_resonance(code, etf_rows, turnover, margin_raw)
    history = result["history"]

    close_by_date = {r["date"]: r["close_price"] for r in etf_rows}
    signals, closes, dates = [], [], []
    for h in history:
        c = close_by_date.get(h["date"])
        if c is None:
            continue
        signals.append({"red": h["red"], "green": h["green"]})
        closes.append(c)
        dates.append(h["date"])
    return signals, closes, dates


def _print_report(result: dict, code: str) -> None:
    m = result["metrics"]
    b = result["benchmark"]
    print(f"\n{'='*60}")
    print(f"  共振仓位策略回测 — {code}")
    print(f"{'='*60}")
    print(f"  回测天数:       {m['days']}")
    print(f"  交易次数:       {m['trade_count']}")
    print(f"  市场暴露:       {m['exposure_pct']}%")
    print(f"{'─'*60}")
    print(f"  {'指标':<12}{'策略':>12}{'买入持有':>12}")
    print(f"{'─'*60}")
    print(f"  {'总收益%':<12}{m['total_return']:>12.2f}{b['total_return']:>12.2f}")
    print(f"  {'年化收益%':<12}{m['annual_return']:>12.2f}{b['annual_return']:>12.2f}")
    print(f"  {'年化波动%':<12}{m['annual_vol']:>12.2f}{b['annual_vol']:>12.2f}")
    print(f"  {'Sharpe':<12}{m['sharpe']:>12.3f}{b['sharpe']:>12.3f}")
    print(f"  {'最大回撤%':<12}{m['max_drawdown']:>12.2f}{b['max_drawdown']:>12.2f}")
    print(f"{'='*60}")

    if result["trades"]:
        print(f"\n  逐笔交易 ({len(result['trades'])} 笔):")
        print(f"  {'日期':<12}{'动作':<8}{'仓位变化':<12}{'红/绿':<8}{'原因'}")
        print(f"  {'─'*56}")
        for t in result["trades"]:
            pos_chg = f"{t['from_pos']:.0%}→{t['to_pos']:.0%}"
            rg = f"{t['red']}/{t['green']}"
            print(f"  {t['date']:<12}{t['action']:<8}{pos_chg:<12}{rg:<8}{t['reason']}")
    print()


def _save_csv(result: dict, path: str) -> None:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "equity", "position"])
        for pt in result["equity_curve"]:
            w.writerow([pt["date"], pt["equity"], pt["position"]])
    print(f"  [CSV] 权益曲线已写入 {path}")


def _save_plot(result: dict, path: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [PLOT] matplotlib 不可用,跳过绘图")
        return

    curve = result["equity_curve"]
    xs = [p["date"] for p in curve]
    ys = [p["equity"] for p in curve]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(xs, ys, linewidth=1)
    ax.set_title("Resonance Strategy Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    step = max(1, len(xs) // 10)
    ax.set_xticks(range(0, len(xs), step))
    ax.set_xticklabels([xs[i] for i in range(0, len(xs), step)], rotation=45, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"  [PLOT] 权益曲线已写入 {path}")


def main():
    parser = argparse.ArgumentParser(description="共振策略回测")
    parser.add_argument("--code", default=STRATEGY_CODE)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--csv", default=None, metavar="PATH", help="导出权益曲线 CSV")
    parser.add_argument("--plot", default=None, metavar="PATH", help="导出权益曲线图")
    args = parser.parse_args()

    init_db()
    signals, closes, dates = _load_data(args.code, args.start, args.end)

    if len(signals) < 10:
        print(f"[ERROR] 有效信号仅 {len(signals)} 天,不足以回测")
        sys.exit(1)

    print(f"[BACKTEST] {args.code} | {dates[0]} ~ {dates[-1]} | {len(signals)} 天")
    result = run_backtest(signals, closes, dates)

    if args.json:
        print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
        print(json.dumps(result["benchmark"], ensure_ascii=False, indent=2))
    else:
        _print_report(result, args.code)

    if args.csv:
        _save_csv(result, args.csv)
    if args.plot:
        _save_plot(result, args.plot)


if __name__ == "__main__":
    main()
