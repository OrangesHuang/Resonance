"""924 之后 8 标的组合回测(薄壳): 复用 backend/analysis/portfolio.py。

规则:
- 每个标的发出买入信号 → 至少持有 12.5% 仓位(1 单位)
- 若还有余钱 → 仓位可升至 25%(2 单位)
- 一旦其他标的发出买入信号 → 原有 25% 仓位必须降至 12.5% 释放资金
- 信号次日按当日收盘价成交
- 起算: 2024-10-08(924 之后), 起始 100% 现金
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from api.portfolio import _load_trades, ALL_CODES, TRADE_START
from store.daily_repo import get_by_code, get_trading_dates
from analysis.portfolio import simulate

INIT_CAPITAL = 1_000_000


def main() -> None:
    trades_by_code = _load_trades()

    price_map: dict[str, dict[str, float]] = {}
    for code in ALL_CODES:
        rows = {r["date"]: r.get("close_price") for r in get_by_code(code)}
        for t in trades_by_code[code]:
            rows.setdefault(t["date"], t["price"])
        price_map[code] = rows

    dates = [d for d in get_trading_dates() if d >= TRADE_START]
    result = simulate(trades_by_code, price_map, dates)

    scale = INIT_CAPITAL
    print(f"总收益: {result['total_return_pct']:+.1f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.1f}%")
    print(f"平均仓位: {result['avg_position_pct']:.1f}%")
    print(f"期末权益: {result['final_equity'] * scale:,.0f} 元 (每份 {result['final_equity']:.4f} 元)")
    print(f"信号数: {sum(len(v) for v in trades_by_code.values())} 笔, "
          f"组合操作 {len(result['trade_log'])} 次")
    print()
    print("=== 组合操作明细(信号次日成交) ===")
    for t in result["trade_log"]:
        sig = f"信号 {t['signal_date']}" if t.get("signal_date") else ""
        print(f"  {t['date']} {sig:>12} {t['code']} {t['kind']:<6} "
              f"{t['units']}u @{t['price']} 金额{t['amount'] * t['price'] * scale:,.0f} 元")
    print()
    print("=== 权益曲线(每季末) ===")
    prev_q = ""
    for h in result["history"]:
        q = h["date"][:4] + "Q" + str((int(h["date"][5:7]) - 1) // 3 + 1)
        if q != prev_q:
            print(f"  {q} 末: {h['equity'] * scale:,.0f} 元 (仓位 {h['position_pct']:.0f}%)")
            prev_q = q
    print(f"  末: {result['history'][-1]['equity'] * scale:,.0f} 元")


if __name__ == "__main__":
    main()
