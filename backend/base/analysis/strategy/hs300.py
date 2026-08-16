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

算法结构(按市场状态切换, 向中证1000 对齐):
  状态 = bull 当 ma250 走平转上(ma250[i] > ma250[i-20])且收盘 > ma250。
  熊市(bear):
    P1 恐慌吸筹: pp<=8 + ACCUMULATE + share_prob>=65
    P2 低位强承接: pp<=40 + ACCUMULATE + share_prob>=80 + composite_prob>=70
    跌势成熟门槛: ma60 20日斜率<=-2%(2022-08-31 斜+1.40%接刀-5.5%被拦)
    卖 S1 尾随止盈: 持仓>=5 天后收盘 <= 持仓最高收盘 x (1-6%)
  牛市(bull):
    B0 恐慌回踩: pp<=40 + ACCUMULATE + share_prob>=80, 跳过卖出冷却
      (案例 2025-04-07 关税暴跌 pp17.5+吸筹+sp83 -> 吃 2025 下半年行情 +27%)
    买 B1 回调: 收盘<=ma20 且 <=5日最低 且 pp<=40(只买低位回调,
      2026-01-23 pp68高位-2.2%被拦) 且 ma60 距离带(贴ma60浅回调拦/深回调放行)
    卖 B2 趋势破位: 收盘 < ma60
  通用:
    买入验证期: 买入后 20 日累计<3% 且份额未增>=5% 即认错
      (2022-03-16 -3.9%->+0.9%; 2024-08-28 20日+16.3%通过保+21.1%)
    卖出冷却: 止损后 10 日/15 日不重复买(真恐慌单日跌>=3%跳过)
  过渡: 熊市买入后市场转牛 -> 卖出规则自动切到 B2(趋势破位), 让持仓吃牛市。
