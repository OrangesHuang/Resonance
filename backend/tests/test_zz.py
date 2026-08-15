"""中证1000 策略单测(合成数据, 无 I/O)。

覆盖: 低位吸筹买入 + 底部失败守卫(连续浮亏离场, 案例 2023-04-25)。
"""

from __future__ import annotations

from base.analysis.strategy.zz import run_zz_strategy


def _mk(closes, caps):
    rows = []
    for i, c in enumerate(closes):
        cap = caps.get(i, {})
        rows.append(
            {
                "date": f"2021-{i // 30 + 1:02d}-{i % 30 + 1:02d}",
                "close_price": c,
                "price_position": cap.get("pp", 50.0),
                "trade_direction": cap.get("td", "NEUTRAL"),
                "share_prob": cap.get("sp", 10.0),
                "composite_prob": cap.get("cp", 45.0),
                "change_pct": cap.get("chg", 0.0),
                "volume_ratio": cap.get("vr", 1.0),
                "shares_yi": cap.get("sy", 100.0),
                "shares_delta_yi": cap.get("sd", 0.0),
            }
        )
    return rows


def test_low_accum_buy_then_underwater_guard_sell() -> None:
    # 40 天走平(无暴跌集群) -> 低位吸筹买入@2.0 -> 之后持续阴跌至 1.8
    # (低于 2.0*0.92=1.84, 连续 15 日) → 底部失败守卫卖出
    closes = [2.0] * 41 + [1.8] * 20
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 2
    assert trades[0]["action"] == "BUY" and "低位吸筹" in trades[0]["reason"]
    assert trades[1]["action"] == "SELL" and "底部失败" in trades[1]["reason"]
    # 卖出日: 买入后第 15 个浮亏日(索引 55 = 40+15)
    assert trades[1]["date"] == "2021-02-26"


def test_recovery_no_guard_sell() -> None:
    # 买入后短暂下探(未破 -8%)即收复 → 守卫不触发
    closes = [2.0] * 41 + [1.95, 1.9, 1.95, 2.0, 2.05] + [2.1] * 20
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 1  # 只有买入, 无卖出
    assert trades[0]["action"] == "BUY"
