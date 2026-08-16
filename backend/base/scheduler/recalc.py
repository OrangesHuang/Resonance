"""存量综合概率重算任务: 将历史 composite_prob/signal_level 对齐到当前 V2 算法。

背景: 历史行在 V1 简单加权时代固化(V2 于 2026-08-11 升级),
且份额后补回填时未重算 cp。本任务重算 dir_prob + composite_prob +
signal_level, 不改动任何原始数据字段, 幂等可重入。

注意: dp 也需重算 — 方向概率的 rally 折扣/低位反弹启动(f1)等规则会随
代码演进变化(如 pp≤50 指数大涨日豁免打折), 旧 dp 重算出的 cp 仍会偏。
dp 重算依赖行内 change_pct/volume_ratio/idx_chg + 前5日收盘(重建 t5)。
"""

from __future__ import annotations

from base.config import ETFS
from base.scheduler.job_manager import ProgressFn
from base.store.daily_repo import get_by_code, update_direction_signal
from resonance.analysis.composite import calc_composite_probability
from resonance.analysis.factors import calc_direction_probability, classify_signal


def _t5_return(rows: list[dict], idx: int) -> float:
    if idx < 4:
        return 0.0
    win = rows[idx - 4 : idx + 1]
    if not win[0].get("close_price"):
        return 0.0
    return (win[-1]["close_price"] / win[0]["close_price"] - 1) * 100


def _idx_t5_return(rows: list[dict], idx: int) -> float:
    """用行内 idx_chg 累乘重建指数近似收盘, 算含当日5日涨幅(与生产 scheduler
    _calc_t5_return 语义一致: 窗口含 target_idx 当日)。"""
    if idx < 4:
        return 0.0
    idx_close = [100.0]
    for j in range(1, idx + 1):
        ic = rows[j].get("idx_chg") or 0
        idx_close.append(idx_close[-1] * (1 + ic / 100))
    return (idx_close[idx] / idx_close[idx - 4] - 1) * 100


def job_recalc_composite(progress: ProgressFn) -> dict:
    """全量重算 dir_prob + composite_prob + signal_level。"""
    codes = list(ETFS.keys())
    updated = 0
    unchanged = 0
    for i, code in enumerate(codes, 1):
        progress(i, len(codes), f"{code} {ETFS[code]['name']}")
        rows = list(reversed(get_by_code(code)))  # 升序: _t5_return 需"过去4日"窗口
        for idx, r in enumerate(rows):
            vp = r.get("vol_prob")
            if vp is None:
                continue
            pp = r.get("price_position")
            sp = r.get("share_prob")
            chg = r.get("change_pct") or 0
            dp = calc_direction_probability(
                chg=chg,
                t5_etf=_t5_return(rows, idx),
                t5_idx=_idx_t5_return(rows, idx),
                volume_ratio=r.get("volume_ratio") or 0,
                idx_chg=r.get("idx_chg") or 0,
                price_position=pp,
            )
            cp = calc_composite_probability(vp, dp, sp, pp)
            level = classify_signal(cp)
            if (
                abs((r.get("dir_prob") or 0) - dp) < 0.05
                and cp == r.get("composite_prob")
                and level == r.get("signal_level")
            ):
                unchanged += 1
                continue
            update_direction_signal(r["date"], code, dp, cp, level)
            updated += 1
    progress(len(codes), len(codes), f"重算 {updated} 行 (一致 {unchanged} 行)")
    return {"updated": updated, "unchanged": unchanged, "etfs": len(codes)}
