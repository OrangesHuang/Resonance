from fastapi import APIRouter, Query

from config import ETFS
from store.daily_repo import get_by_code
from store.realtime_repo import get_today_snapshots
from scheduler.tasks import task_manual_refresh

router = APIRouter(prefix="/api/etf", tags=["etf"])


@router.post("/refresh")
def etf_refresh():
    result = task_manual_refresh()
    if result.get("status") == "skipped":
        return result
    return {
        "status": "ok",
        "count": result["count"],
        "date": result["date"],
    }


@router.get("/list")
def etf_list():
    return [
        {"code": code, "name": info["name"], "idx": info["idx"]}
        for code, info in ETFS.items()
    ]


@router.get("/{code}/history")
def etf_history(code: str, days: int = Query(default=640, ge=1, le=640)):
    if code not in ETFS:
        return {"error": f"unknown ETF code: {code}"}

    daily_records = get_by_code(code)
    # 从本地数据库构建K线，避免每次请求调腾讯API被封禁
    kline = _build_kline_from_db(daily_records, days)

    return {
        "code": code,
        "name": ETFS[code]["name"],
        "idx": ETFS[code]["idx"],
        "kline": kline,
        "daily_signals": daily_records[:days],
    }


def _build_kline_from_db(records: list[dict], limit: int) -> list[dict]:
    """从 etf_daily 表构建 K 线数据，不调外部 API。"""
    recent = records[:limit][::-1]  # DESC → ASC
    result = []
    for r in recent:
        close = r.get("close_price")
        chg = r.get("change_pct")
        if close is None or close == 0:
            continue
        # 从收盘价和涨跌幅反推开盘价
        if chg is not None and chg != 0:
            op = round(close / (1 + chg / 100), 3)
        else:
            op = close
        result.append({
            "date": r["date"],
            "open": op,
            "close": close,
            "high": round(max(op, close), 3),
            "low": round(min(op, close), 3),
            "volume": r.get("volume") or 0,
        })
    return result


@router.get("/{code}/intraday")
def etf_intraday(code: str, date: str = Query(default=None)):
    if code not in ETFS:
        return {"error": f"unknown ETF code: {code}"}

    snapshots = get_today_snapshots(code=code, date_str=date)
    return {
        "code": code,
        "name": ETFS[code]["name"],
        "snapshots": snapshots,
    }
