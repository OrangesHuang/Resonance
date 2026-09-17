"""份额折算/合并修正任务(存量修复 + 折算日标记)。

背景(为什么要做)
----------------
份额折算(拆分/合并)按比例 k 改变基金份额总数, 但**不涉及任何资金申赎**。
系统原先只按份额差分算申赎, 于是把折算日记成了天量申赎:

  - 515880(通信ETF) 2026-07-03 的 2:1 折算 → 记为 **+333.13 亿份申购**
  - 515880 2026-02-02 的 3:1 折算 → 记为 +97.37 亿份申购
  - 512100(中证1000) 2022-09-05 的约 3:1 **合并** → 记为 −65.79 亿份赎回(假利空)

危害不只是图上一根假柱子: `share_prob` 是水平型双基准(当日 vs 前 N 日均值),
折算造成基准断层, 使折算日及之后约 SHARE_WINDOW 个交易日的份额概率被放大。

判定判据(为什么不能用幅度阈值)
------------------------------
份额折算会使**复权因子(不复权/前复权)按 k 跳变**, 份额同步按 k 变化; 真实申赎
不会改变复权因子。故"份额比例 ≈ 因子比例"才判为折算。反例: 512100 2024-02-05
(+132.8%)、563300 2024-02-08(+444.9%)、588000 2021-04-01(+65.2%) 都是真实天量
申购, 因子全程不变 —— 按幅度粗暴抹除会毁掉真信号。

执行顺序
--------
1. 扫描候选: |单日份额变化%| ≥ SHARE_ADJUST_TRIGGER_PCT 的 (code, date)。
2. 拉取事件日附近窗口的复权因子, 找跳变 → 判定折算比例。
3. 修正: 事件日写入"扣除折算后的真实净申赎" + 折算标记, 并按折算后基准
   重算事件日与随后 SHARE_WINDOW 日的 share_prob。
4. 结尾提示跑「重算综合概率」以对齐 composite_prob / signal_level。
"""

from __future__ import annotations

from base.analysis.shares_adjust import (
    SHARE_ADJUST_TRIGGER_PCT,
    detect_share_adjust,
    find_factor_jump,
    is_candidate,
)
from base.config import ETFS, SHARE_WINDOW
from base.fetch.adjust_factor import factor_window_around, fetch_factor_series
from base.scheduler.job_manager import ProgressFn
from base.store.daily_repo import (
    clear_share_adjust,
    get_by_code,
    update_share_adjust,
    update_share_prob,
)
from resonance.analysis.factors import calc_share_probability_dual


def _scan_candidates() -> list[tuple[str, str, float, float, float]]:
    """扫描全部标的, 返回 [(code, date, 前一日份额, 当日份额, 当日变化%)] 升序。"""
    out: list[tuple[str, str, float, float, float]] = []
    for code in ETFS:
        rows = list(reversed(get_by_code(code)))  # 升序
        prev: float | None = None
        for r in rows:
            cur = r.get("shares_yi")
            dp = r.get("shares_delta_pct")
            flagged = r.get("share_adjust") is not None
            if prev and cur and (is_candidate(dp) or flagged):
                out.append((code, r["date"], prev, cur, float(dp or 0.0)))
            if cur:
                prev = cur
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def _share_prob_at(
    rows_asc: list[dict], idx: int, ratio: float, split_idx: int, delta_pct: float | None
) -> float | None:
    """按折算后基准重算 idx 日的 share_prob。

    窗口内**折算前**的位置(j < split_idx)份额水平乘以 ratio 归一到折算后基准,
    折算当日及之后的位置保持原值 —— 否则水平型双基准的 pct_10d 会凭空放大。
    """
    if idx < 1:
        return None
    start = max(0, idx - SHARE_WINDOW)
    levels: list[float] = []
    for j in range(start, idx):
        v = rows_asc[j].get("shares_yi")
        if v is None:
            continue
        levels.append(float(v) * (ratio if j < split_idx else 1.0))
    return calc_share_probability_dual(delta_pct, rows_asc[idx].get("shares_yi"), levels, SHARE_WINDOW)


def _recompute_after(rows_asc: list[dict], split_idx: int, ratio: float) -> int:
    """重算折算日之后 SHARE_WINDOW 个交易日的 share_prob(其窗口跨越基准断层)。"""
    touched = 0
    for j in range(split_idx + 1, min(split_idx + 1 + SHARE_WINDOW, len(rows_asc))):
        row = rows_asc[j]
        if row.get("shares_yi") is None:
            continue
        sp = _share_prob_at(rows_asc, j, ratio, split_idx, row.get("shares_delta_pct"))
        if sp is None:
            continue
        update_share_prob(row["date"], row["code"], sp)
        touched += 1
    return touched


def job_fix_share_splits(progress: ProgressFn, dry_run: bool = False) -> dict:
    """修正全库份额折算/合并事件(幂等, 可重复执行)。"""
    candidates = _scan_candidates()
    progress(0, max(len(candidates), 1), f"候选 {len(candidates)} 起(阈值 {SHARE_ADJUST_TRIGGER_PCT:.0f}%)")
    fixed: list[dict] = []
    real: list[dict] = []
    skipped: list[dict] = []
    for i, (code, date, sb, sa, dp) in enumerate(candidates, 1):
        progress(i, len(candidates), f"{code} {date} ({dp:+.1f}%)")
        start, end = factor_window_around(date)
        series = fetch_factor_series(code, start, end)
        if not series:
            skipped.append({"code": code, "date": date, "reason": "复权因子拉取失败, 保持原样"})
            continue
        jump = find_factor_jump(series)
        adj = detect_share_adjust(sb, sa, jump[0], jump[1]) if jump else None
        if adj is None:
            # 复核为非折算 → 清掉可能存在的旧标记(自愈)
            if not dry_run:
                clear_share_adjust(date, code)
            real.append(
                {
                    "code": code,
                    "date": date,
                    "delta_pct": dp,
                    "reason": "复权因子无跳变(真实申赎)" if jump is None else "份额比例与因子比例不符(真实申赎)",
                }
            )
            continue
        if not dry_run:
            rows = list(reversed(get_by_code(code)))
            idx = next((k for k, r in enumerate(rows) if r["date"] == date), -1)
            sp = _share_prob_at(rows, idx, adj.ratio, idx, adj.real_delta_pct) if idx >= 0 else None
            update_share_adjust(date, code, adj.real_delta_yi, adj.real_delta_pct, sp, adj.ratio)
            tail = _recompute_after(rows, idx, adj.ratio) if idx >= 0 else 0
        else:
            tail = 0
        fixed.append(
            {
                "code": code,
                "date": date,
                "ratio": round(adj.ratio, 4),
                "fake_delta_yi": round(sa - sb, 2),
                "real_delta_yi": round(adj.real_delta_yi, 2),
                "real_delta_pct": round(adj.real_delta_pct, 2),
                "recomputed_tail": tail,
            }
        )
    progress(
        len(candidates),
        max(len(candidates), 1),
        f"折算 {len(fixed)} 起, 真实申赎 {len(real)} 起, 跳过 {len(skipped)} 起",
    )
    return {
        "candidates": len(candidates),
        "fixed": fixed,
        "real": real,
        "skipped": skipped,
        "dry_run": dry_run,
    }
