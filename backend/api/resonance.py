from fastapi import APIRouter, HTTPException

from config import ETFS, DEFAULT_RESONANCE_CODE, SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS
from store.daily_repo import get_by_code
from store.sentiment_repo import get_turnover_series, get_margin_series
from analysis.sentiment import enrich_turnover, percentile_series
from analysis.resonance import compute_resonance, turnover_value
from analysis.resonance_evidence import compute_day_detail

router = APIRouter(prefix="/api/resonance", tags=["resonance"])


def _load_series(code: str):
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    etf_rows = list(reversed(get_by_code(code)))
    etf_rows = [r for r in etf_rows if r.get("composite_prob") is not None]
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    return etf_rows, turnover, margin


@router.get("/overview")
def resonance_overview(code: str = DEFAULT_RESONANCE_CODE):
    etf_rows, turnover, margin = _load_series(code)
    return compute_resonance(code, etf_rows, turnover, margin)


@router.get("/day")
def resonance_day(code: str = DEFAULT_RESONANCE_CODE, date: str = ""):
    if not date:
        raise HTTPException(status_code=400, detail="缺少 date 参数")
    etf_rows, turnover, margin = _load_series(code)
    detail = compute_day_detail(code, etf_rows, turnover, margin, date)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"{code} 在 {date} 无共振数据")
    return detail


@router.get("/trades")
def resonance_trades(code: str = DEFAULT_RESONANCE_CODE):
    """页面「共振买卖点」— 按 ETF 代码分派各专属策略(与组合回测共用统一入口)。"""
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")

    from analysis.strategy_a500 import A500_CODE
    from analysis.strategy_kc50 import KC50_CODE
    from analysis.trades_router import compute_trades

    etf_rows = list(reversed(get_by_code(code)))
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

    hs300_rows = None
    kc_idx_rows = None
    if code == A500_CODE:
        hs300_rows = list(reversed(get_by_code("510300")))
    elif code == KC50_CODE:
        kc_idx_rows = list(reversed(get_by_code("589680")))

    result = compute_trades(code, etf_rows, t_pct=t_pct, m_pct=m_pct,
                            hs300_rows=hs300_rows, kc_idx_rows=kc_idx_rows)
    return {"code": code, "trades": result["trades"]}


@router.get("/trades_kc")
def resonance_trades_kc():
    from analysis.strategy_kc import run_kc_strategy, KC_CODE
    etf_rows = list(reversed(get_by_code(KC_CODE)))
    return run_kc_strategy(etf_rows)


# ========== V2 信号系统 ==========

from analysis.signature import compute_signal_history, compute_signal_day
from analysis.regime import detect_regime, regime_label
from store.breadth_repo import get_breadth_series


def _load_v2_data(code: str):
    """加载 V2 计算所需的全部数据。"""
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    etf_rows = list(reversed(get_by_code(code)))
    etf_rows = [r for r in etf_rows if r.get("close_price") is not None]
    breadth_rows = get_breadth_series()
    return etf_rows, breadth_rows


@router.get("/v2/signals/{code}")
def resonance_v2_signals(code: str):
    """V2 信号历史 + 最近信号。"""
    etf_rows, breadth_rows = _load_v2_data(code)
    result = compute_signal_history(etf_rows, breadth_rows if breadth_rows else None)
    # 只返回最近 200 天的信号明细，减少响应体积
    signals = result["signals"]
    recent = signals[-200:] if len(signals) > 200 else signals
    return {
        "code": result["code"],
        "regime": result["regime"],
        "regime_label": regime_label(result["regime"]),
        "latest": result["latest"],
        "signal_count": len(signals),
        "signals": recent,
    }


@router.get("/v2/signal")
def resonance_v2_signal_day(code: str = "510300", date: str = ""):
    """单日 V2 信号详情（含逐维度分解）。"""
    if not date:
        raise HTTPException(status_code=400, detail="缺少 date 参数")
    etf_rows, breadth_rows = _load_v2_data(code)
    # 找到目标日及之前的数据
    target_idx = None
    for i, r in enumerate(etf_rows):
        if r["date"] == date:
            target_idx = i
            break
    if target_idx is None:
        raise HTTPException(status_code=404, detail=f"{code} 在 {date} 无数据")

    etf_before = etf_rows[:target_idx]
    breadth_before = None
    breadth_row = None
    if breadth_rows:
        breadth_before = []
        for br in breadth_rows:
            if br["date"] < date:
                breadth_before.append(br)
            elif br["date"] == date:
                breadth_row = br

    return compute_signal_day(
        etf_rows[target_idx], etf_before,
        breadth_row, breadth_before if breadth_before else None,
    )


@router.get("/v2/regime")
def resonance_v2_regime(code: str = "510300"):
    """当前市场状态。"""
    etf_rows, _ = _load_v2_data(code)
    closes = [r.get("close_price") or 0.0 for r in etf_rows]
    score = detect_regime(closes)
    return {
        "code": code,
        "regime_score": score,
        "regime_label": regime_label(score),
        "data_points": len(closes),
    }


@router.get("/v2/backtest/{code}")
def resonance_v2_backtest(code: str = "510300"):
    """V2 信号回测。"""
    from analysis.decision import run_backtest_v2
    etf_rows, breadth_rows = _load_v2_data(code)
    result = compute_signal_history(etf_rows, breadth_rows if breadth_rows else None)
    signals = result["signals"]
    closes = [s["close"] for s in signals]
    return run_backtest_v2(signals, closes)


# ========== V3 主力资金节奏策略 ==========

@router.get("/v3/trades/{code}")
def resonance_v3_trades(code: str = "510300"):
    """V3 策略买卖点 — 基于国家队行为特征匹配。"""
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    from analysis.strategy_v3 import run_v3_strategy
    etf_rows = list(reversed(get_by_code(code)))
    result = run_v3_strategy(etf_rows)
    return {"code": code, "trades": result["trades"],
            "metrics": result["metrics"], "holding": result["holding"]}


# ========== V5 吸筹/出货周期策略 ==========

@router.get("/v5/trades/{code}")
def resonance_v5_trades(code: str = "510300"):
    """V5 策略买卖点 — 锚定ACCUMULATE/DISTRIBUTE信号，量能周期对比。"""
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    from analysis.strategy_v5 import run_v5_strategy
    etf_rows = list(reversed(get_by_code(code)))
    result = run_v5_strategy(etf_rows)
    return {"code": code, "trades": result["trades"],
            "metrics": result["metrics"], "holding": result["holding"]}


# ========== V4 政策市策略 ==========

@router.get("/v4/trades/{code}")
def resonance_v4_trades(code: str = "510300"):
    """V4 策略买卖点 — 基于924后政策市逻辑推导。"""
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    from analysis.strategy_v4 import run_v4_strategy
    etf_rows = list(reversed(get_by_code(code)))
    result = run_v4_strategy(etf_rows)
    return {"code": code, "trades": result["trades"],
            "metrics": result["metrics"], "holding": result["holding"]}
