"""Database startup bootstrap: migrations + optional storage-based auto recovery."""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
)
from app.infra import storage
from app.infra.db import session_scope
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from app.scripts.rebuild_db_from_storage import RebuildSummary

logger = logging.getLogger(__name__)


class StartupDatabaseBootstrapError(RuntimeError):
    """Raised when startup migration/recovery cannot complete safely."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_alembic_migrations() -> int:
    """Run `alembic upgrade head` and return process exit code."""
    project_root = _project_root()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(project_root / "alembic.ini"),
            "upgrade",
            "head",
        ],
        check=False,
        cwd=project_root,
    )
    return completed.returncode


def _has_recoverable_storage_data(storage_root: Path) -> bool:
    authors_dir = storage_root / "authors"
    if not authors_dir.exists():
        return False
    return any(path.is_dir() for path in authors_dir.iterdir())


def _is_core_data_empty() -> bool:
    with session_scope() as session:
        counts = [
            int(session.execute(select(func.count()).select_from(Author)).scalar_one()),
            int(session.execute(select(func.count()).select_from(AuthorDocument)).scalar_one()),
            int(session.execute(select(func.count()).select_from(DocumentChapter)).scalar_one()),
            int(session.execute(select(func.count()).select_from(DocumentSegment)).scalar_one()),
            int(session.execute(select(func.count()).select_from(AuthorSkillSnapshot)).scalar_one()),
        ]
    return all(count == 0 for count in counts)


def _should_run_auto_recovery(storage_root: Path) -> bool:
    return _is_core_data_empty() and _has_recoverable_storage_data(storage_root)


def bootstrap_database_on_startup(
    *,
    migration_runner: Callable[[], int] | None = None,
    rebuild_runner: Callable[[Path], RebuildSummary] | None = None,
    storage_root: Path | None = None,
) -> None:
    """Ensure schema exists and auto-recover DB from storage when needed."""
    migration_fn = migration_runner or run_alembic_migrations
    migration_code = migration_fn()
    if migration_code != 0:
        raise StartupDatabaseBootstrapError(
            f"database migration failed before startup (exit_code={migration_code})"
        )

    root = storage_root or storage.ensure_storage_root()
    if not _should_run_auto_recovery(root):
        return

    from app.scripts.rebuild_db_from_storage import rebuild_from_storage

    rebuild_fn = rebuild_runner or rebuild_from_storage

    try:
        summary = rebuild_fn(root)
    except IntegrityError as exc:
        # If another process has already recovered data, continue startup.
        if not _is_core_data_empty():
            logger.warning(
                (
                    "auto recovery hit integrity conflict but core data now exists; "
                    "treating as concurrent recovery"
                ),
                exc_info=exc,
            )
            return
        raise StartupDatabaseBootstrapError(
            "automatic database recovery failed due to integrity conflict"
        ) from exc
    except Exception as exc:
        raise StartupDatabaseBootstrapError(
            f"automatic database recovery failed: {exc}"
        ) from exc

    if _has_recoverable_storage_data(root) and _is_core_data_empty():
        raise StartupDatabaseBootstrapError(
            "automatic database recovery completed but restored no core data"
        )

    logger.info(
        (
            "automatic database recovery completed: authors=%s documents=%s "
            "chapters=%s segments=%s snapshots=%s warnings=%s"
        ),
        summary.authors,
        summary.documents,
        summary.chapters,
        summary.segments,
        summary.snapshots,
        len(summary.warnings),
    )
