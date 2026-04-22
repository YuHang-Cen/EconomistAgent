from __future__ import annotations

import pytest
from app.cli import (
    _build_worker_command,
    _build_worker_options,
    serve,
    worker,
)
from app.infra.db_recovery import StartupDatabaseBootstrapError


def test_build_worker_options_windows_defaults_to_threads() -> None:
    options = _build_worker_options(platform="win32", env={})
    assert options == ["worker", "--loglevel=info", "--pool=threads", "--concurrency=1"]


def test_build_worker_options_uses_configured_pool_and_concurrency() -> None:
    options = _build_worker_options(
        platform="win32",
        env={"CELERY_WORKER_POOL": "solo", "CELERY_WORKER_CONCURRENCY": "3"},
    )
    assert options == ["worker", "--loglevel=info", "--pool=solo", "--concurrency=3"]


def test_build_worker_options_solo_defaults_to_single_concurrency() -> None:
    options = _build_worker_options(
        platform="linux",
        env={"CELERY_WORKER_POOL": "solo"},
    )
    assert options == ["worker", "--loglevel=info", "--pool=solo", "--concurrency=1"]


def test_build_worker_command_wraps_options() -> None:
    command = _build_worker_command(
        platform="win32",
        env={"CELERY_WORKER_POOL": "threads", "CELERY_WORKER_CONCURRENCY": "8"},
    )
    assert command == [
        "celery",
        "-A",
        "app.infra.queue:celery_app",
        "worker",
        "--loglevel=info",
        "--pool=threads",
        "--concurrency=8",
    ]


def test_worker_bootstraps_database_before_running_command(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def fake_bootstrap() -> None:
        events.append("bootstrap")

    def fake_run(command: list[str]) -> int:
        events.append("run")
        assert command == ["celery", "fake"]
        return 0

    monkeypatch.setattr("app.cli.bootstrap_database_on_startup", fake_bootstrap)
    monkeypatch.setattr("app.cli._build_worker_command", lambda: ["celery", "fake"])
    monkeypatch.setattr("app.cli._run", fake_run)

    with pytest.raises(SystemExit) as exc:
        worker()

    assert exc.value.code == 0
    assert events == ["bootstrap", "run"]


def test_worker_exits_when_bootstrap_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_bootstrap() -> None:
        raise StartupDatabaseBootstrapError("bootstrap failed")

    monkeypatch.setattr("app.cli.bootstrap_database_on_startup", fail_bootstrap)

    with pytest.raises(SystemExit) as exc:
        worker()

    assert exc.value.code == 1


def test_serve_bootstraps_database_before_running_command(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def fake_bootstrap() -> None:
        events.append("bootstrap")

    def fake_run(command: list[str]) -> int:
        events.append("run")
        assert command == ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
        return 0

    monkeypatch.setattr("app.cli.bootstrap_database_on_startup", fake_bootstrap)
    monkeypatch.setattr("app.cli._run", fake_run)

    with pytest.raises(SystemExit) as exc:
        serve()

    assert exc.value.code == 0
    assert events == ["bootstrap", "run"]
