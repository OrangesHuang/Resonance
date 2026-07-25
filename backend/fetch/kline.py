import json
import urllib.request
from typing import Optional

from config import KLINE_URL, HTTP_TIMEOUT, KLINE_LIMIT, ETFS, INDEX_CODE


def _market_prefix(code: str) -> str:
    if code.startswith(("sh", "sz")):
        return code[:2], code[2:]
    info = ETFS.get(code)
    if info:
        return info["market"], code
    if code.startswith(("51", "56", "58", "0")):
        return "sh", code
    return "sz", code


def fetch_kline(code: str, limit: int = KLINE_LIMIT) -> list[dict]:
    prefix, num_code = _market_prefix(code)
    symbol = f"{prefix}{num_code}"
    url = KLINE_URL.format(symbol=symbol, limit=limit)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[FETCH] kline {code} failed: {e}")
        return []

    node = data.get("data", {}).get(symbol, {})
    rows = node.get("day") or node.get("qfqday") or []

    result = []
    for r in rows:
        if len(r) < 6 or not r[0]:
            continue
        result.append({
            "date": r[0],
            "open": float(r[1]),
            "close": float(r[2]),
            "high": float(r[3]),
            "low": float(r[4]),
            "volume": float(r[5]),
        })
    return result


def fetch_index_kline(limit: int = KLINE_LIMIT) -> list[dict]:
    return fetch_kline(INDEX_CODE, limit)


def calc_volume_ma(kline: list[dict], window: int = 20) -> Optional[float]:
    if len(kline) < window:
        return None
    recent = kline[-window:]
    return sum(k["volume"] for k in recent) / window
