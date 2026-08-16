"""沪深300 (510300) — 熊市恐慌底波段 + 牛市趋势持有(混合策略)。

核心认知:
  大盘宽基, 2021-2024 是三年熊市(前复权 5.39 -> 2.98, -45%), 2025 起转牛。
  60 日价格位置在"顶部急跌"时会误判为低位(2021-03-09 pp12.2 实为 2021-02
  顶部急跌, 直接放开旧通用策略会买在 4.56 并扛到 3.90, -14.6% 四年);
  熊市里"60日pp>=80+出货"卖出几乎不触发, 导致一路深套错过真底部。

历史教训:
  - 2021-12-21 高位平台 cp62.7 诱多: 60日pp38 看似低位, 实为 2022 崩盘前夜
    (P2 需 cp>=70, 该日被拒);
  - 2022-04-25 pp0.6+吸筹+sp95 真恐慌底 -> +11.7%; 2022-10-25 -> +10.1%;
    2024-08-28 -> +21.1%(924 行情); 2024-01-18 pp37.8+sp86+cp89 强承接 -> +6.8%;
  - 熊市波段代价: 2022-01/03/08/09 的恐慌日买入 -3.9%~-5.5%(尾随止损兜底)。

算法结构(按市场状态切换):
  状态 = bull 当 ma250 走平转上(ma250[i] > ma250[i-20])且收盘 > ma250。
  熊市(bear):
    P1 恐慌吸筹: pp<=8 + ACCUMULATE + share_prob>=65
    P2 低位强承接: pp<=40 + ACCUMULATE + share_prob>=80 + composite_prob>=70
    卖 S1 尾随止盈: 持仓>=5 天后收盘 <= 持仓最高收盘 x (1-6%)
  牛市(bull):
    B0 恐慌回踩: pp<=40 + ACCUMULATE + share_prob>=80, 跳过卖出冷却
      (案例 2025-04-07 关税暴跌 pp17.5+吸筹+sp83 -> 吃 2025 下半年行情 +27%)
    买 B1 回调: 收盘 <= ma20 且 <= 5 日最低(且距上次卖出>=15 天防打脸)
    卖 B2 趋势破位: 收盘 < ma60
  过渡: 熊市买入后市场转牛 -> 卖出规则自动切到 B2(趋势破位), 让持仓吃牛市。
"""

from __future__ import annotations

MA250_WINDOW = 250  # 牛熊状态: 长周期均线(250 日)
MA20_WINDOW = 20  # 牛市回调买: 短期均线
MA60_WINDOW = 60  # 牛市趋势破位卖
BULL_MA_LOOKBACK = 20  # 牛熊判定: ma250 与 20 日前比较(走平转上)
BEAR_P1_PP_MAX = 8  # P1 恐慌吸筹 pp 上限(案例 2022-04-25 pp0.6 / 2022-10-25 pp1.8)
BEAR_P1_SHARE_MIN = 65  # P1 净申购概率下限
BEAR_P2_PP_MAX = 40  # P2 低位强承接 pp 上限
BEAR_P2_SHARE_MIN = 80  # P2 净申购概率下限(2024-01-18 sp86)
BEAR_P2_CP_MIN = 70  # P2 综合概率下限(拒 2021-12-21 cp62.7 顶部诱多, 收 2024-01-18 cp89)
PANIC_CRASH_PCT = -5.0  # 恐慌回踩: 单日跌幅下限(案例 2025-04-07 关税暴跌 -8.2% -> +27%)
BULL_PANIC_PP_MAX = 40  # 牛市恐慌回踩 pp 上限
TRAIL_PCT = 6.0  # 熊市尾随止盈: 收盘回撤持仓最高 x6%(波段小亏封顶)
TRAIL_MIN_HOLD = 5  # 尾随止盈最短持有
SELL_COOLDOWN = 15  # 牛市卖出后冷却天数(防连续打脸)
# 全策略卖出冷却: 卖出后 N 日内不重复买入, 消除"卖出后立马买回"的连亏循环
# (案例 2022-09-22卖->09-26买/10-24卖->10-25买 间隔1-2日, 三次-5.5%连亏;
#  但真恐慌单日跌>=PANIC_SKIP_COOLDOWN_CHG 可跳过冷却 — 2025-04-07 -7.0% 恐慌回踩
#  +27.5% 大赢家, 2022-04-25 -5.3% +11.7%, 均不能被冷却误杀)
BEAR_SELL_COOLDOWN = 10
PANIC_SKIP_COOLDOWN_CHG = -3.0
# 跌势成熟门槛: 熊市接刀要求 ma60 下行(2022-08-31 下跌刚1个月 ma60斜率+1.40%
#  接刀-5.5%; 真底 2022-10-25 ma60斜-4.64% / 2024-08-28 -2.32% 全为负 —
#  与"只抓跌透的底"哲学一致, 2021 顶部急跌假低位同样被拦)
MA60_SLOPE_LOOKBACK = 20  # ma60 斜率回看窗口
BEAR_MA60_SLOPE_MIN = -2.0  # 熊市接刀门槛: ma60 20日斜率<=此值(跌势成熟, %/20日)

