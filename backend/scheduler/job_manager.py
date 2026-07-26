"""后台任务引擎:内存任务注册表 + 线程执行 + 进度上报。

阻塞型拉取任务通过 asyncio.to_thread 丢到工作线程执行,事件循环保持空闲以响应轮询。
任务状态仅存内存,重启后丢失(已落库数据不受影响)。
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

ProgressFn = Callable[[int, int, str], None]

PENDING = "pending"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"

_ACTIVE = (PENDING, RUNNING)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class JobState:
    id: str
    task: str
    params: dict
    exclusive: bool = False
    status: str = PENDING
    current: int = 0
    total: int = 0
    message: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task": self.task,
            "params": self.params,
            "status": self.status,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "result": self.result,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def _active(self) -> list[JobState]:
        return [j for j in self._jobs.values() if j.status in _ACTIVE]

    def is_running(self, task: str) -> bool:
        with self._lock:
            return any(j.task == task for j in self._active())

    def can_start(self, task: str, exclusive: bool) -> bool:
        with self._lock:
            active = self._active()
            if any(j.task == task for j in active):
                return False
            if exclusive:
                return not active
            return not any(j.exclusive for j in active)

    def submit(self, task: str, params: dict, exclusive: bool = False) -> str:
        job_id = uuid.uuid4().hex[:12]
        state = JobState(id=job_id, task=task, params=params, exclusive=exclusive)
        with self._lock:
            self._jobs[job_id] = state
            self._order.append(job_id)
        return job_id

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = RUNNING
                job.started_at = _now()

    def progress(self, job_id: str, current: int, total: int, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.current = current
                job.total = total
                job.message = message

    def finish(self, job_id: str, result: Optional[dict], error: Optional[str]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = FAILED if error else SUCCESS
            job.result = result
            job.error = error
            job.finished_at = _now()
            if error:
                job.message = error

    def get(self, job_id: str) -> Optional[JobState]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int) -> list[JobState]:
        with self._lock:
            ids = list(reversed(self._order))[:limit]
            return [self._jobs[i] for i in ids if i in self._jobs]


job_manager = JobManager()


async def run_job(job_id: str, fn: Callable[[ProgressFn], dict]) -> None:
    job_manager.mark_running(job_id)

    def cb(current: int, total: int, message: str) -> None:
        job_manager.progress(job_id, current, total, message)

    try:
        result = await asyncio.to_thread(fn, cb)
        job_manager.finish(job_id, result, None)
    except Exception as e:  # 任务边界,捕获一切避免线程裸崩
        job_manager.finish(job_id, None, str(e))
