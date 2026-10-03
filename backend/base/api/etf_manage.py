"""ETF 动态管理 API: 清单增删 + 每只标的的数据覆盖状态(/api/etfs)。

etfs 表为真源, 增删后立即 load_into_config() 刷新 config.ETFS 运行时镜像,
所有依赖在册清单的模块(定时任务/实时行情/份额过滤/策略列举)自动生效。
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from functools import partial

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from base.analysis.etf_naming import derive_idx_name
from base.analysis.strategy.router import list_strategy_versions
from base.config import ETFS, PROTECTED_ETFS
from base.fetch.realtime import fetch_etf_quote
from base.scheduler import state
from base.scheduler.job_manager import job_manager, run_job
from base.scheduler.job_registry import JOB_DEFS, JOB_FNS
from base.store import etf_repo

router = APIRouter(prefix="/api/etfs", tags=["etfs"])

_CODE_RE = re.compile(r"\d{6}")

# 会批量写 etf_daily/etf_realtime 的全局任务: 运行期间禁止删除标的,
# 否则清理掉的行会被回填任务重新写回
_BLOCKING_TASKS = frozenset(
    {
        "rebuild_all",
        "backfill_etf_daily",
        "backfill_missing_etf_daily",
        "backfill_etf",
        "backfill_shares",
        "backfill_missing_shares",
        "fetch_etf_latest",
        "recalc_composite",
        "fix_share_splits",
    }
)

_EMPTY_COVERAGE = {
    "first_date": None,
    "last_date": None,
    "daily_rows": 0,
    "shares_last_date": None,
    "adjust_events": 0,
    "realtime_rows": 0,
    "realtime_last": None,
}


class EtfAddRequest(BaseModel):
    code: str
    idx: str | None = None


def _normalize_code(code: str) -> str:
    code = (code or "").strip()
    if not _CODE_RE.fullmatch(code):
        raise HTTPException(status_code=400, detail="代码必须为 6 位数字")
    if code[0] not in ("5", "1"):
        raise HTTPException(status_code=400, detail="不支持的代码段(仅支持 5/1 开头的场内基金)")
    return code


def _probe(code: str) -> dict:
    quote = fetch_etf_quote(code)
    if not quote:
        raise HTTPException(status_code=400, detail=f"无法从行情接口识别代码 {code}, 请确认是场内 ETF")
    return quote


def _submit_if_idle(task: str) -> str | None:
    defn = JOB_DEFS[task]
    if not job_manager.can_start(task, defn["exclusive"]):
        return None
    job_id = job_manager.submit(task, defn["defaults"], defn["exclusive"])
    asyncio.create_task(run_job(job_id, partial(JOB_FNS[task], **defn["defaults"])))
    return job_id


@router.get("")
def list_etfs() -> list[dict]:
    """在册清单 + 每只标的的数据覆盖 + 策略版本 + 删除保护标记。"""
    coverage = etf_repo.etf_coverage()
    versions = list_strategy_versions()
    out = []
    for item in etf_repo.list_all():
        code = item["code"]
        out.append(
            {
                **item,
                "coverage": coverage.get(code, dict(_EMPTY_COVERAGE)),
                "protected": code in PROTECTED_ETFS,
                "strategy_versions": versions.get(code, ["stable"]),
                "active_job": code in job_manager.active_codes(),
            }
        )
    return out


@router.get("/validate")
def validate_etf(code: str = Query(..., description="6 位 ETF 代码")) -> dict:
    """添加前预校验(只读): 格式 → 重复 → 行情接口识别, 返回带出的名称/市场。"""
    code = _normalize_code(code)
    if code in ETFS:
        raise HTTPException(status_code=409, detail=f"{code} 已在监控列表中")
    quote = _probe(code)
    return {
        "code": code,
        "name": quote["name"],
        "market": quote["market"],
        "idx": derive_idx_name(quote["name"]),
    }


@router.post("", status_code=201)
def add_etf(body: EtfAddRequest) -> dict:
    code = _normalize_code(body.code)
    if code in ETFS:
        raise HTTPException(status_code=409, detail=f"{code} 已在监控列表中")
    quote = _probe(code)
    idx = (body.idx or "").strip() or derive_idx_name(quote["name"])
    try:
        etf_repo.insert_etf(code, quote["name"], idx, quote["market"])
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"{code} 已在监控列表中") from None
    etf_repo.load_into_config()
    return {"code": code, "name": quote["name"], "idx": idx, "market": quote["market"]}


@router.delete("/{code}")
async def delete_etf(code: str) -> dict:
    """硬删除: 清单移除 + 该标的日度/实时数据清除 + 刷新日历槽位(不可恢复)。"""
    if code not in ETFS:
        raise HTTPException(status_code=404, detail=f"unknown ETF code: {code}")
    if code in PROTECTED_ETFS:
        raise HTTPException(status_code=409, detail=f"{code} 为策略基准标的, 不可删除")
    if code in job_manager.active_codes() or job_manager.is_any_active(_BLOCKING_TASKS):
        raise HTTPException(status_code=409, detail="回填任务正在运行, 请等待完成后再删除")

    purged = etf_repo.purge_code_data(code)
    etf_repo.delete_etf(code)
    etf_repo.load_into_config()
    state.forget_code(code)
    slots_job = _submit_if_idle("refresh_calendar_slots")
    return {"code": code, **purged, "slots_refresh_job": slots_job}
