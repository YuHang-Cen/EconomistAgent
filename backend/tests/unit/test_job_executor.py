from __future__ import annotations

from threading import Event

import pytest
from app.infra.job_executor import JobExecutor


def test_executor_runs_jobs_one_at_a_time_in_submission_order() -> None:
    executor = JobExecutor()
    first_started = Event()
    release_first = Event()
    all_done = Event()
    events: list[str] = []

    def first() -> None:
        events.append("first-start")
        first_started.set()
        release_first.wait(timeout=2)
        events.append("first-end")

    def second() -> None:
        events.append("second")
        all_done.set()

    executor.start()
    executor.submit("job-1", first)
    executor.submit("job-2", second)
    assert first_started.wait(timeout=2)
    assert events == ["first-start"]

    release_first.set()
    assert all_done.wait(timeout=2)
    assert events == ["first-start", "first-end", "second"]
    executor.shutdown()


def test_executor_rejects_jobs_when_not_running() -> None:
    executor = JobExecutor()
    with pytest.raises(RuntimeError, match="not running"):
        executor.submit("job-1", lambda: None)


def test_shutdown_cancels_work_that_has_not_started() -> None:
    executor = JobExecutor()
    first_started = Event()
    release_first = Event()
    second_started = Event()

    def first() -> None:
        first_started.set()
        release_first.wait(timeout=0.2)

    executor.start()
    executor.submit("job-1", first)
    executor.submit("job-2", second_started.set)
    assert first_started.wait(timeout=2)

    canceled = executor.shutdown()

    assert canceled == ["job-2"]
    assert not second_started.is_set()
