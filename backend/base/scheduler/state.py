"""任务共享内存状态(模块级单例)。

盘中轮询/日度任务通过本模块读写缓存与最新信号;
api 层经 get_latest_signals / get_last_update 只读访问。
"""

from __future__ import annotations

from datetime import datetime

_kline_cache: dict[str, list[dict]] = {}
_idx_kline_cache: list[dict] = []
_share_delta_cache: dict[str, dict] = {}
_latest_signals: list[dict] = []
_last_update: str | None = None
_last_manual_refresh: datetime | None = None


def get_latest_signals() -> list[dict]:
    return _latest_signals


def get_last_update() -> str | None:
    return _last_update
