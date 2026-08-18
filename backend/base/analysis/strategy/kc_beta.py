"""科创综指 (589680) Beta — 正式版 kc.py 上加「高位散户顶/加速赶顶/洗盘回买」。

核心认知(与正式版共用): 主力极度惜售, 吸筹期份额持续净流入(12-24~12-31
+3.8亿, 05-18~05-25 +3.3亿, 07-30 崩盘 +3.35亿); "卖少则砸" = 顶部不砸
大单, 小幅流出后直接砸盘; "砸后低吸" = 回调中份额仍流入。
  量能记忆: 卖出确认必须与吸筹量匹配 —— 出货信号日仍净申购(sd>0) =
  洗盘/换手(08-13 +1.0 / 08-18 +0.8 / 08-28 +1.2 / 05-20 +0.5), 净赎回
  (sd<0) = 真出货(09-02 -0.35 / 06-22 -0.5)。近10日吸筹≥2亿时出货信号
  豁免, 但豁免须看吸筹周期资金留存: 01-07 单日-1.0亿回撤36%是换手,
  连续两日回撤≥30% 才是真撤离。份额 T+1 披露 → 信号当日触发次日执行。

Beta 新增(每条一个以上案例):
  1. 高位贪婪散户顶: pp≥97 + 大量净申购(sp≥90 且 sd≥0.5亿) + 浮盈≥15%
     = 散户接盘力竭 → 次日卖。案例: 2025-08-28 (sp91.5/sd+1.2/pp99.7)
     → 08-29 @1.27(顶 09-01 @1.28); 2026-05-13 (sp95/sd+0.65/pp99.5)
     → 05-14 @1.65(顶 05-20 @1.72, 后崩 -11%)。反例: 2025-04 吸筹群
     sp95 但 pp<60 = 低位机构吸筹, 位置过滤全拦。
  2. 加速赶顶卖: 2日累计涨≥6% + pp≥99 + 浮盈≥15% → 当日卖。案例:
     2026-06-30 (06-29 +3.5% + 06-30 +4.02%, pp100) → @1.97, 次日
     07-02 -5.3%。06-18 同指纹 pp98 拦(主升中段)。
  3. 洗盘回买: 连两日大跌(前日≥2% 当日≥2.5%) + pp≤60 + 距20日高≤-8%
     + 前5日累计净申赎≥-0.5亿 + 前一日 sp≥60 + vr≤1.3 缩量 → 当日买。案例: 2026-06-08
     @1.53 → 06-30 @1.97 +28.8%。06-01 同指纹 pp62.9 拦; 07-13 同指纹
     sp37.6 / 07-16 sp50.2(份额动能塌)、07-17 放量崩盘 vr2.06 拦 = 防接刀。
  4. S1 出货信号加浮盈≥20% 门槛: 06-22 DISTRIBUTE 浮盈 16.2% 是主升中段
     洗盘(事后 06-30 +28.8% 更高) → 不卖, 交给加速赶顶卖。

历史教训(共用): 08-13 出货信号但申购+1.0 → 若卖只 +33.5%, 实际 09-02
卖 +48.2%; 01-09 卖 @1.418 +19.3% (R1 撤离); 10-17 止盈 @1.234 (T1)。
算法: 买入 5 路径(P1 恐慌/P2 低位吸筹/极低位缩量/极低位放量恐慌/P-W
洗盘回买), 卖出 7 规则(S-G→S-B→S1→S2→R1→T1), 份额类规则 T+1 执行。
"""

from __future__ import annotations

from base.analysis.strategy.metrics import calc_round_metrics

KC_BETA_CODE = "589680"

BUY_PP_MAX = 35
PANIC_DROP = -10.0
PANIC_PP_MAX = 40

