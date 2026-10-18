"""科创50 (588000) 正式版策略单测(合成数据, 无 I/O)。

覆盖: 恐慌底买入 / 累计大流出卖出 / 卖出日禁止同日买回 / 预热期不交易。
"""

from __future__ import annotations

from base.analysis.strategy.kc50 import run_kc50_strategy


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
    res = run_kc50_strategy(_mk(closes, caps))
    assert res["trades"] == []


def test_panic_bottom_buy() -> None:
    # 恐慌底: 单日跌>=6% + pp<=20(案例 2026-07-30 -6.0% pp3) -> 买入
    closes = [2.0] * 290 + [1.88] + [2.0] * 20
    caps = {290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE", "sd": 3.0}}
    res = run_kc50_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) >= 1
    assert trades[0]["action"] == "BUY" and "恐慌底" in trades[0]["reason"]


def test_outflow_cumulative_sell() -> None:
    # 持仓后 DISTRIBUTE 日累计流出 >=60亿 -> 卖(案例 2025-07-31+08-14 洗盘不卖)
    closes = [2.0] * 290 + [1.88] + [1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]
    caps = {
        290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE", "sd": 3.0},
        294: {"pp": 90.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2, "sp": 50.0},
        295: {"pp": 92.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2, "sp": 50.0},
        296: {"pp": 95.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2, "sp": 50.0},
        297: {"pp": 96.0, "td": "DISTRIBUTE", "sd": -30.0, "chg": 1.0, "vr": 1.2, "sp": 50.0},
    }
    res = run_kc50_strategy(_mk(closes, caps))
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert any("顶部大流出" in t["reason"] for t in sells)


def test_bull_crash_sell() -> None:
    # 牛市持仓单日暴跌>=6% -> 果断离场(案例 2026-07-02 顶后次日 -7.5% 卖@2.119)
    closes = [1.0 + i * 0.004 for i in range(290)] + [2.1, 2.0, 1.95]
    caps = {
        290: {"pp": 10.0, "sp": 95.0, "chg": -6.5, "td": "ACCUMULATE", "sd": 3.0},  # P1 买@2.1
        291: {"pp": 50.0, "sp": 50.0, "chg": -7.5, "td": "NEUTRAL"},  # 跌4.8%不触止损, S6 离场
    }
    res = run_kc50_strategy(_mk(closes, caps))
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert any("牛市暴跌" in t["reason"] for t in sells)


def test_sell_blocks_same_day_rebuy() -> None:
    # 卖出日不得同日买回: 止损日同时满足 P1 恐慌底(旧版 2026-03-23 尾随卖+同日买)也只卖
    closes = [2.0] * 290 + [1.88, 1.78, 1.9, 1.92, 1.95]
    caps = {
        290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE", "sd": 3.0},  # P1 买@1.88
        291: {"pp": 8.0, "sp": 95.0, "chg": -6.2, "td": "ACCUMULATE", "sd": 3.0},  # 止损日 + P1 再买被拦
    }
    res = run_kc50_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert [t["action"] for t in trades] == ["BUY", "SELL"]  # 同日接力被 REBUY_DELAY 阻断


def test_no_same_day_sell_then_buy_anywhere() -> None:
    # 不变量: 任何行情序列都不应出现同日 SELL+BUY
    closes = [2.0] * 290 + [1.88, 1.78, 1.68, 1.6, 1.5, 1.9, 1.85]
    caps = {
        290: {"pp": 10.0, "sp": 95.0, "chg": -6.0, "td": "ACCUMULATE", "sd": 3.0},
        291: {"pp": 8.0, "sp": 95.0, "chg": -6.2, "td": "ACCUMULATE", "sd": 3.0},
        292: {"pp": 5.0, "sp": 95.0, "chg": -6.5, "td": "ACCUMULATE", "sd": 3.0},
        293: {"pp": 4.0, "sp": 95.0, "chg": -6.1, "td": "ACCUMULATE", "sd": 3.0},
        295: {"pp": 6.0, "sp": 95.0, "chg": -6.3, "td": "ACCUMULATE", "sd": 3.0},
    }
    trades = run_kc50_strategy(_mk(closes, caps))["trades"]
    sell_dates = {t["date"] for t in trades if t["action"] == "SELL"}
    buy_dates = {t["date"] for t in trades if t["action"] == "BUY"}
    assert sell_dates & buy_dates == set()
