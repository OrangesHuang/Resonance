#!/usr/bin/env python3
"""多指标共振 CLI —— 供 Qoderwork 等外部 Agent 直接读取共振数据与解读。

直接读取本地 SQLite（经 backend 分析模块），无需启动 Web 服务。

用法示例:
  python cli/resonance.py                     # 默认 ETF(510300) 当前共振 + 解读
  python cli/resonance.py --code 510500       # 指定 ETF
  python cli/resonance.py --all               # 全部 ETF 摘要
  python cli/resonance.py --date 2026-07-24   # 某日逐指标依据
  python cli/resonance.py --json              # 结构化 JSON 输出
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import ETFS, DEFAULT_RESONANCE_CODE  # noqa: E402
from store.daily_repo import get_by_code  # noqa: E402
from store.sentiment_repo import get_turnover_series, get_margin_series  # noqa: E402
from analysis.sentiment import enrich_turnover  # noqa: E402
from analysis.resonance import compute_resonance, INDICATORS  # noqa: E402
from analysis.resonance_evidence import compute_day_detail  # noqa: E402

STATE_ICON = {"red": "🔴", "green": "🟢", "gray": "⚪"}
VERDICT_ICON = {"危险共振": "🔴", "机会共振": "🟢", "中性": "⚪"}


def _load_series(code: str):
    etf_rows = list(reversed(get_by_code(code)))
    etf_rows = [r for r in etf_rows if r.get("composite_prob") is not None]
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    return etf_rows, turnover, margin


def _resonance(code: str) -> dict:
    etf_rows, turnover, margin = _load_series(code)
    return compute_resonance(code, etf_rows, turnover, margin)


def _day_detail(code: str, date: str):
    etf_rows, turnover, margin = _load_series(code)
    return compute_day_detail(code, etf_rows, turnover, margin, date)


def _fmt_indicator_line(ind: dict) -> str:
    icon = STATE_ICON.get(ind["state"], "⚪")
    return f"  {icon} {ind['name']}: {ind['display']}（{ind['note']}）"


def render_overview(r: dict) -> str:
    if not r["indicators"]:
        return f"{r['name']}({r['code']}): 暂无共振数据（数据不足或未拉取）"
    icon = VERDICT_ICON.get(r["verdict"], "⚪")
    lines = [
        f"{icon} {r['name']}({r['code']})  数据日期 {r['date']}",
        f"   判定: {r['verdict']}  红{r['red_count']} / 绿{r['green_count']} / 灰{r['gray_count']}（共{r['total']}项）",
        "   指标:",
    ]
    lines += [_fmt_indicator_line(i) for i in r["indicators"]]
    return "\n".join(lines)


def render_digest(rows: list) -> str:
    lines = ["多指标共振摘要", "=" * 32]
    alerts = [r for r in rows if r["verdict"] != "中性" and r["indicators"]]
    if alerts:
        lines.append("⚠️ 触发共振:")
        for r in alerts:
            icon = VERDICT_ICON.get(r["verdict"], "⚪")
            lines.append(f"  {icon} {r['name']}({r['code']}): {r['verdict']} "
                         f"[红{r['red_count']}/绿{r['green_count']}] {r['date']}")
    else:
        lines.append("✅ 无 ETF 触发共振（全部中性）")
    lines.append("-" * 32)
    for r in rows:
        if not r["indicators"]:
            lines.append(f"  ⚪ {r['name']}({r['code']}): 无数据")
            continue
        icon = VERDICT_ICON.get(r["verdict"], "⚪")
        lines.append(f"  {icon} {r['code']} {r['verdict']} 红{r['red_count']}/绿{r['green_count']} {r['date']}")
    return "\n".join(lines)


def render_day(detail: dict) -> str:
    icon = VERDICT_ICON.get(detail["verdict"], "⚪")
    lines = [
        f"{icon} {detail['name']}({detail['code']})  {detail['date']}  判定: {detail['verdict']}",
        f"   红{detail['red_count']} / 绿{detail['green_count']} / 灰{detail['gray_count']}",
    ]
    for ind in detail["indicators"]:
        ev = ind.get("evidence", {})
        lines.append(f"{STATE_ICON.get(ind['state'], '⚪')} {ind['name']}: {ind['display']}")
        if ev.get("reason"):
            lines.append(f"     依据: {ev['reason']}")
    return "\n".join(lines)


def _output(payload, as_json: bool, text: str) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)


def cmd_overview(args) -> int:
    r = _resonance(args.code)
    _output(r, args.json, render_overview(r))
    return 0


def cmd_all(args) -> int:
    rows = [_resonance(code) for code in ETFS]
    _output(rows, args.json, render_digest(rows))
    return 0


def cmd_day(args) -> int:
    detail = _day_detail(args.code, args.date)
    if detail is None:
        msg = f"{args.code} 在 {args.date} 无共振数据"
        if args.json:
            print(json.dumps({"error": msg}, ensure_ascii=False))
        else:
            print(msg)
        return 1
    _output(detail, args.json, render_day(detail))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="多指标共振 CLI")
    p.add_argument("--code", default=DEFAULT_RESONANCE_CODE, help="ETF 代码")
    p.add_argument("--all", action="store_true", help="输出全部 ETF 摘要")
    p.add_argument("--date", default="", help="查询某日逐指标依据 (YYYY-MM-DD)")
    p.add_argument("--json", action="store_true", help="结构化 JSON 输出")
    args = p.parse_args(argv)

    if args.code not in ETFS:
        print(f"未知 ETF 代码: {args.code}，可选: {', '.join(ETFS)}", file=sys.stderr)
        return 2
    if args.all:
        return cmd_all(args)
    if args.date:
        return cmd_day(args)
    return cmd_overview(args)


if __name__ == "__main__":
    raise SystemExit(main())
