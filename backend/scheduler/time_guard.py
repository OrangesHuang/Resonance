from datetime import datetime, time
from functools import wraps
from typing import Any, Callable, Optional

from config import (
    MARKET_OPEN_HOUR, MARKET_OPEN_MIN,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN,
    LUNCH_START_HOUR, LUNCH_START_MIN,
    LUNCH_END_HOUR, LUNCH_END_MIN,
)
from store.calendar_repo import is_trading_day


def is_trading_time(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if not is_trading_day(now.strftime("%Y-%m-%d")):
        return False
    t = now.time()
    morning = time(MARKET_OPEN_HOUR, MARKET_OPEN_MIN) <= t <= time(LUNCH_START_HOUR, LUNCH_START_MIN)
    afternoon = time(LUNCH_END_HOUR, LUNCH_END_MIN) <= t <= time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN)
    return morning or afternoon


def trading_day_guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """仅交易日执行定时任务;手动/启动调用请直接用原函数,勿经此守卫。"""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if is_trading_day(datetime.now().strftime("%Y-%m-%d")):
            return fn(*args, **kwargs)
        print(f"[SCHEDULER] skip {fn.__name__} (non-trading day)")
        return None
    return wrapper
