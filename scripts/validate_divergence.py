"""三维背离算法验证: 全历史信号 + 已知事件命中 + 黑盒评审匹配。

黑盒评审协议:
1. 独立评审 agent 仅获得 588000 的 K线数据(date/open/high/low/close/volume),
   主观标注显著顶底(见 data/evaluator_marks_588000.csv, 32条)。
2. 算法信号与评审标注按 ±5 交易日匹配(同类: TOP对TOP/BOT对BOT)。
3. 输出召回率(全量/major)与未匹配信号清单。
评审结果(2026-08): 17/32 命中, major 4/5, 剔除PCR空窗期(2024-06前)后 59%。
"""
import sys
import csv
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from store.daily_repo import get_by_code
from store.derivatives_repo import get_pcr_series, get_basis_series
from analysis.derivatives_divergence import compute_divergence

CODE = "588000"
FUTURES = "IC"  # 科创50 无对应股指期货, 用中证500(IC)代理
MATCH_DAYS = 5

# 12 个已知行情事件(用户/历史复盘确认的顶底)
KNOWN_EVENTS = [
    ("BOT", "2024-08-05"), ("TOP", "2024-10-08"), ("BOT", "2025-06-20"),
    ("TOP", "2025-08-28"), ("TOP", "2025-10-09"), ("BOT", "2025-11-21"),
    ("BOT", "2026-02-06"), ("BOT", "2026-03-31"), ("TOP", "2026-05-25"),
    ("BOT", "2026-06-08"), ("TOP", "2026-06-30"), ("BOT", "2026-07-17"),
]


def _idx(dates: list[str]) -> dict[str, int]:
    return {d: i for i, d in enumerate(dates)}


def _near(sig: list[dict], kind: str, date: str, idx: dict[str, int], days: int = MATCH_DAYS) -> list[dict]:
    return [s for s in sig if s["kind"] == kind and abs(idx[date] - idx[s["date"]]) <= days]


def main() -> None:
    kl = get_by_code(CODE)
    pcr = [r for r in get_pcr_series() if r["underlying_code"] == CODE]
    basis = [r for r in get_basis_series() if r["futures_code"] == FUTURES]
    sig = compute_divergence(kl, pcr, basis)

    conn = sqlite3.connect(str(Path.home() / ".etf-monitor" / "etf_monitor.db"))
    dates = [r[0] for r in conn.execute(
        "SELECT date FROM etf_daily WHERE code=? ORDER BY date", (CODE,)
    ).fetchall()]
    conn.close()
    idx = _idx(dates)

    print(f"=== 信号: {len(sig)} (CONF {sum(1 for s in sig if s['grade'] == 'CONF')} / "
          f"WATCH {sum(1 for s in sig if s['grade'] == 'WATCH')}) ===")
    for s in sig:
        print(f"{s['date']} {s['kind']} {s['score']:.1f} {s['grade']} [{','.join(s['rules'])}]")

    print(f"\n=== 已知事件命中(±{MATCH_DAYS}交易日) ===")
    hit = miss = 0
    for kind, ev in KNOWN_EVENTS:
        near = _near(sig, kind, ev, idx)
        if near:
            best = max(near, key=lambda h: h["score"])
            print(f"{kind} {ev}: HIT {best['date']} {best['score']:.1f} {best['grade']}")
            hit += 1
        else:
            print(f"{kind} {ev}: MISS")
            miss += 1
    print(f"事件命中 {hit}/{len(KNOWN_EVENTS)}")

    marks = list(csv.DictReader(
        open(Path(__file__).resolve().parent / "data" / "evaluator_marks_588000.csv",
             encoding="utf-8")
    ))
    hits = []
    for m in marks:
        near = _near(sig, m["kind"], m["date"], idx)
        if near:
            hits.append(m)
    misses = [m for m in marks if m not in hits]
    pre_pcr = [m for m in misses if m["date"] < "2024-06-26"]
    majors = [m for m in marks if m["level"] == "major"]
    major_hits = [m for m in majors if m in hits]
    print(f"\n=== 黑盒评审匹配(评审标注 {len(marks)} 条) ===")
    print(f"命中 {len(hits)}/{len(marks)} = {len(hits)/len(marks)*100:.0f}%  "
          f"| major {len(major_hits)}/{len(majors)}  "
          f"| 剔除PCR空窗期(2024-06前, {len(pre_pcr)}条)后 "
          f"{len(hits)}/{len(marks)-len(pre_pcr)} = {len(hits)/(len(marks)-len(pre_pcr))*100:.0f}%")
    for m in misses:
        print(f"MISS {m['kind']} {m['date']} {m['level']}  {m['rationale']}")

    unmatched = [s for s in sig if not any(
        s["kind"] == m["kind"] and abs(idx[m["date"]] - idx[s["date"]]) <= MATCH_DAYS
        for m in marks
    )]
    print(f"\n=== 未匹配信号 {len(unmatched)} 条(评审未在±{MATCH_DAYS}日内标注同类转折) ===")
    for s in unmatched:
        print(f"EXTRA {s['kind']} {s['date']} {s['score']:.1f} {s['grade']} [{','.join(s['rules'])}]")


if __name__ == "__main__":
    main()
