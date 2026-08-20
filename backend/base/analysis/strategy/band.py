"""中证1000 (512100) 波段策略 v3 — 训练期(2014~2024-09-23)统计驱动, 924后样本外验证。

v3 规则由训练期形态统计决定(防过拟合):
  - 删除 S1"高位涨3%卖": 训练期77次后10日 +3.9%(中证1000高位涨3%是动量
    延续, 不是顶; 该规则来自沪深300, 移植即过拟合)
  - 卖点核心改为"高位缩量赎回": 训练期36次后10日 -2.1%, 涨>2%占比仅3%
  - B1 放宽: "当日净申购5亿"训练期仅1次(过严), 改为暴跌+低位+5日机构未撤
测试期(924后): B2中继 +1.7%/胜率67%, B3右侧 +0.8%/60% — 有效。

卖出: S-A高位缩量赎回(vr<=0.8+pp>=70+5日净赎回) / S-C破位(收盘<5日低,
持仓>=3日) / T1尾随10% / TP止盈+15% / SL止损-6%。
买入: B1恐慌(chg<=-5%+pp<=30+5日净申赎>=0) / B2中继回踩(年线上行+缩量
回撤6-12%+5日净申购>=0.5亿) / B3右侧确认(站回年线+放量+5日净申购>=2亿)。
"""

from __future__ import annotations

BAND_CODE = "512100"
TRADE_START = "2014-01-01"

# ---- 卖出参数(v3: 训练期统计驱动) ----
SA_VR = 0.8  # 高位缩量赎回: 量比上限
SA_PP = 70.0  # 高位缩量赎回: 位置下限
SA_SD5 = -1.0  # 高位缩量赎回: 近5日累计净申赎上限(亿)
BREAK_DAYS = 5  # 破位: 跌破近N日最低收盘
BREAK_MIN_HOLD = 3  # 破位前最短持仓(防恐慌日次日洗盘)
SL_PCT = 6.0  # 硬止损(入场价-6%)
TP_PCT = 15.0  # 止盈(波段目标+15%, 仅熊/震荡有效)
TRAIL_PCT = 0.10  # 尾随: 持仓峰值回落比例
BULL_SLOPE = 0.3  # 牛市判定: MA250近20日斜率>此值=牛市(吃趋势)
BULL_TRAIL = 0.12  # 牛市尾随放宽(主升洗盘不卖)

# ---- 买入参数(v3) ----
B1_CHG = -5.0  # 恐慌承接: 当日跌幅下限(%)
B1_PP = 30.0  # 恐慌承接: pp 上限(训练期统计放宽)
B1_SD5 = 0.0  # 恐慌承接: 近5日累计净申赎下限(机构未大撤)
B2_DD60_LO = -12.0  # 中继回踩: 距60日高回撤下界(%)
B2_DD60_HI = -6.0  # 中继回踩: 距60日高回撤上界(收窄, 浅回撤易洗)
B2_VR = 0.8  # 中继回踩: 缩量上限
B2_SD5 = 0.5  # 中继回踩: 近5日累计净申赎下限(机构未撤且增持)
B3_VR = 1.2  # 右侧确认: 量比下限
B3_SD5 = 2.0  # 右侧确认: 近5日累计净申赎下限(亿)
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

        cooldown += 1
        action = None
        reason = ""

        # ---- 卖出(持仓时) ----
        if position > 0:
            hold_days += 1
            peak_close = max(peak_close, close)
            # SL 硬止损(入场-6%)
            if close < entry_price * (1 - SL_PCT / 100):
                action = "SELL"
                reason = f"SL止损: 入场{entry_price:.3f}回撤{SL_PCT:.0f}%"
            # 牛熊分治: 牛市(年线强上行)关止盈吃趋势
            bull_now = (slope := _ma_slope(closes, i, 250)) is not None and slope > BULL_SLOPE
            # S-A 高位缩量赎回(训练期最强卖出形态: f10 -2.1%, 涨>2%仅3%)
            if (
                vr <= SA_VR
                and pp is not None
                and pp >= SA_PP
                and (sd5 := _sd_sum(rows, i, 5)) is not None
                and sd5 <= SA_SD5
            ):
                action = "SELL"
                reason = f"S-A高位缩量赎回: vr{vr:.1f} pp{pp:.0f} 5日{sd5:+.1f}亿"
            # TP 止盈(仅非牛市有效)
            elif not bull_now and close >= entry_price * (1 + TP_PCT / 100):
                action = "SELL"
                reason = f"TP止盈: 入场{entry_price:.3f}+{TP_PCT:.0f}%"
            # S-C 破位(收盘 < 近5日最低收盘, 持仓>=3日才生效防洗)
            elif hold_days >= BREAK_MIN_HOLD and close < min(closes[max(0, i - BREAK_DAYS) : i]):
                action = "SELL"
                reason = f"S-C破位: 收盘{close:.3f}<近{BREAK_DAYS}日低"
            # T1 尾随(牛市放宽到12%, 吃主升)
            elif peak_close > entry_price and close < peak_close * (1 - (BULL_TRAIL if bull_now else TRAIL_PCT)):
                action = "SELL"
                reason = f"T1尾随: 峰{peak_close:.3f}回落{(BULL_TRAIL if bull_now else TRAIL_PCT) * 100:.0f}%"

        # ---- 买入(空仓时) ----
        if action is None and position == 0 and cooldown >= COOLDOWN:
            m250 = _ma(closes, i, 250)
            slope250 = _ma_slope(closes, i, 250)
            sd5 = _sd_sum(rows, i, 5)
            sd5_v = sd5 if sd5 is not None else 0.0
            # B3 右侧确认: 站回年线上方 + 放量 + 5日净申购
            if m250 is not None and close > m250 and vr >= B3_VR and sd5 is not None and sd5 >= B3_SD5:
                action = "BUY"
                reason = f"B3右侧: 站回年线{vr:.1f}量+5日{sd5:+.1f}亿申购"
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
            # B1 恐慌承接: 单日暴跌 + 低位 + 5日机构未大撤
            elif chg <= B1_CHG and pp is not None and pp <= B1_PP and sd5_v >= B1_SD5:
                action = "BUY"
                reason = f"B1恐慌承接: 跌{chg:.1f}% pp{pp:.0f} 5日申赎{sd5_v:+.1f}亿"

        if action == "BUY":
            position = 1.0
            hold_days = 0
            cooldown = 0
            peak_close = close
            entry_price = close
            trades.append({"date": d, "action": "BUY", "price": close, "reason": reason})
        elif action == "SELL":
            position = 0.0
            hold_days = 0
            cooldown = 0
            peak_close = 0.0
            entry_price = 0.0
            trades.append({"date": d, "action": "SELL", "price": close, "reason": reason})

    # 牛熊 regime 序列(斜率>0.3=牛), 供前端蒙版
    regimes: list[dict] = []
    for i in range(len(rows)):
        d = rows[i]["date"]
        if d < TRADE_START:
            continue
        slope = _ma_slope(closes, i, 250)
        regimes.append({"date": d, "regime": "bull" if (slope is not None and slope > BULL_SLOPE) else "bear"})

    metrics = {"total": 0.0}
    return {"code": BAND_CODE, "trades": trades, "regimes": regimes, "metrics": metrics, "holding": position > 0}
