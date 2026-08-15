"""中证1000 策略单测(合成数据, 无 I/O)。

覆盖:
  1. 低位吸筹买入 + 买入验证期(10日未脱离成本区+份额未承接 → 认错离场, 案例 2023-04-25)
  2. 买入后短期下探即收复 → 验证期不误触发
  3. 先脱离成本区后深套 → 底部失败守卫(连续浮亏 15 日)离场
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


def test_buy_then_verify_sell() -> None:
    # 40 天走平 -> 低位吸筹买入@2.0 -> 之后横盘阴跌(第10日 -1.1%, 份额不动)
    # → 买入验证期第 10 日认错离场(2023-04-25 案例, 原守卫要扛到 -9.2%)
    closes = [2.0] * 41 + [2.0, 1.95, 1.9, 1.92, 1.9, 1.85, 1.88, 1.9, 1.85, 1.86]
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 2
    assert trades[0]["action"] == "BUY" and "低位吸筹" in trades[0]["reason"]
    assert trades[1]["action"] == "SELL" and "买入未验证" in trades[1]["reason"]
    assert trades[1]["date"] == "2021-02-21"  # 索引 50 = 40+10


def test_recovery_no_verify_sell() -> None:
    # 买入后短暂下探但第 10 日前收复 ≥3% → 验证期不触发
    closes = [2.0] * 41 + [1.95, 1.9, 1.95, 2.0, 2.05] + [2.1] * 20
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 1  # 只有买入, 无卖出
    assert trades[0]["action"] == "BUY"


def test_escape_then_underwater_guard_sell() -> None:
    # 买入后前 15 日已脱离成本区(+5%, 验证期窗口过后) → 再阴跌 8%+ 持续 15 日
    # → 底部失败守卫离场(2024-02-01 式浮亏但最终收复的防线)
    closes = [2.0] * 41 + [2.1] * 15 + [1.8] * 20
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 2
    assert trades[0]["action"] == "BUY"
    assert trades[1]["action"] == "SELL" and "底部失败" in trades[1]["reason"]
    # 买入 i=40, +1..+15 日=2.1(脱离), 第 16 日(索引56)起 1.8 浮亏 8%+
    # 连续 15 日后(索引 70)守卫卖出
    assert trades[1]["date"] == "2021-03-11"
