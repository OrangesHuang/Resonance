"""份额折算/合并的识别与中和(纯函数, 无 I/O)。

核心认知
--------
"份额折算"(拆分/合并) 会按比例 k 改变基金份额总数, 但**没有任何资金申赎发生**:
份额 ×k 的同时单位净值 ÷k —— 不复权价格 ÷k, 而前复权价格保持连续。因此:

  - 不识别 → 把折算日当成天量申购/赎回。实例: 515880(通信ETF) 2026-07-03 的
    2:1 折算被记为 **+333.13 亿份申购**, 2026-02-02 的 3:1 折算被记为 +97.37 亿份;
    512100 2022-09-05 的约 3:1 **份额合并** 被记为 −65.79 亿份赎回(假利空)。
  - 判别依据是 **复权因子(不复权/前复权)比例 ≈ 份额比例**: 折算使因子按 k 跳变,
    份额同步按 k 变化。

为什么不能用"变化幅度阈值"判定
------------------------------
`512100` 2024-02-05(+132.8%)、`563300` 2024-02-08(+444.9%)、`588000` 2021-04-01
(+65.2%) 都是**真实的天量申购**(救市资金/爆款发行), 复权因子全程不变。若按
"|变化| > 50% 即折算"粗暴抹掉, 会把真信号一起毁掉。故必须比对复权因子。

算法结构
--------
1. `find_factor_jump`: 在事件日附近的复权因子序列里找跳变点 → 折算前后因子。
2. `detect_share_adjust`: 校验"份额比例 ≈ 因子比例", 并扣除折算成分, 得到真实净申赎。
3. `rebase_shares_window`: 把折算前的份额水平按 k 归一到折算后基准, 供份额概率
   (水平型双基准) 重算 —— 否则跨折算日的 `pct_10d` 会被基准断层放大。
"""

from __future__ import annotations

from dataclasses import dataclass

SHARE_ADJUST_TRIGGER_PCT = 30.0  # |单日份额变化%| 达到此值才作为折算候选(真实单日申赎极少超 30%)
SHARE_ADJUST_FACTOR_EPS = 0.005  # 复权因子相对变化超过此值视为跳变
SHARE_ADJUST_RATIO_TOL = 0.12  # 份额比例与折算比例允许的相对偏差
# 折算必然使单位净值大幅变动(常见 1.5:1~10:1), 故要求比例显著偏离 1;
# 否则源数据里 0.5% 级别的因子抖动会与"水平几乎没变"的脏行相互匹配成假阳性
# (实例: 515080 2021-01-04 因子 1.0→1.0052 曾被误判为折算)。
SHARE_ADJUST_MIN_DEV = 0.15


@dataclass(frozen=True)
class ShareAdjust:
    """一次折算/合并的判定结果。"""

    ratio: float  # 折算比例 k = 折算前因子 / 折算后因子(>1 拆分, <1 合并)
    real_delta_yi: float  # 扣除折算后的真实净申赎(亿份, 折算后基准)
    real_delta_pct: float  # 真实净申赎相对折算后份额的百分比


def find_factor_jump(ratios: list[tuple[str, float]]) -> tuple[float, float] | None:
    """在 (日期, 复权因子) 序列里找首个跳变, 返回 (折算前因子, 折算后因子)。

    无跳变返回 None(真实申赎场景)。
    """
    for i in range(1, len(ratios)):
        prev, cur = ratios[i - 1][1], ratios[i][1]
        if prev <= 0 or cur <= 0:
            continue
        if abs(cur / prev - 1) > SHARE_ADJUST_FACTOR_EPS:
            return prev, cur
    return None


def detect_share_adjust(
    shares_before: float | None,
    shares_after: float | None,
    factor_before: float | None,
    factor_after: float | None,
) -> ShareAdjust | None:
    """判定事件日是否为份额折算; 是则返回折算比例与扣除后的真实净申赎。

    - shares_before/after: 事件前一日 / 事件日的份额(亿份)
    - factor_before/after: 事件日附近折算前 / 后的复权因子
    判据: 份额比例 ≈ 折算比例(因子比)。不满足则视为真实申赎, 返回 None。
    """
    if not shares_before or not shares_after or shares_before <= 0:
        return None
    if not factor_before or not factor_after or factor_before <= 0 or factor_after <= 0:
        return None
    ratio = shares_after / shares_before
    k = factor_before / factor_after
    if abs(k - 1.0) < SHARE_ADJUST_MIN_DEV:
        return None  # 因子跳变不显著 → 噪音, 非折算
    if abs(ratio - 1.0) < SHARE_ADJUST_MIN_DEV:
        return None  # 份额水平未显著变化 → 非折算(可拦截存量脏行: delta 与实际水平不符)
    if abs(ratio - k) / k > SHARE_ADJUST_RATIO_TOL:
        return None  # 份额变化与折算比例不成比例 → 非折算
    base = shares_before * k  # 折算后应有份额(无真实申赎时)
    real_delta = shares_after - base
    real_pct = real_delta / base * 100 if base > 0 else 0.0
    return ShareAdjust(ratio=k, real_delta_yi=real_delta, real_delta_pct=real_pct)


def rebase_shares_window(levels: list[float], ratio: float) -> list[float]:
    """把折算前(旧基准)的份额水平按 ratio 归一到折算后基准。

    `calc_share_probability_dual` 是水平型双基准(当日 vs 前 N 日均值), 跨折算日时
    旧基准水平会使 pct_10d 凭空放大 k 倍; 归一后比较才有意义。
    """
    return [lv * ratio for lv in levels]


def is_candidate(delta_pct: float | None) -> bool:
    """份额单日变化是否达到折算候选阈值。"""
    return delta_pct is not None and abs(delta_pct) >= SHARE_ADJUST_TRIGGER_PCT
