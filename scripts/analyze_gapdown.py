"""中证1000(512100) 高开低走概率分析 — 输出 markdown 报告。

数据: etf_daily(前复权 OHLC), 2024-01-05 ~ 最新。
定义:
  高开   = open_price > 昨收(前一日 close_price)
  高开幅度 = (open - prev_close) / prev_close x 100
  低走   = close_price < open_price(日内高开后回落, 无论最终涨跌)
  翻绿   = close_price < prev_close(高开且收盘跌破昨收)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

CODE = "512100"
DB = Path.home() / ".etf-monitor" / "etf_monitor.db"
OUT = Path(__file__).resolve().parents[1] / "docs" / "analysis_512100_gapdown.md"


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
            "gap_up": o > prev_close,
            "gap_down_day": c < o,
            "turn_green": c < prev_close,
            "intraday_ret": (c / o - 1) * 100 if o else 0.0,
            "day_chg": r["change_pct"] or (c / prev_close - 1) * 100,
        })

    total = len(data)
    gap_up = [d for d in data if d["gap_up"]]
    n_up = len(gap_up)
    n_gapdown = sum(1 for d in gap_up if d["gap_down_day"])
    n_green = sum(1 for d in gap_up if d["turn_green"])

    # 按高开幅度分档
    bands = [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 999.0)]
    band_rows = []
    for lo, hi in bands:
        seg = [d for d in gap_up if lo <= d["gap"] < hi]
        if not seg:
            continue
        n = len(seg)
        gd = sum(1 for d in seg if d["gap_down_day"])
        gr = sum(1 for d in seg if d["turn_green"])
        avg_intra = sum(d["intraday_ret"] for d in seg) / n
        avg_day = sum(d["day_chg"] for d in seg) / n
        label = f"{lo:.1f}% ~ {hi:.1f}%" if hi < 999 else f">= {lo:.1f}%"
        band_rows.append({
            "band": label, "n": n,
            "gapdown": gd / n * 100, "green": gr / n * 100,
            "avg_intra": avg_intra, "avg_day": avg_day,
        })

    # 按年份
    years: dict[str, list[dict]] = {}
    for d in gap_up:
        years.setdefault(d["date"][:4], []).append(d)
    year_rows = []
    for y in sorted(years):
        seg = years[y]
        n = len(seg)
        gd = sum(1 for d in seg if d["gap_down_day"])
        gr = sum(1 for d in seg if d["turn_green"])
        year_rows.append({"year": y, "n": n, "gapdown": gd / n * 100, "green": gr / n * 100})

    # 高开低走典型案例(高开 >=1.5% 且低走, 按高开幅度排序取前 10)
    cases = sorted(
        [d for d in gap_up if d["gap"] >= 1.5 and d["gap_down_day"]],
        key=lambda d: -d["gap"],
    )[:10]

    # 高开低走后的次日表现
    next_day_rows = []
    for d in gap_up:
        if not d["gap_down_day"]:
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
    L.append("# 中证1000（512100）高开低走概率分析")
    L.append("")
    d0, dlast = data[0]["date"], data[-1]["date"]
    L.append(f"> 数据范围：{d0} ~ {dlast}（共 {total} 个交易日，前复权日线）")
    L.append("> 口径：高开 = 开盘价 > 昨收；低走 = 收盘价 < 开盘价（日内高开回落）；翻绿 = 收盘价 < 昨收")
    L.append("")
    L.append("## 一、总览")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 交易日数 | {total} |")
    L.append(f"| 高开天数 | {n_up}（{fmt_pct(n_up / total * 100)}） |")
    L.append(f"| 高开且日内低走 | {n_gapdown}（**占高开日的 {fmt_pct(n_gapdown / n_up * 100)}**） |")
    L.append(f"| 高开且收盘翻绿 | {n_green}（**占高开日的 {fmt_pct(n_green / n_up * 100)}**） |")
    L.append(f"| 高开低走占全部交易日 | {fmt_pct(n_gapdown / total * 100)} |")
    L.append("")
    gd_pct = fmt_pct(n_gapdown / n_up * 100)
    gr_pct = fmt_pct(n_green / n_up * 100)
    L.append(f"**结论：中证1000 高开后日内回落（低走）的概率约 {gd_pct}，收盘跌破昨收（翻绿）的概率约 {gr_pct}。**")
    L.append("")
    L.append("## 二、按高开幅度分档")
    L.append("")
    L.append("| 高开幅度 | 样本 | 低走概率 | 翻绿概率 | 平均日内收益(开→收) | 平均当日涨跌 |")
    L.append("|---|---|---|---|---|---|")
    for b in band_rows:
        L.append(f"| {b[chr(98)+chr(97)+chr(110)+chr(100)]} | {b[chr(110)]} | {fmt_pct(b[chr(103)+chr(97)+chr(112)+chr(100)+chr(111)+chr(119)+chr(110)])} | {fmt_pct(b[chr(103)+chr(114)+chr(101)+chr(101)+chr(110)])} | {b[chr(97)+chr(118)+chr(103)+chr(95)+chr(105)+chr(110)+chr(116)+chr(114)+chr(97)]:+.2f}% | {b[chr(97)+chr(118)+chr(103)+chr(95)+chr(100)+chr(97)+chr(121)]:+.2f}% |")
    L.append("")
    L.append("> 注：高开幅度 >=2% 的样本仅 5 个（2024-10-08/12-10、2026-07-31 等极端行情日），对应档位概率参考意义有限；0~1% 区间（172 个样本）结论更稳健。")
    L.append("")
    L.append("## 三、按年份")
    L.append("")
    L.append("| 年份 | 高开天数 | 低走概率 | 翻绿概率 |")
    L.append("|---|---|---|---|")
    for y in year_rows:
        L.append(f"| {y[chr(121)+chr(101)+chr(97)+chr(114)]} | {y[chr(110)]} | {fmt_pct(y[chr(103)+chr(97)+chr(112)+chr(100)+chr(111)+chr(119)+chr(110)])} | {fmt_pct(y[chr(103)+chr(114)+chr(101)+chr(101)+chr(110)])} |")
    L.append("")
    L.append("## 四、高开低走后的次日表现")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 高开低走样本 | {next_n} |")
    L.append(f"| 次日上涨概率 | {fmt_pct(next_up / next_n * 100) if next_n else '-'} |")
    L.append(f"| 次日平均涨跌 | {next_avg:+.2f}% |")
    L.append("")
    L.append("## 五、典型高开低走案例（高开 >=1.5% 且低走，按高开幅度排序）")
    L.append("")
    L.append("| 日期 | 高开幅度 | 日内(开→收) | 当日涨跌 |")
    L.append("|---|---|---|---|")
    for c in cases:
        L.append(f"| {c[chr(100)+chr(97)+chr(116)+chr(101)]} | +{c[chr(103)+chr(97)+chr(112)]:.2f}% | {c[chr(105)+chr(110)+chr(116)+chr(114)+chr(97)+chr(100)+chr(97)+chr(121)+chr(95)+chr(114)+chr(101)+chr(116)]:+.2f}% | {c[chr(100)+chr(97)+chr(121)+chr(95)+chr(99)+chr(104)+chr(103)]:+.2f}% |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*分析脚本：`scripts/analyze_gapdown.py`，可重复执行刷新本报告。*")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()