"""一级退出/供给数据抓取: 限售解禁、股东减持、IPO 发行。

数据源均为国内接口(东财/akshare)。抓取时临时置 NO_PROXY 绕过 macOS 系统代理
——本地代理进程常未启动, 会令 requests 抛 ProxyError; 国内接口直连更快。
本模块只做 I/O 与字段规整, 不做聚合/判定(聚合属纯函数层)。
"""

from __future__ import annotations

import math
import os
from contextlib import contextmanager


@contextmanager
def _no_proxy():
    """抓取期间临时禁用代理(含系统代理), 结束后还原。"""
    saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _f(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "nan", "NaT", "None") else s


def _date10(v) -> str | None:
    s = _s(v)
    return s[:10] if s and len(s) >= 10 else None


def fetch_unlock_events(start_date: str, end_date: str) -> list[dict]:
    """限售解禁明细(区间)。字段来自东财, 比例列原始为小数, 转百分比。"""
    import akshare as ak

    with _no_proxy():
        df = ak.stock_restricted_release_detail_em(
            start_date=start_date.replace("-", ""), end_date=end_date.replace("-", "")
        )
    out: list[dict] = []
    for _, r in df.iterrows():
        d = _date10(r.get("解禁时间"))
        code = _s(r.get("股票代码"))
        if not d or not code:
            continue
        ratio = _f(r.get("占解禁前流通市值比例"))
        out.append(
            {
                "date": d,
                "code": code.zfill(6),
                "name": _s(r.get("股票简称")),
                "unlock_type": _s(r.get("限售股类型")),
                "shares": _f(r.get("实际解禁数量")) or _f(r.get("解禁数量")),
                "market_value": _f(r.get("实际解禁市值")),
                "ratio_pct": round(ratio * 100, 4) if ratio is not None else None,
                "pre20_chg": _f(r.get("解禁前20日涨跌幅")),
                "post20_chg": _f(r.get("解禁后20日涨跌幅")),
            }
        )
    return out


def fetch_reduction_events(since: str) -> list[dict]:
    """股东/高管增减持明细(全量拉取后过滤 since 起的减持)。全量约 127s, 仅周更任务调用。"""
    import akshare as ak

    with _no_proxy():
        df = ak.stock_hold_management_detail_em()
    out: list[dict] = []
    for _, r in df.iterrows():
        d = _date10(r.get("日期"))
        if not d or d < since:
            continue
        delta = _f(r.get("变动股数"))
        if delta is None or delta >= 0:  # 只保留减持(负)
            continue
        code = _s(r.get("代码"))
        if not code:
            continue
        out.append(
            {
                "date": d,
                "code": code.zfill(6),
                "name": _s(r.get("名称")),
                "holder": _s(r.get("变动人")),
                "role": _s(r.get("职务")),
                "shares_delta": delta,
                "price": _f(r.get("成交均价")),
                "amount": _f(r.get("变动金额")),
                "ratio_pct": _f(r.get("变动比例")),
                "reason": _s(r.get("变动原因")),
            }
        )
    return out


def fetch_ipo_events() -> list[dict]:
    """新股发行一览(全量含历史)。用于统计发行家数与募资节奏。"""
    import akshare as ak

    with _no_proxy():
        df = ak.stock_xgsglb_em()
    out: list[dict] = []
    for _, r in df.iterrows():
        code = _s(r.get("股票代码"))
        if not code:
            continue
        out.append(
            {
                "code": code.zfill(6),
                "name": _s(r.get("股票简称")),
                "board": _s(r.get("板块")),
                "exchange": _s(r.get("交易所")),
                "issue_date": _date10(r.get("申购日期")),
                "list_date": _date10(r.get("上市日期")),
                "price": _f(r.get("发行价格")),
                "total_shares": _f(r.get("发行总数")),
                "pe": _f(r.get("发行市盈率")),
            }
        )
    return out
