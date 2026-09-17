"""份额折算识别单测(纯函数, 无 I/O)。

覆盖真实案例: 515880 2026-07-03 的 2:1 折算、2026-02-02 的 3:1 折算、
512100 2022-09-05 的份额合并, 以及三例**真实天量申购**(不得误判为折算)。
"""

from __future__ import annotations

from base.analysis.shares_adjust import (
    detect_share_adjust,
    find_factor_jump,
    is_candidate,
    rebase_shares_window,
)


def test_detect_split_515880_20260703() -> None:
    # 真实案例: 份额 339.58 → 672.72 亿份, 复权因子 2.0 → 1.0 (2:1 拆分)
    adj = detect_share_adjust(339.58387, 672.71774, 2.0, 1.0)
    assert adj is not None
    assert abs(adj.ratio - 2.0) < 1e-9
    # 扣除折算后应有份额 679.17, 实际 672.72 → 真实净赎回约 -6.45 亿
    assert -7.0 < adj.real_delta_yi < -6.0
    assert -1.1 < adj.real_delta_pct < -0.8


def test_detect_split_515880_20260202() -> None:
    # 真实案例: 复权因子 6.0 → 2.0 (3:1 拆分), 份额 46.52 → 143.89
    adj = detect_share_adjust(46.52, 143.89, 6.0, 2.0)
    assert adj is not None
    assert abs(adj.ratio - 3.0) < 1e-9
    # 折算后应有 139.56, 实际 143.89 → 真实净申购约 +4.33 亿
    assert 4.0 < adj.real_delta_yi < 4.7


def test_detect_merge_512100_20220905() -> None:
    # 真实案例: 512100 约 3:1 份额合并(份额下降), 因子 0.376 → 1.03
    adj = detect_share_adjust(100.0, 36.0, 0.376, 1.030)
    assert adj is not None
    assert adj.ratio < 1.0  # 合并
    # 折算后应有 36.5 亿, 实际 36.0 → 轻微真实赎回
    assert abs(adj.real_delta_yi) < 1.0


def test_real_flow_not_detected() -> None:
    """真实天量申购: 复权因子全程不变 → 不得判为折算。"""
    # 512100 2024-02-05 +132.8% / 563300 2024-02-08 +444.9% / 588000 2021-04-01 +65.2%
    for before, after in ((100.0, 232.8), (10.0, 54.5), (100.0, 165.2)):
        assert detect_share_adjust(before, after, 1.0, 1.0) is None


def test_factor_changed_but_ratio_mismatch() -> None:
    """因子有跳变但份额比例对不上 → 不是折算(如折算叠加了真实申赎)。"""
    assert detect_share_adjust(100.0, 110.0, 2.0, 1.0) is None


def test_factor_noise_not_detected() -> None:
    """因子仅抖动 0.5% 且份额水平未变 → 不得判为折算。

    实例: 515080 2021-01-04, 存量行自相矛盾(delta_pct=+82% 但 shares_yi 与
    前一日相同 3.461489), 因子 1.0→1.0052 属源数据噪音。
    """
    assert detect_share_adjust(3.461489, 3.461489, 1.0, 1.0052) is None


def test_detect_none_inputs() -> None:
    assert detect_share_adjust(None, 672.7, 2.0, 1.0) is None
    assert detect_share_adjust(339.5, None, 2.0, 1.0) is None
    assert detect_share_adjust(339.5, 672.7, 0.0, 1.0) is None
    assert detect_share_adjust(0.0, 672.7, 2.0, 1.0) is None


def test_find_factor_jump() -> None:
    series = [
        ("2026-07-01", 2.0),
        ("2026-07-02", 2.0),
        ("2026-07-03", 2.0),
        ("2026-07-06", 1.0),
        ("2026-07-07", 1.0),
    ]
    assert find_factor_jump(series) == (2.0, 1.0)


def test_find_factor_jump_none() -> None:
    assert find_factor_jump([("2026-02-05", 1.0), ("2026-02-06", 1.0)]) is None
    assert find_factor_jump([]) is None


def test_rebase_shares_window() -> None:
    # 折算前基准的水平 ×k 后与折算后基准可比
    assert rebase_shares_window([10.0, 20.0], 3.0) == [30.0, 60.0]


def test_is_candidate() -> None:
    assert is_candidate(98.1) is True
    assert is_candidate(-64.5) is True
    assert is_candidate(29.9) is False
    assert is_candidate(None) is False
