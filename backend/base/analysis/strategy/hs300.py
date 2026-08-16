"""沪深300 (510300) — 熊市绝望底波段 + 牛市趋势持有(混合策略)。

核心认知:
  大盘宽基, 2021-2024 三年熊市(前复权 5.39 -> 2.98, -45%), 2025 起转牛。
  熊市可交易波段只有"绝望底 -> 反弹到位"四种(买卖点先行, 后拟合规则):
    A 2022-04-26 3.44 -> 07-04 4.18 +21.5%(上海解封行情)
    B 2022-10-31 3.22 -> 2023-01-30 3.93 +21.9%(防疫放开行情)
    C 2024-02-02 2.98 -> 05-20 3.47 +16.7%(国家队救市反弹)
    D 2024-08-28 3.15 -> 10-08 4.20 +33.5%(924 反转)
  假底无法靠单日信号区分(2022-09-26 双绝望底与真底指纹几乎一致, 后还有
  最后一跌 -9.4%), 故架构 = 放宽买点覆盖所有绝望底 + 硬止损快速认错 +
  极端底豁免卖出冷却再上车(左侧买卖)。

历史教训:
  - 2021-12-21 高位平台 cp62.7 诱多(60日pp38 假低位, 2022 崩盘前夜);
  - 2022-09-26 接刀假底: 信号与真底几乎一致, 靠 -5% 硬止损 + 10-31 再买弥补;
  - 微微红+2%卖(已弃): 把 A 波段 +21.5% 做成 +2.3%, 熊市反弹目标位是 ma250;
  - 4 个真底共同指纹: 份额承接 sp>=75 + 融资分位 mp<=3(杠杆出清) + 深背离或双绝望;
  - 3 个反弹顶共同指纹: 反弹触线(距 ma250 ±3%)且当日温和(涨幅<4%/量比<2)。

算法结构(按市场状态切换):
  状态 = bull 当 ma250 走平转上(ma250[i] > ma250[i-20])且收盘 > ma250*0.98。
  熊市(bear):
    买 B 绝望底: pp<=40 + sp>=75 + ma60 20日斜率<=-2%(跌势成熟) + 底部门槛
      (深背离 div<=-15% 且 mp<=5, 或 双绝望 tp<=10 且 mp<=10);
      深背离极端底豁免卖出冷却(04-26/10-31 止损后次日级再上车)
    卖 S1 硬止损: 收盘较买入 <= -5%(接刀失败快速认错, 2022-09-26 轮)
    卖 S2 触线止盈: |div|<=3%(反弹到 ma250 目标位)且当日温和即卖;
      暴力穿越例外(单日>=4% 且量比>=2, 924: 09-24 +4.7%/vr2.8)转持有模式,
      保 2024-08-28 -> 10-08 +33.5%
    卖 S3 尾随止盈: 持仓>=5 天收盘 <= 最高收盘 x (1-6%)(盈利回撤兜底)
  牛市(bull): 恐慌回踩 + 移植正式版四路径买入, 出货共振卖出(与生产一致)。
  过渡: 熊市买入后转牛 -> 触线/止损失效, 出货共振+尾随管, 让持仓吃牛市。
"""

from __future__ import annotations

import math

