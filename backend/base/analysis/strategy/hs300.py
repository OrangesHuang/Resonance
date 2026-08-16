"""沪深300 (510300) — 熊市绝望底波段 + 牛市趋势持有(混合策略)。[Beta]

核心认知: 大盘宽基, 2021-2024 三年熊市(-45%), 2025 起转牛。熊市可交易波段
= 绝望底 -> 反弹到位(买卖点先行): A 2022-04-26 3.44->07-04 4.18 +21.5% /
B 2022-10-31 3.22->01-30 3.93 +21.9% / C 2024-02-02 2.98->05-20 3.47 +16.7%
/ D 2024-08-28 3.15->10-08 4.20 +33.5%; 2020 快熊 V 底: 02-03 疫情恐慌底
3.17->3.46 +9.1% / 03-23 全球股灾底 3.04->7-01 3.78 +24.6%。
假底无法靠单日信号区分(2022-09-26 与真底指纹一致后仍跌 -9.4%), 架构 = 放宽
买点覆盖所有绝望底 + 硬止损快速认错 + 极端底豁免冷却再上车。
历史教训: 2021-03-09 顶部假低位(与 2025-01-02 牛市回调底同指纹, 买入即接顶)
-> 2021 年整年跳过; 2022-09-26 接刀假底靠 -5% 硬止损 + 10-31 再买弥补;
2020-03-23 贴线买 4-07 触线卖飞 +8.4% vs +30%+ -> 贴线买禁触线;
微微红+2%卖(已弃)把 A 波段 +21.5% 做成 +2.3%, 熊市反弹目标位是 ma250。

算法(按市场状态切换):
  状态 bull = ma250 上行(20日比较)且 close > ma250*0.98(2%缓冲)。
  熊市买: P1 恐慌底 单日跌>=7%+pp<=20(不分牛熊); P2 绝望底 pp<=15+sp>=75
  +chg<=1+ma60 20日斜率<=-2% + 底部门槛(深背离 div<=-15% 且 mp<=5, 或
  双绝望 tp<=10 且 mp<=10); P3 强承接冰点底 pp<=8+sp>=90+div>=-10(急跌贴线V底)。
  熊市卖: 硬止损-5% -> 触线止盈(|div|<=3 且温和, 贴线买/暴力穿越除外)
  -> 尾随6%; 深背离极端底豁免卖出冷却。
  牛市(bull): 恐慌回踩 + 移植正式版四路径买入, 出货共振卖出(与生产一致)。
  过渡: 熊市买入后转牛 -> 出货共振+尾随管, 让持仓吃牛市。
"""

from __future__ import annotations

import math

from base.analysis.strategy.hs300_metrics import build_danger_zone, calc_metrics

