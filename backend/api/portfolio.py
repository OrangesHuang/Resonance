"""组合回测 API: 8 标的统一仓位分配逻辑的净值走势与交易记录。"""
from __future__ import annotations

import math

from fastapi import APIRouter

from config import ETFS, SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
from store.daily_repo import get_by_code, get_trading_dates
from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import enrich_turnover, percentile_series
from analysis.resonance import turnover_value
from analysis.portfolio import simulate
from analysis.strategy_sh50 import run_sh50_strategy, SH50_CODE
from analysis.strategy_zz500 import run_zz500_strategy, ZZ500_CODE
from analysis.strategy_kc import run_kc_strategy, KC_CODE
from analysis.strategy_kc50 import run_kc50_strategy, KC50_CODE
from analysis.strategy_sc50 import run_sc50_strategy, SC50_CODE
from analysis.strategy_zz import run_zz_strategy, ZZ_CODE
from analysis.strategy_div import run_div_strategy, DIV_CODE

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

TRADE_START = "2024-10-08"
INIT_CAPITAL = 1_000_000   # 100 万初始净值
INIT_SHARES = 1_000_000    # 每份 1 元

ALL_CODES = ["510300", "510050", "510500", "512100",
             "515080", "588000", "589680", "159780"]

KIND_LABEL = {
    "BUY": "买入(12.5%)",
    "TOPUP": "加仓(至25%)",
    "REDUCE": "减仓(至12.5%)",
    "SELL": "卖出",
}


def _percentile(date_series: list[dict], values: list[float]) -> dict[str, float]:
    pct = percentile_series(date_series, values,
                            SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
    return {d: p.get("percentile") for d, p in pct.items()}


def _generic_v1_trades(code: str) -> list[dict]:
    """510300 通用 V1 逻辑(与 api/resonance.py /trades 一致)。"""
    etf_rows = [r for r in list(reversed(get_by_code(code)))
                if r.get("composite_prob") is not None]
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    t_pct = _percentile([r.get("date") for r in turnover],
                        [turnover_value(r) for r in turnover])
    m_pct = _percentile([r.get("date") for r in margin],
                        [r.get("fin_balance_yi") for r in margin])
    trades, position, hold_days, sell_threshold, dist_count = [], 0.0, 0, 1, 0
    for i, row in enumerate(etf_rows):
        d = row["date"]
        if d not in t_pct and d not in m_pct:
            continue
        close = row.get("close_price")
        if close is None:
            continue
        pp, td, sp, cp = (row.get("price_position"), row.get("trade_direction"),
                          row.get("share_prob"), row.get("composite_prob"))
        tp, mp = t_pct.get(d), m_pct.get(d)
        action = None
        if position == 0 and d >= TRADE_START:
            pp_green = pp is not None and pp <= 40
            pp_extreme = pp is not None and pp <= 10
            td_green = td == "ACCUMULATE"
            sp_green = sp is not None and sp >= 65
            tp_cold = tp is not None and tp <= 10
            cp_high = cp is not None and cp > 60
            if pp_green and sp_green and td_green:
                action = "BUY"
            elif pp_green and td_green and tp_cold:
                action = "BUY"
            elif pp_extreme and td_green and cp_high:
                action = "BUY"
        if position == 1:
            hold_days += 1
            if (td == "DISTRIBUTE" and pp is not None and pp >= 80
                    and mp is not None and mp >= 90):
                dist_count += 1
            if hold_days >= 10 and td == "DISTRIBUTE" and dist_count >= sell_threshold:
                action = "SELL"
        if action == "BUY":
            position, hold_days, dist_count = 1.0, 0, 0
            vol = row.get("volume") or 0
            prev_vols = [etf_rows[j].get("volume") or 0
                         for j in range(max(0, i - 20), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            sell_threshold = 1 if (tp is not None and tp <= 10) \
                else max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": "BUY", "price": close})
        elif action == "SELL":
            position = 0.0
            trades.append({"date": d, "action": "SELL", "price": close})
    return trades


def _load_trades() -> dict[str, list[dict]]:
    runners = {
        SH50_CODE: run_sh50_strategy, ZZ500_CODE: run_zz500_strategy,
        KC_CODE: run_kc_strategy, KC50_CODE: run_kc50_strategy,
        SC50_CODE: run_sc50_strategy, ZZ_CODE: run_zz_strategy,
        DIV_CODE: run_div_strategy,
    }
    out: dict[str, list[dict]] = {}
    for code in ALL_CODES:
        fn = runners.get(code)
        if fn is None:
            trades = _generic_v1_trades(code)
        else:
            rows = list(reversed(get_by_code(code)))
            if fn in (run_div_strategy, run_zz_strategy):
                turnover = enrich_turnover(get_turnover_series())
                t_pct = _percentile([r.get("date") for r in turnover],
                                    [turnover_value(r) for r in turnover])
                for r in rows:
                    r["_tp"] = t_pct.get(r["date"])
            result = fn(rows)
            trades = result["trades"]
        out[code] = [t for t in trades if t["date"] >= TRADE_START]
    return out


@router.get("/backtest")
def portfolio_backtest():
    trades_by_code = _load_trades()

    price_map: dict[str, dict[str, float]] = {}
    for code in ALL_CODES:
        rows = {r["date"]: r.get("close_price") for r in get_by_code(code)}
        for t in trades_by_code[code]:
            rows.setdefault(t["date"], t["price"])
        price_map[code] = rows

    dates = [d for d in get_trading_dates() if d >= TRADE_START]
    if not dates:
        dates = sorted({d for m in price_map.values() for d in m})

    result = simulate(trades_by_code, price_map, dates)

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
