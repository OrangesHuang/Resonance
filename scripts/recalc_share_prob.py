"""重算全部 ETF 的 share_prob(双基准窗口) — 修复分批后补份额时窗口缺失导致的 sp 偏差。

背景: share_prob 是回填时写入的历史值, 依赖前 SHARE_WINDOW 日份额窗口;
分批/后补回填时窗口没建满会退化为单日基准 sp(如 510300 2024-08-28
sp48 而非 78, 导致绝望底买点丢失)。本脚本按回填同款逻辑(calc_share_probability_dual)
逐日重算并写库, 幂等可重复执行。

用法: python3 scripts/recalc_share_prob.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from base.config import ETFS, SHARE_WINDOW
from base.store.daily_repo import get_by_code, update_share_data
from resonance.analysis.factors import calc_share_probability_dual


def main() -> None:
    total = 0
    for code in ETFS:
        rows = [
            r
            for r in reversed(get_by_code(code))
            if r.get("composite_prob") is not None
        ]
        hist: list[float] = []
        n = 0
        for r in rows:
            sy = r.get("shares_yi")
            if sy is None:
                continue
            dp = r.get("shares_delta_pct")
            sp = calc_share_probability_dual(dp, sy, hist, SHARE_WINDOW)
            if sp is not None and sp != r.get("share_prob"):
                update_share_data(r["date"], code, sy, r.get("shares_delta_yi"), dp, sp)
                n += 1
            hist.append(sy)
            if len(hist) > SHARE_WINDOW:
                hist.pop(0)
        print(f"{code} 重算更新: {n} 天")
        total += n
    print(f"TOTAL updated: {total}")


if __name__ == "__main__":
    main()
