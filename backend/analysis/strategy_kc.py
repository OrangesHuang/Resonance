"""科创综指 (589680) V1 量价记忆策略。

基于 510300 V1 同构设计，针对科创综指特征适配:
  - ACCUMULATE 极稀缺(1.2%) → 加入"类吸筹"判定
  - 出货前置模式清晰 → DISTRIBUTE集群后1-4周急跌
  - 份额波动大 → 用原始sd%辅助判断,不完全依赖sp
  - 量价记忆: 买入时量比 → 卖出所需确认次数
"""

import math

KC_CODE = "589680"

# 买入参数
BUY_PP_MAX = 40           # 买入位置上限
BUY_VR_MIN = 1.3           # 类吸筹量比下限 (科创量比分布偏右,1.3≈80分位)
PANIC_DROP = -3.0          # 恐慌跌幅
PANIC_PP_MAX = 35          # 恐慌位置上限

# 卖出参数 (科创波动大, 出货信号需要更强位置确认)
SELL_PP_MIN = 80           # 与510300一致
SELL_VR_MIN = 1.4          # 出货量比确认

MIN_HOLD = 5               # 最短持仓 (科创波动大, 可缩短)
COOLDOWN = 3               # 冷却期 (科创节奏快)
VOL_LOOKBACK = 20
TRADE_START = "2025-04-01"


def _is_quasi_accum(row: dict) -> bool:
    """类吸筹判定: 捕捉实质吸筹但td!=ACCUMULATE的日子。

    科创综指 ACCUMULATE 仅1.2%, 很多低位放量日被td=NEUTRAL错过。
    类吸筹 = (低位 + 放量 + 资金流入) OR (恐慌暴跌)
    """
    pp = row.get("price_position")
    vr = row.get("volume_ratio") or 0
    sp = row.get("share_prob")
    sd = row.get("shares_delta_pct")
    chg = row.get("change_pct") or 0
    td = row.get("trade_direction")

    if td == "ACCUMULATE":
        return True  # 原版ACCUMULATE直接通过

    if pp is None:
        return False

    # 低位+放量+资金流入(份额增加)
    if pp <= 30 and vr >= BUY_VR_MIN:
        if sp is not None and sp >= 60:
            return True
        if sd is not None and sd >= 3:
            return True

    # 恐慌暴跌日: 跌超3%+放量+非高位
    # 极端暴跌(-5%+)放宽量比要求: 暴跌本身就是信号, 不需要量比确认
    # pp≤70: 不要求在极端低位, 连续下跌后的暴跌也应捕获
    if chg <= -5 and vr >= 0.8 and pp is not None and pp <= 70:
        return True
    if chg <= PANIC_DROP and vr >= 1.5 and pp <= PANIC_PP_MAX:
        return True

    return False


def run_kc_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": KC_CODE, "trades": [], "metrics": {}, "holding": False}

    closes = [r.get("close_price") or 0.0 for r in rows]

    trades = []
    position = 0.0
    hold_days = 0
    cooldown = COOLDOWN
    sell_threshold = 1
    dist_count = 0

    for i in range(n):
        row = rows[i]
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        sd = row.get("shares_delta_pct")

        if d < TRADE_START:
            continue

        cooldown += 1
        action = None
        reason = ""

        # ---- 买入 (三路径) ----
        if position == 0 and cooldown >= COOLDOWN:
            qa = _is_quasi_accum(row)
            pp_low = pp is not None and pp <= BUY_PP_MAX
            pp_extreme = pp is not None and pp <= 10
            sp_ok = sp is not None and sp >= 60
            cp_ok = cp is not None and cp >= 60

            # 路径1: 低位吸筹 (需要份额确认)
            if qa and pp_low and sp_ok:
                action = "BUY"
                reason = f"低位吸筹: pp{pp:.0f}+sp{sp:.0f}"

            # 路径2: 恐慌接筹 (不要求份额, ETF初期不可靠)
            elif qa and pp is not None and pp <= PANIC_PP_MAX and vr >= 1.5:
                action = "BUY"
                reason = f"恐慌接筹: 跌{chg:.1f}%+vr{vr:.1f}+pp{pp:.0f}"

            # 路径3: 极端低位
            elif qa and pp_extreme and cp_ok:
                action = "BUY"
                reason = f"极端低位: pp{pp:.0f}+cp{cp:.0f}%"

        # ---- 卖出 ----
        if position == 1:
            hold_days += 1
            is_dist = td == "DISTRIBUTE"
            pp_high = pp is not None and pp >= SELL_PP_MIN
            vr_high = vr >= SELL_VR_MIN

            if is_dist and pp_high and vr_high:
                dist_count += 1

            if hold_days >= MIN_HOLD and is_dist and dist_count >= sell_threshold:
                reason = (f"出货确认({dist_count}/{sell_threshold})"
                          f"+pp{pp:.0f}+vr{vr:.1f}")
                action = "SELL"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            dist_count = 0
            # 量价记忆: 买入量比 → 卖出阈值
            vol = row.get("volume") or 0
            prev_vols = [rows[j].get("volume") or 0
                         for j in range(max(0, i - VOL_LOOKBACK), i)]
            avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 1
            ratio = vol / avg_vol if avg_vol > 0 else 1.0
            # KC DISTRIBUTE密度低于510300, 降低卖出门槛基数(2→1)
            if vr < 0.8:
                sell_threshold = 1
            else:
                sell_threshold = max(2, math.ceil(1 + ratio * 0.55))
            trades.append({"date": d, "action": "BUY", "price": close,
                           "reason": f"{reason} [阈值{sell_threshold}]"})
        elif action == "SELL":
            position = 0.0
            cooldown = 0
            trades.append({"date": d, "action": "SELL", "price": close,
                           "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0, position)
    return {"code": KC_CODE, "trades": trades, "metrics": metrics,
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
