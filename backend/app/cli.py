"""Entry points for `uv run` commands."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.infra.db_recovery import (
    StartupDatabaseBootstrapError,
    bootstrap_database_on_startup,
    run_alembic_migrations,
)


def _run(command: Sequence[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def _bootstrap_storage_from_demo() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    bootstrap_storage_script = backend_root / "scripts" / "bootstrap_storage.py"
    if bootstrap_storage_script.exists():
        storage_code = _run([sys.executable, str(bootstrap_storage_script)])
        if storage_code != 0:
            raise SystemExit(storage_code)


def _bootstrap_or_exit() -> None:
    _bootstrap_storage_from_demo()
    try:
        bootstrap_database_on_startup()
    except StartupDatabaseBootstrapError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def dev() -> None:
    """Start FastAPI development server."""
    _bootstrap_or_exit()
    raise SystemExit(_run(["uvicorn", "app.main:app", "--reload"]))


def serve() -> None:
    """Start FastAPI server for stable/non-reload runtime (e.g. Docker)."""
    _bootstrap_or_exit()
    raise SystemExit(
        _run(["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
    )


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
    elif runtime_platform.startswith("win") and pool == "threads":
        # SQLite allows one writer; keep a safe default on Windows threads pool.
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
    _bootstrap_or_exit()
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


def rebuild_db() -> None:
    """Rebuild the SQLite database from storage manifests/artifacts."""
    migration_code = run_alembic_migrations()
    if migration_code != 0:
        raise SystemExit(migration_code)
    from app.infra import storage
    from app.scripts.rebuild_db_from_storage import rebuild_from_storage

    summary = rebuild_from_storage(storage_root=storage.ensure_storage_root())
    print(
        {
            "authors": summary.authors,
            "documents": summary.documents,
            "chapters": summary.chapters,
            "segments": summary.segments,
            "snapshots": summary.snapshots,
            "warnings": summary.warnings,
        }
    )
    raise SystemExit(0)


if __name__ == "__main__":
    sys.exit(_run(["uvicorn", "app.main:app", "--reload"]))
