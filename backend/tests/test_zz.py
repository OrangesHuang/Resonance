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
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0, "vr": 1.5}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 2
    assert trades[0]["action"] == "BUY" and "低位吸筹" in trades[0]["reason"]
    assert trades[1]["action"] == "SELL" and "买入未验证" in trades[1]["reason"]
    assert trades[1]["date"] == "2021-02-21"  # 索引 50 = 40+10


def test_recovery_no_verify_sell() -> None:
    # 买入后短暂下探但第 10 日前收复 ≥3% → 验证期不触发
    closes = [2.0] * 41 + [1.95, 1.9, 1.95, 2.0, 2.05] + [2.1] * 20
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0, "vr": 1.5}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 1  # 只有买入, 无卖出
    assert trades[0]["action"] == "BUY"


def test_escape_then_underwater_guard_sell() -> None:
    # 买入后前 15 日已脱离成本区(+5%, 验证期窗口过后) → 再阴跌 8%+ 持续 15 日
    # → 底部失败守卫离场(2024-02-01 式浮亏但最终收复的防线)
    closes = [2.0] * 41 + [2.1] * 15 + [1.8] * 20
    caps = {40: {"pp": 20.0, "td": "ACCUMULATE", "sp": 80.0, "chg": 1.0, "vr": 1.5}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) == 2
    assert trades[0]["action"] == "BUY"
    assert trades[1]["action"] == "SELL" and "底部失败" in trades[1]["reason"]
    # 买入 i=40, +1..+15 日=2.1(脱离), 第 16 日(索引56)起 1.8 浮亏 8%+
    # 连续 15 日后(索引 70)守卫卖出
    assert trades[1]["date"] == "2021-03-11"


def test_quiet_deep_bottom_buy() -> None:
    # 缩量深底: 250日高点后回撤 30%(高点3.0→2.1), NEUTRAL+pp<=12+融资<=30+近10日无ACCUMULATE
    # → 缩量深底买入, 30日验证期(20-30日), 不触发10日普通验证
    closes = [3.0] * 200 + [2.9, 2.8, 2.7, 2.6, 2.5, 2.4, 2.3, 2.2, 2.15, 2.1] + [2.2] * 40
    caps = {
        209: {"pp": 8.0, "td": "NEUTRAL", "sp": 90.0, "vr": 1.0, "mp": 5.0},
    }
    rows = _mk(closes, caps)
    # 注入 _mp(router 会做, 测试直接模拟)
    for i, r in enumerate(rows):
        if i == 209:
            r["_mp"] = 5.0
    res = run_zz_strategy(rows)
    trades = res["trades"]
    assert len(trades) >= 1
    assert trades[0]["action"] == "BUY" and "缩量深底" in trades[0]["reason"]
    # 20-30日验证期内价格从2.1涨到2.2(+4.8%>3%) → 通过, 不卖出
    assert len(trades) == 1


def test_quiet_deep_bottom_not_with_recent_accum() -> None:
    # 近10日有 ACCUMULATE → 缩量深底不触发(防与放量信号重叠, 案例 2024-06-24)
    closes = [3.0] * 200 + [2.9, 2.8, 2.7, 2.6, 2.5, 2.4, 2.3, 2.2, 2.15, 2.1] + [2.2] * 40
    caps = {
        205: {"pp": 30.0, "td": "ACCUMULATE", "sp": 80.0, "vr": 1.5},
        209: {"pp": 8.0, "td": "NEUTRAL", "sp": 90.0, "vr": 1.0, "mp": 5.0},
    }
    rows = _mk(closes, caps)
    for i, r in enumerate(rows):
        if i == 209:
            r["_mp"] = 5.0
    res = run_zz_strategy(rows)
    trades = [t for t in res["trades"] if t["action"] == "BUY"]
    # 205 是 ACCUMULATE+pp30+sp80+vr1.5 → 低位吸筹(pp30>25 不触发), 不买
    # 209 因近10日(205)有 ACCUMULATE → 缩量深底不触发
    assert all("缩量深底" not in t["reason"] for t in trades)


