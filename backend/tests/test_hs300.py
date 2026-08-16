"""沪深300 混合策略单测(合成数据, 无 I/O)。

覆盖(熊市 v3 买卖点先行): 绝望底买入 + 硬止损 / 触线止盈 / 暴力穿越例外 /
极端底冷却豁免 / 危险区。牛熊状态由 ma250 判定。
"""

from __future__ import annotations

from base.analysis.strategy.hs300 import run_hs300_strategy


def _mk(closes, caps, idx):
    """构建合成行: 前 270 天缓降(暖机 ma250≈3.16, ma60 斜率≈-2%), 之后注入信号日。"""
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
                "volume_ratio": cap.get("vr", 0.0),
                "_tp": cap.get("tp"),
                "_mp": cap.get("mp"),
                "change_pct": cap.get("chg", 0.0),
            }
        )
    return rows


def _declining(n: int, start: float = 3.6, step: float = 0.003) -> list[float]:
    """前 n 天线性缓降(ma60 20日斜率约 -2%, 满足跌势成熟门槛)。"""
    return [round(start - i * step, 4) for i in range(n)]


# 合成几何: ma250(第270天) ≈ 3.16; close 2.79 div≈-11.8%(靠双绝望 tp5/mp5 买入);
# 触线需 close >= 3.07; 深背离极端底(-15%)需 close <= 2.69
BUY_CAP = {"pp": 5.0, "sp": 90.0, "chg": -3.0, "tp": 5.0, "mp": 5.0}


def test_bear_despair_buy_then_touch_sell() -> None:
    # 绝望底买入 -> 温和反弹触线(div -2%) -> 触线止盈(案例 2022-04-26 买 -> 07-04 卖 +21.5%)
    closes = _declining(270) + [2.79, 2.90, 3.10]
    caps = {270: BUY_CAP, 272: {"chg": 3.9, "vr": 0.8}}  # 温和触线日(涨幅<4, 量比<2)
    res = run_hs300_strategy(_mk(closes, caps, 270))
    assert len(res["trades"]) == 2
    assert "熊市绝望底" in res["trades"][0]["reason"]
    sell = res["trades"][1]
    assert sell["action"] == "SELL"
    assert "反弹触线止盈" in sell["reason"]
    assert sell["price"] == 3.10


def test_bear_stop_loss_on_failed_catch() -> None:
    # 接刀失败: 买入后继续跌 -5%+ -> 硬止损(案例 2022-09-26 假底 -> 10-24 止损 -5.5%)
    closes = _declining(270) + [2.79, 2.70, 2.60]
    caps = {270: BUY_CAP, 272: {"chg": -3.7}}
    res = run_hs300_strategy(_mk(closes, caps, 270))
    assert len(res["trades"]) == 2
    sell = res["trades"][1]
    assert "接刀失败止损" in sell["reason"]
    assert sell["price"] == 2.60  # 收盘较买入 -6.8% <= -5%


def test_bear_violent_cross_then_trail() -> None:
    # 触线日暴力穿越(单日>=4%且量比>=2, 924式) -> 触线止盈失效转持有 -> 尾随兜底
    closes = _declining(270) + [2.79, 3.10, 3.20, 3.25, 3.30, 3.05]
    caps = {270: BUY_CAP, 271: {"chg": 11.1, "vr": 2.5}, 275: {"chg": -7.6}}
    res = run_hs300_strategy(_mk(closes, caps, 270))
    assert len(res["trades"]) == 2
    sell = res["trades"][1]
    # 暴力穿越后触线失效: 271~274 日(+11%~+18%)未被触线卖出
    assert sell["date"] == "2021-10-06"  # 第 276 天: 高点3.30回撤6% -> 3.05
    assert "尾随止盈" in sell["reason"]
    assert sell["price"] == 3.05


def test_bear_extreme_bottom_skips_cooldown() -> None:
    # 止损后冷却期内, 深背离极端底(div<=-15%且mp<=5)豁免冷却立即再买
    # (案例 2022-04-25 止损 -> 04-26 极端底再买 -> +21.5%)
    closes = _declining(270) + [2.79, 2.60, 2.55]
    caps = {270: BUY_CAP, 271: {"chg": -6.8}, 272: {**BUY_CAP, "chg": -1.9}}
    res = run_hs300_strategy(_mk(closes, caps, 270))
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    assert len(buys) == 2  # 271 止损后 272(冷却期内, div-19.4% 极端)仍买
    assert "熊市绝望底" in buys[1]["reason"]


def test_bear_cooldown_blocks_normal_rebuy() -> None:
    # 止损后冷却期内, 非极端底(双绝望但 div 仅 -14.7%)被冷却拦截
    # (案例 2022-09 假底 div-13.7 被拦, 真底 10-31 div-20.2 豁免)
    closes = _declining(270) + [2.79, 2.60, 2.70]
    caps = {270: BUY_CAP, 271: {"chg": -6.8}, 272: {**BUY_CAP, "chg": 0.5}}
    res = run_hs300_strategy(_mk(closes, caps, 270))
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    assert len(buys) == 1  # 272 在冷却期内且非极端/非恐慌 -> 拦


def test_insufficient_history_no_trade() -> None:
    # 不足 30 行: 直接返回空
    closes = [3.0] * 20
    res = run_hs300_strategy(_mk(closes, {}, 20))
    assert res["trades"] == []
    assert res["danger_zone"] is None


def test_danger_zone_covers_pre_first_buy() -> None:
    # 首个买点前无买点的空仓段 -> 危险区(数据起点 ~ 买点前一日)
    closes = _declining(270) + [2.79, 2.74, 2.69]
    rows = _mk(closes, {270: BUY_CAP}, 270)
    res = run_hs300_strategy(rows)
    assert res["danger_zone"] is not None
    assert res["danger_zone"]["start"] == rows[0]["date"]
    assert res["danger_zone"]["end"] == rows[269]["date"]  # 首买点前一日
    assert res["danger_zone"]["label"] == "危险区·无买点"
