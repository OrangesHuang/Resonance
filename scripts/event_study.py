"""事件研究脚手架 — 把"规律"当分布来测, 不当个案来 fit。

方法论(见《量化买卖规律发现方法论与可靠性评估.md》):
  - 定义信号谓词(份额/价格/量比/分位的组合条件)
  - 池化全部 ETF、全部历史满足谓词的**所有事件**(几十~上百个, 而非几个底)
  - 对每个事件算**前向 5/10/20 日收益**, 看分布(均值/中位数/胜率/离散度)
  - 与基线比 edge: ①无条件前向收益 ②最笨的"逢跌就买"; edge = 事件收益 - 基线
  - bootstrap 给置信区间; 参数平台曲线(取平台区, 而非尖峰)

用法:
  python3 scripts/event_study.py --study=<名字> [--asset=510300,512100 ...] [--k=5,10,20]
  --list  列出所有已定义 study
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from base.analysis.sentiment.core import (  # noqa: E402
    enrich_turnover,
    percentile_series,
    turnover_value,
)
from base.config import ETFS, SENTIMENT_ZONE_MIN_PTS, SENTIMENT_ZONE_WINDOW  # noqa: E402
from base.store.daily_repo import get_by_code  # noqa: E402
from base.store.sentiment_repo import get_margin_series, get_turnover_series  # noqa: E402


# ---------------------------------------------------------------- 数据加载
def load_pool(codes: list[str] | None = None) -> list[list[dict]]:
    """返回逐 ETF 的升序行列表(注入 _tp/_mp 分位; 只留含 composite_prob 的行)。
    前向收益需在同 ETF 内部计算, 故按标的分组返回。"""
    turnover = enrich_turnover(get_turnover_series())
    margin = get_margin_series()
    t_pct = percentile_series(
        [r.get("date") for r in turnover],
        [turnover_value(r) for r in turnover],
        SENTIMENT_ZONE_WINDOW,
        SENTIMENT_ZONE_MIN_PTS,
    )
    m_pct = percentile_series(
        [r.get("date") for r in margin],
        [r.get("fin_balance_yi") for r in margin],
        SENTIMENT_ZONE_WINDOW,
        SENTIMENT_ZONE_MIN_PTS,
    )
    pool: list[list[dict]] = []
    chosen = [c for c in (codes or ETFS.keys()) if c in ETFS]
    for code in chosen:
        rows = list(reversed(get_by_code(code)))
        rows = [r for r in rows if r.get("composite_prob") is not None]
        out = []
        for idx, r in enumerate(rows):
            c = dict(r)
            c["_tp"] = (t_pct or {}).get(r["date"], {}).get("percentile")
            c["_mp"] = (m_pct or {}).get(r["date"], {}).get("percentile")
            # 份额 T+1 公布: sd_prev = 昨日份额变化(当日收盘可知), 消除前视
            c["sd_prev"] = rows[idx - 1].get("shares_delta_yi") if idx > 0 else None
            out.append(c)
        if out:
            pool.append(out)
    return pool


# ---------------------------------------------------------------- 前向收益
def _close(row: dict) -> float:
    return float(row.get("close_price") or 0.0)


def forward_returns(rows: list[dict], k: int) -> list[float | None]:
    """逐行 close[i+k]/close[i]-1 (同证券内部; 尾部 None)。"""
    n = len(rows)
    out: list[float | None] = []
    for i in range(n):
        if i + k < n:
            c0 = _close(rows[i])
            c1 = _close(rows[i + k])
            out.append((c1 / c0 - 1) * 100 if c0 > 0 else None)
        else:
            out.append(None)
    return out


# ---------------------------------------------------------------- 统计
def _stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "mean": float("nan"), "median": float("nan"), "win": float("nan")}
    v = sorted(vals)
    n = len(v)
    mean = sum(v) / n
    med = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    win = sum(1 for x in v if x > 0) / n * 100
    return {"n": n, "mean": mean, "median": med, "win": win}


def bootstrap_ci(vals: list[float], reps: int = 2000, seed: int = 7) -> tuple[float, float]:
    """bootstrap 均值置信区间(2.5%~97.5%)。"""
    if len(vals) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        s = [vals[rng.randrange(len(vals))] for _ in range(len(vals))]
        means.append(sum(s) / len(s))
    means.sort()
    return means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def _mean_ci(vals: list[float]) -> tuple[float, float]:
    lo, hi = bootstrap_ci(vals)
    return lo, hi


# ---------------------------------------------------------------- 信号谓词
# 每个 study: name -> (谓词描述, 谓词函数, 基线谓词)
# 谓词签名: fn(row, era) -> bool;  era: dict 提供窗口辅助(后续扩展)

@dataclass
class Study:
    name: str
    desc: str
    pred: object  # callable(row) -> bool
    base_pred: object | None = None  # 可选: "逢跌就买"类基线
    k: tuple[int, ...] = (5, 10, 20)
    header: tuple[str, ...] = ()


def _r(row, *names):
    """取字段, None 安全。"""
    v = None
    for n in names:
        v = row.get(n)
        if v is not None:
            break
    return v


# 预测函数库(机制假设 + 证伪条件见各 doc 注释)
def _pred_netredeem_crash(row) -> bool:
    """假设: 大额净赎回 + 急跌 = 流动性冲击(非基本面), 释放后均值回归。
    (份额 T+1 公布, 实盘按当日不可见 — 用"昨日份额变化"回测, 见 holds_* 变体)"""
    sd = row.get("shares_delta_yi")
    chg = row.get("change_pct") or 0
    return sd is not None and sd <= -3.0 and chg <= -3.0


def _pred_netredeem_crash_strong(row) -> bool:
    sd = row.get("shares_delta_yi")
    chg = row.get("change_pct") or 0
    return sd is not None and sd <= -5.0 and chg <= -4.0


def _pred_cold_low(row) -> bool:
    """假设: 成交额极度冷清 + 价格低位 = 情绪冰点, 反映的是极度缩量而非抛压, 后续回暖。"""
    tp = row.get("_tp")
    pp = row.get("price_position")
    return tp is not None and tp <= 10.0 and pp is not None and pp <= 20.0


def _pred_cold_low_inflow(row) -> bool:
    """冷清低位 + 机构净申购(强承接): 缩量+资金进场, 底部质量更高。"""
    tp = row.get("_tp")
    pp = row.get("price_position")
    sd = row.get("shares_delta_yi")
    return tp is not None and tp <= 15.0 and pp is not None and pp <= 20.0 and sd is not None and sd > 0.0


def _pred_high_distribute(row) -> bool:
    """假设: 高位 + 出货信号 + 高杠杆 = 顶部确认, 风险。用于评估卖出信号(反向前向)。"""
    pp = row.get("price_position")
    td = row.get("trade_direction")
    mp = row.get("_mp")
    return pp is not None and pp >= 80.0 and td == "DISTRIBUTE" and mp is not None and mp >= 80.0


def _pred_bull_panic(row) -> bool:
    """牛市恐慌回踩: 深跌 + 份额强承接(牛市不卖点)。"""
    pp = row.get("price_position")
    chg = row.get("change_pct") or 0
    sd = row.get("shares_delta_yi")
    return pp is not None and pp <= 40.0 and chg <= -4.0 and sd is not None and sd > 0.0


# ---- 无前视信号(只用价格/位置/成交额分位, 均当日收盘可知; 不用份额/综合概率) ----
def _pred_crash_position(row) -> bool:
    """纯价格均值回归: 深跌 + 低位置(不含份额, 无 T+1 前视)。"""
    pp = row.get("price_position")
    chg = row.get("change_pct") or 0
    return pp is not None and pp <= 20.0 and chg <= -5.0


def _pred_cold_crash(row) -> bool:
    """成交额极冷 + 深跌 + 低位置: 缩量恐慌, 抛压枯竭(无份额前视)。"""
    tp = row.get("_tp")
    pp = row.get("price_position")
    chg = row.get("change_pct") or 0
    return tp is not None and tp <= 15.0 and pp is not None and pp <= 30.0 and chg <= -5.0


# 基线: 无条件(所有日); "逢跌就买"(当日跌幅 > 阈值)
def _base_any(_row) -> bool:
    return True


def _base_dip(row) -> bool:
    return (row.get("change_pct") or 0) <= -2.0


STUDIES: dict[str, Study] = {
    "netredeem_crash": Study(
        "netredeem_crash", "净赎回<=-3亿 + 单日跌<=-3% → 均值回归", _pred_netredeem_crash, _base_dip),
    "netredeem_crash_strong": Study(
        "netredeem_crash_strong", "净赎回<=-5亿 + 单日跌<=-4% → 均值回归", _pred_netredeem_crash_strong, _base_dip),
    "cold_low": Study("cold_low", "成交额<=10分位 + 位置<=20 → 冰点回暖", _pred_cold_low, _base_dip),
    "cold_low_inflow": Study(
        "cold_low_inflow", "成交额<=15分位 + 位置<=20 + 净申购>0 → 低位承接", _pred_cold_low_inflow, _base_dip),
    "high_distribute": Study(
        "high_distribute", "位置>=80 + DISTRIBUTE + 融资>=80 → 顶部(反向前向)", _pred_high_distribute, None),
    "bull_panic": Study("bull_panic", "位置<=40 + 跌<=-4% + 净申购>0 → 牛市恐慌回踩", _pred_bull_panic, _base_dip),
    "crash_position": Study("crash_position", "跌<=-5% + 位置<=20 (无份额前视) → 纯价格均值回归", _pred_crash_position, _base_dip),
    "cold_crash": Study("cold_crash", "成交额<=15 + 跌<=-5% + 位置<=30 (无份额前视) → 缩量恐慌", _pred_cold_crash, _base_dip),
    # ---- 净申赎模型(用滞后份额 sd_prev, 无 T+1 前视) ----
    "flow_entry_low": Study(
        "flow_entry_low", "滞后净申购>0 + 位置<=20 → 机构低位吸筹", lambda r: (r.get("sd_prev") or 0) > 0 and (r.get("price_position") or 0) <= 20, _base_dip),
    "flow_entry_panic": Study(
        "flow_entry_panic", "滞后净申购>0 + 跌<=-5% + 位置<=30 → 恐慌吸筹", lambda r: (r.get("sd_prev") or 0) > 0 and (r.get("change_pct") or 0) <= -5.0 and (r.get("price_position") or 0) <= 30, _base_dip),
    "flow_exit_top": Study(
        "flow_exit_top", "滞后净赎回<=-3 + 位置>=70 → 高位派发(期望前向下行=卖点)",
        lambda r: (r.get("sd_prev") is not None and r.get("sd_prev") <= -3.0 and (r.get("price_position") or 0) >= 70), None),
    "flow_exit_drive": Study(
        "flow_exit_drive", "滞后净赎回<=-3 + 位置>=80 + 量比>=1.3 → 高位放量派发(真顶)",
        lambda r: (r.get("sd_prev") is not None and r.get("sd_prev") <= -3.0 and (r.get("price_position") or 0) >= 80 and (r.get("volume_ratio") or 0) >= 1.3), None),
}


# ---- 参数平台扫描(取平台区而非尖峰) ----
def _p_pp_chg_sd(row, pp_max=40.0, chg_min=-4.0, sd_test=None) -> bool:
    pp = row.get("price_position")
    chg = row.get("change_pct") or 0
    sd = row.get("shares_delta_yi")
    if pp is None or pp > pp_max or chg > chg_min:
        return False
    return sd_test(sd) if sd_test else True


def _collect(pool, pred, base, k):
    ev: list[float] = []
    ba: list[float] = []
    for rows in pool:
        fr = forward_returns(rows, k)
        for i, row in enumerate(rows):
            v = fr[i]
            if v is None:
                continue
            if pred(row):
                ev.append(v)
            if base(row):
                ba.append(v)
    return ev, ba


def _edge(pool, pred, base, k) -> tuple[float, int, float, float]:
    ev, ba = _collect(pool, pred, base, k)
    es, bs = _stats(ev), _stats(ba)
    return es["mean"] - bs["mean"], es["n"], es["mean"], es["win"]


def _bull_panic_scan(pool: list[list[dict]], k: int = 10) -> None:
    """扫 bull_panic 三参数: 看 edge 是否在平台区(而非尖峰)。"""
    codes = [r[0].get("code") for r in pool]
    print(f"=== bull_panic 参数平台扫描 (k={k}, 标的={codes}) ===")

    print("\n-- pp_max (chg<=-4%, sd>0) --")
    for pp in [10, 15, 20, 25, 30, 40, 50, 60]:
        e, n, m, w = _edge(pool, lambda r, p=pp: _p_pp_chg_sd(r, pp_max=p, sd_test=lambda s: s is not None and s > 0), _base_dip, k)
        print(f"  pp<={pp:>3}  edge={e:>6.2f} n={n:>4} mean={m:>6.2f} win={w:>5.1f}%")

    print("\n-- chg 阈值 (pp<=40, sd>0) --")
    for chg in [-2.0, -3.0, -4.0, -5.0, -6.0, -7.0]:
        e, n, m, w = _edge(pool, lambda r, c=chg: _p_pp_chg_sd(r, chg_min=c, sd_test=lambda s: s is not None and s > 0), _base_dip, k)
        print(f"  chg<={chg:>4}  edge={e:>6.2f} n={n:>4} mean={m:>6.2f} win={w:>5.1f}%")

    print("\n-- 份额条件重要性 (pp<=40, chg<=-4) --")
    tests = [
        ("无 sd 条件", lambda s: True),
        ("净申购>0", lambda s: s is not None and s > 0),
        ("净赎回<=-1", lambda s: s is not None and s <= -1.0),
        ("净赎回<=-3", lambda s: s is not None and s <= -3.0),
    ]
    for label, t in tests:
        e, n, m, w = _edge(pool, lambda r, t=t: _p_pp_chg_sd(r, sd_test=t), _base_dip, k)
        print(f"  {label:<12}  edge={e:>6.2f} n={n:>4} mean={m:>6.2f} win={w:>5.1f}%")


def run_study(study: Study, pool: list[list[dict]], codes: list[str], k_list: list[int]) -> dict:
    """跑某个 study, 返回各 k 的事件/基线统计。"""
    results: dict[str, dict] = {}
    ev_by_k: dict[int, list[float]] = {k: [] for k in k_list}
    base_by_k: dict[int, list[float]] = {k: [] for k in k_list}
    n_event = 0
    for rows in pool:
        n = len(rows)
        fr = {k: forward_returns(rows, k) for k in k_list}
        for i, row in enumerate(rows):
            base_hit = study.base_pred(row) if study.base_pred else True
            # 基线(逢跌就买)应收集所有命中基线谓词的日, 与事件谓词无关
            if base_hit:
                for k in k_list:
                    v = fr[k][i]
                    if v is not None:
                        base_by_k[k].append(v)
            if study.pred(row):
                n_event += 1
                for k in k_list:
                    v = fr[k][i]
                    if v is not None:
                        ev_by_k[k].append(v)
    for k in k_list:
        ev = ev_by_k[k]
        base = base_by_k[k]
        es = _stats(ev)
        # 无条件基线: 所有日(不区分谓词)
        allfr = []
        for rows in pool:
            allfr += [v for v in forward_returns(rows, k) if v is not None]
        bs = _stats(base)  # 逢跌就买基线
        alls = _stats(allfr)  # 无条件基线
        edge = es["mean"] - alls["mean"]
        ci = _mean_ci(ev)
        results[k] = {
            "event": es, "base_dip": bs, "base_uncond": alls,
            "edge_vs_uncond": edge,
            "edge_vs_dip": es["mean"] - bs["mean"],
            "event_ci": ci,
        }
    return {"name": study.name, "desc": study.desc, "n_events": n_event, "by_k": results, "codes": codes}


def _fmt(results: dict) -> str:
    lines = []
    lines.append(f"study={results['name']}  事件数={results['n_events']}  标的={','.join(results['codes'])}")
    lines.append(f"  {results['desc']}")
    lines.append(f"  {'k':>4} | {'事件均':>8} {'中位':>8} {'胜率%':>7} {'n':>5} | {'逢跌均':>8} {'无条件均':>9} | {'edge(无条)':>10} {'edge(逢跌)':>10} | {'CI[2.5,97.5]':>20}")
    for k, st in results["by_k"].items():
        e = st["event"]; bd = st["base_dip"]; bu = st["base_uncond"]
        ci = st["event_ci"]
        lines.append(
            f"  {k:>4} | {e['mean']:>8.2f} {e['median']:>8.2f} {e['win']:>7.1f} {e['n']:>5} | "
            f"{bd['mean']:>8.2f} {bu['mean']:>9.2f} | {st['edge_vs_uncond']:>10.2f} {st['edge_vs_dip']:>10.2f} | "
            f"[{ci[0]:>8.2f}, {ci[1]:>8.2f}]"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--study", default="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--plateau", default="", help="参数平台扫描: bull_panic")
    ap.add_argument("--asset", default="510300,512100,588000,159780,515080", help="逗号分隔的标池")
    ap.add_argument("--k", default="5,10,20")
    args = ap.parse_args()

    if args.list:
        for s in STUDIES.values():
            print(f"  {s.name:<26} {s.desc}")
        return 0

    codes = [c.strip() for c in args.asset.split(",") if c.strip()]
    k_list = [int(x) for x in args.k.split(",") if x.strip()]
    pool = load_pool(codes)

    if args.plateau == "bull_panic":
        _bull_panic_scan(pool, k=k_list[0])
        return 0

    names = [args.study] if args.study != "*" else list(STUDIES.keys())
    for nm in names:
        if nm not in STUDIES:
            print(f"unknown study: {nm} (用 --list 查看)")
            continue
        print(_fmt(run_study(STUDIES[nm], pool, codes, k_list)))
        print()
    return 0


if __name__ == "__main__":
    main()
