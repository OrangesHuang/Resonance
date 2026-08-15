from __future__ import annotations

import json
import time
import urllib.request

from base.config import (
    ETFS,
    HTTP_TIMEOUT,
    INDEX_CODE,
    KLINE_CACHE_TTL_SEC,
    KLINE_FAIL_COOLDOWN_SEC,
    KLINE_LIMIT,
    KLINE_URL,
    KLINE_URL_RANGE,
    SINA_KLINE_URL,
)

_CACHE: dict[tuple, tuple[float, list[dict] | None]] = {}


def _cached(code: str, limit: int, start_date: str | None = None, end_date: str | None = None):
    """内存 TTL 缓存: 有效期内直接返回, 失败也冷却缓存避免重试风暴。"""
    key = (code, limit, start_date, end_date)
    now = time.time()
    hit = _CACHE.get(key)
    if hit is None:
        return None
    ts, data = hit
    if data is None:
        if now - ts < KLINE_FAIL_COOLDOWN_SEC:
            return data
    elif now - ts < KLINE_CACHE_TTL_SEC:
        return data
    _CACHE.pop(key, None)
    return None


def _store(
    code: str, limit: int, data: list[dict] | None, start_date: str | None = None, end_date: str | None = None
) -> None:
    _CACHE[(code, limit, start_date, end_date)] = (time.time(), data)


def _market_prefix(code: str) -> tuple[str, str]:
    if code.startswith(("sh", "sz")):
        return code[:2], code[2:]
    info = ETFS.get(code)
    if info:
        return info["market"], code
    if code.startswith(("51", "56", "58", "0")):
        return "sh", code
    return "sz", code


def _fetch_sina(code: str, limit: int) -> list[dict] | None:
    """新浪K线(日线, 未复权): 腾讯不可达时的降级源(无需代理直连可用)。"""
    prefix, num = _market_prefix(code)
    url = SINA_KLINE_URL.format(symbol=f"{prefix}{num}", limit=limit)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[FETCH] kline sina {code} failed: {e}")
        return None
    if not isinstance(data, list) or not data:
        return None
    result = []
    for r in data:
        if not r.get("day"):
            continue
        result.append(
            {
                "date": r["day"],
                "open": float(r["open"]),
                "close": float(r["close"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "volume": float(r["volume"]),
            }
        )
    return result or None


def fetch_kline(
    code: str,
    limit: int = KLINE_LIMIT,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """拉取日K线(前复权)。

    不带日期: 返回最近 limit 根(腾讯接口上限约 640 根, 单次拉不到更早历史);
    带日期: 返回 [start_date, end_date] 区间内全部K线(limit 需 ≥ 区间根数),
    供 2021 等历史回填使用。新浪降级源不支持日期区间, 仅无日期路径可用。
    """
    cached = _cached(code, limit, start_date, end_date)
    if cached is not None:
        return cached

    prefix, num_code = _market_prefix(code)
    symbol = f"{prefix}{num_code}"
    if start_date or end_date:
        url = KLINE_URL_RANGE.format(symbol=symbol, start=start_date or "", end=end_date or "", limit=limit)
    else:
        url = KLINE_URL.format(symbol=symbol, limit=limit)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[FETCH] kline {code} failed: {e}")
        if not (start_date or end_date):
            result = _fetch_sina(code, limit)  # 降级新浪
            if result:
                _store(code, limit, result)
                return result
        _store(code, limit, None, start_date, end_date)
        return []

    node = data.get("data", {}).get(symbol, {})
    rows = node.get("day") or node.get("qfqday") or []

    result = []
    for r in rows:
        if len(r) < 6 or not r[0]:
            continue
        result.append(
            {
                "date": r[0],
                "open": float(r[1]),
                "close": float(r[2]),
                "high": float(r[3]),
                "low": float(r[4]),
                "volume": float(r[5]),
            }
        )
    if not result and not (start_date or end_date):
        result = _fetch_sina(code, limit) or []
    _store(code, limit, result, start_date, end_date)
    return result


def fetch_index_kline(
    limit: int = KLINE_LIMIT, start_date: str | None = None, end_date: str | None = None
) -> list[dict]:
    return fetch_kline(INDEX_CODE, limit, start_date, end_date)


def calc_volume_ma(kline: list[dict], window: int = 20) -> float | None:
    if len(kline) < window:
        return None
    recent = kline[-window:]
    return sum(k["volume"] for k in recent) / window
