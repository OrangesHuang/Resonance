import urllib.request
from dataclasses import dataclass
from typing import Optional

from config import REALTIME_URL, HTTP_TIMEOUT, ETFS, INDEX_CODE


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


def _parse_line(line: str) -> Optional[RealtimeQuote]:
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


def fetch_index_quote() -> Optional[RealtimeQuote]:
    quotes = fetch_realtime_quotes()
    return quotes.get("000300")
