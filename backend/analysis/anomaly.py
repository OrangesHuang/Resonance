"""异常度量化模块 — 纯函数，无 I/O。

将 5 个维度的原始数据转换为连续的异常度分数 ∈ [-1, 1]，
替代 V1 的离散红绿灯判定。

维度:
  1. 量能异常度 — 当日成交量相对历史分布有多极端
  2. 价格异常度 — 当日涨跌幅相对近期波动率有多极端
  3. 份额异常度 — 份额变动相对历史分布有多异常
  4. 市场广度   — 全市场涨跌比偏离正常水平多少 (新增维度)
  5. 量价背离   — 价格与量能是否出现背离 (捕捉逆势行为)
"""

import math
from typing import Optional

from config import (
    ANOMALY_VOL_WINDOW, ANOMALY_SHARE_WINDOW,
    ANOMALY_VOLATILITY_WINDOW, ANOMALY_BREADTH_WINDOW, VOL_Z_SCALE,
)


def _tanh_squash(x: float) -> float:
    """tanh(x/2) 压缩: 将任意实数映射到 [-1, 1]。"""
    return round(math.tanh(x / 2.0), 4)


def _median(values: list[float]) -> float:
    """计算中位数 (避免 numpy 依赖)。"""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float], ddof: int = 1) -> float:
    """样本标准差。"""
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return math.sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - ddof))


def volume_anomaly(
    current_vol: float,
    vol_history: list[float],
    z_scale: float = VOL_Z_SCALE,
) -> float:
    """量能异常度。

    当日成交量相对于 120 日分布中位数的偏离程度。
    放量 → 正分数，缩量 → 负分数。

    Args:
        current_vol: 当日成交量
        vol_history: 历史成交量序列 (升序)
        z_scale: z-score 缩放因子
    """
    if current_vol is None or current_vol <= 0:
        return 0.0
    clean = [v for v in vol_history if v is not None and v > 0]
    if len(clean) < 20:
        return 0.0
    med = _median(clean)
    if med <= 0:
        return 0.0
    z = (current_vol / med - 1.0) / z_scale
    return _tanh_squash(z)


def price_anomaly(
    daily_return: float,
    volatility_20d: float,
) -> float:
    """价格行为异常度。

    当日涨跌幅相对于近期波动率的偏离程度。
    跌幅远超波动率 → 负分数（恐慌），涨幅远超波动率 → 正分数（亢奋）。

    Args:
        daily_return: 当日涨跌幅 (%)
        volatility_20d: 近 20 日收益率标准差 (%)
    """
    if daily_return is None or volatility_20d is None or volatility_20d <= 0:
        return 0.0
    z = daily_return / volatility_20d
    return _tanh_squash(z)


def share_anomaly(
    current_delta_pct: Optional[float],
    delta_history: list[float],
    window: int = ANOMALY_SHARE_WINDOW,
) -> float:
    """份额异常度。

    当日份额变动率相对于 60 日分布的异常程度。
    大额净申购 → 正分数，大额净赎回 → 负分数。

    Args:
        current_delta_pct: 当日份额变动率 (%)
        delta_history: 历史份额变动率序列
    """
    if current_delta_pct is None:
        return 0.0
    clean = [v for v in delta_history if v is not None]
    if len(clean) < 20:
        return 0.0
    avg = _mean(clean)
    std = _std(clean)
    if std <= 0:
        return 0.0
    z = (current_delta_pct - avg) / std
    return _tanh_squash(z)


def breadth_anomaly(
    advance_pct: Optional[float],
    breadth_history: list[float],
    window: int = ANOMALY_BREADTH_WINDOW,
) -> float:
    """市场广度异常度。

    全市场上涨家数占比偏离其近期分布的程度。
    广度极低 → 负分数（多数个股下跌），广度极高 → 正分数（普涨）。

    当 breadth 数据缺失时返回 0.0 (不影响其余维度的匹配)。

    Args:
        advance_pct: 当日上涨家数占比 (0-100)
        breadth_history: 历史广度序列
    """
    if advance_pct is None:
        return 0.0
    clean = [v for v in breadth_history if v is not None]
    if len(clean) < 20:
        return 0.0
    avg = _mean(clean)
    std = _std(clean)
    if std <= 0:
        return 0.0
    z = (advance_pct - avg) / std
    return _tanh_squash(z)


