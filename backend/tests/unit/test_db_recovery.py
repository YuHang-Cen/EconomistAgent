from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.domain.models import Author
from app.infra.db import session_scope
from app.infra.db_recovery import (
    StartupDatabaseBootstrapError,
    bootstrap_database_on_startup,
)
from app.scripts.rebuild_db_from_storage import RebuildSummary
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError


def _make_local_temp_storage_root() -> Path:
    root = Path("storage") / "test_tmp" / f"db-recovery-{uuid4()}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_bootstrap_skips_auto_recovery_when_storage_has_no_authors_dir() -> None:
    storage_root = _make_local_temp_storage_root()
    called = False

    def fake_rebuild(storage_root: Path) -> RebuildSummary:
        nonlocal called
        called = True
        return RebuildSummary(
            authors=0,
            documents=0,
            chapters=0,
            segments=0,
            snapshots=0,
            warnings=[],
        )

    try:
        bootstrap_database_on_startup(
            migration_runner=lambda: 0,
            rebuild_runner=fake_rebuild,
            storage_root=storage_root,
        )
        assert called is False
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_bootstrap_fails_fast_when_migrations_fail() -> None:
    storage_root = _make_local_temp_storage_root()
    try:
        with pytest.raises(StartupDatabaseBootstrapError, match="migration failed"):
            bootstrap_database_on_startup(
                migration_runner=lambda: 2,
                storage_root=storage_root,
            )
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_bootstrap_tolerates_concurrent_integrity_conflict_if_data_exists() -> None:
    storage_root = _make_local_temp_storage_root()
    (storage_root / "authors" / "author-1").mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=UTC).isoformat()

    def fake_rebuild(_storage_root: Path) -> RebuildSummary:
        with session_scope() as session:
            session.add(
                Author(
                    author_id="author-1",
                    author_name="Recovered",
                    school=None,
                    avatar_url=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        raise IntegrityError("INSERT INTO authors ...", {}, Exception("duplicate key"))

    try:
        bootstrap_database_on_startup(
            migration_runner=lambda: 0,
            rebuild_runner=fake_rebuild,
            storage_root=storage_root,
        )

        with session_scope() as session:
            authors_count = int(
                session.execute(select(func.count()).select_from(Author)).scalar_one()
            )
        assert authors_count == 1
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)
