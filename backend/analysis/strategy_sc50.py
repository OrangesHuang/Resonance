"""双创50 (159780) 右侧趋势策略。

核心认知:
  双创50是2024-10-08前即上市的高波动成长ETF, 与中证500同属趋势型,
  但有两个截然不同的特征:
  1. DISTRIBUTE 集群极长 — 2025年6月到8月几乎天天出货信号, 价格却一路涨
     → 卖出不能用"数出货次数", 必须用趋势破位(MA30)
  2. 份额信号历史缺失(2024~2025年无回填) → 份额仅作可选方向过滤
  历史教训:
  1. 买太早: 2024-01-11 孤立ACCUMULATE日买入@0.462, 实际是暴跌集群开端,
     继续跌到 02-05 @0.407(-12%) → 双创50不做P2低位孤立, 左侧只留给极端恐慌
  2. 卖出太早: 5月/10月/11月三次深回调都是假破位(后续创更高),
     2026-07 才是真趋势破坏 → 用 MA30+3% 深度破位过滤浅回调
  3. 集群右侧: 2024-09-24 集群中第一个放量反弹日买入@0.423 → 吃到924行情
     → 集群中禁止左侧, 等反弹确认(涨+量+低位)

算法:
  买入(2路径):
    P1 单日极端恐慌: 跌≥9%+ACCUMULATE+pp≤20+非集群 → 左侧买
       (2025-04-07 -10.85% @0.485; 2026-07-28 -7.74% 被拦截)
    P3 暴跌集群右侧: 10天≥3个ACCUMULATE → 等反弹确认
       反弹需: 涨≥2%+vr≥1.2+pp≤45+份额方向(有数据时sd>0), 跌破前低作废
       (2024-02-05 集群末反弹买@0.418 / 2024-09-24 924反弹买@0.423)
  卖出(1规则):
    趋势破位: 持仓≥25天 + 收盘 < MA30×0.97 → 卖
       (DISTRIBUTE集群是牛市噪音, 用MA30深度破位替代;
        2025-11-18 深回调卖@0.876, 2026-07 崩盘在空仓中避开)
"""

import math

SC50_CODE = "159780"

BUY_PP_MAX = 35
PANIC_DROP = -9.0
PANIC_PP_MAX = 20

CLUSTER_ACCUM = 3
CLUSTER_WINDOW = 10
BOUNCE_CHG = 2.0
BOUNCE_VR = 1.2
BOUNCE_PP_MAX = 45

MA_WINDOW = 30
MA_BREAK = 0.97
MIN_HOLD = 25
COOLDOWN = 3
VOL_LOOKBACK = 20
TRADE_START = "2024-01-01"


def _count_accum(rows: list[dict], idx: int, window: int = CLUSTER_WINDOW) -> int:
    return sum(1 for j in range(max(0, idx - window + 1), idx + 1)
               if rows[j].get("trade_direction") == "ACCUMULATE")


def _ma(closes: list[float], idx: int, window: int = MA_WINDOW) -> float:
    lo = max(0, idx - window + 1)
    return sum(closes[lo:idx + 1]) / (idx - lo + 1)


def run_sc50_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": SC50_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    sell_threshold = 1
    waiting_reversal = False
    wait_low = None

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        sd = row.get("shares_delta_yi")

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- 买入 ----
        if position == 0 and cooldown >= COOLDOWN:
            is_accum = td == "ACCUMULATE"
            accum_count = _count_accum(rows, i)

            # P1: 单日极端恐慌 (非集群中, 左侧)
            if (is_accum and chg <= PANIC_DROP
                    and pp is not None and pp <= PANIC_PP_MAX
                    and accum_count < CLUSTER_ACCUM):
                action = "BUY"
                reason = f"恐慌抄底: 跌{chg:.1f}%+pp{pp:.0f}"

            # P3: 暴跌集群 → 等待右侧确认
            elif accum_count >= CLUSTER_ACCUM:
                waiting_reversal = True
                wait_low = min((rows[j].get("close_price") or 0)
                               for j in range(max(0, i - CLUSTER_WINDOW + 1), i + 1))

        # ---- P3 右侧确认 ----
        if position == 0 and waiting_reversal and wait_low is not None:
            if close < wait_low:
                # 跌破前低 → 假反弹, 本次集群作废
                waiting_reversal = False
                wait_low = None
            else:
                accum_count = _count_accum(rows, i)
                cluster_ended = accum_count < CLUSTER_ACCUM or td != "ACCUMULATE"
                prev_chg = rows[i - 1].get("change_pct") or 0 if i > 0 else 0
                pp_ok = pp is not None and pp <= BOUNCE_PP_MAX
                money_ok = sd is None or sd > 0  # 份额无历史, 有数据时方向过滤

                strong_bounce = (chg >= BOUNCE_CHG and vr >= BOUNCE_VR
                                 and pp_ok and money_ok)
                two_day_up = (cluster_ended and chg > 0 and prev_chg > 0
                              and vr > 1.0 and pp_ok and money_ok)

                if strong_bounce or two_day_up:
                    action = "BUY"
                    reason = (f"右侧反弹: 涨{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"
                              if strong_bounce else
                              f"右侧连涨: 2天+放量+pp{pp:.0f}")
                    waiting_reversal = False
                    wait_low = None
                elif pp is not None and pp > 55:
                    waiting_reversal = False  # 价格回升太多, 重置
                    wait_low = None

        # ---- 卖出: 趋势破位 ----
        if position == 1:
            hold_days += 1
            if (hold_days >= MIN_HOLD
                    and close < _ma(closes, i) * MA_BREAK):
                reason = (f"趋势破位: 收盘{close:.3f}<MA{MA_WINDOW}×{MA_BREAK}"
                          f"+持仓{hold_days}天")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            waiting_reversal = False
            wait_low = None
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            sell_threshold = max(2, math.ceil(2 + ratio * 0.55))
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": f"{reason} [阈值{sell_threshold}]"})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": SC50_CODE, "trades": trades, "metrics": metrics,
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
                "return_pct": round(ret, 2)})
            buy_price = None

    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append({
            "buy_date": buy_date, "sell_date": None,
            "buy_price": buy_price, "sell_price": last_close,
            "return_pct": round(ret, 2)})

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
        "win_rate": round(wins / len(rounds) * 100, 1) if rounds else 0,
        "trade_count": len(trades),
    }