HS300_CODE = "510300"


def _ma(closes: list[float], window: int, idx: int) -> float | None:
    if idx < window - 1:
        return None
    return sum(closes[idx - window + 1 : idx + 1]) / window


def run_hs300_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": HS300_CODE, "trades": [], "metrics": {}, "holding": False}
    closes = [r.get("close_price") or 0.0 for r in rows]

    trades: list[dict] = []
    position = 0.0
    hold_days = 0
    high_since_buy = 0.0
    last_sell_idx = -999
    sell_mode = "trend"  # 买入时确定: "trail"(恐慌/波段底) / "trend"(健康回踩=趋势持有)
    pullback_buy = False  # 是否健康回调买入(牛市 B1)

    for i, row in enumerate(rows):
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")

        m250 = _ma(closes, MA250_WINDOW, i)
        m250_prev = _ma(closes, MA250_WINDOW, max(0, i - BULL_MA_LOOKBACK))
        m20 = _ma(closes, MA20_WINDOW, i)
        m60 = _ma(closes, MA60_WINDOW, i)
        bull = m250 is not None and m250_prev is not None and m250 > m250_prev and close > m250

        action = None
        reason = ""

        if position == 0:
            if bull:
                # 牛市: 恐慌回踩(大跌+强吸筹, 跳过冷却) / 回调买入(站上长均线+短期回踩)
                chg = row.get("change_pct") or 0
                if (
                    pp is not None
                    and pp <= BULL_PANIC_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BEAR_P2_SHARE_MIN
                    and chg <= PANIC_CRASH_PCT
                ):
                    action, reason = "BUY", "牛市恐慌回踩(大跌+强吸筹)"
                else:
                    low5 = min(closes[max(0, i - 4) : i + 1])
                    # 距ma60>=1%: 避免贴着ma60买入后小回调即破位(2025-02-28 +0.3%买后1日卖)
                    if (
                        m20 is not None
                        and m60 is not None
                        and close <= m20
                        and close <= low5
                        and (i - last_sell_idx) >= SELL_COOLDOWN
                        and close >= m60 * 1.01
                    ):
                        action, reason = "BUY", "牛市回调(站上ma250+回踩ma20)"
                        pullback_buy = True
            else:
                # 熊市: 只买恐慌底/强承接(拒绝顶部急跌假低位)
                chg = row.get("change_pct") or 0
                # 卖出冷却: 卖出后 BEAR_SELL_COOLDOWN 日内不重复买(真恐慌单日大跌除外)
                in_cooldown = (i - last_sell_idx) <= BEAR_SELL_COOLDOWN
                panic_day = chg <= PANIC_SKIP_COOLDOWN_CHG
                # 跌势成熟门槛: ma60 下行才接刀(2022-08-31 下跌刚1个月 ma60斜率+1.40%
                #  接刀-5.5%; 真底 2022-10-25 ma60斜-4.64% / 2024-08-28 -2.32% 全为负)
                m60_prev = _ma(closes, MA60_WINDOW, max(0, i - MA60_SLOPE_LOOKBACK))
                # 斜率<=-2%: 跌势成熟才接刀(09-16 斜-0.5% 接刀-8.1%, 10-25 斜-4.6% 真底+10.1%)
                trend_mature = (
                    m60 is not None and m60_prev is not None and (m60 / m60_prev - 1) * 100 <= BEAR_MA60_SLOPE_MIN
                )
                if (
                    pp is not None
                    and pp <= BEAR_P1_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BEAR_P1_SHARE_MIN
                    and (not in_cooldown or panic_day)
                    and trend_mature
                ):
                    action, reason = "BUY", "恐慌吸筹P1"
                elif (
                    pp is not None
                    and pp <= BEAR_P2_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BEAR_P2_SHARE_MIN
                    and cp is not None
                    and cp >= BEAR_P2_CP_MIN
                    and not in_cooldown
                    and trend_mature
                ):
                    action, reason = "BUY", "低位强承接P2"
                elif (
                    pp is not None
                    and pp <= BEAR_P2_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BEAR_P2_SHARE_MIN
                    and chg <= PANIC_CRASH_PCT
                    and (not in_cooldown or panic_day)
                ):
                    # 单日大跌>=5%是极端事件(2025-04-07 -7.0% 关税暴跌), 不要求跌势成熟
                    action, reason = "BUY", "恐慌回踩(单日大跌+强承接)"
        else:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            if sell_mode == "trend":
                # 趋势持有(买入时在 ma60 上方): 破位卖
                if m60 is not None and close < m60:
                    action, reason = "SELL", "趋势破位(跌破ma60)"
            else:
                # 波段/恐慌底(买入时在 ma60 下方): 尾随止盈
                if (
                    hold_days >= TRAIL_MIN_HOLD
                    and high_since_buy > 0
                    and close <= high_since_buy * (1 - TRAIL_PCT / 100)
                ):
                    action, reason = "SELL", "尾随止盈(回撤" + str(TRAIL_PCT) + "%)"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            high_since_buy = close
            # 恐慌/波段底买入始终尾随(价格天然低于均线); 健康回调才可能趋势持有
            sell_mode = "trend" if (pullback_buy and m60 is not None and close >= m60) else "trail"
            pullback_buy = False
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            last_sell_idx = i
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = _calc_metrics(trades, closes[-1] if closes else 0.0, position)
    return {"code": HS300_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}


def _calc_metrics(trades: list[dict], last_close: float, position: float) -> dict:
    rounds = []
    buy_price = None
    buy_date = None
    for t in trades:
        if t["action"] == "BUY":
            buy_price = t["price"]
            buy_date = t["date"]
        elif t["action"] == "SELL" and buy_price is not None:
            ret = (t["price"] - buy_price) / buy_price * 100
            rounds.append(
                {
                    "buy_date": buy_date,
                    "sell_date": t["date"],
                    "buy_price": buy_price,
                    "sell_price": t["price"],
                    "return_pct": round(ret, 2),
                }
            )
            buy_price = None

    if position > 0 and buy_price is not None:
        ret = (last_close - buy_price) / buy_price * 100
        rounds.append(
            {
                "buy_date": buy_date,
                "sell_date": None,
                "buy_price": buy_price,
                "sell_price": last_close,
                "return_pct": round(ret, 2),
            }
        )

    total_ret = 1.0
    wins = 0
    for r in rounds:
        total_ret *= 1 + r["return_pct"] / 100
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
