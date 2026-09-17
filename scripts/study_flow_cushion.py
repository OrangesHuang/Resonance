"""ETF 份额申赎的"缓冲垫"效应检验(临时研究脚本)。

假设: 一级市场大额净申购虽不能作为精确买点, 但出现后价格的下行波动被压缩
(缓冲垫); 大额净赎回则相反。

方法:
1. 份额变动标准化: flow_bp = 当日份额变动 / 当日份额总额 * 10000 (万分之)
2. 事件定义: 在滚动 250 日窗口内, flow_bp 处于前 5% 分为"极端流入",
   后 5% 分为"极端流出"; 排除 share_adjust 非空的日子(拆分/合并失真)
3. 前瞻窗口 5/10/20 日: 收益、最大回撤(向下)、最大上行、下行波动
4. 跨标的比较: 流入强度(std)、极端事件幅度、价格与份额的同期相关性
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from base.config import ETFS  # noqa: E402
from base.store.daily_repo import get_by_code  # noqa: E402

ROLL = 250
TAIL = 0.05
HORIZONS = (5, 10, 20)
MIN_HISTORY = 300


def _clean(code: str) -> list[dict]:
    rows = list(reversed(get_by_code(code)))
    keep = []
    for r in rows:
        if r.get("shares_delta_yi") is None or r.get("shares_yi") in (None, 0):
            continue
        if r.get("share_adjust") is not None:
            continue
        keep.append(r)
    return keep


def _normalized(rows: list[dict]) -> list[float | None]:
    out: list[float | None] = []
    for r in rows:
        sh = r["shares_yi"] - r["shares_delta_yi"]
        out.append(r["shares_delta_yi"] / sh * 10000 if sh > 0 else None)
    return out


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def _forward(rows: list[dict], i: int, horizon: int) -> dict | None:
    """事件日收盘之后 horizon 个交易日的路径统计(不含事件日)。"""
    if i + horizon >= len(rows):
        return None
    entry = rows[i]["close_price"]
    seg = rows[i + 1 : i + 1 + horizon]
    closes = [r["close_price"] for r in seg]
    rets = [
        closes[j] / (closes[j - 1] if j else entry) - 1 for j in range(len(closes))
    ]
    downside = [x for x in rets if x < 0]
    return {
        "ret": closes[-1] / entry - 1,
        "mdd": min(r["close_price"] for r in seg) / entry - 1,
        "mup": max(r["close_price"] for r in seg) / entry - 1,
        "dvol": statistics.pstdev(downside) if len(downside) > 1 else 0.0,
    }


def _events(rows: list[dict]) -> tuple[list[int], list[int]]:
    flows = _normalized(rows)
    inflow, outflow = [], []
    for i in range(ROLL, len(rows)):
        window = [f for f in flows[i - ROLL : i] if f is not None]
        if len(window) < ROLL * 0.8 or flows[i] is None:
            continue
        sw = sorted(window)
        if flows[i] >= _percentile(sw, 1 - TAIL):
            inflow.append(i)
        elif flows[i] <= _percentile(sw, TAIL):
            outflow.append(i)
    return inflow, outflow


def _summarize(rows: list[dict], idxs: list[int]) -> dict:
    out: dict[str, dict[str, float]] = {}
    for h in HORIZONS:
        stats = [s for i in idxs if (s := _forward(rows, i, h))]
        if not stats:
            continue
        out[h] = {
            "n": float(len(stats)),
            "ret": statistics.mean(s["ret"] for s in stats) * 100,
            "mdd": statistics.mean(s["mdd"] for s in stats) * 100,
            "mup": statistics.mean(s["mup"] for s in stats) * 100,
            "dvol": statistics.mean(s["dvol"] for s in stats) * 100,
        }
    return out


def _fmt(label: str, summ: dict) -> str:
    parts = [f"{label:<14}"]
    for h in HORIZONS:
        if h in summ:
            s = summ[h]
            parts.append(f"{h}日 收益{s['ret']:+6.2f}% 回撤{s['mdd']:+6.2f}% 上行{s['mup']:+6.2f}%")
    return "  ".join(parts)


def main() -> None:
    codes = list(ETFS)
    print("=" * 100)
    print("一、各标的份额流入强度(表达清晰度) —— 标准化 flow_bp 的离散度")
    print("=" * 100)
    print(f"{'代码':<8}{'名称':<20}{'样本':>6}{'std(bp)':>10}{'P99(bp)':>10}{'P1(bp)':>10}{'极值/中位':>10}")
    intensity: dict[str, float] = {}
    for code in codes:
        rows = _clean(code)
        flows = [f for f in _normalized(rows) if f is not None]
        if len(flows) < MIN_HISTORY:
            print(f"{code:<8}{ETFS[code]['name'][:18]:<20}{len(flows):>6}  样本不足")
            continue
        sd = statistics.pstdev(flows)
        sw = sorted(flows)
        p99, p1 = _percentile(sw, 0.99), _percentile(sw, 0.01)
        med = abs(_percentile(sw, 0.5)) or 1e-9
        ratio = max(abs(p99), abs(p1)) / med
        intensity[code] = sd
        print(
            f"{code:<8}{ETFS[code]['name'][:18]:<20}{len(flows):>6}"
            f"{sd:>10.2f}{p99:>10.1f}{p1:>10.1f}{ratio:>10.1f}"
        )

    print()
    print("=" * 100)
    print("二、缓冲垫检验: 极端净申购 vs 极端净赎回 之后的价格路径")
    print("=" * 100)
    for code in ("515880", "588000"):
        rows = _clean(code)
        inflow, outflow = _events(rows)
        print(f"\n--- {code} {ETFS[code]['name']} (样本 {len(rows)} 日) ---")
        print(f"  极端流入事件 {len(inflow)} 次 / 极端流出事件 {len(outflow)} 次")
        print("  " + _fmt("极端流入后:", _summarize(rows, inflow)))
        print("  " + _fmt("极端流出后:", _summarize(rows, outflow)))

    print()
    print("=" * 100)
    print("三、同期关系: 价格下跌时份额是否净流入(逆势申购)")
    print("=" * 100)
    print(f"{'代码':<8}{'名称':<20}{'corr(涨跌,flow)':>16}{'跌超2%日均flow':>16}{'涨超2%日均flow':>16}")
    for code in codes:
        rows = _clean(code)
        if len(rows) < MIN_HISTORY:
            continue
        flows = _normalized(rows)
        pairs = [
            (r["change_pct"], f)
            for r, f in zip(rows, flows)
            if f is not None and r.get("change_pct") is not None
        ]
        if len(pairs) < MIN_HISTORY:
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((a - mx) * (b - my) for a, b in pairs)
        den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
        corr = num / den if den else 0.0
        down = [b for a, b in pairs if a <= -2]
        up = [b for a, b in pairs if a >= 2]
        print(
            f"{code:<8}{ETFS[code]['name'][:18]:<20}{corr:>16.3f}"
            f"{(statistics.mean(down) if down else 0):>16.1f}"
            f"{(statistics.mean(up) if up else 0):>16.1f}"
        )


if __name__ == "__main__":
    main()
