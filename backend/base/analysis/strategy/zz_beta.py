"""中证1000 (512100) Beta — 数据延伸至 2006-01-01 验证 20 年多轮牛熊。

与正式版 zz.py 同一套规则, 唯一差异是 trade_start 提前到 2006-01-01:
2005-01~2014-10 为中证指数公司官方回溯点位(中证1000 基日 2004-12-31
=1000 点)按上市首日收盘比缩放的价格代理, 2014-10-17 起接腾讯真实数据,
2016-11-04 起真实 ETF 与上交所份额。回放 06-07 大牛/08 崩盘/09 反弹/
10-14 慢熊/15 疯牛股灾/16 熔断/18 熊市/19-21 牛/22 熊 全部周期。
份额规则在代理期自动降级(sd/sp None); 融资分位 2010-03 前无数据
(两融未开), 缩量深底路径在 2006-2010 不生效。本地验证槽位, 不升级。

数据边界(见 scripts/backfill_zz1000_2014.py):
  2014-10-17~2016-11-03: 中证1000 指数按上市首日比例缩放的价格代理
  (分红未计, 误差<2%), 无份额数据; 2016-11-04 起真实 ETF 与上交所份额。
"""

from __future__ import annotations

from base.analysis.strategy.zz import run_zz_strategy

ZZ_BETA_TRADE_START = "2006-01-01"


def run_zz_beta_strategy(rows: list[dict]) -> dict:
    return run_zz_strategy(rows, trade_start=ZZ_BETA_TRADE_START)
