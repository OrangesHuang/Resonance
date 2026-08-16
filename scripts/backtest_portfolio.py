"""组合回测(薄壳): 复用 backend/portfolio/api.py。

规则(等权满仓调度):
- 首个买入信号 → 全仓买入即满仓
- 新买入信号 → 与现有持仓按总权益严格等权(1/m):
  TRIM 超配 → 建新仓 → REFILL 低配, 完成后现金 ≈ 0
- 卖出信号 → 整仓清掉回现金, 剩余持仓不再平衡; 回款待下一个买点并入分配池
- 信号次日按当日收盘价成交
- 起算: 2021-01-01(此前不计), 起始 100% 现金
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from base.store.calendar_repo import get_trade_days
from base.store.daily_repo import get_by_code
from portfolio.analysis.simulator import simulate
from portfolio.api import ALL_CODES, TRADE_START, _load_trades

INIT_CAPITAL = 1_000_000


def main() -> None:
    trades_by_code = _load_trades()

    price_map: dict[str, dict[str, float]] = {}
    for code in ALL_CODES:
        rows = {r["date"]: r.get("close_price") for r in get_by_code(code)}
        for t in trades_by_code[code]:
            rows.setdefault(t["date"], t["price"])
        price_map[code] = rows

    max_kline_date = max(d for m in price_map.values() for d in m)
    dates = [d for d in get_trade_days(TRADE_START) if d <= max_kline_date]
    result = simulate(trades_by_code, price_map, dates)

    scale = INIT_CAPITAL
    print(f"总收益: {result['total_return_pct']:+.1f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.1f}%")
    print(
        f"空仓日期: {result['empty_days']} 天 ({result['empty_days_pct']:.1f}% 交易日)"
    )
    print(
        f"期末权益: {result['final_equity'] * scale:,.0f} 元 (净值 {result['final_equity']:.4f})"
    )
    print(
        f"信号数: {sum(len(v) for v in trades_by_code.values())} 笔, "
        f"组合操作 {len(result['trade_log'])} 次"
    )
    print()
    print("=== 组合操作明细(信号次日成交) ===")
    for t in result["trade_log"]:
        sig = f"信号 {t['signal_date']}" if t.get("signal_date") else ""
        print(
            f"  {t['date']} {sig:>12} {t['code']} {t['kind']:<7} "
            f"@{t['price']} 金额{t['amount'] * scale:,.0f} 元 "
            f"权重{t['weight_pct']:.1f}%"
        )
    print()
    print("=== 权益曲线(每季末) ===")
    prev_q = ""
    last_h = None
    for h in result["history"]:
        q = h["date"][:4] + "Q" + str((int(h["date"][5:7]) - 1) // 3 + 1)
        if q != prev_q:
            if last_h is not None:
                print(
                    f"  {prev_q} 末: {last_h['equity'] * scale:,.0f} 元 (仓位 {last_h['position_pct']:.0f}%)"
                )
            prev_q = q
        last_h = h
    if last_h is not None:
        print(
            f"  {prev_q} 末: {last_h['equity'] * scale:,.0f} 元 (仓位 {last_h['position_pct']:.0f}%)"
        )
    print(f"  末: {result['history'][-1]['equity'] * scale:,.0f} 元")


if __name__ == "__main__":
    main()
