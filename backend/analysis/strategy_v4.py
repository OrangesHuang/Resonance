"""V4 政策市策略 — 基于 924 后市场结构性变化的逻辑推导。

公理:
  1. 政策底存在: 5000亿互换便利+3000亿回购再贷款可扩容，政府有能力也有意愿托市
  2. 大资金有惯性: ETF份额日增>3%意味着机构资金承诺，影响持续3-6个月，短期"出货信号"不可信
  3. 持有>交易: 土地→股权财政是十年叙事，频繁交易是负优化

买入逻辑:
  - 恐慌接筹: 暴跌日跟随国家队进场
  - 回调吸筹: 低位+机构买入确认
  - 极端价值: 跌到政策底附近

卖出逻辑(严格):
  - 主力离场: 份额连续收缩+高位放量(机构真的在走)
  - 系统性出货: 连续3天DISTRIBUTE+高位(非单日噪音)
  - 大资金衰减: 天量买入180天后自动退出(资金影响消退)

仓位管理:
  - 满仓/空仓二元切换，不存在分批次加仓
"""

from typing import Optional


# ===== 买入参数 =====
PANIC_DROP = -2.0           # 恐慌跌幅阈值
PANIC_VR = 2.0              # 恐慌量比
PANIC_PP_MAX = 30.0         # 恐慌位置上限
PANIC_SP_MIN = 65.0         # 恐慌份额下限

DIP_PP_MAX = 35.0           # 回调吸筹位置上限
DIP_SP_MIN = 65.0           # 回调份额下限
DIP_VR_MIN = 1.5            # 回调量比下限

VALUE_PP_MAX = 15.0         # 极端价值位置上限
VALUE_VR_MIN = 1.2          # 极端价值量比下限

# ===== 卖出参数 =====
EXIT_PP_MIN = 75.0          # 离场位置下限
EXIT_VR_MIN = 1.5           # 离场量比下限
SHARE_CONTRACT_DAYS = 2     # 份额连续收缩确认天数
SHARE_CONTRACT_EACH = -1.0  # 份额收缩每日本阈值(%)
DISTRIB_STREAK = 3          # 连续出货确认天数
WHALE_SHADOW_DAYS = 180     # 天量资金影响持续时间
WHALE_SHARE_THRESHOLD = 3.0 # 判定"天量资金"的份额日增阈值(%)

COOLDOWN_BUY = 5            # 买入冷却期
COOLDOWN_SELL = 3           # 卖出冷却期
TRADE_START = "2024-10-08"  # 策略生效起始日


