"""沪深300 (510300) Beta — 数据延伸至 2014-01-01 验证多轮牛熊。

与正式版 hs300.py 同一套规则, 唯一差异是 trade_start 提前到 2014-01-01:
510300 于 2012-05-28 上市, 2014 起全程真实 ETF 数据(腾讯上市首日起、
上交所份额 2013-06 起), 无指数代理。回放 14-15 大牛/15 股灾/16 熔断/
17 白马牛/18 熊 周期, 检验牛熊分治规则在更长样本上的可行性。
2013 年为预热年(MA250 窗口)。本地验证槽位, 不升级。
"""

from __future__ import annotations

from base.analysis.strategy.hs300 import run_hs300_strategy

HS300_BETA_TRADE_START = "2014-01-01"


def run_hs300_beta_strategy(rows: list[dict]) -> dict:
    return run_hs300_strategy(rows, trade_start=HS300_BETA_TRADE_START)
