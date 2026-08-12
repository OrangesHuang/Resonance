"""衍生品数据拉取: 期权PCR + 股指期货基差。"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta

# 上证50ETF / 沪深300ETF / 中证500ETF / 科创50ETF 期权标的
OPTION_UNDERLYINGS = {
    "510050": "上证50ETF",
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "588000": "科创50ETF",
}

# 股指期货 → 现货指数代码
FUTURES_SPOT_MAP = {
    "IF": {"name": "沪深300", "spot_code": "sh000300", "label": "IF(沪深300)"},
    "IC": {"name": "中证500", "spot_code": "sh000905", "label": "IC(中证500)"},
    "IH": {"name": "上证50", "spot_code": "sh000016", "label": "IH(上证50)"},
}

PCR_BACKFILL_SLEEP = 0.3


def _parse_pcr_day(df) -> list[dict]:
    """解析单日期权统计DataFrame为行列表。"""
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        code = str(row.get("合约标的代码", ""))
        if code not in OPTION_UNDERLYINGS:
            continue
        pcr_raw = row.get("认沽/认购")
        if pcr_raw is None:
            continue
        pcr_val = float(pcr_raw)
        pcr = round(pcr_val / 100.0, 4) if pcr_val > 5 else round(pcr_val, 4)
        trade_date = str(row.get("交易日", ""))[:10]
        rows.append(
            {
                "date": trade_date,
                "underlying_code": code,
                "underlying_name": OPTION_UNDERLYINGS[code],
                "pcr": pcr,
                "call_volume": int(row.get("认购成交量", 0)),
                "put_volume": int(row.get("认沽成交量", 0)),
                "call_oi": int(row.get("未平仓认购合约数", 0)),
                "put_oi": int(row.get("未平仓认沽合约数", 0)),
            }
        )
    return rows


def fetch_option_pcr(
    start_date: str | None = None,
    end_date: str | None = None,
    on_row: Callable[[dict], None] | None = None,
) -> list[dict]:
    """拉取上交所期权每日统计(PCR = 认沽成交量/认购成交量)。

    akshare.option_daily_stats_sse(date) 每次只返回单日数据,
    需要逐日调用。start_date/end_date 格式为 YYYY-MM-DD。
    不传参数则仅拉取最新一个交易日。
    on_row: 每拉到一行立即回调(边拉边写)。
    """
    import akshare as ak

    today = datetime.now().strftime("%Y-%m-%d")
    end = end_date or today
    end = min(end, today)

    if start_date:
        start = start_date
    else:
        start = end

    all_rows: list[dict] = []
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    while current <= end_dt:
        if current.weekday() < 5:
            date_str = current.strftime("%Y%m%d")
            try:
                df = ak.option_daily_stats_sse(date=date_str)
            except Exception as e:
                err = str(e)[:60]
                if "None of" not in err:
                    print(f"[FETCH] PCR {date_str} failed: {err}")
                current += timedelta(days=1)
                continue

            day_rows = _parse_pcr_day(df)
            for r in day_rows:
                all_rows.append(r)
                if on_row:
                    on_row(r)

            time.sleep(PCR_BACKFILL_SLEEP)

        current += timedelta(days=1)

    return sorted(all_rows, key=lambda r: r["date"])


def _fetch_index_close(spot_code: str) -> dict[str, float]:
    """获取现货指数日线收盘价 {date: close}。"""
    import akshare as ak

    df = ak.stock_zh_index_daily(symbol=spot_code)
    if df is None or df.empty:
        return {}
    result = {}
    for _, row in df.iterrows():
        d = str(row["date"])[:10]
        result[d] = float(row["close"])
    return result


def fetch_futures_basis(date: str | None = None) -> list[dict]:
    """拉取股指期货(IF/IC/IH)主力合约收盘价, 计算基差 = 期货 - 现货。

    基差 > 0 为升水(看多), 基差 < 0 为贴水(看空)。
    同时计算基差率(基差/现货*100)便于跨品种比较。
    """
    rows = []
    try:
        import akshare as ak
    except ImportError:
        return []

    # 收集所有现货指数数据
    spot_data: dict[str, dict[str, float]] = {}
    for fut_code, info in FUTURES_SPOT_MAP.items():
        try:
            spot_data[fut_code] = _fetch_index_close(info["spot_code"])
        except Exception as e:
            print(f"[FETCH] index {info['spot_code']} failed: {e}")
            spot_data[fut_code] = {}

    for fut_code, info in FUTURES_SPOT_MAP.items():
        try:
            df = ak.futures_zh_daily_sina(symbol=f"{fut_code}0")
        except Exception as e:
            print(f"[FETCH] futures {fut_code} failed: {e}")
            continue
        if df is None or df.empty:
            continue

        spot_closes = spot_data.get(fut_code, {})
        for _, row in df.iterrows():
            trade_date = str(row["date"])[:10]
            if date and trade_date != date:
                continue
            fut_close = float(row["close"])
            spot_close = spot_closes.get(trade_date)
            if spot_close is None or spot_close == 0:
                continue
            basis = round(fut_close - spot_close, 2)
            basis_pct = round(basis / spot_close * 100, 4)
            rows.append(
                {
                    "date": trade_date,
                    "futures_code": fut_code,
                    "futures_name": info["label"],
                    "fut_close": fut_close,
                    "spot_close": round(spot_close, 2),
                    "basis": basis,
                    "basis_pct": basis_pct,
                    "volume": int(row.get("volume", 0)),
                    "hold": int(row.get("hold", 0)),
                }
            )
    return sorted(rows, key=lambda r: (r["date"], r["futures_code"]))
