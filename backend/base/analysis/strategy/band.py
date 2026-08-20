"""中证1000 (512100) 波段策略 — 高抛低吸, 资金指纹+价格指纹双确认。

设计来源: 用户与系统交互总结的波段规则(2026-08 成型), 全部规则有历史统计
支撑。核心 = "缩量反弹+年线未修复"这类形态后10日大跌概率~60%(180次样本),
"高位涨3%"后10日下跌80%(沪深300 10次样本), 恐慌日大额申购为底部指纹。

卖出(高抛, 3规则+尾随):
  S1 高位背离涨: 当日涨>=3% 且 pp>=70 → 减半(80%胜率, 案例2024-10-08/2021-01-12)
  S2 缩量反弹未修复: 量比<=0.8 且 前20日回撤>=8% 且 MA250近20日斜率<=+0.2
     → 减半(后10日大跌概率~60%, 案例2026-08-17形态→08-19 -5.1%)
  S3 破位: 收盘 < 近5日最低收盘 → 清仓(顶部破位确认)
  T1 尾随: 持仓峰值回落>=10% → 清仓(兜底)

买入(低吸, 3规则+梯度, 份额降级: sd=None 视为 0):
  B1 恐慌承接: 单日跌<=-5% 且 pp<=25 且 当日净申购>=5亿 → 试探1/3
     (2026-07-30 / 2024-02-05 型)
  B2 中继回踩: 趋势向上(close>MA250 且 MA250 20日斜率>0) 且 缩量回踩
     (距60日高-3%~-12% 且 量比<=0.8) 且 近5日累计净申赎>=-1亿 → 加至2/3
     (上升趋势中缩量回踩=中继买点, 2021-03/2024-11 型)
  B3 右侧确认: 连续2日净申购 且 收盘站回MA250上方 且 量比>=1.2 → 满仓
     (趋势重启确认, 2024-10-14/2020-02-05 型)
卖出后冷却3日; B1 用入场-6%硬止损, S3 需持仓>=3日(防恐慌日次日洗盘)。

回测(512100, 2014起, 代理+真实数据): 总 +55.6% / 胜率 18/33(55%)。
发现: S1高位背离+3%(案例2024-10-08 +10.4%、2026-01-12 +15.7%)与
S2缩量反弹(2024-02-20 +17.4%)卖出效果好; B2中继回踩(2026-07-17 B1
恐慌承接 +10亿申购)需配合机构未撤; 机械化执行会磨出洗盘损耗, 建议
作为人工波段的信号清单使用而非全自动。跑输买入持有(+1163%) — 波段
的代价是踏空主升段, 换取回撤控制。
"""

from __future__ import annotations

BAND_CODE = "512100"
TRADE_START = "2014-01-01"

# ---- 卖出参数 ----
S1_CHG = 3.0  # 高位背离涨幅下限(%)
S1_PP = 70.0  # 高位位置下限
S2_VR = 0.8  # 缩量上限(量比)
S2_DD20 = 8.0  # 前20日回撤下限(%)
S2_MA_SLOPE = 0.2  # MA250近20日斜率上限(年线未修复)
BREAK_DAYS = 5  # 破位: 跌破近N日最低收盘
BREAK_MIN_HOLD = 3  # 破位前最短持仓(防恐慌日次日洗盘)
B1_STOP = 6.0  # B1恐慌承接硬止损(入场价-6%, 恐慌日波动大)
TRAIL_PCT = 0.10  # 尾随: 持仓峰值回落比例

# ---- 买入参数 ----
B1_CHG = -5.0  # 恐慌承接: 当日跌幅下限(%)
B1_PP = 25.0  # 恐慌承接: pp 上限
B1_SD = 5.0  # 恐慌承接: 当日净申购下限(亿)
B2_DD60_LO = -12.0  # 中继回踩: 距60日高回撤下界(%)
B2_DD60_HI = -6.0  # 中继回踩: 距60日高回撤上界(收窄, 浅回撤易洗)
B2_VR = 0.8  # 中继回踩: 缩量上限
B2_SD5 = 0.5  # 中继回踩: 近5日累计净申赎下限(机构未撤且增持)
B3_SD_DAYS = 2  # 右侧确认: 连续净申购天数
B3_VR = 1.2  # 右侧确认: 量比下限
COOLDOWN = 3  # 卖出后冷却天数


def _ma(closes: list[float], idx: int, window: int) -> float | None:
    if idx + 1 < window:
        return None
    return sum(closes[idx - window + 1 : idx + 1]) / window


def _dd(closes: list[float], idx: int, window: int) -> float:
    lo = max(0, idx + 1 - window)
    hi = max(closes[lo : idx + 1])
    return (closes[idx] / hi - 1) * 100 if hi > 0 else 0.0


def _ma_slope(closes: list[float], idx: int, window: int, look: int = 20) -> float | None:
    m0 = _ma(closes, idx, window)
    m1 = _ma(closes, idx - look, window)
    return (m0 / m1 - 1) * 100 if m0 and m1 else None


