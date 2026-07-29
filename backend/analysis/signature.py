"""特征匹配 + 贝叶斯推断 — 纯函数模块。

将异常度向量与主力行为特征进行余弦相似度匹配，
结合市场状态先验通过贝叶斯推断输出信号强度。
"""

import math
from typing import Optional

from config import (
    ACCUM_SIGNATURE, DIST_SIGNATURE, SIGNATURE_LAMBDA,
    REGIME_BULL_THRESHOLD, REGIME_BEAR_THRESHOLD,
)
from analysis.regime import detect_regime, regime_prior as _regime_prior_func
from analysis.anomaly import compute_anomaly_vector, compute_volatility

_DIM_KEYS = ["vol", "price", "share", "breadth", "divergence"]


def _vec_to_list(vec: dict) -> list[float]:
    return [
        vec.get(k, 0.0) if vec.get(k) is not None else 0.0
        for k in _DIM_KEYS
    ]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度，自动跳过双方均为 0 的维度。"""
    dot = 0.0
    norm_a2 = 0.0
    norm_b2 = 0.0
    for va, vb in zip(a, b):
        if va != 0.0 or vb != 0.0:
            dot += va * vb
            norm_a2 += va * va
            norm_b2 += vb * vb
    if norm_a2 == 0.0 or norm_b2 == 0.0:
        return 0.0
    return round(dot / (math.sqrt(norm_a2) * math.sqrt(norm_b2)), 4)


def match_signatures(
    anomaly_vec: dict,
    accum_sig: list[float] = ACCUM_SIGNATURE,
    dist_sig: list[float] = DIST_SIGNATURE,
) -> tuple[float, float]:
    """匹配异常度向量与吸筹/出货特征。返回 (match_accum, match_dist)。"""
    vec = _vec_to_list(anomaly_vec)
    return cosine_similarity(vec, accum_sig), cosine_similarity(vec, dist_sig)


def _regime_label(score: float) -> str:
    if score > REGIME_BULL_THRESHOLD:
        return "bull"
    if score < REGIME_BEAR_THRESHOLD:
        return "bear"
    return "range"


def _logit(p: float) -> float:
    p_safe = max(0.001, min(0.999, p))
    return math.log(p_safe / (1.0 - p_safe))


def _sigmoid(x: float) -> float:
    return round(1.0 / (1.0 + math.exp(-x)), 6)


def bayesian_update(
    anomaly_vec: dict,
    regime_score: float,
    lambd: float = SIGNATURE_LAMBDA,
) -> dict:
    """贝叶斯推断：先验(市场状态) + 似然(特征匹配) → 后验概率。

    Returns:
        {p_accum, p_dist, p_neutral, signal, match_accum, match_dist,
         regime, regime_label}
    """
    ma, md = match_signatures(anomaly_vec)

    p_accum_prior, p_dist_prior, p_neutral_prior = _regime_prior_func(regime_score)

    log_odds_accum = _logit(p_accum_prior) + lambd * ma
    log_odds_dist = _logit(p_dist_prior) + lambd * md

    p_accum = _sigmoid(log_odds_accum)
    p_dist = _sigmoid(log_odds_dist)
    total = p_accum + p_dist + max(0.0, 1.0 - p_accum - p_dist)
    if total > 0:
        p_accum = round(p_accum / total, 6)
        p_dist = round(p_dist / total, 6)
    p_neutral = round(1.0 - p_accum - p_dist, 6)
    signal = round(p_accum - p_dist, 4)

    return {
        "p_accum": p_accum, "p_dist": p_dist, "p_neutral": p_neutral,
        "signal": signal,
        "match_accum": round(ma, 4), "match_dist": round(md, 4),
        "regime": regime_score, "regime_label": _regime_label(regime_score),
    }


def _rolling_histories(
    volumes: list[float], returns: list[float],
    shares_deltas: list[Optional[float]],
    breadth_ratios: list[Optional[float]],
    i: int,
) -> dict:
    """构建第 i 个交易日的全部历史上下文。"""
    from config import (
        ANOMALY_VOL_WINDOW, ANOMALY_SHARE_WINDOW, ANOMALY_BREADTH_WINDOW,
    )
    v_start = max(0, i - ANOMALY_VOL_WINDOW)
    vol_hist = volumes[v_start:i]

    s_start = max(0, i - ANOMALY_SHARE_WINDOW)
    share_hist = [s for s in shares_deltas[s_start:i] if s is not None]

    b_start = max(0, i - ANOMALY_BREADTH_WINDOW)
    breadth_hist = [b for b in breadth_ratios[b_start:i] if b is not None]

    vols_list = compute_volatility(returns[:i + 1])
    volatility = vols_list[-1] if vols_list else 0.0

    return {"vol_history": vol_hist, "volatility": volatility,
            "share_history": share_hist, "breadth_history": breadth_hist}


def compute_signal_history(
    etf_rows: list[dict],
    breadth_rows: Optional[list[dict]] = None,
) -> dict:
    """计算 V2 信号历史序列。

    Args:
        etf_rows: ETF 日线 (升序)，需 close_price, change_pct, volume, shares_delta_pct
        breadth_rows: 广度数据 (升序)，date → advance_pct。可为 None

    Returns:
        {code, signals, latest, regime}
    """
    n = len(etf_rows)
    if n < 60:
        return {"code": "", "signals": [], "latest": None, "regime": 0.0}

    dates = [r["date"] for r in etf_rows]
    closes = [r.get("close_price") or 0.0 for r in etf_rows]
    volumes = [r.get("volume") or 0.0 for r in etf_rows]
    returns = [r.get("change_pct") or 0.0 for r in etf_rows]
    shares_deltas = [r.get("shares_delta_pct") for r in etf_rows]

    breadth_map = {}
    if breadth_rows:
        for br in breadth_rows:
            breadth_map[br["date"]] = br.get("advance_pct")
    breadth_ratios = [breadth_map.get(d) for d in dates]

    regime_score = detect_regime(closes)

    signals = []
    for i in range(n):
        row = etf_rows[i]
        ctx = _rolling_histories(volumes, returns, shares_deltas, breadth_ratios, i)
        anomaly_vec = compute_anomaly_vector(
            row,
            vol_history=ctx["vol_history"],
            volatility=ctx["volatility"],
            delta_history=ctx["share_history"],
            breadth_ratio=breadth_ratios[i],
            breadth_history=ctx["breadth_history"],
        )
        bayes = bayesian_update(anomaly_vec, regime_score)
        signals.append({
            "date": dates[i], "close": closes[i],
            "anomaly": anomaly_vec, **bayes,
        })

    code = etf_rows[0].get("code", "") if etf_rows else ""
    return {
        "code": code, "signals": signals,
        "latest": signals[-1] if signals else None,
        "regime": regime_score,
    }


def compute_signal_day(
    etf_row: dict,
    etf_rows_before: list[dict],
    breadth_row: Optional[dict] = None,
    breadth_rows_before: Optional[list[dict]] = None,
    regime_score: float = 0.0,
) -> dict:
    """单日 V2 信号详情 (含逐维度分解)。

    Args:
        etf_row: 目标日 ETF 数据
        etf_rows_before: 历史 ETF 数据 (升序)
        breadth_row: 目标日广度数据
        breadth_rows_before: 历史广度数据
        regime_score: 预设市场状态 (0 则自动计算)
    """
    closes_before = [r.get("close_price") or 0.0 for r in etf_rows_before]
    if not regime_score and len(closes_before) >= 200:
        regime_score = detect_regime(closes_before)

    volumes_before = [r.get("volume") or 0.0 for r in etf_rows_before]
    returns_before = [r.get("change_pct") or 0.0 for r in etf_rows_before]
    shares_before = [r.get("shares_delta_pct") for r in etf_rows_before]

    breadth_before = []
    if breadth_rows_before:
        breadth_before = [r.get("advance_pct") for r in breadth_rows_before]
    breadth_cur = breadth_row.get("advance_pct") if breadth_row else None

    all_returns = returns_before + [etf_row.get("change_pct") or 0.0]
    vols = compute_volatility(all_returns)
    volatility = vols[-1] if vols else 0.0

    from config import ANOMALY_VOL_WINDOW, ANOMALY_SHARE_WINDOW
    vol_hist = volumes_before[-ANOMALY_VOL_WINDOW:] if volumes_before else []
    share_hist_raw = shares_before[-ANOMALY_SHARE_WINDOW:] if shares_before else []
    share_hist = [s for s in share_hist_raw if s is not None]

    anomaly_vec = compute_anomaly_vector(
        etf_row, vol_history=vol_hist, volatility=volatility,
        delta_history=share_hist, breadth_ratio=breadth_cur,
        breadth_history=breadth_before[-20:] if breadth_before else [],
    )

    bayes = bayesian_update(anomaly_vec, regime_score)

    chg = etf_row.get("change_pct")
    delta = etf_row.get("shares_delta_pct")
    dimensions = [
        {"key": "vol", "name": "量能异常度", "score": anomaly_vec["vol"],
         "detail": f"当日成交量={etf_row.get('volume')}"},
        {"key": "price", "name": "价格异常度", "score": anomaly_vec["price"],
         "detail": f"涨跌幅={chg}%, 波动率={volatility:.2f}%"},
        {"key": "share", "name": "份额异常度", "score": anomaly_vec["share"],
         "detail": f"份额变动率={delta}%"},
        {"key": "breadth", "name": "市场广度", "score": anomaly_vec["breadth"],
         "detail": f"上涨占比={breadth_cur}%"},
        {"key": "divergence", "name": "量价背离度", "score": anomaly_vec["divergence"],
         "detail": f"涨跌幅={chg}%, 量能异常={anomaly_vec['vol']}"},
    ]

    return {"date": etf_row["date"], "anomaly": anomaly_vec,
            "dimensions": dimensions, **bayes}
