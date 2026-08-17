"""科创50 Beta 策略单测(合成数据, 无 I/O)。

覆盖: 恐慌底买入 / 累计大流出卖出 / 先卖后买同日接力 / 预热期不交易。
"""

from __future__ import annotations

from base.analysis.strategy.kc50_beta import run_kc50_beta_strategy


def _mk(closes, caps):
    rows = []
    for i, c in enumerate(closes):
        cap = caps.get(i, {})
        rows.append(
            {
                "date": f"2023-{i // 30 + 1:02d}-{i % 30 + 1:02d}",
                "close_price": c,
                "price_position": cap.get("pp", 50.0),
                "trade_direction": cap.get("td", "NEUTRAL"),
                "share_prob": cap.get("sp", 10.0),
                "composite_prob": cap.get("cp", 45.0),
                "volume_ratio": cap.get("vr", 1.0),
                "shares_delta_yi": cap.get("sd", 0.0),
                "change_pct": cap.get("chg", 0.0),
            }
        )
    return rows


def test_warmup_no_trade() -> None:
    # 预热不足(250+20 交易日): 不交易
    closes = [1.0] * 100 + [0.9] + [0.8]
    caps = {100: {"pp": 5.0, "sp": 90.0, "chg": -7.0}}
    res = run_kc50_beta_strategy(_mk(closes, caps))
    assert res["trades"] == []


def test_panic_bottom_buy() -> None:
    # 恐慌底: 单日跌>=6% + pp<=20(案例 2026-07-30 -6.0% pp3) -> 买入
    closes = [2.0] * 290 + [1.88] + [2.0] * 20
    caps = {290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE"}}
    res = run_kc50_beta_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) >= 1
    assert trades[0]["action"] == "BUY" and "恐慌底" in trades[0]["reason"]


def test_outflow_cumulative_sell() -> None:
    # 持仓后 DISTRIBUTE 日累计流出 >=60亿 -> 卖(案例 2025-07-31+08-14 洗盘不卖)
    closes = [2.0] * 290 + [1.88] + [1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]
    caps = {
        290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE"},
        294: {"pp": 90.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2},
        295: {"pp": 92.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2},
        296: {"pp": 95.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2},
        297: {"pp": 96.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2},
    }
    res = run_kc50_beta_strategy(_mk(closes, caps))
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert any("顶部大流出" in t["reason"] for t in sells)


def test_sell_then_same_day_rebuy() -> None:
    # 先卖后买同日接力: 止损卖出日同时满足 P1 恐慌底(案例 2026-03-23 尾随卖+同日买)
    closes = [2.0] * 290 + [1.88, 1.78, 1.9, 1.92, 1.95]
    caps = {
        290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE"},  # P1 买@1.88
        291: {"pp": 8.0, "sp": 95.0, "chg": -6.2, "td": "ACCUMULATE"},  # 止损日 + 同日 P1 再买
    }
    res = run_kc50_beta_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 3  # 290 BUY + 291 SELL + 291 BUY
    assert trades[1]["action"] == "SELL" and trades[1]["date"] == trades[2]["date"]
    assert trades[2]["action"] == "BUY"
