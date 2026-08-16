"""按 ETF 代码分派各专属策略, 统一生成买卖点。

双槽位架构:
  STABLE 槽位 — 正式版(生产使用, 所有 ETF 都有)
  BETA   槽位 — 调试版(仅手动注册的 ETF 有; 候选升级, 必须回测优于正式版
               才值得发布, 否则连 Beta 都无存在价值)

页面「共振买卖点」与「组合回测」共用本入口, 保证两边买卖点一致。
本模块纯函数无 I/O; 所需数据由调用方注入:
  t_pct / m_pct — {date: {percentile}} 成交额/融资余额分位(部分策略需要)
  hs300_rows    — 510300 日线(A500 复用其买卖点)
  kc_idx_rows   — 589680 日线(科创50 参照其吸筹特征)
"""

from __future__ import annotations

import math
from collections.abc import Callable

from base.analysis.strategy.a500 import A500_CODE, run_a500_strategy
from base.analysis.strategy.div import DIV_CODE, run_div_strategy
from base.analysis.strategy.hs300 import HS300_CODE, run_hs300_strategy
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


# ---- 正式版槽位(生产使用): 每只 ETF 的生产算法 ----
# 未显式注册的 ETF 走 _run_default 通用多指标共振
# 分位注入型策略用 _inject_closure 包装, 避免 lambda 闭包 t_pct 的引用 bug
STABLE_STRATEGIES: dict[str, Callable[..., dict]] = {
    KC_CODE: run_kc_strategy,
    # 中证1000 正式版 = zz.py 右侧量价记忆(2021 起全历史 + 验证期 + 缩量深底 + 热度顶, 2026-08-16 升级)
    ZZ_CODE: run_zz_strategy,
    DIV_CODE: lambda rows, tp=None, mp=None: run_div_strategy(_inject_percentile(rows, tp or {}, mp or {})),
    SH50_CODE: run_sh50_strategy,
    SC50_CODE: run_sc50_strategy,
    KC50_CODE: run_kc50_strategy,
    ZZ500_CODE: run_zz500_strategy_v2,
    # 沪深300 正式版 = 生产环境通用多指标共振(6714ce0)
    HS300_CODE: lambda rows, tp=None, mp=None: _run_default(rows, tp or {}, mp or {}),
    A500_CODE: run_a500_strategy,
}

# ---- Beta 槽位(调试版): 手动注册才有, 未注册的 ETF 无 Beta ----
# 新增 beta 步骤: 在此注册 → 回测对比 STABLE → 优于才考虑升级正式版
BETA_STRATEGIES: dict[str, Callable[..., dict]] = {
    # 沪深300 beta = 调试中的 A+B 混合策略(验证期/跌势门槛/份额承接门槛)
    HS300_CODE: run_hs300_strategy,
}


def list_strategy_versions() -> dict[str, bool]:
    """返回 {code: has_beta} 供前端控制 Beta 切换按钮显隐。"""
    from base.config import ETFS

    return {code: code in BETA_STRATEGIES for code in ETFS}


def compute_trades(
    code: str,
    rows: list[dict],
    *,
    t_pct: dict | None = None,
    m_pct: dict | None = None,
    hs300_rows: list[dict] | None = None,
    kc_idx_rows: list[dict] | None = None,
    version: str = "stable",
) -> dict:
    """生成与页面「共振买卖点」一致的交易信号。

    rows 必须为升序(由调用方从库里加载并排序)。
    version: "stable"(正式版) / "beta"(调试版)。
    beta 未注册的 ETF 回退到正式版(前端应隐藏 Beta 按钮)。
    """
    t_pct = t_pct or {}
    m_pct = m_pct or {}

    fn = None
    if version == "beta":
        fn = BETA_STRATEGIES.get(code)
    if fn is None:
        fn = STABLE_STRATEGIES.get(code)

    if fn is None:
        return _run_default(rows, t_pct, m_pct)
    # 分位注入型(zz/div/hs300-beta): 策略签名单参数 rows, 内部读 _tp/_mp, 统一注入
    if code in (ZZ_CODE, DIV_CODE) or (code == HS300_CODE and version == "beta"):
        return fn(_inject_percentile(rows, t_pct, m_pct))
    # kc50 需要 kc_idx_rows, a500 需要 hs300_rows
    if code == KC50_CODE:
        return fn(rows, kc_idx_rows)
    if code == A500_CODE:
        return fn(rows, hs300_rows)
    # hs300 stable 是 lambda 包装(收 tp/mp 转 _run_default)
    if code == HS300_CODE and version == "stable":
        return fn(rows, t_pct, m_pct)
    return fn(rows)