from base.analysis.strategy.hs300_metrics import build_danger_zone, calc_metrics

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
BEAR_BUY_PP_MAX = 40.0  # 买入 pp 上限(A底0.9/B底1.8/C底25.7/D底4.6)
BEAR_BUY_SHARE_MIN = 75.0  # 份额强承接下限(4真底 75.8~95; 拦 03-15 sp47/11-28 sp44/07-08 sp70)
BEAR_BUY_CHG_MAX = 1.0  # 买入日涨幅上限(绝望底当日不追大涨: 拦 2022-03-16 +4.77%政策底追高)
BEAR_BOTTOM_DIV_MIN = 15.0  # 深背离阈值%(A-23/B-20/C-15.6; 假底09-26 仅-13.7 被拦)
BEAR_BOTTOM_MP_MAX = 5.0  # 深背离路径融资分位上限(杠杆出清: 4真底 mp<=3)
BEAR_DESPAIR_TP_MAX = 10.0  # 绝望底成交额分位上限(924前夜: 2024-08-28 成交额1)
BEAR_DESPAIR_MP_MAX = 10.0  # 绝望底融资分位上限
# 熊市卖出(触线止盈 + 硬止损)
BEAR_STOP_LOSS_PCT = 5.0  # 接刀失败硬止损: 收盘较买入 <= -5% 卖(2022-09-26 轮)
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
    first_buy_idx: int | None = None  # 首个买点位置(危险区标注用)

    for i, row in enumerate(rows):
        d = row["date"]
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
        # 牛熊判定加 2% 缓冲: close 在 ma250 下方 2% 内且 ma250 上行仍算牛市
        # (2026-07-17 close4.589 vs ma250 4.598 差0.2%, 无缓冲会被判熊且贴线拒绝;
        #  正式版无牛熊判定直接买, 缓冲后与正式版一致, 全历史仅影响12天)
        bull = (
            m250 is not None
            and m250_prev is not None
            and m250 > m250_prev
            and close > m250 * (1 - BULL_BUFFER_PCT / 100)
        )

        action = None
        reason = ""

        if position == 0:
            if bull:
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
                # 熊市: 绝望底买入(买卖点先行: 只买跌透+杠杆出清+强承接的底)
                # 卖出冷却: 卖出后 BEAR_SELL_COOLDOWN 日内不重复买(真恐慌单日大跌除外);
                # 深背离极端底豁免冷却 — 止损后市场继续探底, 更强的底立刻再上车
                # (04-25止损->04-26买, 10-24止损->10-31买, 两轮无缝衔接)
                in_cooldown = (i - last_sell_idx) <= BEAR_SELL_COOLDOWN
                panic_day = chg <= PANIC_SKIP_COOLDOWN_CHG
                m60_prev = _ma(closes, MA60_WINDOW, max(0, i - MA60_SLOPE_LOOKBACK))
                trend_mature = (
                    m60 is not None and m60_prev is not None and (m60 / m60_prev - 1) * 100 <= BEAR_MA60_SLOPE_MIN
                )
                tp = row.get("_tp")
                div_dist = (close / m250 - 1) * 100 if m250 else 0.0
                deep_extreme = div_dist <= -BEAR_BOTTOM_DIV_MIN and mp is not None and mp <= BEAR_BOTTOM_MP_MAX
                despair = tp is not None and tp <= BEAR_DESPAIR_TP_MAX and mp is not None and mp <= BEAR_DESPAIR_MP_MAX
                if (
                    pp is not None
                    and pp <= BEAR_BUY_PP_MAX
                    and sp is not None
                    and sp >= BEAR_BUY_SHARE_MIN
                    and chg <= BEAR_BUY_CHG_MAX
                    and trend_mature
                    and (deep_extreme or despair)
                    and (not in_cooldown or panic_day or deep_extreme)
                ):
                    action, reason = "BUY", "熊市绝望底(强承接+杠杆出清)"
        else:
            hold_days += 1
            high_since_buy = max(high_since_buy, close)
            # 熊市持仓卖出(左侧): 硬止损 -> 触线止盈 -> 尾随兜底
            if not buy_bull:
                ret_pct = (close / buy_price - 1) * 100 if buy_price else 0.0
                div_dist = (close / m250 - 1) * 100 if m250 else 0.0
                if ret_pct <= -BEAR_STOP_LOSS_PCT:
                    action, reason = "SELL", f"接刀失败止损(收盘{ret_pct:.1f}%)"
                elif not violent_start and abs(div_dist) <= BEAR_TOUCH_DIV:
                    # 反弹触线 = 到达 ma250 目标位, 当日温和即卖(熊市弱反弹哲学);
                    # 暴力穿越(单日>=4%且量比>=2, 924式)例外: 目标位失效转持有模式;
                    # 缩量+份额有承接的触线暂缓(等下一波: C波段 03-12 sp66/vr0.7
                    #  暂缓 -> 05-20 卖 3.47; A顶 07-04 sp13 直接卖)
                    if chg >= BEAR_VIOLENT_CHG and vr >= BEAR_VIOLENT_VR:
                        violent_start = True
                    elif sp is not None and sp >= BEAR_TOUCH_HOLD_SHARE_MIN and vr < BEAR_TOUCH_HOLD_VR_MAX:
                        pass
                    else:
                        action, reason = "SELL", f"反弹触线止盈(距ma250 {div_dist:+.1f}%)"
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
                # 熊市持仓: 尾随止盈(盈利回撤兜底)
                action, reason = "SELL", f"尾随止盈(回撤{TRAIL_PCT}%)"
            # 牛市买入(buy_bull): 无止损/触线/尾随, 只靠出货共振卖出(正式版逻辑,
            # 牛市回调买点天然在 ma60 下方, 趋势破位会次日误卖; 持仓可长持到出货)

        if action == "BUY":
            position = 1.0
            hold_days = 0
            high_since_buy = close
            buy_price = close
            dist_confirm = 0
            buy_bull = bull  # 记录买入时牛熊(止损/触线只对熊市买入生效)
            violent_start = False  # 新持仓重置暴力穿越标记
            # 动态出货阈值(正式版逻辑): 地量极冷买入阈值1(1次确认即卖),
            # 其余按买入量比: 越高需越多确认
            if reason.startswith("价格低位+吸筹+成交额极冷"):
                dist_threshold = 1
            else:
                dist_threshold = max(2, math.ceil(2 + vr * 0.55)) if vr else 2
            if first_buy_idx is None:
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
        "danger_zone": build_danger_zone(rows, first_buy_idx),
    }
