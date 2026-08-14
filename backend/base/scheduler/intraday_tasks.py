"""盘中任务: 实时轮询/盘中信号入库/成交额轮询/K线预载。

所有触网任务均由 tasks.py 注册时经 asyncio.to_thread 派发,
本模块不直接操作事件循环。
"""

from __future__ import annotations

from datetime import datetime

from base.config import ETFS
from base.fetch.realtime import fetch_market_turnover_intraday, fetch_realtime_quotes
from base.scheduler import state
from base.scheduler.time_guard import is_trading_time
from base.store.daily_repo import upsert_daily
from base.store.realtime_repo import insert_intraday_turnover, insert_snapshots
from resonance.analysis.intraday import calc_intraday_signal, estimate_full_day_turnover


def _load_kline_from_db(code: str, limit: int = 60) -> list[dict]:
    """从本地数据库加载K线缓存，避免每次启动调腾讯API被封禁。"""
    from base.store.daily_repo import get_by_code

    rows = get_by_code(code)
    if not rows:
        return []
    # get_by_code 返回 date DESC，取最近 limit 条后反转为升序
    recent = rows[:limit][::-1]
    result = []
    for r in recent:
        close = r.get("close_price") or 0.0
        result.append(
            {
                "date": r["date"],
                "open": close,
                "close": close,
                "high": close,
                "low": close,
                "volume": r.get("volume") or 0.0,
            }
        )
    return result


def task_preload_kline() -> None:
    state._idx_kline_cache = []  # 指数K线仅daily_analysis使用，preload时跳过
    for code in ETFS:
        data = _load_kline_from_db(code)
        if data:
            state._kline_cache[code] = data
    print(f"[SCHEDULER] loaded kline for {len(state._kline_cache)} ETFs from local db")


def task_realtime_poll() -> None:
    now = datetime.now()
    if not is_trading_time(now):
        return

    quotes = fetch_realtime_quotes()
    if not quotes:
        return

    idx_quote = quotes.get("000300")
    signals = []

    for code in ETFS:
        quote = quotes.get(code)
        if not quote:
            continue
        kline = state._kline_cache.get(code, [])
        share_info = state._share_delta_cache.get(code, {})
        share_delta_pct = share_info.get("delta_pct")

        signal = calc_intraday_signal(
            quote=quote,
            idx_quote=idx_quote,
            kline_history=kline,
            latest_share_delta_pct=share_delta_pct,
            now=now,
        )
        if signal:
            signals.append(
                {
                    "timestamp": signal.timestamp,
                    "code": signal.code,
                    "name": signal.name,
                    "idx_name": signal.idx_name,
                    "price": signal.price,
                    "open": quote.open,
                    "high": quote.high,
                    "low": quote.low,
                    "change_pct": signal.change_pct,
                    "volume_hand": signal.volume_hand,
                    "volume_ratio": signal.volume_ratio,
                    "vol_prob": signal.vol_prob,
                    "dir_prob": signal.dir_prob,
                    "share_prob": signal.share_prob,
                    "composite_prob": signal.composite_prob,
                    "signal_level": signal.signal_level,
                    "premium_pct": signal.premium_pct,
                    "price_position": signal.price_position,
                    "trade_direction": signal.trade_direction,
                }
            )

    if signals:
        state._latest_signals = signals
        state._last_update = now.strftime("%Y-%m-%dT%H:%M:%S")
        insert_snapshots(signals)


def task_intraday_update() -> dict:
    """每15分钟将盘中信号写入 etf_daily，供K线图展示当日数据。"""
    now = datetime.now()
    if not is_trading_time(now):
        return {"status": "not_trading"}
    if not state._latest_signals:
        return {"status": "no_signals"}

    today = now.strftime("%Y-%m-%d")
    count = 0
    for sig in state._latest_signals:
        data = {
            "open": sig.get("open"),
            "high": sig.get("high"),
            "low": sig.get("low"),
            "close": sig.get("price"),
            "change_pct": sig.get("change_pct"),
            "volume": sig.get("volume_hand"),
            "volume_ratio": sig.get("volume_ratio"),
            "vol_prob": sig.get("vol_prob"),
            "dir_prob": sig.get("dir_prob"),
            "share_prob": sig.get("share_prob"),
            "composite_prob": sig.get("composite_prob"),
            "signal_level": sig.get("signal_level"),
            "price_position": sig.get("price_position"),
            "trade_direction": sig.get("trade_direction"),
        }
        upsert_daily(today, sig["code"], data)
        count += 1

    print(f"[SCHEDULER] intraday update: {count} ETFs → {today}")
    return {"status": "ok", "date": today, "count": count}


def task_turnover_poll() -> None:
    """盘中两市成交额轮询(5分钟): 当日累计 + 全天预估, 收盘前分析用。"""
    now = datetime.now()
    if not is_trading_time(now):
        return
    data = fetch_market_turnover_intraday()
    if not data:
        return
    est = estimate_full_day_turnover(data["amount_yi"], now)
    insert_intraday_turnover(now.strftime("%Y-%m-%d %H:%M:%S"), data["amount_yi"], est)
    print(f"[SCHEDULER] intraday turnover: {data['amount_yi']}亿 (预估全天 {est}亿)")
