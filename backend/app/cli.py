"""Entry points for `uv run` commands."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence


def _run(command: Sequence[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def dev() -> None:
    """Start FastAPI development server."""
    raise SystemExit(_run(["uvicorn", "app.main:app", "--reload"]))


def _build_worker_options(
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Build worker options with a Windows-safe default pool."""
    runtime_platform = platform or sys.platform
    environment = env or os.environ

    options: list[str] = ["worker", "--loglevel=info"]

    configured_pool = environment.get("CELERY_WORKER_POOL", "").strip()
    if configured_pool:
        pool = configured_pool
    elif runtime_platform.startswith("win"):
        pool = "threads"
    else:
        pool = ""

    if pool:
        options.append(f"--pool={pool}")

    configured_concurrency = environment.get("CELERY_WORKER_CONCURRENCY", "").strip()
    if configured_concurrency:
        options.append(f"--concurrency={configured_concurrency}")
    elif pool == "solo":
        options.append("--concurrency=1")

    return options


def _build_worker_command(
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Build the full Celery worker command."""
    return ["celery", "-A", "app.infra.queue:celery_app", *_build_worker_options(platform, env)]


def worker() -> None:
    """Start Celery worker."""
    raise SystemExit(_run(_build_worker_command()))


def lint() -> None:
    """Run Ruff lint checks."""
    raise SystemExit(_run(["ruff", "check", "app", "scripts", "tests", "alembic"]))


def format_code() -> None:
    """Run Ruff formatter."""
    raise SystemExit(_run(["ruff", "format", "app", "scripts", "tests", "alembic"]))


def typecheck() -> None:
    """Run Mypy checks."""
    raise SystemExit(_run(["mypy", "app"]))


def test() -> None:
    """Run pytest."""
    raise SystemExit(_run(["python", "-m", "pytest", "-q"]))


if __name__ == "__main__":
    sys.exit(_run(["uvicorn", "app.main:app", "--reload"]))
