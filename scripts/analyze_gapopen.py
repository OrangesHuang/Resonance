"""中证1000(512100) 低开高走概率分析 — 输出 markdown 报告。

数据: etf_daily(前复权 OHLC), 2024-01-05 ~ 最新。
定义:
  低开   = open_price < 昨收(前一日 close_price)
  低开幅度 = (open - prev_close) / prev_close x 100(负值, 按绝对值分档)
  高走   = close_price > open_price(日内低开后回升, 无论最终涨跌)
  翻红   = close_price > prev_close(低开且收盘站上昨收)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

CODE = "512100"
DB = Path.home() / ".etf-monitor" / "etf_monitor.db"
OUT = Path(__file__).resolve().parents[1] / "docs" / "analysis_512100_gapopen.md"


def load_rows() -> list[dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT date, open_price, high_price, low_price, close_price, change_pct, volume "
        "FROM etf_daily WHERE code = ? ORDER BY date",
        (CODE,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def fmt_pct(x: float) -> str:
    return f"{x:.1f}%"


def main() -> None:
    rows = load_rows()
    data = []
    for i, r in enumerate(rows):
        if i == 0:
            continue
        prev_close = rows[i - 1]["close_price"]
        if not prev_close:
            continue
        o, c = r["open_price"], r["close_price"]
        data.append({
            "date": r["date"],
            "gap": (o - prev_close) / prev_close * 100,
            "gap_down": o < prev_close,
            "gap_up_day": c > o,
            "turn_red": c > prev_close,
            "intraday_ret": (c / o - 1) * 100 if o else 0.0,
            "day_chg": r["change_pct"] or (c / prev_close - 1) * 100,
        })

    total = len(data)
    low_open = [d for d in data if d["gap_down"]]
    n_low = len(low_open)
    n_upday = sum(1 for d in low_open if d["gap_up_day"])
    n_red = sum(1 for d in low_open if d["turn_red"])

    # 按低开幅度分档(绝对值)
    bands = [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 999.0)]
    band_rows = []
    for lo, hi in bands:
        seg = [d for d in low_open if lo <= abs(d["gap"]) < hi]
        if not seg:
            continue
        n = len(seg)
        up = sum(1 for d in seg if d["gap_up_day"])
        red = sum(1 for d in seg if d["turn_red"])
        avg_intra = sum(d["intraday_ret"] for d in seg) / n
        avg_day = sum(d["day_chg"] for d in seg) / n
        label = f"{lo:.1f}% ~ {hi:.1f}%" if hi < 999 else f">= {lo:.1f}%"
        band_rows.append({
            "band": label, "n": n,
            "upday": up / n * 100, "red": red / n * 100,
            "avg_intra": avg_intra, "avg_day": avg_day,
        })

    # 按年份
    years: dict[str, list[dict]] = {}
    for d in low_open:
        years.setdefault(d["date"][:4], []).append(d)
    year_rows = []
    for y in sorted(years):
        seg = years[y]
        n = len(seg)
        up = sum(1 for d in seg if d["gap_up_day"])
        red = sum(1 for d in seg if d["turn_red"])
        year_rows.append({"year": y, "n": n, "upday": up / n * 100, "red": red / n * 100})

    # 典型案例(低开 >=1.5% 且高走, 按低开幅度排序取前 10)
    cases = sorted(
        [d for d in low_open if abs(d["gap"]) >= 1.5 and d["gap_up_day"]],
        key=lambda d: d["gap"],
    )[:10]

    # 低开高走后的次日表现
    next_day_rows = []
    for d in low_open:
        if not d["gap_up_day"]:
            continue
        idx = data.index(d)
        if idx + 1 < len(data):
            next_day_rows.append(data[idx + 1]["day_chg"])
    next_n = len(next_day_rows)
    if next_n:
        next_up = sum(1 for x in next_day_rows if x > 0)
        next_avg = sum(next_day_rows) / next_n
    else:
        next_up, next_avg = 0, 0.0

    L: list[str] = []
    L.append("# 中证1000（512100）低开高走概率分析")
    L.append("")
    d0, dlast = data[0]["date"], data[-1]["date"]
    L.append(f"> 数据范围：{d0} ~ {dlast}（共 {total} 个交易日，前复权日线）")
    L.append("> 口径：低开 = 开盘价 < 昨收；高走 = 收盘价 > 开盘价（日内低开回升）；翻红 = 收盘价 > 昨收")
    L.append("")
    L.append("## 一、总览")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 交易日数 | {total} |")
    L.append(f"| 低开天数 | {n_low}（{fmt_pct(n_low / total * 100)}） |")
    L.append(f"| 低开且日内高走 | {n_upday}（**占低开日的 {fmt_pct(n_upday / n_low * 100)}**） |")
    L.append(f"| 低开且收盘翻红 | {n_red}（**占低开日的 {fmt_pct(n_red / n_low * 100)}**） |")
    L.append(f"| 低开高走占全部交易日 | {fmt_pct(n_upday / total * 100)} |")
    L.append("")
    up_pct = fmt_pct(n_upday / n_low * 100)
    red_pct = fmt_pct(n_red / n_low * 100)
    L.append(f"**结论：中证1000 低开后日内回升（高走）的概率约 {up_pct}，收盘站上昨收（翻红）的概率约 {red_pct}。**")
    L.append("")
    L.append("## 二、按低开幅度分档")
    L.append("")
    L.append("| 低开幅度 | 样本 | 高走概率 | 翻红概率 | 平均日内收益(开→收) | 平均当日涨跌 |")
    L.append("|---|---|---|---|---|---|")
    for b in band_rows:
        L.append(f"| {b[chr(98)+chr(97)+chr(110)+chr(100)]} | {b[chr(110)]} | {fmt_pct(b[chr(117)+chr(112)+chr(100)+chr(97)+chr(121)])} | {fmt_pct(b[chr(114)+chr(101)+chr(100)])} | {b[chr(97)+chr(118)+chr(103)+chr(95)+chr(105)+chr(110)+chr(116)+chr(114)+chr(97)]:+.2f}% | {b[chr(97)+chr(118)+chr(103)+chr(95)+chr(100)+chr(97)+chr(121)]:+.2f}% |")
    L.append("")
    L.append("> 注：低开幅度 >=2% 的样本较少，对应档位概率参考意义有限；0~1% 区间结论更稳健。")
    L.append("")
    L.append("## 三、按年份")
    L.append("")
    L.append("| 年份 | 低开天数 | 高走概率 | 翻红概率 |")
    L.append("|---|---|---|---|")
    for y in year_rows:
        L.append(f"| {y[chr(121)+chr(101)+chr(97)+chr(114)]} | {y[chr(110)]} | {fmt_pct(y[chr(117)+chr(112)+chr(100)+chr(97)+chr(121)])} | {fmt_pct(y[chr(114)+chr(101)+chr(100)])} |")
    L.append("")
    L.append("## 四、低开高走后的次日表现")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 低开高走样本 | {next_n} |")
    L.append(f"| 次日上涨概率 | {fmt_pct(next_up / next_n * 100) if next_n else '-'} |")
    L.append(f"| 次日平均涨跌 | {next_avg:+.2f}% |")
    L.append("")
    L.append("## 五、典型低开高走案例（低开 >=1.5% 且高走，按低开幅度排序）")
    L.append("")
    L.append("| 日期 | 低开幅度 | 日内(开→收) | 当日涨跌 |")
    L.append("|---|---|---|---|")
    for c in cases:
        L.append(f"| {c[chr(100)+chr(97)+chr(116)+chr(101)]} | {c[chr(103)+chr(97)+chr(112)]:.2f}% | {c[chr(105)+chr(110)+chr(116)+chr(114)+chr(97)+chr(100)+chr(97)+chr(121)+chr(95)+chr(114)+chr(101)+chr(116)]:+.2f}% | {c[chr(100)+chr(97)+chr(121)+chr(95)+chr(99)+chr(104)+chr(103)]:+.2f}% |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*分析脚本：`scripts/analyze_gapopen.py`，可重复执行刷新本报告。*")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()