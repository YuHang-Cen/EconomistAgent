"""Run pipeline jobs in one in-process background thread."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock


class JobExecutor:
    """A restartable single-worker executor suitable for the local SQLite runtime."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._executor: ThreadPoolExecutor | None = None
        self._accepting = False
        self._jobs: dict[Future[None], str] = {}

    def start(self) -> None:
        """Start accepting jobs, recreating the pool after an application restart."""
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix="pipeline-job",
                )
            self._accepting = True

    def submit(self, job_id: str, task: Callable[[], None]) -> None:
        """Submit one job without blocking the request that created it."""
        with self._lock:
            if not self._accepting or self._executor is None:
                raise RuntimeError("job executor is not running")
            future = self._executor.submit(task)
            self._jobs[future] = job_id
            future.add_done_callback(self._forget)

    def shutdown(self) -> list[str]:
        """Stop accepting work and cancel jobs that have not started yet."""
        with self._lock:
            executor = self._executor
            if executor is None:
                return []
            self._accepting = False
            canceled_job_ids: list[str] = []
            for future, job_id in list(self._jobs.items()):
                if future.cancel():
                    canceled_job_ids.append(job_id)
            self._executor = None
        executor.shutdown(wait=True, cancel_futures=True)
        return canceled_job_ids

    def _forget(self, future: Future[None]) -> None:
        with self._lock:
            self._jobs.pop(future, None)


job_executor = JobExecutor()
