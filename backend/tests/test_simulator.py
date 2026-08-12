"""simulator 等权满仓调度单测(合成数据, 无 I/O)。"""

from __future__ import annotations

from portfolio.analysis.simulator import simulate

D = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09"]
PRICE = 1.0  # 全部标的恒定价格, 金额即份额


def pm(*codes: str) -> dict[str, dict[str, float]]:
    return {c: {d: PRICE for d in D} for c in codes}


def hist(r: dict, d: str) -> dict:
    return next(h for h in r["history"] if h["date"] == d)


def log(r: dict, d: str, kind: str) -> list[dict]:
    return [t for t in r["trade_log"] if t["date"] == d and t["kind"] == kind]


def test_first_buy_full_position() -> None:
    r = simulate({"A": [{"date": D[0], "action": "BUY", "price": PRICE}]}, pm("A"), D)
    h = hist(r, D[1])  # 信号次日成交
    assert h["position_pct"] == 100.0
    assert r["trade_log"][0]["kind"] == "BUY"
    assert r["trade_log"][0]["weight_pct"] == 100.0


def test_second_buy_equal_half() -> None:
    trades = {
        "A": [{"date": D[0], "action": "BUY", "price": PRICE}],
        "B": [{"date": D[2], "action": "BUY", "price": PRICE}],
    }
    r = simulate(trades, pm("A", "B"), D)
    h = hist(r, D[3])  # B 成交日
    assert h["position_pct"] == 100.0
    assert len(log(r, D[3], "TRIM")) == 1  # A 减半
    assert abs(log(r, D[3], "TRIM")[0]["amount"] - 0.5) < 1e-6
    for t in log(r, D[3], "TRIM") + log(r, D[3], "BUY"):
        assert abs(t["weight_pct"] - 50.0) < 0.01


def test_third_buy_equal_thirds() -> None:
    trades = {
        "A": [{"date": D[0], "action": "BUY", "price": PRICE}],
        "B": [{"date": D[1], "action": "BUY", "price": PRICE}],
        "C": [{"date": D[2], "action": "BUY", "price": PRICE}],
    }
    r = simulate(trades, pm("A", "B", "C"), D)
    exec_d = D[3]  # C 成交日
    for t in log(r, exec_d, "TRIM") + log(r, exec_d, "BUY") + log(r, exec_d, "REFILL"):
        assert abs(t["weight_pct"] - 100.0 / 3) < 0.01
    assert hist(r, exec_d)["position_pct"] == 100.0


def test_sell_cash_idle_until_next_buy() -> None:
    trades = {
        "A": [
            {"date": D[0], "action": "BUY", "price": PRICE},
            {"date": D[3], "action": "SELL", "price": PRICE},
        ],
        "B": [{"date": D[1], "action": "BUY", "price": PRICE}],
        "C": [{"date": D[2], "action": "BUY", "price": PRICE}],
        "D": [{"date": D[4], "action": "BUY", "price": PRICE}],
    }
    r = simulate(trades, pm("A", "B", "C", "D"), D)
    h_sell = hist(r, D[4])  # A 清仓日: 回款闲置, 剩余持仓不再平衡
    assert abs(h_sell["position_pct"] - 66.7) < 0.1
    assert len(log(r, D[4], "REFILL")) == 0
    # D 成交: 并入闲置资金, B/C/D 三仓各 1/3(卖出的 A 不再持有)
    for t in log(r, D[5], "TRIM") + log(r, D[5], "BUY"):
        assert abs(t["weight_pct"] - 100.0 / 3) < 0.01
    assert hist(r, D[5])["position_pct"] == 100.0


def test_same_day_multi_buy_equal_weight() -> None:
    trades = {
        "A": [{"date": D[0], "action": "BUY", "price": PRICE}],
        "B": [{"date": D[0], "action": "BUY", "price": PRICE}],
        "C": [{"date": D[0], "action": "BUY", "price": PRICE}],
    }
    r = simulate(trades, pm("A", "B", "C"), D)
    buys = log(r, D[1], "BUY")
    assert len(buys) == 3
    for t in buys:
        assert abs(t["weight_pct"] - 100.0 / 3) < 0.01
    assert hist(r, D[1])["position_pct"] == 100.0


def test_same_day_sell_then_rebuy_same_code() -> None:
    trades = {
        "A": [
            {"date": D[0], "action": "BUY", "price": PRICE},
            {"date": D[2], "action": "SELL", "price": PRICE},
            {"date": D[2], "action": "BUY", "price": PRICE},
        ],
        "B": [{"date": D[1], "action": "BUY", "price": PRICE}],
    }
    r = simulate(trades, pm("A", "B"), D)
    # D[3]: 先清 A 再重建, 最终 A/B 各 50%
    assert hist(r, D[3])["position_pct"] == 100.0
    assert {p["code"] for p in r["open_positions"]} == {"A", "B"}


def test_all_sell_empty_position() -> None:
    trades = {
        "A": [{"date": D[0], "action": "BUY", "price": PRICE}, {"date": D[2], "action": "SELL", "price": PRICE}],
        "B": [{"date": D[1], "action": "BUY", "price": PRICE}, {"date": D[2], "action": "SELL", "price": PRICE}],
    }
    r = simulate(trades, pm("A", "B"), D)
    assert hist(r, D[3])["position_pct"] == 0.0
    assert r["empty_days"] == len(D) - 2  # 除持仓两日外全部空仓
