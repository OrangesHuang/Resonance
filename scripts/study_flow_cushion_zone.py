"""缓冲垫效应分层检验: 按价格位置分组, 检验"低位大额申购"是否才是有效缓冲。

假设修正: 大额净申购的缓冲作用只在价格处于区间低位时成立;
高位大额申购往往是散户接盘, 不构成缓冲。

分组: 事件日 price_position 分为 低位(<30) / 中位(30-70) / 高位(>70)
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from base.config import ETFS  # noqa: E402
from base.store.daily_repo import get_by_code  # noqa: E402

ROLL = 250
TAIL = 0.05
HORIZONS = (5, 10, 20)
LOW, HIGH = 30.0, 70.0


def _clean(code: str) -> list[dict]:
    rows = list(reversed(get_by_code(code)))
    return [
        r
        for r in rows
        if r.get("shares_delta_yi") is not None
        and r.get("shares_yi") not in (None, 0)
        and r.get("share_adjust") is None
        and r.get("price_position") is not None
    ]


def _flows(rows: list[dict]) -> list[float | None]:
    out: list[float | None] = []
    for r in rows:
        sh = r["shares_yi"] - r["shares_delta_yi"]
        out.append(r["shares_delta_yi"] / sh * 10000 if sh > 0 else None)
    return out


def _pct(sv: list[float], q: float) -> float:
    if not sv:
        return 0.0
    return sv[min(len(sv) - 1, max(0, int(q * (len(sv) - 1))))]


def _fwd(rows: list[dict], i: int, h: int) -> dict | None:
    if i + h >= len(rows):
        return None
    entry = rows[i]["close_price"]
    seg = rows[i + 1 : i + 1 + h]
    px = [r["close_price"] for r in seg]
    return {
        "ret": px[-1] / entry - 1,
        "mdd": min(px) / entry - 1,
        "mup": max(px) / entry - 1,
    }


def _bucket(rows: list[dict]) -> dict[str, list[int]]:
    fl = _flows(rows)
    groups: dict[str, list[int]] = {"低位流入": [], "中位流入": [], "高位流入": [],
                                    "低位流出": [], "中位流出": [], "高位流出": []}
    for i in range(ROLL, len(rows)):
        if fl[i] is None:
            continue
        win = sorted(f for f in fl[i - ROLL : i] if f is not None)
        if len(win) < ROLL * 0.8:
            continue
        pos = rows[i]["price_position"]
        zone = "低位" if pos < LOW else ("高位" if pos > HIGH else "中位")
        if fl[i] >= _pct(win, 1 - TAIL):
            groups[f"{zone}流入"].append(i)
        elif fl[i] <= _pct(win, TAIL):
            groups[f"{zone}流出"].append(i)
    return groups


def _line(rows: list[dict], idxs: list[int]) -> str:
    if not idxs:
        return "  (无事件)"
    parts = [f"n={len(idxs):<3}"]
    for h in HORIZONS:
        st = [s for i in idxs if (s := _fwd(rows, i, h))]
        if not st:
            continue
        parts.append(
            f"{h}日 收益{statistics.mean(s['ret'] for s in st) * 100:+6.2f}%"
            f" 回撤{statistics.mean(s['mdd'] for s in st) * 100:+6.2f}%"
            f" 上行{statistics.mean(s['mup'] for s in st) * 100:+6.2f}%"
        )
    return "  ".join(parts)


def main() -> None:
    for code in ("515880", "588000", "588200", "512100"):
        rows = _clean(code)
        g = _bucket(rows)
        print("=" * 104)
        print(f"{code} {ETFS[code]['name']}  样本 {len(rows)} 日")
        print("=" * 104)
        for label in ("低位流入", "中位流入", "高位流入", "低位流出", "中位流出", "高位流出"):
            print(f"  {label}  {_line(rows, g[label])}")
        # 缓冲垫核心指标: 低位流入 vs 高位流入 的 20 日回撤差
        def mdd20(key: str) -> float | None:
            st = [s for i in g[key] if (s := _fwd(rows, i, 20))]
            return statistics.mean(s["mdd"] for s in st) * 100 if st else None
        lo, hi = mdd20("低位流入"), mdd20("高位流入")
        if lo is not None and hi is not None:
            print(f"  → 20日回撤: 低位流入 {lo:+.2f}% vs 高位流入 {hi:+.2f}%  差 {lo - hi:+.2f}pct")
        print()


if __name__ == "__main__":
    main()