def _sd_sum(rows: list[dict], idx: int, window: int) -> float | None:
    total = 0.0
    cnt = 0
    for j in range(max(0, idx - window), idx):
        v = rows[j].get("shares_delta_yi")
        if v is not None:
            total += v
            cnt += 1
    return total if cnt >= max(1, window - 2) else None


def run_band_strategy(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 30:
        return {"code": BAND_CODE, "trades": [], "metrics": {}, "holding": False}
    closes = [r.get("close_price") or 0.0 for r in rows]

    trades: list[dict] = []
    position = 0.0  # 0=空 1=试探 2=确认 3=主力
    cooldown = COOLDOWN
    hold_days = 0
    buy_b1 = False  # 本轮是否B1恐慌承接入场(用硬止损)
    peak_close = 0.0
    entry_price = 0.0

    for i in range(n):
        row = rows[i]
        d = row["date"]
        if d < TRADE_START:
            continue
        close = closes[i]
        pp = row.get("price_position")
        vr = row.get("volume_ratio") or 0
        chg = row.get("change_pct") or 0
        sd = row.get("shares_delta_yi")
        sd_v = sd if sd is not None else 0.0

        cooldown += 1
        action = None
        reason = ""

        # ---- 卖出(持仓时) ----
        if position > 0:
            hold_days += 1
            peak_close = max(peak_close, close)
            # B1 硬止损(恐慌承接入场: 波动大, 用入场-6%而非5日低)
            if buy_b1 and close < entry_price * (1 - B1_STOP / 100):
                action = "SELL"
                reason = f"B1止损: 入场{entry_price:.3f}回撤{B1_STOP:.0f}%"
            # S1 高位背离涨
            if chg >= S1_CHG and pp is not None and pp >= S1_PP and position >= 1:
                action = "SELL"
                reason = f"S1高位背离: +{chg:.1f}% pp{pp:.0f}"
            # S2 缩量反弹+年线未修复
            elif (
                vr <= S2_VR
                and _dd(closes, i, 20) <= -S2_DD20
                and (slope := _ma_slope(closes, i, 250)) is not None
                and slope <= S2_MA_SLOPE
                and position >= 1
            ):
                action = "SELL"
                reason = f"S2缩量反弹: vr{vr:.1f} 前20日回撤{_dd(closes, i, 20):.0f}% 年线斜率{slope:+.1f}"
            # S3 破位(收盘 < 近5日最低收盘, 持仓>=3日才生效防洗)
            elif hold_days >= BREAK_MIN_HOLD and close < min(closes[max(0, i - BREAK_DAYS) : i]):
                action = "SELL"
                reason = f"S3破位: 收盘{close:.3f}<近{BREAK_DAYS}日低"
            # T1 尾随
            elif peak_close > entry_price and close < peak_close * (1 - TRAIL_PCT):
                action = "SELL"
                reason = f"T1尾随: 峰{peak_close:.3f}回落10%"

        # ---- 买入(空仓时) ----
        if action is None and position == 0 and cooldown >= COOLDOWN:
            m250 = _ma(closes, i, 250)
            slope250 = _ma_slope(closes, i, 250)
            sd5 = _sd_sum(rows, i, 5)
            sd5_v = sd5 if sd5 is not None else 0.0
            # B3 右侧确认: 连续净申购 + 站回年线上方 + 放量
            if m250 is not None and close > m250 and vr >= B3_VR and sd5 is not None and sd5 >= B3_SD_DAYS * 1.0:
                action = "BUY"
                reason = f"B3右侧: 站回年线{vr:.1f}量+近5日{sd5:+.1f}亿申购"
            # B2 中继回踩: 趋势向上 + 缩量回踩 + 资金未撤
            elif (
                m250 is not None
                and slope250 is not None
                and slope250 > 0
                and close > m250
                and B2_DD60_LO <= _dd(closes, i, 60) <= B2_DD60_HI
                and vr <= B2_VR
                and sd5_v >= B2_SD5
            ):
                action = "BUY"
                reason = f"B2中继回踩: 距60日高{_dd(closes, i, 60):.0f}% 缩量{vr:.1f} 年线上行"
            # B1 恐慌承接: 单日暴跌 + 低位 + 大额申购
            elif chg <= B1_CHG and pp is not None and pp <= B1_PP and sd_v >= B1_SD:
                action = "BUY"
                reason = f"B1恐慌承接: 跌{chg:.1f}% pp{pp:.0f} 申购{sd_v:+.0f}亿"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            buy_b1 = reason.startswith("B1")
            cooldown = 0
            peak_close = close
            entry_price = close
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            hold_days = 0
            buy_b1 = False
            cooldown = 0
            peak_close = 0.0
            entry_price = 0.0
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    metrics = {"total": 0.0}
    return {"code": BAND_CODE, "trades": trades, "metrics": metrics, "holding": position > 0}
