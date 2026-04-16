"""Celery worker script entrypoint."""

from __future__ import annotations

from app.cli import _build_worker_options
from app.infra.queue import celery_app


def main() -> None:
    """Start Celery worker with shared CLI options."""
    celery_app.worker_main(_build_worker_options())


if __name__ == "__main__":
    main()
