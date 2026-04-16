from __future__ import annotations

from app.cli import _build_worker_command, _build_worker_options


def test_build_worker_options_windows_defaults_to_threads() -> None:
    options = _build_worker_options(platform="win32", env={})
    assert options == ["worker", "--loglevel=info", "--pool=threads"]


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
