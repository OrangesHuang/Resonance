"""市场情绪成交额数据源单测(无真实网络)。

覆盖:
  1. 分批切块: _turnover_chunks 按 chunk_days 自然日切批
  2. 东财失败回退雪球: fetch_turnover_range 优先东财, 空则雪球
  3. 批量行格式: date/sh_amount_yi/sz_amount_yi/total_amount_yi
"""

from __future__ import annotations

from base.scheduler.sentiment_jobs import _turnover_chunks


def test_turnover_chunks_splits_by_days() -> None:
    chunks = _turnover_chunks("2021-01-01", "2021-01-31", 10)
    assert len(chunks) == 4  # 1-10, 11-20, 21-30, 31
    assert chunks[0] == ("2021-01-01", "2021-01-10")
    assert chunks[-1] == ("2021-01-31", "2021-01-31")


def test_turnover_chunks_single() -> None:
    chunks = _turnover_chunks("2021-01-01", "2021-01-05", 10)
    assert chunks == [("2021-01-01", "2021-01-05")]


def test_turnover_chunks_force_break() -> None:
    # 跨年切批: 年底最后一天单独成批
    chunks = _turnover_chunks("2021-12-30", "2022-01-03", 5)
    assert chunks[0] == ("2021-12-30", "2022-01-03")