TRADE_START = "2019-01-01"  # 策略交易起点: 2019 起(2019-2020 恐慌底/强承接底 + 2022 起绝望底)
TRADE_SKIP_START = "2021-01-01"  # 2021 年整年跳过: 2021-03-09 顶部假低位(pp12.2+sp90.8)与
TRADE_SKIP_END = "2022-01-01"  # 与 2025-01-02 牛市回调底同指纹, 大顶后急跌无法事前区分, 2021 只画线不交易
DANGER_ZONE_START = "2021-01-01"  # 危险区标注起点: 2021 年大顶回落段标危险;
# 2020 年是牛市(策略未启用)不标危险
MA250_WINDOW = 250  # 牛熊状态: 长周期均线(250 日)
MA20_WINDOW = 20  # 牛市回调买: 短期均线
MA60_WINDOW = 60  # 牛市趋势破位卖
BULL_MA_LOOKBACK = 20  # 牛熊判定: ma250 与 20 日前比较(走平转上)
BULL_BUFFER_PCT = 2.0  # 牛熊边界缓冲: close 在 ma250 下方 2% 内仍算牛
PANIC_CRASH_PCT = -5.0  # 恐慌回踩: 单日跌幅下限(案例 2025-04-07 关税暴跌 -8.2% -> +27%)
BULL_PANIC_PP_MAX = 40  # 牛市恐慌回踩 pp 上限
BULL_PANIC_SHARE_MIN = 80.0  # 牛市恐慌回踩份额承接下限(2025-04-07 sp83)
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
TRAIL_PCT = 6.0  # 尾随止盈: 收盘回撤持仓最高 x6%(熊市波段回撤兜底)
TRAIL_MIN_HOLD = 5  # 尾随止盈最短持有
# 熊市绝望底买入(买卖点先行拟合: 4 真底指纹)
BEAR_BUY_PP_MAX = 15.0  # 买入 pp 上限: 60日价格必须真触底(用户: 滚动60天没触底才是接飞刀关键;
# 真底 pp 0.9/1.8/14.8/4.6, 拦 2022-04-13 pp21.5 假底; 2024-02-02 C底 pp25.7 但 01-22 pp14.8 已买)
BEAR_BUY_SHARE_MIN = 75.0  # 份额强承接下限(4真底 75.8~95; 拦 03-15 sp47/11-28 sp44/07-08 sp70)
BEAR_BUY_CHG_MAX = 1.0  # 买入日涨幅上限(绝望底当日不追大涨: 拦 2022-03-16 +4.77%政策底追高)
BEAR_BOTTOM_DIV_MIN = 15.0  # 深背离阈值%(A-23/B-20/C-15.6; 假底09-26 仅-13.7 被拦)
BEAR_BOTTOM_MP_MAX = 5.0  # 深背离路径融资分位上限(杠杆出清: 4真底 mp<=3)
BEAR_DESPAIR_TP_MAX = 10.0  # 绝望底成交额分位上限(924前夜: 2024-08-28 成交额1)
BEAR_DESPAIR_MP_MAX = 10.0  # 绝望底融资分位上限
PANIC_CHG_MIN = 7.0  # 恐慌底单日跌幅下限(2020-02-03 疫情底 -9.6%)
PANIC_PP_MAX = 20.0  # 恐慌底 pp 上限(2024-10-09 -8.4% pp64.8 被拦)
STRONG_PP_MAX = 8.0  # 强承接冰点底 pp 上限(2020-03-23 股灾底 pp4.7)
STRONG_SHARE_MIN = 90.0  # 强承接冰点底份额概率下限(2020-03-23 sp95)
STRONG_DIV_MIN = -10.0  # 强承接底距线门槛: 急跌贴线V底(2020-03-23 -9.8%); 2022-09 阴跌假底被拦
SHALLOW_DIV_MIN = -11.0  # 贴线买禁触线(2020-03-23 买后 4-07 触线卖飞 +8.4% vs +30%+), 靠尾随+出货
# 熊市卖出(触线止盈 + 硬止损)
BEAR_STOP_LOSS_PCT = 5.0  # 接刀失败硬止损: 收盘较买入 <= -5% 卖(2022-09-26 轮)
# 深背离路径快速验证(用户: 宏观极端承接后理应快速反弹, 一段时间内没反弹=还没到底):
# 买入后 QUICK_VERIFY_DAY 日内从未收盘 +2% 且仍低于买价 -> 离场。深背离真底
# (04-26/10-31/01-22) 3日内即 +2% 不误杀; 双绝望冰点底(08-28)可横盘17天等924,
# 不适用时间止损(维持 -5% 硬止损)
BEAR_QUICK_VERIFY_DAY = 10  # 深背离买入快速验证窗口
BEAR_QUICK_VERIFY_PCT = 2.0  # 窗口内需出现的反弹幅度
BEAR_TOUCH_DIV = 3.0  # 反弹触线: |div|<=3% 即 ma250 附近(熊市反弹目标位), 当日温和即卖
BEAR_VIOLENT_CHG = 4.0  # 暴力穿越例外: 触线日单日涨幅下限(924: 09-24 +4.7%)
BEAR_VIOLENT_VR = 2.0  # 暴力穿越例外: 触线日量比下限(924: 09-24 vr2.8)
BEAR_TOUCH_HOLD_SHARE_MIN = 50.0  # 触线暂缓: 份额仍有承接(sp>=50, C波段 03-12 sp66)且缩量 -> 持有等下一波
BEAR_TOUCH_HOLD_VR_MAX = 1.0  # 触线暂缓: 量比<1(缩量无出货压力; A顶 07-04 sp13 直接卖)
SELL_COOLDOWN = 15  # 牛市卖出后冷却天数(防连续打脸)
# 全策略卖出冷却: 卖出后 N 日内不重复买入, 消除"卖出后立马买回"的连亏循环
# (案例 2022-09-22卖->09-26买 间隔短连亏; 真恐慌单日跌>=PANIC_SKIP_COOLDOWN_CHG
#  可跳过冷却 — 2025-04-07 -7.0% 恐慌回踩, 2022-04-25 -5.3% +11.7% 不能被误杀)
BEAR_SELL_COOLDOWN = 10
PANIC_SKIP_COOLDOWN_CHG = -3.0
# 跌势成熟门槛: 熊市接刀要求 ma60 下行(2022-08-31 下跌刚1个月 ma60斜率+1.40% 接刀-5.5%;
# 真底 2022-10-31 ma60斜-4.8% / 2024-08-28 -2.3% 全为负 — 2021 顶部急跌假低位同样被拦)
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
        return {"code": HS300_CODE, "trades": [], "metrics": {}, "holding": False, "danger_zone": None}
    closes = [r.get("close_price") or 0.0 for r in rows]

    trades: list[dict] = []
    position = 0.0
    hold_days = 0
    high_since_buy = 0.0
    last_sell_idx = -999
    buy_price = 0.0  # 买入价(止损/触线用)
    dist_confirm = 0  # 出货确认计数(出货共振卖出)
    dist_threshold = 2  # 出货共振确认阈值(买入量比动态调整, 移植正式版)
    buy_bull = False  # 买入时是否牛市(牛熊分治: 熊市才走止损/触线)
    violent_start = False  # 暴力穿越例外: 触线日放量暴涨, 转持有模式
    buy_path_deep = False  # 买入走深背离路径(快速验证适用; 双绝望冰点底不适用)
    buy_shallow = False  # 贴线买(div>=-12): 触线止盈禁用, 靠尾随+出货共振
    quick_verified = False  # 快速验证: 窗口内出现过 +2% 收盘
    first_buy_idx: int | None = None  # 首个买点位置(危险区标注用)

    for i, row in enumerate(rows):
        d = row["date"]
        if d < TRADE_START:
            continue
        if TRADE_SKIP_START <= d < TRADE_SKIP_END:
            continue  # 2021 年跳过(顶部假低位保护)
        close = closes[i]
        pp = row.get("price_position")
        td = row.get("trade_direction")
        sp = row.get("share_prob")
        cp = row.get("composite_prob")
        vr = row.get("volume_ratio") or 0
        mp = row.get("_mp")  # 融资分位(router 注入)
        chg = row.get("change_pct") or 0

        m250 = _ma(closes, MA250_WINDOW, i)
        m250_prev = _ma(closes, MA250_WINDOW, max(0, i - BULL_MA_LOOKBACK))
        m60 = _ma(closes, MA60_WINDOW, i)
        div_dist = (close / m250 - 1) * 100 if m250 else 0.0  # 距 ma250 偏离(%)
        # 牛熊判定加 2% 缓冲: close 在 ma250 下方 2% 内仍算牛(2026-07-17 边界案例)
        bull = (
            m250 is not None
            and m250_prev is not None
            and m250 > m250_prev
            and close > m250 * (1 - BULL_BUFFER_PCT / 100)
        )

        action = None
        reason = ""

        if position == 0:
            # 恐慌底(不分牛熊): 2020-02-03 疫情底买入->V反弹; 2025-04-07 与牛市回踩同日
            if chg <= -PANIC_CHG_MIN and pp is not None and pp <= PANIC_PP_MAX:
                action, reason = "BUY", f"恐慌底(单日跌{chg:.1f}%+pp{pp:.0f})"
            elif bull:
                # 牛市买入(移植正式版优势): 恐慌回踩 + 正式版四路径
                tp = row.get("_tp")  # 成交额分位(正式版路径用)
                if (
                    pp is not None
                    and pp <= BULL_PANIC_PP_MAX
                    and td == "ACCUMULATE"
                    and sp is not None
                    and sp >= BULL_PANIC_SHARE_MIN
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
                # 熊市绝望底: 只买跌透+杠杆出清+强承接的底; 卖出冷却(真恐慌大跌除外),
                # 深背离极端底豁免冷却(04-25止损->04-26买 / 10-24止损->10-31买无缝衔接)
                in_cooldown = (i - last_sell_idx) <= BEAR_SELL_COOLDOWN
                panic_day = chg <= PANIC_SKIP_COOLDOWN_CHG
                m60_prev = _ma(closes, MA60_WINDOW, max(0, i - MA60_SLOPE_LOOKBACK))
                trend_mature = (
                    m60 is not None and m60_prev is not None and (m60 / m60_prev - 1) * 100 <= BEAR_MA60_SLOPE_MIN
                )
                tp = row.get("_tp")
                deep_extreme = div_dist <= -BEAR_BOTTOM_DIV_MIN and mp is not None and mp <= BEAR_BOTTOM_MP_MAX
                despair = tp is not None and tp <= BEAR_DESPAIR_TP_MAX and mp is not None and mp <= BEAR_DESPAIR_MP_MAX
                strong_hold = (
                    pp is not None
                    and pp <= STRONG_PP_MAX
                    and sp is not None
                    and sp >= STRONG_SHARE_MIN
                    and div_dist >= STRONG_DIV_MIN
                )
                if (
                    pp is not None
                    and pp <= BEAR_BUY_PP_MAX
                    and sp is not None
                    and sp >= BEAR_BUY_SHARE_MIN
                    and chg <= BEAR_BUY_CHG_MAX
                    and (trend_mature and (deep_extreme or despair) or strong_hold)
                    and (not in_cooldown or panic_day or deep_extreme)
                ):
                    action, reason = "BUY", "熊市绝望底(强承接+杠杆出清)"
                    buy_path_deep = deep_extreme
        else:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            # 熊市持仓卖出(左侧): 硬止损 -> 触线止盈 -> 尾随兜底
            if not buy_bull:
                ret_pct = (close / buy_price - 1) * 100 if buy_price else 0.0
                if ret_pct <= -BEAR_STOP_LOSS_PCT:
                    action, reason = "SELL", f"接刀失败止损(收盘{ret_pct:.1f}%)"
                elif buy_path_deep and hold_days <= BEAR_QUICK_VERIFY_DAY:
                    # 深背离快速验证(用户: 极端承接后理应快速反弹, 没反弹=还没到底)
                    if close >= buy_price * (1 + BEAR_QUICK_VERIFY_PCT / 100):
                        quick_verified = True
                    elif hold_days == BEAR_QUICK_VERIFY_DAY and not quick_verified and close < buy_price:
                        action, reason = "SELL", f"接刀未验证({BEAR_QUICK_VERIFY_DAY}日未反弹)"
                elif not violent_start and not buy_shallow and abs(div_dist) <= BEAR_TOUCH_DIV:
                    # 反弹触线 = 到 ma250 目标位当日温和即卖; 暴力穿越(924式)转持有;
                    # 缩量+份额承接暂缓(C波段 03-12 sp66 暂缓 -> 05-20 卖 3.47)
                    if chg >= BEAR_VIOLENT_CHG and vr >= BEAR_VIOLENT_VR:
                        violent_start = True
                    elif sp is not None and sp >= BEAR_TOUCH_HOLD_SHARE_MIN and vr < BEAR_TOUCH_HOLD_VR_MAX:
                        pass
                    else:
                        action, reason = "SELL", f"反弹触线止盈(距ma250 {div_dist:+.1f}%)"
            # 出货共振卖出(移植正式版): DISTRIBUTE+pp>=80+vr>=1.3+融资>=90, 动态阈值
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
                # 熊市持仓: 尾随止盈(盈利回撤兜底)
                action, reason = "SELL", f"尾随止盈(回撤{TRAIL_PCT}%)"
            # 牛市买入(buy_bull): 无止损/触线/尾随, 只靠出货共振卖出(持仓长持到出货)

        if action == "BUY":
            position = 1.0
            hold_days = 0
            high_since_buy = close
            buy_price = close
            dist_confirm = 0
            buy_bull = bull  # 记录买入时牛熊(止损/触线只对熊市买入生效)
            buy_shallow = div_dist >= SHALLOW_DIV_MIN  # 贴线买: 触线止盈无意义
            violent_start = False  # 新持仓重置暴力穿越标记
            quick_verified = False  # 新持仓重置快速验证标记(buy_path_deep 在触发时已记录)
            # 动态出货阈值: 地量极冷买入 1 次确认即卖, 其余按买入量比越高越多确认
            if reason.startswith("价格低位+吸筹+成交额极冷"):
                dist_threshold = 1
            else:
                dist_threshold = max(2, math.ceil(2 + vr * 0.55)) if vr else 2
            if first_buy_idx is None and d >= TRADE_SKIP_END:
                first_buy_idx = i
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            dist_confirm = 0
            last_sell_idx = i
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = calc_metrics(trades, closes[-1] if closes else 0.0, position)
    return {
        "code": HS300_CODE,
        "trades": trades,
        "metrics": metrics,
        "holding": position > 0,
        "danger_zone": build_danger_zone(rows, first_buy_idx, DANGER_ZONE_START),
    }
