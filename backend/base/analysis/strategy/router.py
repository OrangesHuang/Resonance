"""按 ETF 代码分派各专属策略, 统一生成买卖点。

页面「共振买卖点」与「组合回测」共用本入口, 保证两边买卖点一致:
  589680 科创综指 → strategy_kc      512100 中证1000 → strategy_zz(注入分位)
  515080 中证红利 → strategy_div     510050 上证50   → strategy_sh50
  159780 双创50   → strategy_sc50    588000 科创50   → strategy_kc50(参照科创综指)
  510500 中证500  → strategy_zz500_v2 159352 中证A500 → strategy_a500(复用沪深300)
  其余(如 510300) → 通用多指标共振(价格低位+吸筹+份额/成交额/概率共振)

本模块纯函数无 I/O; 所需数据由调用方注入:
  t_pct / m_pct — {date: {percentile}} 成交额/融资余额分位(部分策略需要)
  hs300_rows    — 510300 日线(A500 复用其买卖点)
  kc_idx_rows   — 589680 日线(科创50 参照其吸筹特征)
"""

from __future__ import annotations

import math

from base.analysis.strategy.a500 import A500_CODE, run_a500_strategy
from base.analysis.strategy.div import DIV_CODE, run_div_strategy
from base.analysis.strategy.kc import KC_CODE, run_kc_strategy
from base.analysis.strategy.kc50 import KC50_CODE, run_kc50_strategy
from base.analysis.strategy.sc50 import SC50_CODE, run_sc50_strategy
from base.analysis.strategy.sh50 import SH50_CODE, run_sh50_strategy
from base.analysis.strategy.zz import ZZ_CODE, run_zz_strategy
from base.analysis.strategy.zz500_v2 import ZZ500_CODE, run_zz500_strategy_v2

# ---- 通用多指标共振(510300 等无专属策略的 ETF) ----
SELL_PP = 80  # 卖出: 价格位置阈值
SELL_MP = 90  # 卖出: 融资余额分位阈值
MIN_HOLD = 10  # 卖出: 最短持有天数
VOL_LOOKBACK = 20  # 卖出阈值: 量比回看窗口
TRADE_START = "2024-10-08"
BUY_PP_MAX = 40  # 买入: 价格位置阈值
BUY_PP_EXTREME = 10  # 买入: 极低位阈值
SHARE_PROB_MIN = 65  # 买入: 份额净申购概率阈值
TP_COLD_MAX = 10  # 买入: 成交额极冷分位阈值
CP_HIGH_MIN = 50  # 买入: 综合概率阈值
BUY_PP_PANIC = 15  # 买入: 恐慌吸筹路径 pp 上限
# P5 恐慌吸筹: 极端低位+ACCUMULATE(无需等份额/概率确认, 后10日上涨69%)
# 案例: 510300 2026-03-23 pp5.5+ACCUMULATE+净申购8.3亿(旧式cp46.3<50漏买,
# 3-23买@4.430→4-29卖@4.821 +8.8%)


def _run_default(rows: list[dict], t_pct: dict, m_pct: dict) -> dict:
    """通用多指标共振买卖点(页面 /trades 默认分支原逻辑)。"""
    code = rows[0].get("code", "") if rows else ""
    trades = []
    position = 0.0
    hold_days = 0
    sell_threshold = 1
    dist_count = 0

    for i, row in enumerate(rows):
        d = row["date"]
        if d not in t_pct and d not in m_pct:
            continue
        close = row.get("close_price")
        if close is None:
            continue
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        tp = t_pct.get(d, {}).get("percentile")
        mp = m_pct.get(d, {}).get("percentile")

        action = None
        reason = ""

        if position == 0 and d >= TRADE_START:
            pp_green = pp is not None and pp <= BUY_PP_MAX
            pp_extreme = pp is not None and pp <= BUY_PP_EXTREME
            td_green = td == "ACCUMULATE"
            sp_green = sp is not None and sp >= SHARE_PROB_MIN
            tp_cold = tp is not None and tp <= TP_COLD_MAX
            cp_high = cp is not None and cp > CP_HIGH_MIN
            if pp_green and sp_green and td_green:
                action, reason = "BUY", "价格低位+份额净申购+吸筹"
            elif pp_green and td_green and tp_cold:
                action, reason = "BUY", "价格低位+吸筹+成交额极冷"
            elif pp_extreme and td_green and cp_high:
                action, reason = "BUY", "价格极低位+吸筹+概率>50%"
            elif pp is not None and pp <= BUY_PP_PANIC and td_green:
                action, reason = "BUY", "恐慌吸筹: 极低位+吸筹信号"

        if position == 1:
            hold_days += 1
            if td == "DISTRIBUTE" and pp is not None and pp >= SELL_PP and mp is not None and mp >= SELL_MP:
                dist_count += 1

            if hold_days >= MIN_HOLD and td == "DISTRIBUTE" and dist_count >= sell_threshold:
                reason = f"出货共振(第{dist_count}/{sell_threshold}次出货确认)+价格{pp:.0f}%+融资{mp:.0f}%分位"
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            dist_count = 0
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0 for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            if tp_cold:
                sell_threshold = 1
            else:
                sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": action, "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            trades.append({"date": d, "action": action, "price": close, "reason": reason})

    return {"code": code, "trades": trades}


def _inject_percentile(rows: list[dict], t_pct: dict, m_pct: dict) -> list[dict]:
    """浅拷贝行并注入成交额(_tp)/融资(_mp)分位, 不污染调用方数据。"""
    out = []
    for r in rows:
        copy = dict(r)
        copy["_tp"] = (t_pct or {}).get(r["date"], {}).get("percentile")
        copy["_mp"] = (m_pct or {}).get(r["date"], {}).get("percentile")
        out.append(copy)
    return out


def compute_trades(
    code: str,
    rows: list[dict],
    *,
    t_pct: dict | None = None,
    m_pct: dict | None = None,
    hs300_rows: list[dict] | None = None,
    kc_idx_rows: list[dict] | None = None,
) -> dict:
    """生成与页面「共振买卖点」一致的交易信号。

    rows 必须为升序(由调用方从库里加载并排序)。
    """
    t_pct = t_pct or {}
    m_pct = m_pct or {}

    if code == KC_CODE:
        return run_kc_strategy(rows)
    if code == ZZ_CODE:
        return run_zz_strategy(_inject_percentile(rows, t_pct, m_pct))
    if code == DIV_CODE:
        return run_div_strategy(_inject_percentile(rows, t_pct, m_pct))
    if code == SH50_CODE:
        return run_sh50_strategy(rows)
    if code == SC50_CODE:
        return run_sc50_strategy(rows)
    if code == KC50_CODE:
        return run_kc50_strategy(rows, kc_idx_rows)
    if code == ZZ500_CODE:
        return run_zz500_strategy_v2(rows)
    if code == A500_CODE:
        return run_a500_strategy(rows, hs300_rows, t_pct, m_pct)
    return _run_default(rows, t_pct, m_pct)
