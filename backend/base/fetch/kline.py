from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta

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

# 腾讯日期区间接口单次响应上限约 640~700 根(实测 limit=2000 仍只返回最近 640 根),
# 历史回填必须分块拉取; 每块按自然日切分, 保证交易日数 ≤ 安全上限。
RANGE_CHUNK_NATURAL_DAYS = 850  # 每块自然日跨度(≈600 交易日, 5/7 密度上限 607)
RANGE_CHUNK_LIMIT = 650  # 每块请求 limit(覆盖块内最大交易日数)

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


def _iter_date_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """[start_date, end_date] 按自然日切块(每块 ≤ RANGE_CHUNK_NATURAL_DAYS 天),
    块间首尾相接不重叠, 保证每块交易日数不触发接口单次上限。"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    windows: list[tuple[str, str]] = []
    cur = start
    while cur <= end:
        win_end = min(cur + timedelta(days=RANGE_CHUNK_NATURAL_DAYS), end)
        windows.append((cur.strftime("%Y-%m-%d"), win_end.strftime("%Y-%m-%d")))
        cur = win_end + timedelta(days=1)
    return windows


def _parse_tencent_rows(symbol: str, data: dict) -> list[dict]:
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
    return result


def _fetch_tencent(symbol: str, url: str) -> list[dict] | None:
    """腾讯 K线 GET + 解析; 网络失败返回 None(供上层降级/记录)。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[FETCH] kline {symbol} failed: {e}")
        return None
    return _parse_tencent_rows(symbol, data) or None


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

    不带日期: 返回最近 limit 根(腾讯接口单次上限约 640~700 根);
    带日期: 返回 [start_date, end_date] 区间内全部K线。区间超过单次上限
    (约 600 交易日)时自动分块拉取合并, 避免 640 根截断导致历史缺口
    (曾因单次大区间只返回最近 640 根, 2021~2023 中间段永久拉不到)。
    新浪降级源不支持日期区间, 仅无日期路径可用。
    """
    cached = _cached(code, limit, start_date, end_date)
    if cached is not None:
        return cached

    prefix, num_code = _market_prefix(code)
    symbol = f"{prefix}{num_code}"

    if start_date or end_date:
        # 日期区间: 分块拉取合并(交易日历不可用时按自然日估算, 块内交易日 ≤ 上限)
        s = start_date or "2000-01-01"
        e = end_date or datetime.now().strftime("%Y-%m-%d")
        merged: list[dict] = []
        for ws, we in _iter_date_windows(s, e):
            url = KLINE_URL_RANGE.format(symbol=symbol, start=ws, end=we, limit=RANGE_CHUNK_LIMIT)
            bars = _fetch_tencent(symbol, url) or []
            if not bars:
                print(f"[FETCH] kline {code} 区间 {ws}~{we} 无数据")
            merged.extend(bars)
        seen: set[str] = set()
        result: list[dict] = []
        for r in sorted(merged, key=lambda x: x["date"]):
            if r["date"] not in seen:
                seen.add(r["date"])
                result.append(r)
        _store(code, limit, result, start_date, end_date)
        return result

    # 无日期路径: 最近 limit 根(腾讯不可达时降级新浪)
    url = KLINE_URL.format(symbol=symbol, limit=limit)
    recent_bars: list[dict] | None = _fetch_tencent(symbol, url)
    if recent_bars is None:
        recent_bars = _fetch_sina(code, limit)  # 降级新浪
    if recent_bars is None:
        recent_bars = []
    _store(code, limit, recent_bars, start_date, end_date)
    return recent_bars


def fetch_index_kline(
    limit: int = KLINE_LIMIT, start_date: str | None = None, end_date: str | None = None
) -> list[dict]:
    return fetch_kline(INDEX_CODE, limit, start_date, end_date)


def calc_volume_ma(kline: list[dict], window: int = 20) -> float | None:
    if len(kline) < window:
        return None
    recent = kline[-window:]
    return sum(k["volume"] for k in recent) / window
