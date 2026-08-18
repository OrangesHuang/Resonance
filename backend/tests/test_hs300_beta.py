"""沪深300 Beta 策略单测(合成数据, 无 I/O)。

覆盖: 2014 数据延伸起点生效(2015 恐慌底可买, 正式版 2019 前不交易)。
"""

from __future__ import annotations

from base.analysis.strategy.hs300 import run_hs300_strategy
from base.analysis.strategy.hs300_beta import run_hs300_beta_strategy


def _mk(n: int = 40) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "date": f"2015-{(i // 30 + 5):02d}-{(i % 30 + 1):02d}",
                "close_price": 1.0,
                "price_position": 50.0,
                "trade_direction": "NEUTRAL",
                "share_prob": None,
                "volume_ratio": 1.0,
                "shares_delta_yi": None,
                "change_pct": 0.0,
                "composite_prob": 45.0,
            }
        )
    return rows


def test_beta_2015_panic_buy() -> None:
    # 恐慌底(跌>=7%+pp<=20, 不分牛熊): 2015 年可买
    rows = _mk()
    rows[-1].update({"change_pct": -8.0, "price_position": 10.0})
    res = run_hs300_beta_strategy(rows)
    buys = [t for t in res["trades"] if t["action"] == "BUY"]
    assert len(buys) == 1
    assert "恐慌" in buys[0]["reason"]


def test_stable_skips_pre_2019() -> None:
    # 正式版 TRADE_START=2019: 同数据 2015 年不交易
    rows = _mk()
    rows[-1].update({"change_pct": -8.0, "price_position": 10.0})
    res = run_hs300_strategy(rows)
    assert res["trades"] == []
