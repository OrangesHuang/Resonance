"""复权因子(不复权/前复权)拉取 —— 识别份额折算/合并的判据来源。

份额折算会使复权因子按比例 k 跳变(份额 ×k、不复权净值 ÷k、前复权价格连续),
真实申赎不会。故比对"不复权/前复权"比值即可区分二者, 详见
`base/analysis/shares_adjust.py`。

本模块只做 I/O 与比值计算, 不判定折算(判定属纯函数层)。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from base.fetch.kline import fetch_kline

FACTOR_WINDOW_DAYS = 30  # 事件日前后各取的自然日跨度(覆盖登记日/除权日错位)
FACTOR_FETCH_LIMIT = 800  # 单窗口K线根数上限(远大于窗口内交易日数)


def fetch_factor_series(code: str, start: str, end: str) -> list[tuple[str, float]]:
    """返回窗口内 (日期, 不复权/前复权) 的升序序列; 任一侧缺失的日期跳过。

    两侧各一次区间拉取(腾讯接口), 走 fetch_kline 的 TTL 缓存。
    """
    qfq = {b["date"]: b["close"] for b in fetch_kline(code, FACTOR_FETCH_LIMIT, start, end, "qfq")}
    bfq = {b["date"]: b["close"] for b in fetch_kline(code, FACTOR_FETCH_LIMIT, start, end, "bfq")}
    series: list[tuple[str, float]] = []
    for d in sorted(set(qfq) & set(bfq)):
        q, b = qfq[d], bfq[d]
        if q and q > 0:
            series.append((d, b / q))
    return series


def factor_window_around(date: str, span_days: int = FACTOR_WINDOW_DAYS) -> tuple[str, str]:
    """事件日 date 前后各 span_days 自然日的窗口。"""
    d = datetime.strptime(date, "%Y-%m-%d")
    return (
        (d - timedelta(days=span_days)).strftime("%Y-%m-%d"),
        (d + timedelta(days=span_days)).strftime("%Y-%m-%d"),
    )