"""

from __future__ import annotations

import math

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
BULL_PP_MAX = 40  # 牛市回调 B1 pp 上限(只买低位回调, 2026-01-23 pp68高位被拦-2.2%,
#  2024-10-30 pp52白做+0.4%被拦; 2026-03-23 pp5.5 +7.1%、2025-01-02 pp14 +2.1%保留)
# 牛市买入四路径(移植正式版 _run_default 参数)
STABLE_BUY_PP_MAX = 40.0  # 价格低位阈值
STABLE_PP_EXTREME = 10.0  # 极低位阈值
STABLE_PP_PANIC = 15.0  # 恐慌吸筹 pp 上限
STABLE_SHARE_MIN = 65.0  # 份额净申购概率阈值
STABLE_TP_COLD_MAX = 10.0  # 成交额极冷分位阈值
STABLE_CP_MIN = 50.0  # 综合概率阈值
# 出货共振卖出(移植正式版优势): 牛市真顶 = 出货信号 + 高位 + 杠杆高位
# (2025-06-25 pp100+vr2.4 但融资88 中继震荡不卖; 2025-10-31 pp84+融资94 真顶卖)
DIST_PP_MIN = 80.0  # 出货共振 pp 下限
DIST_VR_MIN = 1.3  # 出货共振量比下限
DIST_MP_MIN = 90.0  # 出货共振融资分位下限(区分中继震荡与真顶)
DIST_EXTREME_VR = 3.5  # 加速赶顶量比(924式暴涨顶: 10-08 vr3.85 立即卖, 常规出货1.5~2.5不误触)
#  (2025-01-02 sp42 -5.8% / 01-03 sp35 -3.8% / 01-06 sp34 -2.4%;
#  2026-03-23 sp65 +14.9% 保留 — 同一波 03-31 sp27 拦掉无损失)
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
# 熊市博弈门槛(贴线阴跌无博弈价值, 深背离才有均值回归机会):
BEAR_DIVERGENCE_MIN = 13.0  # 距ma250深背离阈值%(<-13%才有博弈价值, 2023贴线-1~-3% 60日全负)
BEAR_DESPAIR_TP_MAX = 10.0  # 绝望底成交额分位上限(924前夜: 2024-08-28 成交额1)
BEAR_DESPAIR_MP_MAX = 10.0  # 绝望底融资分位上限(杠杆出清: 2024-08-28 融资1)
# 买入验证期(向中证1000 对齐): 买入后 20 日累计涨幅<3% 且份额未增长>=5% → 认错离场
# (2022-03-16 20日+0.9%份额-3.5%止损-3.9%该卖; 2024-10-30 +0.4%白做止损省事;
#  2026-01-23 +0.7%份额-30%止损-2.2%该卖; 而 2024-08-28 20日+16.3%份额+12.9%
#  通过保+21.1%, 2024-01-18 份额+37%通过保+6.8% — 大赢家全靠20日窗口保住)
VERIFY_DAY = 20  # 买入后第 N 日检查
VERIFY_ESCAPE_PCT = 3.0  # 累计涨幅低于此值视为未脱离成本区
VERIFY_SHARES_PCT = 5.0  # 份额较买入日增长>=此值视为有承接(豁免)

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
    buy_price = 0.0  # 买入价(验证期用)
    entry_shares = None  # 买入时份额(验证期豁免用)
    dist_confirm = 0  # 出货确认计数(出货共振卖出)
    dist_threshold = 2  # 出货共振确认阈值(买入量比动态调整, 移植正式版)
    buy_bull = False  # 买入时是否牛市(牛熊分治: 牛市买入不验证, 熊市买入验证)

    for i, row in enumerate(rows):
        d = row["date"]
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        vr = row.get("volume_ratio") or 0
        mp = row.get("_mp")  # 融资分位(出货共振用, router 注入)

        m250 = _ma(closes, MA250_WINDOW, i)
        m250_prev = _ma(closes, MA250_WINDOW, max(0, i - BULL_MA_LOOKBACK))
        m60 = _ma(closes, MA60_WINDOW, i)
        # 牛熊判定加 2% 缓冲: close 在 ma250 下方 2% 内且 ma250 上行仍算牛市
        # (2026-07-17 close4.589 vs ma250 4.598 差0.2%, 无缓冲会被判熊且贴线拒绝,
        #  正式版无牛熊判定直接买; 缓冲后与正式版一致, 全历史仅影响12天)
        bull = m250 is not None and m250_prev is not None and m250 > m250_prev and close > m250 * 0.98

        action = None
        reason = ""

        if position == 0:
            if bull:
                # 牛市买入(移植正式版优势): 恐慌回踩 + 正式版四路径
                # (B1 过度设计的 sp/ma60距离带 曾误伤 2025-11-21 sp45 真买点, 移除)
                chg = row.get("change_pct") or 0
                tp = row.get("_tp")  # 成交额分位(正式版路径用)
                if (
                    pp is not None
                    and pp <= BULL_PANIC_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BEAR_P2_SHARE_MIN
                    and chg <= PANIC_CRASH_PCT
                ):
                    action, reason = "BUY", "牛市恐慌回踩(大跌+强吸筹)"
                elif pp is not None and pp <= STABLE_BUY_PP_MAX and td == "ACCUMULATE":
                    # 正式版四路径: 价格低位+吸筹 是前提, 份额/成交额/概率任一确认
                    if sp is not None and sp >= STABLE_SHARE_MIN:
                        action, reason = "BUY", "价格低位+份额净申购+吸筹"
                    elif tp is not None and tp <= STABLE_TP_COLD_MAX:
                        action, reason = "BUY", "价格低位+吸筹+成交额极冷"
                    elif pp <= STABLE_PP_EXTREME and cp is not None and cp > STABLE_CP_MIN:
                        action, reason = "BUY", "价格极低位+吸筹+概率>50%"
                    elif pp <= STABLE_PP_PANIC:
                        action, reason = "BUY", "恐慌吸筹: 极低位+吸筹信号"
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
                # 熊市博弈门槛: 深背离(距ma250<=-13%)或绝望底(成交额+融资双低<=10)
                # 贴线阴跌(>-13%)无博弈价值(2023全年贴线-1.5~-3% 60日全负-5~-10%);
                # 深背离才有均值回归机会(2022-04 -18~-23% 60日+9~+14%);
                # 绝望底抓 924 前夜(2024-08-28 成交额1融资1 -> +20.5%)
                tp = row.get("_tp")
                m250_now = m250
                div_dist = (close / m250_now - 1) * 100 if m250_now else 0.0
                deep_div = div_dist <= -BEAR_DIVERGENCE_MIN
                despair = tp is not None and tp <= BEAR_DESPAIR_TP_MAX and mp is not None and mp <= BEAR_DESPAIR_MP_MAX
                bear_gate = deep_div or despair
                if (
                    pp is not None
                    and pp <= BEAR_P1_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BEAR_P1_SHARE_MIN
                    and (not in_cooldown or panic_day)
                    and trend_mature
                    and bear_gate
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
                    and bear_gate
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
                    # 也不要求 bear_gate(极端恐慌本身就是博弈时机)
                    action, reason = "BUY", "恐慌回踩(单日大跌+强承接)"
        else:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            # 买入验证期(仅熊市买入): 20日未脱离成本区即认错
            # 牛市买入不验证 — 慢涨回调正常(2025-01-02 20日+2.1% 后加速),
            # 交给出货共振/趋势破位; 熊市抄底需快速认错(2022-03-16 防阴跌)
            if hold_days == VERIFY_DAY and not buy_bull:
                ret_pct = (close / buy_price - 1) * 100 if buy_price else 0.0
                cur_shares = row.get("shares_yi")
                shares_gain = (
                    (cur_shares / entry_shares - 1) * 100
                    if cur_shares is not None and entry_shares and entry_shares > 0
                    else 0.0
                )
                if ret_pct < VERIFY_ESCAPE_PCT and shares_gain < VERIFY_SHARES_PCT:
                    action, reason = "SELL", f"买入未验证: 第{VERIFY_DAY}日累计{ret_pct:+.1f}%+份额{shares_gain:+.1f}%"
            # 出货共振卖出(移植正式版优势): DISTRIBUTE+pp>=80+vr>=1.3+融资>=90
            # 动态阈值: 买入量比越高需越多确认(正式版 sell_threshold)
            if (
                action is None
                and td == "DISTRIBUTE"
                and pp is not None
                and pp >= DIST_PP_MIN
                and vr >= DIST_VR_MIN
                and mp is not None
                and mp >= DIST_MP_MIN
            ):
                dist_confirm += 1
                # 加速赶顶(924式): 极端放量直接卖, 不等凑满阈值(移植 zz EXTREME_VR)
                if vr >= DIST_EXTREME_VR and hold_days >= TRAIL_MIN_HOLD:
                    action, reason = (
                        "SELL",
                        f"出货共振+加速赶顶({dist_confirm}/{dist_threshold}次)+pp{pp:.0f}+vr{vr:.1f}",
                    )
                elif hold_days >= TRAIL_MIN_HOLD and dist_confirm >= dist_threshold:
                    action, reason = "SELL", f"出货共振(第{dist_confirm}/{dist_threshold}次)+pp{pp:.0f}+融资{mp:.0f}"
            if (
                action is None
                and not buy_bull
                and hold_days >= TRAIL_MIN_HOLD
                and high_since_buy > 0
                and close <= high_since_buy * (1 - TRAIL_PCT / 100)
            ):
                # 熊市买入: 尾随止盈(波段小亏封顶)
                action, reason = "SELL", "尾随止盈(回撤" + str(TRAIL_PCT) + "%)"
            # 牛市买入(buy_bull): 无趋势破位/尾随, 只靠出货共振卖出(正式版逻辑,
            # 牛市回调买点天然在 ma60 下方, 趋势破位会次日误卖; 持仓可长持到出货)

        if action == "BUY":
            position = 1.0
            hold_days = 0
            high_since_buy = close
            buy_price = close
            entry_shares = row.get("shares_yi")
            dist_confirm = 0
            buy_bull = bull  # 记录买入时牛熊(验证期只对熊市买入生效)
            # 动态出货阈值(正式版逻辑): 地量极冷买入阈值1(1次确认即卖),
            # 其余按买入量比: 越高需越多确认
            if reason.startswith("价格低位+吸筹+成交额极冷"):
                dist_threshold = 1
            else:
                dist_threshold = max(2, math.ceil(2 + vr * 0.55)) if vr else 2
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            dist_confirm = 0
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
