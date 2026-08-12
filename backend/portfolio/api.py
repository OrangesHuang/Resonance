"""组合回测 API: 等权满仓调度的净值走势与交易记录。

买卖点与页面「共振买卖点」共用统一入口(analysis.strategy.router),
保证组合回测遵循各 ETF 多指标共振买卖点, 而非单一通用策略。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from base.analysis.sentiment.core import enrich_turnover, percentile_series, turnover_value
from base.analysis.strategy.a500 import A500_CODE
from base.analysis.strategy.kc50 import KC50_CODE
from base.analysis.strategy.router import compute_trades
from base.config import ETFS, SENTIMENT_ZONE_MIN_PTS, SENTIMENT_ZONE_WINDOW
from base.store.calendar_repo import get_trade_days
from base.store.daily_repo import get_by_code
from base.store.sentiment_repo import get_margin_series, get_turnover_series
from portfolio.analysis.simulator import simulate

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

TRADE_START = "2025-01-01"
INIT_CAPITAL = 1_000_000  # 100 万初始净值

ALL_CODES = ["510300", "510050", "510500", "512100", "515080", "588000", "589680", "159780", "159352"]

KIND_LABEL = {
    "BUY": "买入建仓",
    "SELL": "整仓卖出",
    "TRIM": "减仓平衡",
    "REFILL": "补仓平衡",
}


def _load_trades(codes: list[str] | None = None) -> dict[str, list[dict]]:
    """按各 ETF 专属策略生成买卖点(与页面共振买卖点一致)。"""
    target_codes = codes if codes else ALL_CODES
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    t_pct = percentile_series(
        [r.get("date") for r in turnover],
        [turnover_value(r) for r in turnover],
        SENTIMENT_ZONE_WINDOW,
        SENTIMENT_ZONE_MIN_PTS,
    )
    m_pct = percentile_series(
        [r.get("date") for r in margin],
        [r.get("fin_balance_yi") for r in margin],
        SENTIMENT_ZONE_WINDOW,
        SENTIMENT_ZONE_MIN_PTS,
    )

    hs300_rows = list(reversed(get_by_code("510300")))
    kc_idx_rows = list(reversed(get_by_code("589680")))

    out: dict[str, list[dict]] = {}
    for code in target_codes:
        rows = list(reversed(get_by_code(code)))
        result = compute_trades(
            code,
            rows,
            t_pct=t_pct,
            m_pct=m_pct,
            hs300_rows=hs300_rows if code == A500_CODE else None,
            kc_idx_rows=kc_idx_rows if code == KC50_CODE else None,
        )
        out[code] = [t for t in result["trades"] if t["date"] >= TRADE_START]
    return out


@router.get("/backtest")
def portfolio_backtest(codes: str | None = Query(None)):
    code_list = codes.split(",") if codes else None
    target_codes = code_list if code_list else ALL_CODES
    trades_by_code = _load_trades(code_list)

    price_map: dict[str, dict[str, float]] = {}
    for code in target_codes:
        rows: dict[str, float] = {}
        for r in get_by_code(code):
            cp = r.get("close_price")
            if cp is not None:
                rows[r["date"]] = cp
        for t in trades_by_code[code]:
            rows.setdefault(t["date"], t["price"])
        price_map[code] = rows

    # 日期轴以交易日历为准(排除节假日/周末), 上限为最后有 K 线价格的日期
    max_kline_date = max(d for m in price_map.values() for d in m)
    dates = [d for d in get_trade_days(TRADE_START) if d <= max_kline_date]
    if not dates:
        dates = sorted({d for m in price_map.values() for d in m})

    result = simulate(trades_by_code, price_map, dates)

    scale = INIT_CAPITAL
    curve = [
        {
            "date": h["date"],
            "nav": round(h["equity"] * scale, 0),  # 总资产(元)
            "nav_per_share": round(h["equity"], 4),  # 归一化净值(1.0 起)
            "position_pct": h["position_pct"],
        }
        for h in result["history"]
    ]
    trade_log = [
        {
            "date": t["date"],
            "signal_date": t.get("signal_date", ""),
            "code": t["code"],
            "name": ETFS.get(t["code"], {}).get("name", t["code"]),
            "kind": t["kind"],
            "kind_label": KIND_LABEL.get(t["kind"], t["kind"]),
            "price": t["price"],
            "amount": round(t["amount"] * scale, 0),
            "weight_pct": t.get("weight_pct", 0.0),
        }
        for t in result["trade_log"]
    ]
    last_date = dates[-1] if dates else ""
    open_positions = []
    final_equity = result["final_equity"]
    for p in result["open_positions"]:
        pm = price_map.get(p["code"], {})
        px = next((pm[x] for x in sorted(pm, reverse=True) if x <= last_date), 0.0)
        mv = p["shares"] * px
        open_positions.append(
            {
                "code": p["code"],
                "name": ETFS.get(p["code"], {}).get("name", p["code"]),
                "buy_date": p["buy_date"],
                "market_value": round(mv * scale, 0),
                "weight_pct": round(mv / final_equity * 100, 1) if final_equity > 0 else 0.0,
            }
        )

    # 各 ETF 序列: 归一化净值(以区间首日收盘为基准 1.0) + 份额净申赎 + 策略买卖点
    etf_series = []
    for code in target_codes:
        row_map: dict[str, dict] = {r["date"]: r for r in get_by_code(code)}
        ordered = sorted((d, r) for d, r in row_map.items() if r.get("close_price") is not None)
        base = ordered[0][1]["close_price"] if ordered else None
        nav = [
            round(row_map[d]["close_price"] / base, 4)
            if d in row_map and row_map[d].get("close_price") and base
            else None
            for d in dates
        ]
        delta = [row_map[d].get("shares_delta_yi") if d in row_map else None for d in dates]
        etf_series.append(
            {
                "code": code,
                "name": ETFS.get(code, {}).get("name", code),
                "nav": nav,
                "delta": delta,
                "trades": [
                    {"date": t["date"], "action": t["action"]}
                    for t in trades_by_code[code]
                    if t["action"] in ("BUY", "SELL")
                ],
            }
        )

    return {
        "initial_capital": INIT_CAPITAL,
        "initial_nav_per_share": 1.0,
        "total_return_pct": result["total_return_pct"],
        "max_drawdown_pct": result["max_drawdown_pct"],
        "empty_days": result["empty_days"],
        "empty_days_pct": result["empty_days_pct"],
        "final_nav": curve[-1]["nav"] if curve else INIT_CAPITAL,
        "final_nav_per_share": curve[-1]["nav_per_share"] if curve else 1.0,
        "signal_count": sum(len(v) for v in trades_by_code.values()),
        "curve": curve,
        "trades": trade_log,
        "open_positions": open_positions,
        "etf_series": etf_series,
    }
