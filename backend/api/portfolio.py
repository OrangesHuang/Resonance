"""组合回测 API: 8 标的统一仓位分配逻辑的净值走势与交易记录。

买卖点与页面「共振买卖点」共用统一入口(analysis.trades_router),
保证组合回测遵循各 ETF 多指标共振买卖点, 而非单一通用策略。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from config import ETFS, SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
from store.daily_repo import get_by_code, get_trading_dates
from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import enrich_turnover, percentile_series
from analysis.resonance import turnover_value
from analysis.portfolio import simulate
from analysis.trades_router import compute_trades
from analysis.strategy_a500 import A500_CODE
from analysis.strategy_kc50 import KC50_CODE

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
    "SKIP": "信号跳过(资金不足)",
}


def _load_trades(codes: Optional[list[str]] = None) -> dict[str, list[dict]]:
    """按各 ETF 专属策略生成买卖点(与页面共振买卖点一致)。"""
    target_codes = codes if codes else ALL_CODES
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    t_pct = percentile_series(
        [r.get("date") for r in turnover],
        [turnover_value(r) for r in turnover],
        SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
    m_pct = percentile_series(
        [r.get("date") for r in margin],
        [r.get("fin_balance_yi") for r in margin],
        SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)

    hs300_rows = list(reversed(get_by_code("510300")))
    kc_idx_rows = list(reversed(get_by_code("589680")))

    out: dict[str, list[dict]] = {}
    for code in target_codes:
        rows = list(reversed(get_by_code(code)))
        result = compute_trades(code, rows, t_pct=t_pct, m_pct=m_pct,
                                hs300_rows=hs300_rows if code == A500_CODE else None,
                                kc_idx_rows=kc_idx_rows if code == KC50_CODE else None)
        out[code] = [t for t in result["trades"] if t["date"] >= TRADE_START]
    return out


@router.get("/backtest")
def portfolio_backtest(codes: Optional[str] = Query(None)):
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
