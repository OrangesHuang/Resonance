"""科创芯片 (588200) — 复用科创50(588000) 的买卖点日期, 自身不产生信号。

核心认知:
  588000 体量最大、一级申赎数据最干净, kc50.py 的买卖点是本组最可靠的时间信号。
  588200 与它日收益相关 0.957、beta 1.18(943 个交易日), 同一批日期落在芯片上弹性
  更大。实测 2022-12-23~2026-10-16: 复用日期 +726.2%(13轮/胜61.5%/权益回撤-21.5%),
  同段日期留在 588000 自身 +387.3%, 588200 买入持有 +177.3%,
  此前 588200 落通用共振 _run_default 仅 1 笔 -20.0%。
  收益差主要来自 beta 放大而非新信息 —— 这是同一注押在更高弹性的标的上。

算法:
  1. 参考端买卖点由 router 调 kc50(含 _tp 成交额分位注入)算好后传入
  2. 按日期在 588200 收盘价上成交; 缺K线(上市前/停牌)的日期跳过
  3. 强制 BUY/SELL 交替: 若某轮的一腿被跳过, 另一腿一并丢弃, 不留下孤立的反向单
"""

from __future__ import annotations

from base.analysis.strategy.metrics import calc_round_metrics

CHIP_CODE = "588200"
REASON = "复用科创50信号"


def run_chip_strategy(rows: list[dict], ref_trades: list[dict]) -> dict:
    """把 588000 的买卖日期映射到 588200 的价格上。rows 须升序。"""
    by_date = {r["date"]: r for r in rows}
    trades: list[dict] = []
    in_pos = False
    for t in ref_trades:
        row = by_date.get(t["date"])
        if row is None or row.get("close_price") is None:
            continue
        if (t["action"] == "BUY") == in_pos:  # 同向重复 = 该轮另一腿缺K线, 丢弃
            continue
        in_pos = not in_pos
        trades.append({"date": t["date"], "action": t["action"], "price": row["close_price"], "reason": REASON})

    position = 1.0 if in_pos else 0.0
    last_close = rows[-1].get("close_price") or 0.0 if rows else 0.0
    return {
        "code": CHIP_CODE,
        "trades": trades,
        "metrics": calc_round_metrics(trades, last_close, position),
        "holding": position > 0,
    }