EXTREME_PP = 15  # 极低位缩量: 价格位置上限
EXTREME_VR_MAX = 1.0  # 极低位缩量: 量比上限(低量=卖压耗尽)
EXTREME_CHG = -2.0
PANIC_LOW_PP = 10  # 极低位放量恐慌: pp 上限
PANIC_LOW_CHG = -5.0  # 极低位放量恐慌: 跌幅阈值
PANIC_LOW_VR = 1.2  # 极低位放量恐慌: 量比下限

CLUSTER_ACCUM = 2
CLUSTER_WINDOW = 10
HIGH_LOOKBACK = 30
DROP_EARLY_DAYS = 15

# ---- 卖出参数(与正式版一致) ----
TRAIL_PCT = 0.10  # 止盈: 持仓期最高收盘回落比例(兜底)
DIST_PP_MIN = 97  # 出货信号: pp 阈值(顶部区)
DIST_VR_MIN = 1.5  # 出货信号: 量比阈值
BREAK_CHG = -2.5  # 破位出货: 跌幅阈值
BREAK_VR_MIN = 1.5  # 破位出货: 量比下限
MEMORY_EXEMPT = 2.0  # 量能记忆: 近10日累计吸筹≥2亿(豁免前提之一)
CYCLE_RETREAT_MAX = 0.30  # 量能记忆: 吸筹周期累计净申赎从峰值回撤阈值
# 单日破位=换手(01-07 -1.0亿冲36%次日衰减); 连两日≥30% = 真撤离(01-07/08)
FUND_EXEMPT = 0.5  # 止盈豁免: 前10日累计净申赎阈值(吸筹中)
SD_WINDOW = 10  # 吸筹动能窗口
SD_MIN_COUNT = 8  # 吸筹动能最少有效天数

MIN_HOLD = 10
COOLDOWN = 3
TRADE_START = "2025-04-01"

# ---- Beta 新增参数 ----
GREEDY_SP_MIN = 90.0  # S-G 高位散户顶: 份额概率下限(08-28 91.5 / 05-13 95)
GREEDY_SD_MIN = 0.5  # S-G 当日净申购下限亿(08-28 +1.2 / 05-13 +0.65)
GREEDY_PP_MIN = 97.0  # S-G 位置下限(08-28 99.7 / 05-13 99.5; 4月 pp<60 拦)
GREEDY_PROFIT_MIN = 15.0  # S-G 浮盈下限%(08-28 +54 / 05-13 +34)
BLOW_2D_CHG = 6.0  # S-B 加速赶顶: 2日累计涨幅(06-29+06-30 = 7.7)
BLOW_PP_MIN = 99.0  # S-B 位置(06-18 pp98 拦; 06-30 pp100 过)
BLOW_CHG_MIN = 3.0  # S-B 当日涨幅(06-30 +4.02)
BLOW_PROFIT_MIN = 15.0  # S-B 浮盈下限(06-30 +28.8)
WASH_CHG_MIN = 2.5  # P-W 洗盘回买: 当日跌幅(06-08 -3.47)
WASH_PREV_CHG_MIN = 2.0  # P-W 前一日跌幅(06-05 -2.34)
WASH_PP_MAX = 60.0  # P-W 位置(06-08 56.8; 06-01 62.9 拦)
WASH_DD20_MIN = 8.0  # P-W 距20日高回撤(06-08 -12.1)
WASH_SD5_MIN = -0.5  # P-W 前5日累计净申赎亿(06-08 +0.35, 机构未撤)
WASH_VR_MAX = 1.3  # P-W 缩量(06-08 0.85 洗盘底; 07-17 2.06 放量崩盘拦)
WASH_SP_MIN = 60.0  # P-W 前一日份额概率(06-08 80; 07-13 37.6 / 07-16 50.2 接刀拦)
DIST_PROFIT_MIN = 20.0  # S1 浮盈门槛(06-22 16.2% 主升中段洗盘不卖)


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1) if rows[j].get("trade_direction") == "ACCUMULATE")


