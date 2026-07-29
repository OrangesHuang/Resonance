"""V5 吸筹/出货周期策略 — 锚定大资金脚印。

核心逻辑:
  买点 = 吸筹信号(ACCUMULATE) + 低位确认 + 量能验证
  卖点 = 出货信号(DISTRIBUTE) + 高位确认 + 量能对比验证

量能周期对比(用户核心洞察):
  真正的出货，量能应该≥吸筹阶段的量能。如果高位出货量比低位吸筹量还小，
  说明大资金没用力卖，可能是假出货。

状态机: 空仓 ⇄ 满仓
"""

from typing import Optional

TRADE_START = "2024-10-08"

# ===== 买入: 吸筹信号 + 低位 =====
BUY_PP_MAX = 35.0           # 买入价格位置上限
BUY_VR_MIN = 1.5            # 买入量比下限

# ===== 卖出: 出货信号 + 高位 + 量能对比 =====
SELL_PP_MIN = 75.0          # 卖出价格位置下限
SELL_VR_MIN = 1.5           # 卖出量比下限
SELL_PROFIT_MIN = 2.0       # 卖出最低盈利要求(%)

COOLDOWN = 5                # 交易冷却期


def run_v5_strategy(rows: list[dict]) -> dict:
    """V5 吸筹/出货周期策略。

    买: ACCUMULATE + pp<=35 + vr>=1.5 → 满仓
    卖: DISTRIBUTE + pp>=75 + vr>=1.5 + 盈利>0
         且 当前量能 >= 买入以来累积吸筹均量 (量能对比验证)

    持仓期间持续跟踪:
      - 累积吸筹日的量能(用于卖出时对比)
      - 份额变动方向(辅助判断)
    """
    n = len(rows)
    if n < 30:
        return {"code": "", "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]
    code = rows[0].get("code", "") if rows else ""

    trades: list[dict] = []
    position = 0
    cooldown = COOLDOWN

    # 持仓期间跟踪
    accum_volumes: list[float] = []   # 持仓期间所有吸筹日的量比
    accum_count = 0                    # 持仓期间吸筹日计数
    dist_count = 0                     # 持仓期间出货日计数
    entry_shares: Optional[float] = None  # 买入时的份额水平
    peak_shares: float = 0.0           # 持仓期间份额峰值
    share_trend: list[float] = []     # 持仓期间份额变动序列

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

        cooldown += 1

        if d < TRADE_START:
            continue

        action: Optional[str] = None
        reason = ""

        is_accum = td == "ACCUMULATE"
        is_dist = td == "DISTRIBUTE"
        pp_low = pp is not None and pp <= BUY_PP_MAX
        pp_high = pp is not None and pp >= SELL_PP_MIN
        vr_ok = vr >= BUY_VR_MIN

        # ====== 持仓期间持续跟踪 ======
        if position == 1:
            if is_accum:
                accum_volumes.append(vr)
                accum_count += 1
            if is_dist:
                dist_count += 1
            if sd is not None:
                share_trend.append(sd)
            cur_shares = row.get("shares_yi")
            if cur_shares is not None:
                peak_shares = max(peak_shares, cur_shares)

        # ====== 买入 ======
        if position == 0 and cooldown >= COOLDOWN:
            if is_accum and pp_low and vr_ok:
                action = "BUY"
                reason = (f"吸筹买入: 位置{pp:.0f}+量比{vr:.1f}"
                          f"+份额{sp:.0f}" if sp else
                          f"吸筹买入: 位置{pp:.0f}+量比{vr:.1f}")

        # ====== 卖出 ======
        if position == 1 and cooldown >= COOLDOWN:
            if is_dist and pp_high and vr_ok:
                buy_price = trades[-1]["price"] if trades else close
                profit_pct = (close - buy_price) / buy_price * 100

                if profit_pct <= 0:
                    continue  # 不盈利不卖

                # ---- 量能对比验证 ----
                # 真正的出货，当前量能不应低于吸筹阶段的量能
                avg_accum_vr = (sum(accum_volumes) / len(accum_volumes)
                                if accum_volumes else vr)
                vol_confirmed = vr >= avg_accum_vr * 0.8  # 允许20%容差

                # 份额离场判断: 份额必须跌破买入时水平才算真离场
                # 100亿买进来，份额还在买入价之上 → 主力还在
                # 份额跌到买入价之下 → 主力净卖出，考虑离场
                cur_shares = row.get("shares_yi")
                share_below_entry = False
                share_exit_pct = 0.0
                if entry_shares is not None and cur_shares is not None:
                    share_exit_pct = (entry_shares - cur_shares) / entry_shares * 100
                    # 份额跌到买入时的95%以下(即比买入时少5%)
                    share_below_entry = share_exit_pct >= 5

                if vol_confirmed:
                    action = "SELL"
                    reason = (f"出货卖出: 位置{pp:.0f}+量比{vr:.1f}"
                              f"+浮盈{profit_pct:.0f}%"
                              f" [吸筹均量{avg_accum_vr:.1f}]")
                elif share_below_entry and profit_pct >= SELL_PROFIT_MIN:
                    action = "SELL"
                    reason = (f"主力离场: 份额跌破买入{share_exit_pct:.0f}%"
                              f"+浮盈{profit_pct:.0f}%"
                              f" [买入{entry_shares:.0f}→当前{cur_shares:.0f}亿]")

        if action == "BUY":
            position = 1
            cooldown = 0
            accum_volumes = []
            accum_count = 0
            dist_count = 0
            share_trend = []
            entry_shares = row.get("shares_yi")
            peak_shares = entry_shares or 0.0
            trades.append({
                "date": d, "action": "BUY", "price": close,
                "reason": reason,
            })
        elif action == "SELL":
            position = 0
            cooldown = 0
            trades.append({
                "date": d, "action": "SELL", "price": close,
                "reason": reason,
            })

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": code, "trades": trades, "metrics": metrics,
            "holding": position > 0}


def _calc_metrics(trades: list[dict], last_close: float,
                  position: int) -> dict:
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
