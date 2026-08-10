"""三维背离算法: K线 + 期权PCR + 股指期货基差 联合顶底信号。

核心认知:
- 市场由三类参与者构成: 趋势跟随者(价格表达)、机构(期货基差表达)、
  散户/对冲者(期权PCR表达)。价格定方向, 衍生品定背离; 单指标会被骗,
  背离共振(多规则同分)才触发。
- 基差有结构性水平(IC 常年贴水 -1%~-3%), PCR 各标的基线不同(50ETF 0.69 vs
  科创50 1.07), 绝对水平无意义, 信号在 5 日变化率(一阶导)。
- 涨势中机构加对冲(R1/R8)或散户毫无恐惧(R3/R5) -> 顶; 跌势中机构回补(R2/R9)
  或散户恐慌极点(R10) -> 底。

历史教训(案例即验收基准):
- 2026-06-30 科创50大顶: PCR=1.124 高分位, 单看 PCR 会被读成底部 -> 必须看变化率,
  该顶由 6/25 R1+R3+R8 命中。
- 2025-08-28 加速赶顶: 5日+23% 但基差未跟进、PCR 低分位 -> R5b 命中(8/27)。
- 2025-10-09 动量耗尽型顶: 无先兆背离, 不追; 仅 9/23 R1+R8 领先 6 交易日。
- 2026-03-31 阴跌慢底: 无恐慌, 由 R9 在 4/08 反弹确认时触发(+5日)。

算法结构: 日频指标(5日变化率/120日分位/20日位置/新高新低) -> 10条规则打分 ->
触发(分数>=2.0+位置过滤) -> 分级(CONF=含机构证据/WATCH=纯情绪) -> 同类3日合并。
"""
from typing import Optional

# ---- 参数常量(阈值来源: 588000 全历史 + 12个已知顶底事件回归) ----
P5_TOP = 2.0              # 价格5日涨跌幅阈值(%)
BAS_D5_WIDEN = -0.25      # 基差5日贴水加深阈值(百分点)
PCR_D5_FALL = -0.15       # PCR 5日恐慌撤离阈值
PCR_PCT_COLD = 30.0       # PCR 120日分位: 情绪极冷
P5_BLOWOFF = 5.0          # R5b 加速上涨阈值(%)
B5_GATE = 0.4             # R5b 基差未跟进阈值(百分点)
P5_EXTREME = 15.0         # 极端加速阈值(%), 无视基差门槛
BAS_LEVEL_NO_HEDGE = -0.6  # R7 机构无对冲的基差水平
BAS_PCT_DEEP = 20.0       # R8 基差120日分位: 深度贴水
BAS_D5_CONVERGE = 0.25    # R2 基差快速收窄阈值(百分点)
PCR_D5_RISE = 0.15        # R4 PCR 骤升阈值
PCR_PCT_PANIC = 70.0      # R6 PCR 分位: 恐慌
P5_CONFIRM = 5.0          # R9 止跌回升阈值(%)
BAS_D5_CONFIRM = 0.5      # R9 基差急收窄阈值(百分点)
POS20_CONFIRM = 80.0      # R9 位置上限(底部确认不追高)
PCR_D5_PEAK = 0.25        # R10 PCR 恐慌极点阈值
P5_STABLE = -3.0          # R10 价格企稳下限(%)
POS20_PEAK = 50.0         # R10 位置上限
SCORE_TRIGGER = 2.0       # 触发分数
POS20_TOP = 55.0          # TOP 位置下限
POS20_BOT = 45.0          # BOT 位置上限
MERGE_DAYS = 3            # 同类信号合并窗口(交易日)
WINDOW = 5                # 变化率窗口(交易日)
PCT_WINDOW = 120          # 分位窗口(交易日)
POS_WINDOW = 20           # 位置/新高新低窗口(交易日)

# 科创50 无对应股指期货, 用中证500(IC)代理
FUTURES_PROXY = {"510050": "IH", "510300": "IF", "510500": "IC", "588000": "IC"}

RULE_NAMES = {
    "R1": "涨势中基差贴水加深", "R3": "涨势中恐慌盘骤撤",
    "R5": "新高无人恐慌", "R5b": "加速赶顶+情绪极冷",
    "R7": "新高但机构无对冲", "R8": "涨势中深度贴水",
    "R2": "跌势中基差快速收窄", "R4": "跌势中恐慌升温",
    "R6": "新低恐慌", "R9": "止跌回升+基差急收窄",
    "R10": "恐慌极点+价格企稳",
}


def _percentile(hist: list[Optional[float]], v: Optional[float]) -> Optional[float]:
    vals = [x for x in hist if x is not None]
    if not vals or v is None:
        return None
    return sum(1 for x in vals if x <= v) / len(vals) * 100.0