def run_v4_strategy(rows: list[dict]) -> dict:
    """V4 政策市策略。

    买入逻辑:
      1. 恐慌接筹: 暴跌+天量+份额暴增+ACCUMULATE
      2. 回调吸筹: 低位+份额增长+ACCUMULATE+温和放量
      3. 极端价值: 极低位+ACCUMULATE+放量

    卖出逻辑(仅在三条件之一满足时):
      1. 主力离场: 份额连续2天收缩+高位放量
      2. 系统性出货: 连续3天DISTRIBUTE+高位
      3. 天量资金衰减: 买入时份额增>3%→180天后自动退出

    仓位: 基础1份; 份额>5%额外+1; 位置<10额外+1; 最大3份
    """
    n = len(rows)
    if n < 30:
        return {"code": "", "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]
    code = rows[0].get("code", "") if rows else ""

    trades: list[dict] = []
    position = 0.0           # 0.0 ~ 3.0 (单位份数)
    buy_cooldown = COOLDOWN_BUY
    sell_cooldown = COOLDOWN_SELL
    hold_days = 0
    whale_shadow_end = 0     # 天量资金影响截止日索引
    distrib_streak = 0       # 连续出货天数
    share_contract_streak = 0  # 连续份额收缩天数

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        chg = row.get("change_pct") or 0
        vr = row.get("volume_ratio") or 0
        pp = row.get("price_position")
        sp = row.get("share_prob")
        sd = row.get("shares_delta_pct")
        td = row.get("trade_direction")

        buy_cooldown += 1
        sell_cooldown += 1

        if d < TRADE_START:
            continue

        action: Optional[str] = None
        reason = ""

        # ====== 买入逻辑（仅空仓时） ======
        if position == 0 and buy_cooldown >= COOLDOWN_BUY:
            is_accum = td == "ACCUMULATE"

            # 1. 恐慌接筹
            panic = (chg <= PANIC_DROP and vr >= PANIC_VR
                     and pp is not None and pp <= PANIC_PP_MAX
                     and sp is not None and sp >= PANIC_SP_MIN
                     and is_accum)

            # 2. 回调吸筹
            dip = (is_accum and pp is not None and pp <= DIP_PP_MAX
                   and sp is not None and sp >= DIP_SP_MIN
                   and vr >= DIP_VR_MIN)

            # 3. 极端价值
            value = (is_accum and pp is not None and pp <= VALUE_PP_MAX
                     and vr >= VALUE_VR_MIN)

            if panic:
                action = "BUY"
                reason = (f"恐慌接筹: 跌{chg:.1f}%+量比{vr:.1f}"
                          f"+份额{sp:.0f}+位置{pp:.0f}")
                if sd is not None and sd >= WHALE_SHARE_THRESHOLD:
                    whale_shadow_end = i + WHALE_SHADOW_DAYS

            elif dip:
                action = "BUY"
                reason = (f"回调吸筹: 位置{pp:.0f}+份额{sp:.0f}"
                          f"+量比{vr:.1f}")
                if sd is not None and sd >= WHALE_SHARE_THRESHOLD:
                    whale_shadow_end = i + WHALE_SHADOW_DAYS

            elif value:
                action = "BUY"
                reason = f"极端价值: 位置{pp:.0f}+量比{vr:.1f}"

        # ====== 卖出逻辑（仅持仓时） ======
        if position == 1 and sell_cooldown >= COOLDOWN_SELL:
            hold_days += 1
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= EXIT_PP_MIN
            vr_high = vr >= EXIT_VR_MIN

            # 跟踪连续信号
            if is_dist and pp_high:
                distrib_streak += 1
            else:
                distrib_streak = 0

            if sd is not None and sd <= SHARE_CONTRACT_EACH:
                share_contract_streak += 1
            else:
                share_contract_streak = 0

            # 条件 1: 主力离场 — 份额连续收缩+高位放量
            capital_exit = (share_contract_streak >= SHARE_CONTRACT_DAYS
                            and pp_high and vr_high)

            # 条件 2: 系统性出货 — 连续N天DISTRIBUTE+高位
            systematic_dist = distrib_streak >= DISTRIB_STREAK

            # 条件 3: 天量资金衰减 — whale shadow到期
            whale_expired = (whale_shadow_end > 0 and i >= whale_shadow_end)

            exit_triggered = False
            if capital_exit:
                action = "SELL"
                reason = (f"主力离场: 份额连续{share_contract_streak}天收缩"
                          f"+位置{pp:.0f}+量比{vr:.1f}")
                exit_triggered = True
            elif systematic_dist:
                action = "SELL"
                reason = f"系统性出货: 连续{distrib_streak}天DISTRIBUTE"
                exit_triggered = True
            elif whale_expired:
                # 大资金影响消退，找机会退出（不强制当天，等高位）
                if pp_high:
                    action = "SELL"
                    reason = (f"天量衰减+高位: 买入时份额暴增，"
                              f"已过{WHALE_SHADOW_DAYS}天")
                    exit_triggered = True

            # 不满足任何退出条件 → 继续持有
            # 公理3: 持有>交易，没有明确离场证据就不动

        if action == "BUY":
            position = 1.0
            hold_days = 0
            buy_cooldown = 0
            sell_cooldown = 0
            distrib_streak = 0
            share_contract_streak = 0
            trades.append({
                "date": d, "action": "BUY", "price": close,
                "reason": reason,
            })
        elif action == "SELL":
            position = 0.0
            sell_cooldown = 0
            whale_shadow_end = 0
            distrib_streak = 0
            share_contract_streak = 0
            trades.append({
                "date": d, "action": "SELL", "price": close,
                "reason": reason,
            })

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": code, "trades": trades, "metrics": metrics,
            "holding": position > 0}


def _calc_metrics(trades: list[dict], last_close: float,
                  position: float) -> dict:
    rounds = []
    buy_price = None
    buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price is not None:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append({
                "buy_date": buy_date, "sell_date": t["date"],
                "buy_price": buy_price, "sell_price": t["price"],
                "return_pct": round(ret, 2),
            })
            buy_price = None

    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append({
            "buy_date": buy_date, "sell_date": None,
            "buy_price": buy_price, "sell_price": last_close,
            "return_pct": round(ret, 2),
        })

    total_ret = 1.0
    wins = 0
    for r in rounds:
        total_ret *= (1 + r["return_pct"] / 100)
        if r["return_pct"] > 0:
            wins += 1

    return {
        "rounds": rounds,
        "total_return_pct": round((total_ret - 1) * 100, 2),
        "round_count": len(rounds),
        "win_count": wins,
        "win_rate": (round(wins / len(rounds) * 100, 1) if rounds else 0),
        "trade_count": len(trades),
    }
