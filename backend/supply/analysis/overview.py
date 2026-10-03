"""一级退出监测的纯函数聚合(无 I/O)。

输入为 supply_repo 的原始行, 输出前端直接可用的结构:
  - unlock: 未来 N 周的解禁供给(按周/板块聚合) + 大额解禁个股
  - reduction: 近 N 日股东减持(实际退出)总额 + 减持最多的个股
  - ipo: 近 12 个月新股发行家数与募资节奏
"""

from __future__ import annotations

from datetime import date, timedelta

WEEKS_FORWARD = 8
REDUCTION_DAYS = 30
IPO_MONTHS = 12
TOP_N = 15


def board_of(code: str) -> str:
    c = (code or "").zfill(6)
    if c.startswith("688"):
        return "科创板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("8", "4", "920")):
        return "北交所"
    return "主板"


def _week_start(d: str) -> str:
    dt = date.fromisoformat(d)
    return (dt - timedelta(days=dt.weekday())).isoformat()


def _yi(v: float | None) -> float | None:
    return round(v / 1e8, 2) if v is not None else None


def _month(d: str) -> str:
    return d[:7]


def summarize_unlocks(unlocks: list[dict], today: str, weeks: int = WEEKS_FORWARD) -> dict:
    """未来 weeks 周的解禁供给: 按周(含板块拆分) + 金额最大的个股。"""
    t = date.fromisoformat(today)
    horizon = (t + timedelta(weeks=weeks)).isoformat()
    fwd = [u for u in unlocks if today <= u["date"] <= horizon]
    buckets: dict[str, dict] = {}
    for u in fwd:
        ws = _week_start(u["date"])
        b = buckets.setdefault(ws, {"week_start": ws, "market_value_yi": 0.0, "count": 0, "by_board": {}})
        mv = u.get("market_value") or 0.0
        b["market_value_yi"] += mv / 1e8
        b["count"] += 1
        board = board_of(u["code"])
        b["by_board"][board] = round(b["by_board"].get(board, 0.0) + mv / 1e8, 2)
    week_list = []
    for b in sorted(buckets.values(), key=lambda x: x["week_start"]):
        b["market_value_yi"] = round(b["market_value_yi"], 2)
        week_list.append(b)
    top = sorted(fwd, key=lambda x: x.get("market_value") or 0, reverse=True)[:TOP_N]
    return {
        "forward_weeks": week_list,
        "total_forward_yi": round(sum(w["market_value_yi"] for w in week_list), 2),
        "horizon": horizon,
        "top": [
            {
                "date": u["date"],
                "code": u["code"],
                "name": u.get("name"),
                "board": board_of(u["code"]),
                "unlock_type": u.get("unlock_type"),
                "market_value_yi": _yi(u.get("market_value")),
                "ratio_pct": u.get("ratio_pct"),
                "pre20_chg": u.get("pre20_chg"),
            }
            for u in top
        ],
    }


def summarize_reductions(reductions: list[dict], today: str, days: int = REDUCTION_DAYS) -> dict:
    """近 days 日减持(实际退出): 总金额 + 减持最多的个股。amount 为负, 取绝对值展示。"""
    start = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    recent = [r for r in reductions if r["date"] >= start]
    by_code: dict[str, dict] = {}
    total = 0.0
    for r in recent:
        amt = abs(r.get("amount") or 0.0)
        total += amt
        c = r["code"]
        item = by_code.setdefault(c, {"code": c, "name": r.get("name"), "amount_yi": 0.0, "count": 0})
        item["amount_yi"] += amt / 1e8
        item["count"] += 1
    top = sorted(by_code.values(), key=lambda x: x["amount_yi"], reverse=True)[:TOP_N]
    for it in top:
        it["amount_yi"] = round(it["amount_yi"], 2)
        it["board"] = board_of(it["code"])
    return {
        "days": days,
        "total_yi": round(total / 1e8, 2),
        "count": len(recent),
        "top": top,
    }


def summarize_ipos(ipos: list[dict], today: str, months: int = IPO_MONTHS) -> dict:
    """近 months 个月新股发行: 家数 + 募资(亿)。募资 = 发行总数(万股)×发行价(元)/1e4。"""
    t = date.fromisoformat(today)
    start_month = (t.replace(day=1) - timedelta(days=months * 31)).isoformat()[:7]
    buckets: dict[str, dict] = {}
    for it in ipos:
        d = it.get("issue_date")
        if not d or d[:7] < start_month:
            continue
        m = _month(d)
        b = buckets.setdefault(m, {"month": m, "count": 0, "funds_yi": 0.0})
        b["count"] += 1
        shares = it.get("total_shares")
        price = it.get("price")
        if shares and price:
            b["funds_yi"] += shares * price / 1e4
    out = []
    for b in sorted(buckets.values(), key=lambda x: x["month"]):
        b["funds_yi"] = round(b["funds_yi"], 2)
        out.append(b)
    return {"months": out, "total_funds_yi": round(sum(x["funds_yi"] for x in out), 2)}


def build_overview(
    unlocks: list[dict],
    reductions: list[dict],
    ipos: list[dict],
    today: str,
    updated: str | None = None,
    weeks: int = WEEKS_FORWARD,
) -> dict:
    return {
        "today": today,
        "updated": updated,
        "unlock": summarize_unlocks(unlocks, today, weeks),
        "reduction": summarize_reductions(reductions, today),
        "ipo": summarize_ipos(ipos, today),
    }
