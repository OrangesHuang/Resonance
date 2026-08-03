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
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")

    from analysis.strategy_kc import run_kc_strategy, KC_CODE
    if code == KC_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        result = run_kc_strategy(etf_rows)
        return {"code": code, "trades": result["trades"]}

    from analysis.strategy_zz import run_zz_strategy, ZZ_CODE
    if code == ZZ_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        # 注入成交额分位 (_tp) 和融资分位 (_mp)
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
        for r in etf_rows:
            r["_tp"] = t_pct.get(r["date"], {}).get("percentile")
            r["_mp"] = m_pct.get(r["date"], {}).get("percentile")
        result = run_zz_strategy(etf_rows)
        return {"code": code, "trades": result["trades"]}

    from analysis.strategy_div import run_div_strategy, DIV_CODE
    if code == DIV_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        # 注入成交额分位数据 (_tp)
        turnover = enrich_turnover(get_turnover_series())
        t_pct = percentile_series(
            [r.get("date") for r in turnover],
            [turnover_value(r) for r in turnover],
            SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
        for r in etf_rows:
            r["_tp"] = t_pct.get(r["date"], {}).get("percentile")
        result = run_div_strategy(etf_rows)
        return {"code": code, "trades": result["trades"]}

    from analysis.strategy_sh50 import run_sh50_strategy, SH50_CODE
    if code == SH50_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        result = run_sh50_strategy(etf_rows)
        return {"code": code, "trades": result["trades"],
                "metrics": result["metrics"], "holding": result["holding"]}

    from analysis.strategy_sc50 import run_sc50_strategy, SC50_CODE
    if code == SC50_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        result = run_sc50_strategy(etf_rows)
        return {"code": code, "trades": result["trades"],
                "metrics": result["metrics"], "holding": result["holding"]}

    from analysis.strategy_kc50 import run_kc50_strategy, KC50_CODE
    if code == KC50_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        result = run_kc50_strategy(etf_rows)
        return {"code": code, "trades": result["trades"],
                "metrics": result["metrics"], "holding": result["holding"]}

    from analysis.strategy_zz500 import run_zz500_strategy, ZZ500_CODE
    if code == ZZ500_CODE:
        etf_rows = list(reversed(get_by_code(code)))
        result = run_zz500_strategy(etf_rows)
        return {"code": code, "trades": result["trades"],
                "metrics": result["metrics"], "holding": result["holding"]}

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

    import math
    SELL_PP = 80
    SELL_MP = 90
    MIN_HOLD = 10
    VOL_LOOKBACK = 20
    TRADE_START = "2024-10-08"

    trades = []
    position = 0.0
    hold_days = 0
    sell_threshold = 1
    dist_count = 0

    for i, row in enumerate(etf_rows):
        d = row["date"]
        if d not in t_pct and d not in m_pct:
            continue
        close = row.get("close_price")
        if close is None:
            continue
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        tp = t_pct.get(d, {}).get("percentile")
        mp = m_pct.get(d, {}).get("percentile")

        action = None
        reason = ""

        if position == 0 and d >= TRADE_START:
            pp_green = pp is not None and pp <= 40
            pp_extreme = pp is not None and pp <= 10
            td_green = td == "ACCUMULATE"
            sp_green = sp is not None and sp >= 65
            tp_cold = tp is not None and tp <= 10
            cp_high = cp is not None and cp > 60
            if pp_green and sp_green and td_green:
                action, reason = "BUY", "价格低位+份额净申购+吸筹"
            elif pp_green and td_green and tp_cold:
                action, reason = "BUY", "价格低位+吸筹+成交额极冷"
            elif pp_extreme and td_green and cp_high:
                action, reason = "BUY", "价格极低位+吸筹+概率>60%"

        if position == 1:
            hold_days += 1
            if td == "DISTRIBUTE" and pp is not None and pp >= SELL_PP \
                    and mp is not None and mp >= SELL_MP:
                dist_count += 1

            if hold_days >= MIN_HOLD and td == "DISTRIBUTE" \
                    and dist_count >= sell_threshold:
                reason = (f"出货共振(第{dist_count}/{sell_threshold}次出货确认)"
                          f"+价格{pp:.0f}%+融资{mp:.0f}%分位")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            dist_count = 0
            vol = row.get("volume") or 0
            prev_vols = [etf_rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            tp_cold = tp is not None and tp <= 10
            if tp_cold:
                sell_threshold = 1
            else:
                sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": action, "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            trades.append({"date": d, "action": action, "price": close, "reason": reason})

    return {"code": code, "trades": trades}


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