def _days_since_30d_high(rows: list[dict], idx: int) -> int:
    lo = max(0, idx - HIGH_LOOKBACK + 1)
    high_close = max((rows[j].get("close_price") or 0) for j in range(lo, idx + 1))
    for j in range(idx, lo - 1, -1):
        if (rows[j].get("close_price") or 0) == high_close:
            return idx - j
    return HIGH_LOOKBACK


def _acc_sd(rows: list[dict], idx: int) -> float | None:
    """前 SD_WINDOW 日累计净申赎(不含当日, 只用 T-1 及更早数据).
    份额 T+1 披露, 当日盘中不可得; 有效天数不足返回 None."""
    total = 0.0
    cnt = 0
    for j in range(max(0, idx - SD_WINDOW), idx):
        v = rows[j].get("shares_delta_yi")
        if v is not None:
            total += v
            cnt += 1
    return total if cnt >= SD_MIN_COUNT else None


def _dd20(closes: list[float], idx: int) -> float:
    """距20日最高收盘回撤(%)。"""
    hi = max(closes[max(0, idx - 19) : idx + 1])
    return (closes[idx] / hi - 1) * 100 if hi > 0 else 0.0


def _sd5(rows: list[dict], idx: int) -> float | None:
    """前5日累计净申赎(不含当日, T+1 披露安全), 不足3天返回 None。"""
    total = 0.0
    cnt = 0
    for j in range(max(0, idx - 5), idx):
        v = rows[j].get("shares_delta_yi")
        if v is not None:
            total += v
            cnt += 1
    return total if cnt >= 3 else None


