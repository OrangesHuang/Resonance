"""中证1000 (512100) Beta — 数据延伸至 2014-10-17(指数发布日)验证多轮牛熊。

与正式版 zz.py 同一套规则, 唯一差异是 trade_start 提前到 2014-10-17:
用指数代理期(2014-10~2016-11, shares 全 None)与真实 ETF 期(2016-11 起)
回放 2015 疯牛/2016 熔断/2018 熊市/2019-2021 牛/2022 熊 多轮牛熊,
检验右侧量价记忆规则在更长样本上的可行性。份额规则在代理期自动降级
(sd/sp None, 巨量流出/验证期份额锁定不生效, 价格路径仍完整)。

数据边界(见 scripts/backfill_zz1000_2014.py):
  2014-10-17~2016-11-03: 中证1000 指数按上市首日比例缩放的价格代理
  (分红未计, 误差<2%), 无份额数据; 2016-11-04 起真实 ETF 与上交所份额。
"""

from __future__ import annotations

from base.analysis.strategy.zz import run_zz_strategy

ZZ_BETA_TRADE_START = "2014-10-17"


def run_zz_beta_strategy(rows: list[dict]) -> dict:
    return run_zz_strategy(rows, trade_start=ZZ_BETA_TRADE_START)