def divergence_score(
    price_change: Optional[float],
    vol_anomaly: float,
    price_position: Optional[float] = None,
) -> float:
    """量价方向度（含价格位置修正）。

    核心逻辑：
    - 价跌+放量 → 正分数 (恐慌吸筹特征)，无论位置
    - 价涨+放量+低位 → 正分数 (底部启动吸筹)
    - 价涨+放量+高位 → 负分数 (高位出货)
    - 价涨+放量+中位 → 弱负分数

    Args:
        price_change: 当日涨跌幅 (%)
        vol_anomaly: 量能异常度
        price_position: 60日价格位置 (0-100)，None 则使用原始逻辑
    """
    if price_change is None or price_change == 0:
        return 0.0
    if abs(vol_anomaly) < 0.1:
        return 0.0  # 缩量时不判方向

    vol_strength = abs(vol_anomaly)
    price_down = price_change < 0

    if price_down:
        # 价格下跌+放量 → 恐慌/吸筹特征 → 正分数
        return round(vol_strength, 4)

    # 价格上涨+放量 → 需要看位置
    if price_position is None:
        # 无位置信息时，默认偏负（保守）
        return round(-vol_strength * 0.5, 4)

    if price_position <= 40:
        # 低位+放量上涨 → 底部启动，吸筹信号 → 正分数
        return round(vol_strength * 0.8, 4)
    elif price_position >= 75:
        # 高位+放量上涨 → 出货 → 负分数
        return round(-vol_strength, 4)
    else:
        # 中位+放量上涨 → 中性偏负
        return round(-vol_strength * 0.3, 4)


def compute_volatility(
    returns: list[float],
    window: int = ANOMALY_VOLATILITY_WINDOW,
) -> list[float]:
    """计算滚动波动率序列。

    对每日收益率序列，计算每个交易日的近 N 日标准差。

    Returns:
        与输入等长的波动率序列 (前期不足 window 的为 0.0)
    """
    vols = []
    for i in range(len(returns)):
        start = max(0, i - window + 1)
        seg = returns[start:i + 1]
        if len(seg) < 5:
            vols.append(0.0)
        else:
            vols.append(_std(seg))
    return vols


def compute_anomaly_vector(
    row: dict,
    vol_history: list[float],
    volatility: float,
    delta_history: list[float],
    breadth_ratio: Optional[float],
    breadth_history: list[float],
) -> dict:
    """计算某交易日的 5 维异常度向量。

    Args:
        row: etf_daily 的一行数据
        vol_history: 该日之前的历史成交量序列
        volatility: 该日之前 20 日波动率
        delta_history: 该日之前的历史份额变动率序列
        breadth_ratio: 当日上涨家数占比 (可为 None)
        breadth_history: 该日之前的历史广度序列

    Returns:
        {"vol": float, "price": float, "share": float,
         "breadth": float, "divergence": float}
    """
    vol = row.get("volume")
    chg = row.get("change_pct")
    delta = row.get("shares_delta_pct")
    pp = row.get("price_position")

    v_anom = volume_anomaly(vol, vol_history)
    p_anom = price_anomaly(chg, volatility)
    s_anom = share_anomaly(delta, delta_history)
    b_anom = breadth_anomaly(breadth_ratio, breadth_history)
    d_score = divergence_score(chg, v_anom, pp)

    return {
        "vol": v_anom,
        "price": p_anom,
        "share": s_anom,
        "breadth": b_anom,
        "divergence": d_score,
    }
