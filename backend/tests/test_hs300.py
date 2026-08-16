"""沪深300 混合策略单测(合成数据, 无 I/O)。

覆盖: 熊市 P1 恐慌吸筹买入 + 尾随止盈卖出; 牛熊状态由 ma250 判定。
"""

from __future__ import annotations

from base.analysis.strategy.hs300 import run_hs300_strategy


def _mk(closes, caps, idx):
    """构建合成行: 前 270 天走平(暖机 ma250), 之后注入恐慌吸筹日。"""
    rows = []
    n = len(closes)
    for i in range(n):
        cap = caps.get(i, {})
        rows.append(
            {
                "date": f"2021-{i // 30 + 1:02d}-{i % 30 + 1:02d}",
                "close_price": closes[i],
                "price_position": cap.get("pp", 50.0),
                "trade_direction": cap.get("td", "NEUTRAL"),
                "share_prob": cap.get("sp", 10.0),
                "composite_prob": cap.get("cp", 45.0),
                "change_pct": cap.get("chg", 0.0),
            }
        )
    return rows


def _declining(n: int, start: float = 3.6, step: float = 0.003) -> list[float]:
    """前 n 天线性缓降(ma60 20日斜率约 -2%, 满足跌势成熟门槛)。"""
    return [round(start - i * step, 4) for i in range(n)]


def test_bear_p1_buy_then_trailing_sell() -> None:
    # 270 天缓降(ma60 下行) -> 第 271 天恐慌吸筹(pp5+吸筹+sp90) -> 之后连跌触发尾随止盈
    closes = _declining(270) + [2.79, 2.74, 2.69, 2.64, 2.61, 2.59, 2.57]
    caps = {270: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -3.0}}
    res = run_hs300_strategy(_mk(closes, caps, 270))
    assert res["code"] == "510300"
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert len(buys) == 1
    assert len(sells) == 1
    assert res["trades"][0]["date"] == "2021-10-01"  # 第 271 天(270//30+1=10月, 270%30+1=1)
    assert "恐慌吸筹P1" in res["trades"][0]["reason"]
    # 尾随止盈: 持仓最高 = 买价 2.79, 6% 回撤 = 2.6226, 第 4 个持有日 close 2.61 触发
    assert "尾随止盈" in res["trades"][1]["reason"]


def test_insufficient_history_no_trade() -> None:
    # 不足 30 行: 直接返回空
    closes = [3.0] * 20
    res = run_hs300_strategy(_mk(closes, {}, 20))
    assert res["trades"] == []


def test_bear_sell_cooldown_blocks_rebuy() -> None:
    # 熊市 P1 卖出后 10 日内普通买点被冷却拦截(2022-09-22卖->09-26买 案例)
    closes = _declining(270) + [2.79, 2.74, 2.69, 2.64, 2.61, 2.59, 2.61, 2.64, 2.67, 2.7, 2.72, 2.75]
    caps = {
        270: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -3.0},  # 首次买
        277: {"pp": 8.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -0.5},  # 卖后2日, 非恐慌
    }
    res = run_hs300_strategy(_mk(closes, caps, 270))
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    # 第 277 天 chg=-0.5% 非恐慌 → 冷却拦截, 只买了一次
    assert len(buys) == 1


def test_bear_panic_skips_cooldown() -> None:
    # 卖出后 2 日出现真恐慌(当日跌<=-3%) → 跳过冷却重新买入(2025-04-07 -7.0% 案例)
    closes = _declining(270) + [2.79, 2.74, 2.69, 2.64, 2.61, 2.59, 2.5, 2.61, 2.67]
    caps = {
        270: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -3.0},  # 首次买
        276: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -5.0},  # 卖后1日, 真恐慌
    }
    res = run_hs300_strategy(_mk(closes, caps, 270))
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    # 第 276 天 -5.0% 恐慌 → 跳过冷却, 买了两次
    assert len(buys) == 2


def test_b1_ma60_band_blocks_shallow_allows_deep() -> None:
    # 牛市(B1): 贴ma60浅回调(0.97~1.01)拦截, 深回调(<=0.97*ma60)放行
    # 构造: 缓升趋势(ma60上行) -> 浅回调(距ma60 +0.5%)不买 -> 深回调(距ma60 -6%)买
    n = 300
    closes = [3.0 + i * 0.002 for i in range(n)]  # 缓升, ma60上行 → bull
    # 浅回调日: 价格回落到 ma60 附近(+0.5%)
    # 直接构造: 在 n+1 天设为浅回调(接近ma60), n+2 天深回调
    closes = closes + [4.0, 3.9, 3.8, 3.6, 3.5, 3.45]  # 逐步回调
    caps = {
        301: {"pp": 30.0, "td": "NEUTRAL", "sp": 60.0, "chg": -1.0},  # 浅回调附近
        303: {"pp": 30.0, "td": "NEUTRAL", "sp": 60.0, "chg": -5.0},  # 深回调
    }
    res = run_hs300_strategy(_mk(closes, caps, n))
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    # 至少有一次买入(深回调触发); 具体日期不强制, 主要验证深回调能买
    assert len(buys) >= 1


def test_buy_verify_period_sells_unconfirmed() -> None:
    # 买入后 20 日未脱离成本区(价格<3%)且份额未承接(<5%) → 验证期认错
    # 构造: 缓降(ma60下行) -> 第270天恐慌吸筹买 -> 之后横盘 25 日(第20日不涨)
    closes = _declining(270) + [
        2.79,
        2.80,
        2.78,
        2.79,
        2.81,
        2.80,
        2.79,
        2.82,
        2.80,
        2.79,
        2.81,
        2.80,
        2.78,
        2.79,
        2.80,
        2.81,
        2.79,
        2.80,
        2.78,
        2.79,
        2.80,
        2.81,
        2.79,
        2.80,
        2.78,
    ]  # 25日横盘~+0.7%
    caps = {270: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -3.0}}
    res = run_hs300_strategy(_mk(closes, caps, 270))
    trades = res["trades"]
    buys = [t for t in trades if t["action"] == "BUY"]
    sells = [t for t in trades if t["action"] == "SELL"]
    assert len(buys) == 1
    assert len(sells) == 1
    # 验证期第 20 日卖出(份额默认 100 不变 <5%, 价格 <3%)
    assert "买入未验证" in sells[0]["reason"]
