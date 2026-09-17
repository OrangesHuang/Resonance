"""份额补全任务的"上市前过滤"单测(纯函数, 无 I/O)。

背景: 「补全缺失份额」原先从 2005-01-17 起扫全库 5258 个缺失日, 其中大量是
512100 等标的**尚未成立**的日期 —— 远端必然返回空, 每 3 次失败暂停 60s,
几小时都跑不完。`_fillable_targets` 用"该标的已有份额的最早日期"剔除这些日期。
"""

from __future__ import annotations

from base.scheduler.shares_jobs import _fillable_targets


def test_skip_pre_listing_dates() -> None:
    # 512100 已有份额最早 2022-09-06, 2019 年的行是上市前的占位数据 → 不该补
    first = {"512100": "2022-09-06"}
    assert _fillable_targets("2019-07-22", ["512100"], first) == []
    assert _fillable_targets("2022-09-05", ["512100"], first) == []
    assert _fillable_targets("2022-09-06", ["512100"], first) == ["512100"]
    assert _fillable_targets("2026-07-03", ["512100"], first) == ["512100"]


def test_skip_codes_without_any_shares() -> None:
    # 完全没有份额的标的(需先做区间回填)不参与自动补全, 否则无法判断上市日
    assert _fillable_targets("2026-07-03", ["588200"], {}) == []
    assert _fillable_targets("2026-07-03", ["588200"], {"515880": "2019-10-11"}) == []


def test_mixed_targets() -> None:
    first = {"512100": "2022-09-06", "588200": "2022-11-22"}
    assert _fillable_targets("2026-07-03", ["512100", "588200", "510300"], first) == ["512100", "588200"]
    assert _fillable_targets("2022-10-01", ["512100", "588200"], first) == ["512100"]


def test_empty_targets() -> None:
    assert _fillable_targets("2026-07-03", [], {"588200": "2022-11-22"}) == []