def test_bear_heat_top_stop_sells() -> None:
    # 熊市(ma250下行) 持仓中 pp>=70 且 _tp>=80 且破5日低 → 热度顶波段卖出
    # 构造: 250+ 日缓降(ma250下行=熊市) -> 低位吸筹买 -> 反弹到 pp 高位 + tp 热 -> 破5日低
    closes = [3.6 - i * 0.003 for i in range(270)] + [2.79, 2.85, 2.9, 2.95, 3.0, 3.05, 3.1, 3.12, 3.1, 3.05, 3.0]
    caps = {270: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -3.0, "vr": 1.5}}
    rows = _mk(closes, caps)
    # 注入 _tp 热(>=80) 和 pp 高(>=70) 在反弹高位
    for i in (276, 277, 278, 279, 280):
        rows[i]["price_position"] = 75.0
        rows[i]["_tp"] = 85.0
    res = run_zz_strategy(rows)
    trades = res["trades"]
    sells = [t for t in trades if t["action"] == "SELL"]
    assert any("熊市热度顶" in t["reason"] for t in sells)


def test_panic_bottom_buy() -> None:
    # 单日史诗级恐慌底: 跌>=7%+pp<=20, 不限 td/vr(跌停日量比失真)
    # (案例 2020-02-03 疫情底 -10.4% vr0.85 tdNEUTRAL -> V反弹)
    closes = [2.0] * 40 + [1.79] + [2.0] * 25
    caps = {40: {"pp": 10.0, "td": "NEUTRAL", "vr": 0.8, "chg": -10.5, "sp": 30.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) >= 1
    assert trades[0]["action"] == "BUY" and "恐慌底" in trades[0]["reason"]
    # 买入后第10日累计 +11.7% >= 0 -> 验证锁定, 无卖出
    assert all(t["action"] != "SELL" for t in trades)


def test_rapid_end_buy() -> None:
    # 急跌末端企稳: 当日跌>=4.5%+pp<=30+20日跌>=12%+近10日无ACC
    # (案例 2020-03-23 -4.6% pp27 20日-16% tdNEUTRAL -> V反弹+40.8%)
    closes = [2.2] * 20 + [2.16, 2.12, 2.08, 2.04, 2.0, 1.96, 1.92, 1.88, 1.86, 1.84] + [1.75] + [1.8] * 25
    caps = {30: {"pp": 27.0, "td": "NEUTRAL", "vr": 0.7, "chg": -4.9, "sp": 10.0}}
    res = run_zz_strategy(_mk(closes, caps))
    trades = res["trades"]
    assert len(trades) >= 1
    assert trades[0]["action"] == "BUY" and "急跌末端" in trades[0]["reason"]


def test_extreme_sell_bear_only() -> None:
    # 熊市(ma250下行): DISTRIBUTE集群+加速赶顶(涨>=3%) -> 立即卖(2024-10-08 案例保留)
    closes = [3.6 - i * 0.005 for i in range(270)] + [2.255, 2.26, 2.3, 2.35, 2.42, 2.5]
    caps = {
        270: {"pp": 5.0, "td": "ACCUMULATE", "sp": 90.0, "chg": -2.0, "vr": 1.6},
        273: {"pp": 86.0, "td": "DISTRIBUTE", "vr": 1.6},
        274: {"pp": 88.0, "td": "DISTRIBUTE", "vr": 1.6},
        275: {"pp": 90.0, "td": "DISTRIBUTE", "chg": 3.6, "vr": 1.6},
    }
    res = run_zz_strategy(_mk(closes, caps))
    sells = [t for t in res["trades"] if t["action"] == "SELL"]
    assert any("加速赶顶" in t["reason"] for t in sells)


def test_extreme_no_sell_in_bull() -> None:
    # 牛市(ma250上行): 同样 DISTRIBUTE+加速赶顶 -> 不立即卖, 转顶部观察
    # (案例 2019-02-18 春季主升卖飞+15% / 2020-07-06 科技牛卖飞+8%)
    closes = [2.2 + i * 0.005 for i in range(270)] + [3.55, 3.6, 3.65, 3.7, 3.8, 3.95]
    caps = {
        270: {"pp": 20.0, "td": "ACCUMULATE", "sp": 90.0, "chg": 1.0, "vr": 1.6},
        273: {"pp": 86.0, "td": "DISTRIBUTE", "vr": 1.6},
        274: {"pp": 88.0, "td": "DISTRIBUTE", "vr": 1.6},
        275: {"pp": 90.0, "td": "DISTRIBUTE", "chg": 3.9, "vr": 1.6},
    }
    res = run_zz_strategy(_mk(closes, caps))
    assert all("加速赶顶" not in t["reason"] for t in res["trades"])
