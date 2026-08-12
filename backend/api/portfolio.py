"""组合回测 API: 8 标的统一仓位分配逻辑的净值走势与交易记录。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from config import ETFS
from store.daily_repo import get_by_code, get_trading_dates
from analysis.portfolio import simulate
from analysis.strategy_v3 import run_v3_strategy

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

TRADE_START = "2024-10-08"
INIT_CAPITAL = 1_000_000   # 100 万初始净值
INIT_SHARES = 1_000_000    # 每份 1 元

ALL_CODES = ["510300", "510050", "510500", "512100",
             "515080", "588000", "589680", "159780", "159352"]

KIND_LABEL = {
    "BUY": "买入",
    "TOPUP": "加仓",
    "REDUCE": "减仓",
    "SELL": "卖出",
    "LIQUIDATE": "清仓腾资",
}


def _load_trades(codes: list[str] | None = None) -> dict[str, list[dict]]:
    target_codes = codes if codes else ALL_CODES
    out: dict[str, list[dict]] = {}
    for code in target_codes:
        rows = list(reversed(get_by_code(code)))
        result = run_v3_strategy(rows)
        out[code] = [t for t in result["trades"] if t["date"] >= TRADE_START]
    return out


@router.get("/backtest")
def portfolio_backtest(codes: str | None = Query(None)):
    code_list = codes.split(",") if codes else None
    target_codes = code_list if code_list else ALL_CODES
    trades_by_code = _load_trades(code_list)

    price_map: dict[str, dict[str, float]] = {}
    for code in target_codes:
        rows = {r["date"]: r.get("close_price") for r in get_by_code(code)}
        for t in trades_by_code[code]:
            rows.setdefault(t["date"], t["price"])
        price_map[code] = rows

    dates = [d for d in get_trading_dates() if d >= TRADE_START]
    if not dates:
        dates = sorted({d for m in price_map.values() for d in m})

    result = simulate(trades_by_code, price_map, dates,
                      unit=1.0 / len(target_codes))

    scale = INIT_CAPITAL
    curve = [
        {"date": h["date"],
         "nav": round(h["equity"] * scale, 0),           # 总资产(元)
         "nav_per_share": round(h["equity"], 4),          # 每份净值(元)
         "position_pct": h["position_pct"]}
        for h in result["history"]
    ]
    trade_log = [
        {"date": t["date"], "signal_date": t.get("signal_date", ""),
         "code": t["code"],
         "name": ETFS.get(t["code"], {}).get("name", t["code"]),
         "kind": t["kind"], "kind_label": KIND_LABEL.get(t["kind"], t["kind"]),
         "units": t["units"], "price": t["price"],
         "amount": round(t["amount"] * t["price"] * scale, 0)}
        for t in result["trade_log"]
    ]
    open_positions = [
        {"code": p["code"], "name": ETFS.get(p["code"], {}).get("name", p["code"]),
         "units": p["units"], "buy_date": p["buy_date"]}
        for p in result["open_positions"]
    ]

    return {
        "initial_capital": INIT_CAPITAL,
        "initial_nav_per_share": 1.0,
        "total_return_pct": result["total_return_pct"],
        "max_drawdown_pct": result["max_drawdown_pct"],
        "avg_position_pct": result["avg_position_pct"],
        "final_nav": curve[-1]["nav"] if curve else INIT_CAPITAL,
        "final_nav_per_share": curve[-1]["nav_per_share"] if curve else 1.0,
        "signal_count": sum(len(v) for v in trades_by_code.values()),
        "curve": curve,
        "trades": trade_log,
        "open_positions": open_positions,
    }
