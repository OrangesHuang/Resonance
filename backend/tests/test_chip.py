"""科创芯片 (588200) 日期复用单测(合成数据, 无 I/O)。

覆盖: 同日按目标标的收盘价成交 / 缺K线的日期跳过 / 缺腿不留孤立反向单 / 未平仓轮计价。
"""

from __future__ import annotations

from base.analysis.strategy.chip import run_chip_strategy


def _mk(pairs: list[tuple[str, float]]) -> list[dict]:
    return [{"date": d, "close_price": c} for d, c in pairs]


def _ref(*items: tuple[str, str]) -> list[dict]:
    return [{"date": d, "action": a, "price": 1.0, "reason": "x"} for d, a in items]


def test_maps_target_closes() -> None:
    rows = _mk([("d1", 1.00), ("d2", 1.10), ("d3", 1.21), ("d4", 1.30)])
    res = run_chip_strategy(rows, _ref(("d2", "BUY"), ("d3", "SELL")))
    assert [(t["date"], t["action"], t["price"]) for t in res["trades"]] == [("d2", "BUY", 1.10), ("d3", "SELL", 1.21)]
    assert res["metrics"]["total_return_pct"] == 10.0
    assert res["holding"] is False


def test_skips_dates_without_bar_and_keeps_alternation() -> None:
    # d1(参考端 SELL)在 588200 没有K线 → 不能留下一笔无买入腿的孤立卖单
    rows = _mk([("d2", 2.0), ("d3", 2.2), ("d4", 1.9), ("d5", 1.71)])
    res = run_chip_strategy(rows, _ref(("d1", "SELL"), ("d2", "BUY"), ("d3", "SELL"), ("d4", "BUY")))
    assert [(t["date"], t["action"]) for t in res["trades"]] == [("d2", "BUY"), ("d3", "SELL"), ("d4", "BUY")]
    assert res["holding"] is True
    assert res["metrics"]["round_count"] == 2  # 第二轮未平仓, 按最新收盘 1.71 计浮盈
    assert res["metrics"]["total_return_pct"] == -1.0  # +10% × -10%
    assert res["metrics"]["win_rate"] == 50.0


def test_no_signal_when_ref_missing() -> None:
    rows = _mk([("d1", 1.0), ("d2", 1.0)])
    res = run_chip_strategy(rows, [])
    assert res["trades"] == []
    assert res["holding"] is False
    assert res["metrics"]["total_return_pct"] == 0.0
