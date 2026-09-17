"""极简策略回测: 池化验证的入场信号(低位+深跌+净申购) + 分离风控(止损/尾随)。

设计遵循《量化买卖规律发现方法论与可靠性评估.md》:
  - alpha(入场)取自跨资产池化事件研究: pp<=PP_MAX 且 chg<=CHG_MIN 且 sd>0;
  - 风控(止损/尾随)与 alpha 分离, 为方差控制装置, 不按个案调参;
  - 参数少而圆, 从平台区取(非尖峰)。

用法: python3 scripts/backtest_hs300_pattern.py [--asset=510300 ...] [--pp=40] [--chg=-4] [--stop=8] [--trail=10] [--hold=20]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from base.store.daily_repo import get_by_code  # noqa: E402


def run(rows, pp_max, chg_min, sd_min, stop_pct, trail_pct, max_hold, lag_sd=False, nosd=False):
    n = len(rows)
    trades = []
    pos = 0.0
    buy_price = 0.0
    peak = 0.0
    hold = 0
    for i, r in enumerate(rows):
        close = r.get("close_price") or 0.0
        pp = r.get("price_position")
        chg = r.get("change_pct") or 0.0
        # 份额 T+1 公布: lag_sd 时用"昨日份额变化"(当日收盘已知), 消除前视
        sd = r.get("shares_delta_yi")
        if lag_sd and i > 0:
            sd = rows[i - 1].get("shares_delta_yi")
        if pos == 1.0:
            hold += 1
            peak = max(peak, close)
            ret = (close / buy_price - 1) * 100 if buy_price else 0.0
            # 风控(收益已回吐): 止损 / 尾随 / 时间止损
            if ret <= -stop_pct:
                trades.append({"date": r["date"], "action": "SELL", "price": close, "reason": f"止损{ret:.1f}%"})
                pos = 0.0
            elif close <= peak * (1 - trail_pct / 100) and hold >= 3:
                ret_now = (close / buy_price - 1) * 100
                trades.append({"date": r["date"], "action": "SELL", "price": close, "reason": f"尾随{ret_now:.1f}%"})
                pos = 0.0
            elif hold >= max_hold:
                ret_now = (close / buy_price - 1) * 100
                trades.append({"date": r["date"], "action": "SELL", "price": close, "reason": f"持满{max_hold}日{ret_now:.1f}%"})
                pos = 0.0
        elif pos == 0.0 and pp is not None and pp <= pp_max and chg <= chg_min and (nosd or (sd is not None and sd > sd_min)):
            # 入场(池化验证信号)
            trades.append({"date": r["date"], "action": "BUY", "price": close, "reason": f"低位{pp:.0f}+跌{chg:.1f}%" if nosd else f"低位{pp:.0f}+跌{chg:.1f}%+申购{sd:.1f}亿"})
            pos = 1.0
            buy_price = close
            peak = close
            hold = 0
    # 未平仓按最后收盘
    if pos == 1.0 and rows:
        last = rows[-1]["close_price"]
        trades.append({"date": rows[-1]["date"], "action": "SELL", "price": last, "reason": "未平仓@期末"})
    return trades


def metrics(trades):
    geom = 1.0
    i = 0
    rounds = []
    seq = []
    while i < len(trades):
        if trades[i]["action"] == "BUY" and i + 1 < len(trades) and trades[i + 1]["action"] == "SELL":
            bp = trades[i]["price"]; sp = trades[i + 1]["price"]
            ret = (sp / bp - 1) * 100
            geom *= sp / bp
            rounds.append(ret)
            i += 2
        else:
            seq.append(trades[i]); i += 1
    total = (geom - 1) * 100
    wins = sum(1 for x in rounds if x > 0)
    mdd = 0.0
    return {"trades": trades, "total": total, "n_rounds": len(rounds), "wins": wins,
            "win_rate": wins / len(rounds) * 100 if rounds else 0, "mdd": mdd, "rounds": rounds}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asset", default="510300")
    ap.add_argument("--pp", type=float, default=40.0)
    ap.add_argument("--chg", type=float, default=-4.0)
    ap.add_argument("--sd", type=float, default=0.0)
    ap.add_argument("--stop", type=float, default=8.0)
    ap.add_argument("--trail", type=float, default=10.0)
    ap.add_argument("--hold", type=int, default=20)
    ap.add_argument("--lag", action="store_true", help="份额用昨日值(T+1 诚实版, 消除前视)")
    ap.add_argument("--nosd", action="store_true", help="入场不看份额(无前视纯价格信号)")
    args = ap.parse_args()

    rows = [r for r in reversed(get_by_code(args.asset)) if r.get("composite_prob") is not None]
    trades = run(rows, args.pp, args.chg, args.sd, args.stop, args.trail, args.hold, lag_sd=args.lag, nosd=args.nosd)
    m = metrics(trades)
    print(f"标的={args.asset}  pp<={args.pp} chg<={args.chg} sd>{args.sd} stop={args.stop}% trail={args.trail}% hold<={args.hold}日 lag_sd={args.lag} nosd={args.nosd}")
    print(f"  交易笔数={len(trades)}  轮数={m['n_rounds']}  总收益={m['total']:+.1f}%  胜率={m['win_rate']:.1f}%  胜={m['wins']}/{m['n_rounds']}")
    for t in trades:
        print(f"   {t['date']} {t['action']:<4} {t['price']:.3f}  {t['reason']}")


if __name__ == "__main__":
    main()