def run_kc_beta_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": KC_BETA_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    # 吸筹周期累计(含当日): 从 0 累加净申赎, 跌回<=0 时周期结束, 重置累计与峰值。
    # 份额 T+1 披露, 与 sd_today 同一时点, 次日执行卖出, 无前视偏差。
    cycle_sum = [0.0] * n
    cycle_peak = [0.0] * n
    c = p = 0.0
    for i in range(n):
        c = max(0.0, c + (rows[i].get("shares_delta_yi") or 0.0))
        p = 0.0 if c <= 0.0 else max(p, c)
        cycle_sum[i] = c
        cycle_peak[i] = p

    # 撤离持续确认: 当日与前一日回撤均≥阈值才算资金持续撤离。
    retreat_sustained = [False] * n
    for i in range(1, n):
        if cycle_peak[i] > 0 and cycle_peak[i - 1] > 0:
            r_now = 1.0 - cycle_sum[i] / cycle_peak[i]
            r_prev = 1.0 - cycle_sum[i - 1] / cycle_peak[i - 1]
            retreat_sustained[i] = r_now >= CYCLE_RETREAT_MAX and r_prev >= CYCLE_RETREAT_MAX

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    peak_close = 0.0
    entry_price = 0.0
    pending_sell_idx = None
    pending_kind = "dist"

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        prev_chg = (rows[i - 1].get("change_pct") or 0) if i > 0 else 0.0
        sp_prev = rows[i - 1].get("share_prob") if i > 0 else None
        profit = (close / entry_price - 1) * 100 if position == 1 and entry_price > 0 else 0.0

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- T+1 确认执行挂起的卖出 ----
        if pending_sell_idx is not None and i > pending_sell_idx:
            signal_date = rows[pending_sell_idx]["date"]
            signal_sd = rows[pending_sell_idx].get("shares_delta_yi")
            action = "SELL"
            kind = {"retreat": "资金持续撤离", "greedy": "高位散户顶"}.get(pending_kind, "出货确认")
            reason = f"{signal_date}{kind}sd{signal_sd}"
            pending_sell_idx = None

        # ---- 买入: P1 恐慌 / P2 低位吸筹 / 极低位缩量 / 极低位放量恐慌 / P-W 洗盘回买 ----
        if action is None and position == 0 and cooldown >= COOLDOWN:
            acc = td == "ACCUMULATE"
            acc_n = _count_accum(rows, i)
            dh = _days_since_30d_high(rows, i)
            low15 = pp is not None and pp <= EXTREME_PP and vr < EXTREME_VR_MAX
            sd5 = _sd5(rows, i)
            wash = (
                chg <= -WASH_CHG_MIN
                and prev_chg <= -WASH_PREV_CHG_MIN
                and pp is not None
                and pp <= WASH_PP_MAX
                and _dd20(closes, i) <= -WASH_DD20_MIN
                and sd5 is not None
                and sd5 >= WASH_SD5_MIN
                and vr <= WASH_VR_MAX
                and sp_prev is not None
                and sp_prev >= WASH_SP_MIN
            )

            if acc and chg <= PANIC_DROP and pp is not None and pp <= PANIC_PP_MAX and acc_n < CLUSTER_ACCUM:
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}"
            elif acc and pp is not None and pp <= BUY_PP_MAX and acc_n < CLUSTER_ACCUM and dh >= DROP_EARLY_DAYS:
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+距高点{dh}天"
            elif low15 and chg <= EXTREME_CHG and dh >= DROP_EARLY_DAYS and acc_n < CLUSTER_ACCUM:
                action = "BUY"
                reason = f"极低位: pp{pp:.0f}+缩量{vr:.2f}"
            elif pp is not None and pp <= PANIC_LOW_PP and chg <= PANIC_LOW_CHG and vr >= PANIC_LOW_VR:
                action = "BUY"
                reason = f"放量恐慌: 跌{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"
            elif wash:
                action = "BUY"
                reason = f"洗盘回买: 连跌{prev_chg:.1f}/{chg:.1f}%+pp{pp:.0f}+前5日申赎{sd5:+.1f}亿"

        # ---- 卖出: S1 出货(浮盈门槛) / S2 破位 / R1 撤离 / S-G 散户顶 / S-B 赶顶 / T1 止盈 ----
        if action is None and position == 1:
            hold_days += 1
            peak_close = max(peak_close, close)
            a10 = _acc_sd(rows, i)
            sd_today = rows[i].get("shares_delta_yi")
            is_dist = td == "DISTRIBUTE"
            sp = row.get("share_prob")
            memory_exempt = a10 is not None and a10 >= MEMORY_EXEMPT and not retreat_sustained[i]
            trail_exempt = a10 is not None and a10 >= FUND_EXEMPT
            sd_neg = sd_today is not None and sd_today < 0
            s1 = is_dist and pp is not None and pp >= DIST_PP_MIN and vr >= DIST_VR_MIN and profit >= DIST_PROFIT_MIN
            s2 = chg <= BREAK_CHG and vr >= BREAK_VR_MIN
            sp_ok = sp is not None and sp >= GREEDY_SP_MIN and sd_today is not None and sd_today >= GREEDY_SD_MIN
            blow = chg >= BLOW_CHG_MIN and chg + prev_chg >= BLOW_2D_CHG

            if (s1 or s2) and not memory_exempt and sd_neg:
                pending_sell_idx = i
                pending_kind = "dist"
            elif a10 is not None and a10 >= MEMORY_EXEMPT and retreat_sustained[i] and sd_neg:
                pending_sell_idx = i
                pending_kind = "retreat"
            elif sp_ok and pp is not None and pp >= GREEDY_PP_MIN and profit >= GREEDY_PROFIT_MIN:
                pending_sell_idx = i
                pending_kind = "greedy"
            elif blow and pp is not None and pp >= BLOW_PP_MIN and profit >= BLOW_PROFIT_MIN:
                action = "SELL"
                reason = f"加速赶顶: 2日+{chg + prev_chg:.1f}%+pp{pp:.0f}"
            elif hold_days >= MIN_HOLD and close < peak_close * (1 - TRAIL_PCT) and not trail_exempt:
                reason = f"止盈: 高点{peak_close:.3f}回落至{close:.3f}"
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            peak_close = close
            entry_price = close
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            peak_close = 0.0
            entry_price = 0.0
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = calc_round_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": KC_BETA_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}
