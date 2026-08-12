from __future__ import annotations

import urllib.request
from dataclasses import dataclass

from base.config import (
    ETFS,
    HTTP_TIMEOUT,
    INDEX_CODE,
    MARKET_TURNOVER_SYMBOLS,
    REALTIME_URL,
)


@dataclass
class RealtimeQuote:
    code: str
    name: str
    price: float
    prev_close: float
    open: float
    high: float
    low: float
    volume_hand: float
    amount_wan: float
    change_pct: float
    timestamp: str


def _build_symbols() -> str:
    parts = []
    for code, info in ETFS.items():
        parts.append(f"{info['market']}{code}")
    parts.append(INDEX_CODE)
    return ",".join(parts)


def _parse_line(line: str) -> RealtimeQuote | None:
    if '="' not in line:
        return None
    try:
        raw = line.split('="')[1].rstrip('";\n')
        fields = raw.split("~")
        if len(fields) < 40:
            return None
        code = fields[2]
        return RealtimeQuote(
            code=code,
            name=fields[1],
            price=float(fields[3]),
            prev_close=float(fields[4]),
            open=float(fields[5]),
            high=float(fields[33]) if fields[33] else float(fields[3]),
            low=float(fields[34]) if fields[34] else float(fields[3]),
            volume_hand=float(fields[6]),
            amount_wan=float(fields[37]) if len(fields) > 37 and fields[37] else 0.0,
            change_pct=float(fields[32]) if fields[32] else 0.0,
            timestamp=fields[30] if len(fields) > 30 else "",
        )
    except (IndexError, ValueError) as e:
        print(f"[FETCH] parse realtime failed: {e}")
        return None


def fetch_realtime_quotes() -> dict[str, RealtimeQuote]:
    symbols = _build_symbols()
    url = REALTIME_URL.format(symbols=symbols)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            text = resp.read().decode("gbk")
    except Exception as e:
        print(f"[FETCH] realtime quotes failed: {e}")
        return {}

    result = {}
    for line in text.strip().split("\n"):
        quote = _parse_line(line)
        if quote:
            result[quote.code] = quote
    return result


def fetch_index_quote() -> RealtimeQuote | None:
    quotes = fetch_realtime_quotes()
    return quotes.get("000300")


def _fetch_raw(symbols: str) -> str:
    url = REALTIME_URL.format(symbols=symbols)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read().decode("gbk")


def fetch_market_turnover_intraday() -> dict | None:
    """盘中两市成交额(元): 上证指数+深证成指 实时累计成交额。

    腾讯指数行情字段35格式: "价格/成交量(手)/成交额(元)"。
    """
    try:
        text = _fetch_raw(MARKET_TURNOVER_SYMBOLS)
    except Exception as e:
        print(f"[FETCH] intraday turnover failed: {e}")
        return None

    total_yuan = 0.0
    ts = ""
    for line in text.strip().split("\n"):
        if '="' not in line:
            continue
        raw = line.split('="')[1].rstrip('";\n')
        fields = raw.split("~")
        if len(fields) <= 35 or "/" not in fields[35]:
            continue
        seg = fields[35].split("/")
        if len(seg) < 3:
            continue
        try:
            total_yuan += float(seg[2])
        except (IndexError, ValueError):
            continue
        if not ts and len(fields) > 30:
            ts = fields[30]

    if total_yuan <= 0:
        return None
    return {"amount_yi": round(total_yuan / 1e8, 2), "timestamp": ts}