def compute_divergence(kl: list[dict], pcr: list[dict], basis: list[dict]) -> list[dict]:
    """纯函数: 输入日线/PCR/基差序列, 输出 TOP/BOT 信号列表。

    信号字段: date/kind/score/grade/rules/close。
    """
    dates = [r["date"] for r in sorted(kl, key=lambda r: r["date"])]
    close = {r["date"]: float(r["close_price"]) for r in kl}
    pcr_v = {r["date"]: float(r["pcr"]) for r in pcr}
    bas_v = {r["date"]: float(r["basis_pct"]) for r in basis}
    n = len(dates)
    raw: list[dict] = []

    for i in range(POS_WINDOW, n):
        d = dates[i]
        prev5 = dates[i - WINDOW]
        c, c5 = close[d], close.get(prev5)
        p5 = (c / c5 - 1) * 100.0 if c5 else None
        b, b5 = bas_v.get(d), bas_v.get(prev5)
        bas5 = b - b5 if b is not None and b5 is not None else None
        pv, pv5 = pcr_v.get(d), pcr_v.get(prev5)
        pcr5 = pv - pv5 if pv is not None and pv5 is not None else None

        win = dates[max(0, i - PCT_WINDOW):i]
        pcr_pct = _percentile([pcr_v.get(x) for x in win], pv)
        bas_pct = _percentile([bas_v.get(x) for x in win], b)

        pos_win = [close[x] for x in dates[max(0, i - (POS_WINDOW - 1)):i + 1]]
        lo, hi = min(pos_win), max(pos_win)
        pos20 = (c - lo) / (hi - lo) * 100.0 if hi > lo else 50.0
        nh = c > max(close[x] for x in dates[max(0, i - POS_WINDOW):i])
        nl = c < min(close[x] for x in dates[max(0, i - POS_WINDOW):i])

        st, sb, tr, br = 0.0, 0.0, [], []
        if p5 is not None and p5 > P5_TOP:
            if bas5 is not None and bas5 < BAS_D5_WIDEN:
                st += 1.5; tr.append("R1")
            if pcr5 is not None and pcr5 < PCR_D5_FALL:
                st += 1.0; tr.append("R3")
            if bas_pct is not None and bas_pct < BAS_PCT_DEEP:
                st += 1.5; tr.append("R8")
        if nh and pcr_pct is not None and pcr_pct < PCR_PCT_COLD:
            if p5 is not None and p5 > P5_BLOWOFF and (bas5 is not None and bas5 < B5_GATE or p5 > P5_EXTREME):
                st += 2.5; tr.append("R5b")
            else:
                st += 1.0; tr.append("R5")
        if nh and b is not None and bas5 is not None and b > BAS_LEVEL_NO_HEDGE and bas5 > -0.2:
            st += 0.5; tr.append("R7")
        if p5 is not None and p5 < -P5_TOP:
            if bas5 is not None and bas5 > BAS_D5_CONVERGE:
                sb += 1.5; br.append("R2")
            if pcr5 is not None and pcr5 > PCR_D5_RISE:
                sb += 1.0; br.append("R4")
        if nl and pcr_pct is not None and pcr_pct > PCR_PCT_PANIC:
            sb += 1.0; br.append("R6")
        if p5 is not None and p5 > P5_CONFIRM and bas5 is not None and bas5 > BAS_D5_CONFIRM and pos20 < POS20_CONFIRM:
            sb += 2.0; br.append("R9")
        if pcr5 is not None and pcr5 > PCR_D5_PEAK and p5 is not None and p5 > P5_STABLE and pos20 < POS20_PEAK:
            sb += 2.0; br.append("R10")

        if st >= SCORE_TRIGGER and pos20 > POS20_TOP:
            raw.append({"date": d, "kind": "TOP", "score": st, "pos20": pos20,
                        "grade": "CONF" if ("R1" in tr or "R8" in tr) else "WATCH",
                        "rules": tr, "close": c})
        if sb >= SCORE_TRIGGER and (pos20 < POS20_BOT or "R9" in br or "R10" in br):
            raw.append({"date": d, "kind": "BOT", "score": sb, "pos20": pos20,
                        "grade": "CONF" if ("R2" in br or "R9" in br) else "WATCH",
                        "rules": br, "close": c})

    merged: list[dict] = []
    idx = {x: j for j, x in enumerate(dates)}
    for s in raw:
        if merged and merged[-1]["kind"] == s["kind"] and idx[s["date"]] - idx[merged[-1]["date"]] <= MERGE_DAYS:
            merged[-1] = s  # 取集群内最新信号, 更贴近实际转折
        else:
            merged.append(s)
    for s in merged:
        s["rule_names"] = [RULE_NAMES[r] for r in s["rules"]]
    return merged
