"""科创综指 Beta 策略单测(合成数据, 无 I/O)。

覆盖: 高位散户顶卖 / 加速赶顶卖 / 洗盘回买 / 放量崩盘不买(防接刀) /
S1 出货浮盈门槛(主升中段洗盘不卖)。
"""

from __future__ import annotations

from base.analysis.strategy.kc_beta import run_kc_beta_strategy


def _mk(closes: list[float], caps: dict) -> list[dict]:
    rows = []
    for i, c in enumerate(closes):
        cap = caps.get(i, {})
        rows.append(
            {
                "date": f"2025-{(i // 30 + 4):02d}-{(i % 30 + 1):02d}",
                "close_price": c,
                "price_position": cap.get("pp", 50.0),
                "trade_direction": cap.get("td", "NEUTRAL"),
                "share_prob": cap.get("sp", 10.0),
                "volume_ratio": cap.get("vr", 1.0),
                "shares_delta_yi": cap.get("sd", 0.0),
                "change_pct": cap.get("chg", 0.0),
            }
        )
    return rows


def _buy_at_30(closes: list[float], caps: dict) -> None:
    """第 30 天用放量恐慌路径建立持仓。"""
    caps[30] = {"pp": 5.0, "chg": -5.8, "vr": 1.5, "sd": 0.5}


def test_greedy_top_sell() -> None:
    # 极高位 + 大量净申购 + 浮盈 -> 次日卖(案例 2025-08-28 / 2026-05-13)
    closes = [1.0] * 31 + [1.2] * 12
    caps: dict = {}
    _buy_at_30(closes, caps)
    caps[40] = {"pp": 99.0, "sp": 95.0, "sd": 1.0, "chg": 0.5}
    res = run_kc_beta_strategy(_mk(closes, caps))
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert len(sells) == 1
    assert "高位散户顶" in sells[0]["reason"]


def test_blowoff_sell() -> None:
    # 2日大阳 + pp>=99 + 浮盈 -> 当日卖(案例 2026-06-30)
    closes = [1.0] * 31 + [1.3] * 12
    caps: dict = {}
    _buy_at_30(closes, caps)
    caps[39] = {"chg": 3.0}
    caps[40] = {"pp": 99.5, "chg": 4.0, "sd": -0.1}
    res = run_kc_beta_strategy(_mk(closes, caps))
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert len(sells) == 1
    assert "加速赶顶" in sells[0]["reason"]


def test_washout_buy() -> None:
    # 缩量连两日大跌 + 位置不高 + 机构未撤 -> 当日买(案例 2026-06-08)
    closes = [1.5] * 30 + [1.6] + [1.5, 1.47, 1.45, 1.45, 1.45]
    caps: dict = {i: {"sd": 0.1} for i in range(30, 34)}
    caps[34] = {"chg": -2.5, "sp": 80.0}
    caps[35] = {"pp": 55.0, "chg": -3.5, "vr": 0.8, "sp": 80.0, "sd": 0.1}
    res = run_kc_beta_strategy(_mk(closes, caps))
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    assert len(buys) == 1
    assert "洗盘回买" in buys[0]["reason"]


def test_washout_blocked_by_panic_volume() -> None:
    # 放量崩盘日不是洗盘(案例 2026-07-17 vr2.06 拦): 不买
    closes = [1.5] * 30 + [1.6] + [1.5, 1.47, 1.45, 1.45, 1.45]
    caps: dict = {i: {"sd": 0.1} for i in range(30, 34)}
    caps[34] = {"chg": -2.5, "sp": 80.0}
    caps[35] = {"pp": 55.0, "chg": -3.5, "vr": 2.1, "sp": 80.0, "sd": 0.1}
    res = run_kc_beta_strategy(_mk(closes, caps))
    assert res["trades"] == []


def test_washout_blocked_by_sp_collapse() -> None:
    # 份额动能塌(前一日 sp<60)不买(案例 2026-07-16 sp50.2 拦)
    closes = [1.5] * 30 + [1.6] + [1.5, 1.47, 1.45, 1.45, 1.45]
    caps: dict = {i: {"sd": 0.1} for i in range(30, 34)}
    caps[34] = {"chg": -2.5, "sp": 50.0}
    caps[35] = {"pp": 55.0, "chg": -3.5, "vr": 0.8, "sp": 80.0, "sd": 0.1}
    res = run_kc_beta_strategy(_mk(closes, caps))
    assert res["trades"] == []


def test_s1_profit_floor() -> None:
    # 浮盈<20% 的 DISTRIBUTE 是主升中段洗盘(案例 2026-06-22): 不卖;
    # 浮盈>=20% 时同指纹才卖。
    closes = [1.0] * 31 + [1.15] * 9 + [1.3] * 6
    caps: dict = {}
    _buy_at_30(closes, caps)
    caps[39] = {"pp": 98.0, "td": "DISTRIBUTE", "vr": 1.6, "sd": -0.5, "chg": 1.0}
    res = run_kc_beta_strategy(_mk(closes, caps))
    assert not [t for t in res["trades"] if t["action"] == "SELL"]

    caps2: dict = {}
    _buy_at_30(closes, caps2)
    caps2[44] = {"pp": 99.0, "td": "DISTRIBUTE", "vr": 1.6, "sd": -0.5, "chg": 1.5}
    res2 = run_kc_beta_strategy(_mk(closes, caps2))
    sells = [t for t in res2["trades"] if t["action"] == "SELL"]
    assert len(sells) == 1
    assert "出货确认" in sells[0]["reason"]
