"""存量综合概率重算任务: 将历史 composite_prob/signal_level 对齐到当前 V2 算法。

背景: 历史行在 V1 简单加权时代固化(V2 于 2026-08-11 升级),
且份额后补回填时未重算 cp。本任务仅用行内 vol_prob/dir_prob/share_prob/
price_position 重算, 不改动任何原始数据字段, 幂等可重入。
"""

from __future__ import annotations

from base.config import ETFS
from base.scheduler.job_manager import ProgressFn
from base.store.daily_repo import get_by_code, update_composite_signal
from resonance.analysis.composite import calc_composite_probability
from resonance.analysis.factors import classify_signal


def job_recalc_composite(progress: ProgressFn) -> dict:
    """全量重算 composite_prob/signal_level (V1 → V2 对齐)。"""
    codes = list(ETFS.keys())
    updated = 0
    unchanged = 0
    for i, code in enumerate(codes, 1):
        progress(i, len(codes), f"{code} {ETFS[code]['name']}")
        for r in get_by_code(code):
            vp = r.get("vol_prob")
            dp = r.get("dir_prob")
            if vp is None or dp is None:
                continue
            cp = calc_composite_probability(vp, dp, r.get("share_prob"), r.get("price_position"))
            level = classify_signal(cp)
            if cp == r.get("composite_prob") and level == r.get("signal_level"):
                unchanged += 1
                continue
            update_composite_signal(r["date"], code, cp, level)
            updated += 1
    progress(len(codes), len(codes), f"重算 {updated} 行 (一致 {unchanged} 行)")
    return {"updated": updated, "unchanged": unchanged, "etfs": len(codes)}
